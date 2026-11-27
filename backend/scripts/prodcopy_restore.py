"""Restore a masked production copy into a LOCAL database for debugging (CEO 2026-11-27: "replicate prod in local").

The dump comes from the "Production masked copy" workflow (.github/workflows/prod-masked-copy.yml): personal data was
masked on a throwaway runner before it left GitHub, and a leak check passed. This script:
  1. refuses anything but a local Postgres and a database name without a production marker
  2. (re)creates the target database (default wros_prodcopy) and restores the dump into it
  3. gives every login one local password you choose (PRODCOPY_PASSWORD), no MFA, no forced reset
  4. prints the masked sign-in address of each L15+ person (CEO, Partners) so you can sign in as them

    gh run download <run-id> -n prodcopy-masked -D C:\\dev\\prodcopies
    set PRODCOPY_PASSWORD=<at least 10 characters>
    python scripts/prodcopy_restore.py C:\\dev\\prodcopies\\prodcopy-masked-20261127-0930.dump

Then point the local backend at it: in backend/.env.local set DATABASE_URL to the same URL with the database
name wros_prodcopy (keep a copy of the wros_dev line to switch back), and restart the backend. The queue worker
never acts on the copy: every queued message was dead-lettered by the masking.
"""
import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

PROD_MARKERS = re.compile(r"onboarding_prod|production|prod\.|\.prod|prod-db", re.IGNORECASE)
PG_BIN = os.getenv("PG_BIN", r"C:\Program Files\PostgreSQL\18\bin")


def local_url() -> str:
    """The local DATABASE_URL from backend/.env.local (else .env): only ever a local server."""
    backend = Path(__file__).resolve().parent.parent
    for name in (".env.local", ".env"):
        path = backend / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                match = re.match(r"\s*DATABASE_URL\s*=\s*(.*)", line)
                if match:
                    return match.group(1).strip().strip("'\"")
    raise SystemExit("No DATABASE_URL in backend/.env.local or backend/.env")


def tool(name: str) -> str:
    exe = Path(PG_BIN) / (name + (".exe" if os.name == "nt" else ""))
    return str(exe) if exe.exists() else name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dump", help="the masked .dump downloaded from the workflow")
    parser.add_argument("--db", default="wros_prodcopy", help="local database to (re)create")
    args = parser.parse_args()

    password = os.getenv("PRODCOPY_PASSWORD", "")
    if len(password) < 10:
        raise SystemExit("Set PRODCOPY_PASSWORD (at least 10 characters): every login on the copy gets it")
    url = urlparse(local_url().replace("+psycopg2", ""))
    if url.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise SystemExit(f"Refusing: the local DATABASE_URL points at {url.hostname}, not this machine")
    if PROD_MARKERS.search(args.db) or args.db == url.path.strip("/"):
        raise SystemExit(f"Refusing database name {args.db!r}: it looks like production or is your dev database")
    if not Path(args.dump).is_file():
        raise SystemExit(f"No dump at {args.dump}")

    env = dict(os.environ, PGPASSWORD=unquote(url.password or ""))
    base = ["-h", url.hostname, "-p", str(url.port or 5432), "-U", unquote(url.username or "")]
    subprocess.run([tool("dropdb"), *base, "--if-exists", args.db], env=env, check=True)
    subprocess.run([tool("createdb"), *base, args.db], env=env, check=True)
    restore = subprocess.run([tool("pg_restore"), *base, "--no-owner", "--no-privileges", "-d", args.db, args.dump],
                             env=env, capture_output=True, text=True)
    errors = [line for line in restore.stderr.splitlines() if line.startswith("pg_restore: error")]
    print(f"restored into {args.db} ({len(errors)} restore error(s): orphan rows can refuse a foreign key)")

    import bcrypt
    import psycopg2

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = psycopg2.connect(host=url.hostname, port=url.port or 5432, user=unquote(url.username or ""),
                            password=unquote(url.password or ""), dbname=args.db)
    with conn, conn.cursor() as cur:
        cur.execute("""UPDATE app_schema.users SET "UserPassword" = %s, password_reset_required = false,
                       mfa_enabled = false""", (hashed,))
        print(f"{cur.rowcount} login(s) now use PRODCOPY_PASSWORD")
        cur.execute("""SELECT u."UserEmail", u.job_title, r.hierarchy_level FROM app_schema.users u
                       JOIN app_schema.org_roles r ON lower(r.name) = lower(u.job_title) AND r.tenant_id = u.tenant_id
                       WHERE u.terminated_at IS NULL AND r.hierarchy_level >= 15
                       ORDER BY r.hierarchy_level DESC, u."UserEmail" """)
        for email, title, level in cur.fetchall():
            print(f"  L{level} {title}: sign in as {email}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
