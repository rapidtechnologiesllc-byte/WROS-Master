"""Read-only pg_dump of the production database, streamed to stdout. Piped over SSH by
.github/workflows/prod-masked-copy.yml (cwd: backend/ on the production server):

    venv/bin/python - < backend/scripts/prodcopy_dump.py > raw.dump

The dump goes straight to the GitHub runner, which masks it (scripts/prodcopy_mask.py) and keeps only the masked
copy. Nothing is written on the server and the database URL is never printed.
"""
import os
import subprocess
import sys
from urllib.parse import unquote, urlparse

sys.path.insert(0, os.getcwd())

from app.core.config import settings  # noqa: E402  (loads the server's .env)

url = urlparse((settings.DATABASE_URL or "").replace("+psycopg2", ""))
if not url.hostname or not url.path.strip("/"):
    sys.stderr.write("DATABASE_URL is not set on this server\n")
    sys.exit(2)
env = dict(os.environ, PGPASSWORD=unquote(url.password or ""))
command = ["pg_dump", "-h", url.hostname, "-p", str(url.port or 5432), "-U", unquote(url.username or ""),
           "-Fc", "--no-owner", "--no-privileges", url.path.strip("/")]
result = subprocess.run(command, env=env, stdout=sys.stdout.buffer)
if result.returncode:
    sys.stderr.write(f"pg_dump failed with exit code {result.returncode}\n")
sys.exit(result.returncode)
