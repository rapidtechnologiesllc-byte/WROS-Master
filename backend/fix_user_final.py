#!/usr/bin/env python
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os, bcrypt

load_dotenv('.env')
load_dotenv('.env.local', override=True)
engine = create_engine(os.getenv('DATABASE_URL'))
pwd = bcrypt.hashpw(b'TestUser@123', bcrypt.gensalt()).decode()

with engine.connect() as conn:
    conn.execute(text("""
        INSERT INTO app_schema.users ("UserID", "UserEmail", "UserPassword", "UserName", "UserRole", "tenant_id", "password_reset_required")
        VALUES ('superuser@blitzenx.com', 'superuser@blitzenx.com', :pwd, 'Super User', 'SuperUser', 1, false)
        ON CONFLICT ("UserID") DO UPDATE SET "UserPassword" = :pwd
    """), {'pwd': pwd})
    conn.commit()
    print('\n✓ User ready!\n')
    print('Email: superuser@blitzenx.com')
    print('Password: TestUser@123\n')
