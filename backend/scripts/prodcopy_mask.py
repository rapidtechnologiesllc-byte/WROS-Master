"""Mask a COPY of the production database so it can be used for local debugging (CEO 2026-11-27: "replicate
prod in local ... a masked copy"). Run only by .github/workflows/prod-masked-copy.yml, on a throwaway Postgres
on the GitHub runner that holds the restored dump; never on production.

Keeps every row, id, foreign key, tenant, role, permission, status, date and business amount, so prod bugs
reproduce. Replaces what identifies a person or opens an account:
- emails: u<hash>@<company domain> for company addresses (company rules still apply), else u<hash>@example.invalid;
  the same address always maps to the same mask, so joins and duplicate checks still work
- names of people, phone numbers, addresses, dates of birth, government / bank / tax numbers, IP addresses
- free text that can hold anything (resumes, notes, messages, transcripts, payloads) and uploaded file bytes
- pay (salary, CTC, pay amount): scaled by a per-row factor between 0.8 and 1.2, so P&L magnitudes stay real
- passwords, tokens, secrets, MFA: cleared; the local restore script sets one known local password
Queued work is dead-lettered so a local worker can never act on it.

Then a leak check scans every text column for a real-looking email that was not masked and fails the run.

    python prodcopy_mask.py postgresql://postgres:postgres@localhost:5432/prodcopy blitzenx.com,poliqs.com
"""
import re
import sys

import psycopg2

SCHEMAS = ("app_schema", "public")
# never touch these: the access model, configuration, and migration markers are what make the copy behave like prod
KEEP_TABLES = {"alembic_version", "data_migrations", "modules", "resources", "role_templates",
               "role_template_permissions", "org_roles", "system_config", "tenants"}
TEXT_TYPES = {"text", "character varying", "character", "citext"}
JSON_TYPES = {"json", "jsonb"}
NUMERIC_TYPES = {"integer", "bigint", "numeric", "double precision", "real", "smallint"}
DATE_TYPES = {"date", "timestamp without time zone", "timestamp with time zone"}

EMAIL_COL = re.compile(r"e_?mail")
NAME_COL = re.compile(
    r"^(user_?name|(candidate|employee|contact|recipient|sender|emergency\w*|father|mother|spouse|nominee|"
    r"referr\w*|interviewer|recruiter|manager|reviewer|approver|performed_by|created_by|updated_by|owner|"
    r"guardian|reference|signatory)_?(first_?|last_?|middle_?|full_?|display_?)?name|"
    r"candidate(first|last|middle)name|(first|last|middle|full|legal|preferred|given|family|sur)_?name|"
    r"surname|display_name_person)$")
PHONE_COL = re.compile(r"phone|mobile|whatsapp|\bcell\b|telephone|contact_number")
ADDRESS_COL = re.compile(r"address|street|postal|zip_?code|pincode|pin_code|house|landmark")
BIRTH_COL = re.compile(r"dob|birth")
ID_NUMBER_COL = re.compile(r"ssn|\bpan\b|pan_number|aadha?ar|passport|tax_?id|national_id|bank|account_number|"
                           r"ifsc|routing|iban|swift|\buan\b|pf_number|esi_number|visa_number|license_number|ein")
SECRET_COL = re.compile(r"password|passwd|token|secret|api_?key|otp|totp|mfa_|backup_code|code_hash|"
                        r"private_key|credential|signature_key|webhook_secret")
FREE_TEXT_COL = re.compile(r"resume|\bcv\b|cv_|transcript|^body|_body|content|^notes?$|_notes?$|comment|message|"
                           r"summary|feedback|cover_letter|\bbio\b|payload|raw_|_raw|html|extracted|parsed|"
                           r"justification|reason_text|answer|response_text|prompt|completion|conversation|"
                           r"subject|snippet|signature|stack_trace|traceback|old_value|new_value|event_data|"
                           r"analysis|reasoning|description|details_text|error_detail")
# business text worth keeping as is (a job's description is needed to debug matching)
KEEP_FREE_TEXT = {("jobs", "description"), ("jobs", "job_description"), ("jobs", "jobdescription")}
URL_COL = re.compile(r"linkedin|github|profile_url|photo|avatar|resume_url|sharepoint_url|file_url|document_url|"
                     r"download_url|web_url|meeting_link|join_url")
PAY_COL = re.compile(r"salary|ctc|pay_amount|base_salary|compensation|hourly_cost|wage|bonus|stipend")
IP_COL = re.compile(r"ip_address|\bip\b|client_ip")
EMAIL_VALUE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MASKED_EMAIL = r"^u[0-9a-f]{12}@"
MASKED_ANYWHERE = r"\mu[0-9a-f]{12}@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
# identifiers, references and codes are never personal text: masking them would break joins and unique keys
IDENTIFIER_COL = re.compile(r"(^id$|_id$|_ids$|^uuid|_uuid$|_key$|_ref$|_type$|_status$|^status$|_code$|_kind$|"
                            r"_channel$|_slug$|_number_id$|userid$|candidateid$|jobid$)")


def columns(cur):
    cur.execute("""
        SELECT c.table_schema, c.table_name, c.column_name, c.data_type, c.is_nullable = 'YES',
               c.character_maximum_length
        FROM information_schema.columns c
        JOIN information_schema.tables t ON t.table_schema = c.table_schema AND t.table_name = c.table_name
        WHERE c.table_schema = ANY(%s) AND t.table_type = 'BASE TABLE'
        ORDER BY 1, 2, 3""", (list(SCHEMAS),))
    return cur.fetchall()


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def mask_column(cur, schema, table, column, dtype, nullable, company_domains) -> str:
    """The UPDATE for one column, or "" to leave it. Expressions are deterministic per value (md5)."""
    col, low = q(column), column.lower()
    target = f"{q(schema)}.{q(table)}"
    h = f"md5({col}::text)"
    if dtype == "bytea":
        return f"UPDATE {target} SET {col} = {'NULL' if nullable else chr(39) + chr(39) + '::bytea'} WHERE {col} IS NOT NULL"
    if dtype in TEXT_TYPES:
        if SECRET_COL.search(low):
            return f"UPDATE {target} SET {col} = {'NULL' if nullable else chr(39) + chr(39)} WHERE {col} IS NOT NULL"
        if IDENTIFIER_COL.search(low):
            return ""
        if EMAIL_COL.search(low):
            domains = "ARRAY[" + ",".join(f"'{d}'" for d in company_domains) + "]::text[]"
            return (f"UPDATE {target} SET {col} = 'u' || left({h}, 12) || '@' || CASE WHEN "
                    f"lower(split_part({col}, '@', 2)) = ANY({domains}) THEN lower(split_part({col}, '@', 2)) "
                    f"ELSE 'example.invalid' END WHERE {col} LIKE '%@%'")
        if NAME_COL.search(low):
            return f"UPDATE {target} SET {col} = 'Person ' || left({h}, 6) WHERE {col} IS NOT NULL AND {col} <> ''"
        if PHONE_COL.search(low):
            return (f"UPDATE {target} SET {col} = '+1555' || lpad((('x' || left({h}, 7))::bit(28)::int % 10000000)::text, 7, '0') "
                    f"WHERE {col} IS NOT NULL AND {col} <> ''")
        if (table.lower(), low) in KEEP_FREE_TEXT:
            return ""
        if ID_NUMBER_COL.search(low) or ADDRESS_COL.search(low) or FREE_TEXT_COL.search(low) or BIRTH_COL.search(low):
            return f"UPDATE {target} SET {col} = '[masked ' || left({h}, 8) || ']' WHERE {col} IS NOT NULL AND {col} <> ''"
        if URL_COL.search(low):
            return f"UPDATE {target} SET {col} = 'https://example.invalid/' || left({h}, 12) WHERE {col} IS NOT NULL AND {col} <> ''"
        if IP_COL.search(low):
            return f"UPDATE {target} SET {col} = '0.0.0.0' WHERE {col} IS NOT NULL"
        return ""
    if dtype in JSON_TYPES:
        if IDENTIFIER_COL.search(low):
            return ""
        if FREE_TEXT_COL.search(low) or SECRET_COL.search(low) or low in ("data", "details", "metadata", "extra",
                                                                         "context", "result", "facts", "profile"):
            return f"UPDATE {target} SET {col} = '{{}}'::{dtype} WHERE {col} IS NOT NULL"
        return ""
    if dtype in DATE_TYPES and BIRTH_COL.search(low):
        return f"UPDATE {target} SET {col} = '1990-01-01' WHERE {col} IS NOT NULL"
    if dtype in NUMERIC_TYPES and PAY_COL.search(low):
        cast = "::numeric" if dtype in ("numeric", "double precision", "real") else ""
        factor = f"(0.8 + (('x' || left(md5(ctid::text), 4))::bit(16)::int % 401) / 1000.0)"
        value = f"round({col} * {factor})" + ("" if cast else f"::{dtype}")
        return f"UPDATE {target} SET {col} = {value} WHERE {col} IS NOT NULL"
    return ""


def leaks(cur, cols, company_domains):
    """Text columns that still hold a real-looking email (not one this script made)."""
    found = []
    for schema, table, column, dtype, _, _ in cols:
        if dtype not in TEXT_TYPES | JSON_TYPES or table in KEEP_TABLES:
            continue
        # drop every address this script made (anywhere in the text), then look for any email left
        cur.execute(f"SELECT count(*) FROM {q(schema)}.{q(table)} WHERE "
                    f"regexp_replace({q(column)}::text, %s, '', 'g') ~ %s", (MASKED_ANYWHERE, EMAIL_VALUE.pattern))
        count = cur.fetchone()[0]
        if count:
            found.append((f"{schema}.{table}.{column}", count))
    return found


def main(url: str, company_domains: list) -> int:
    if re.search(r"onboarding_prod|production|prod\.|\.prod|prod-db", url, re.IGNORECASE) or "localhost" not in url:
        print("refusing: this only masks a throwaway local copy, never a production database")
        return 2
    conn = psycopg2.connect(url)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("SET session_replication_role = replica")  # masked values may not satisfy triggers/FKs mid-way
    cols = columns(cur)
    statements = 0
    for schema, table, column, dtype, nullable, max_length in cols:
        if table in KEEP_TABLES:
            continue
        sql = mask_column(cur, schema, table, column, dtype, nullable, company_domains)
        if sql and max_length and dtype in TEXT_TYPES:
            # a masked value never overflows the column (e.g. varchar(16))
            sql = re.sub(r"SET (\"[^\"]+\") = (.*) WHERE", lambda m: f"SET {m.group(1)} = left({m.group(2)}, {max_length}) WHERE",
                         sql, count=1, flags=re.DOTALL)
        if sql:
            cur.execute(sql)
            statements += 1
    # any email still inside other text (keys, descriptions kept as is, logs) is masked the same way as above
    cur.execute(r"""
        CREATE FUNCTION pg_temp.mask_emails(t text, domains text[]) RETURNS text AS $$
        DECLARE m text; result text := t;
        BEGIN
          FOR m IN SELECT DISTINCT (regexp_matches(t, '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', 'g'))[1] LOOP
            IF m !~ '^u[0-9a-f]{12}@' THEN
              result := replace(result, m, 'u' || left(md5(m), 12) || '@' ||
                CASE WHEN lower(split_part(m, '@', 2)) = ANY(domains) THEN lower(split_part(m, '@', 2))
                     ELSE 'example.invalid' END);
            END IF;
          END LOOP;
          RETURN result;
        END $$ LANGUAGE plpgsql""")
    for schema, table, column, dtype, _, _ in cols:
        if table in KEEP_TABLES or dtype not in TEXT_TYPES | JSON_TYPES:
            continue
        col, value = q(column), f"{q(column)}::text"
        expr = f"pg_temp.mask_emails({value}, %s)" + (f"::{dtype}" if dtype in JSON_TYPES else "")
        cur.execute(f"UPDATE {q(schema)}.{q(table)} SET {col} = {expr} WHERE {value} ~ %s",
                    (company_domains, EMAIL_VALUE.pattern))
    # queued work never runs against a copy; tracking stays for debugging
    cur.execute("""UPDATE app_schema.channel_queue_item SET status = 'DEAD_LETTER',
                   error = 'masked production copy: never processed locally'
                   WHERE status IN ('PENDING', 'PROCESSING', 'WAITING_FOR_SLM')""")
    # bank/tax numbers sometimes sit in a column named generically ("value"): API keys and connector config are cleared
    for table in ("api_keys_config", "msgraph_sessions", "account_activation_tokens", "user_mfa", "integration_credentials"):
        cur.execute("SELECT to_regclass(%s)", (f"app_schema.{table}",))
        if cur.fetchone()[0]:
            cur.execute(f"DELETE FROM app_schema.{q(table)}")
    conn.commit()
    print(f"masked {statements} column(s)")

    found = leaks(cur, cols, company_domains)
    if found:
        print("LEAK CHECK FAILED: real-looking emails remain in:")
        for where, count in found:
            print(f"  {where}: {count}")
        return 1
    print("leak check passed: no unmasked email anywhere")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], [d.strip().lower() for d in sys.argv[2].split(",") if d.strip()]))
