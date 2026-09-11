from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os, bcrypt
load_dotenv('.env'); load_dotenv('.env.local', override=True)
engine = create_engine(os.getenv('DATABASE_URL'))
pwd = bcrypt.hashpw(b'TestUser@123', bcrypt.gensalt()).decode()
with engine.connect() as conn:
    conn.execute(text('UPDATE app_schema.users SET "UserPassword" = :pwd WHERE "UserEmail" = :email'), {'pwd': pwd, 'email': 'superuser@blitzenx.com'})
    conn.commit()
print('✓ Ready: superuser@blitzenx.com / TestUser@123')
