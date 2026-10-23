"""What still points at a row -- read from the database's own foreign keys, so a delete check
can never miss a table the way hand-written lists did.

    refs = blocking_references(db, business_unit)   # {"jobs": 4, "users": 2}
    ensure_deletable(db, business_unit, "Business unit 'AXION'")   # 409 naming them, or returns

Only foreign keys the database would refuse (NO ACTION / RESTRICT) block; ON DELETE CASCADE
and SET NULL are the database's own decision and are left to it."""
from typing import Dict

from fastapi import HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

_FOREIGN_KEYS_TO = text("""
    SELECT ns.nspname AS schema_name, cl.relname AS table_name, att.attname AS column_name
    FROM pg_constraint con
    JOIN pg_class cl ON cl.oid = con.conrelid
    JOIN pg_namespace ns ON ns.oid = cl.relnamespace
    JOIN pg_class rcl ON rcl.oid = con.confrelid
    JOIN pg_namespace rns ON rns.oid = rcl.relnamespace
    JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
    WHERE con.contype = 'f' AND array_length(con.conkey, 1) = 1
      AND rcl.relname = :table AND rns.nspname = COALESCE(:schema, current_schema())
      AND con.confdeltype IN ('a', 'r')
""")


def blocking_references(db: Session, row) -> Dict[str, int]:
    """{referencing table: rows} for every row that would stop `row` being deleted."""
    mapper = inspect(row).mapper
    table = mapper.local_table
    primary_key = mapper.primary_key
    if len(primary_key) != 1:
        raise ValueError(f"blocking_references needs a single-column primary key ({table.name})")
    value = mapper.primary_key_from_instance(row)[0]
    found: Dict[str, int] = {}
    for schema_name, table_name, column_name in db.execute(
            _FOREIGN_KEYS_TO, {"table": table.name, "schema": table.schema}).all():
        count = db.execute(text(f'SELECT count(*) FROM "{schema_name}"."{table_name}" WHERE "{column_name}" = :v'),
                           {"v": value}).scalar()
        if count:
            found[table_name] = found.get(table_name, 0) + count
    return found


def describe(references: Dict[str, int]) -> str:
    def label(table: str, count: int) -> str:
        name = table.replace("_", " ")
        return f"{count} {name[:-1] if count == 1 and name.endswith('s') else name}"

    return ", ".join(label(table, count) for table, count in sorted(references.items()))


def ensure_deletable(db: Session, row, label: str) -> None:
    """Raise 409 naming what still uses the row; return when nothing does."""
    references = blocking_references(db, row)
    if references:
        raise HTTPException(status_code=409,
                            detail=f"{label} can't be deleted: still used by {describe(references)}. "
                                   "Move or remove those first.")
