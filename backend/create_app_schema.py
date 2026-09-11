#!/usr/bin/env python
"""Create app_schema for models."""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(".env")
load_dotenv(".env.local", override=True)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    try:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS app_schema"))
        conn.commit()
        print("✓ Schema app_schema created")
    except Exception as e:
        print(f"⚠ {e}")
