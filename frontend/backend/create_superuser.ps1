# PowerShell script to create a superuser in WROS using PostgreSQL
# This script uses Python with SQLAlchemy, requiring:
#  - PostgreSQL running (DATABASE_URL set in environment)
#  - SQLAlchemy + psycopg2 installed
#
# Usage:
#   $env:DATABASE_URL = "postgresql://postgres:123@localhost:5432/wros_dev"
#   .\create_superuser.ps1

$SUPERUSER_EMAIL = "superuser@blitzenx.com"
$SUPERUSER_PASSWORD = "Superuser!123"

Write-Host "Creating superuser: $SUPERUSER_EMAIL" -ForegroundColor Cyan

# Check if DATABASE_URL is set
if ([string]::IsNullOrEmpty($env:DATABASE_URL)) {
    Write-Host "ERROR: DATABASE_URL environment variable not set!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Set DATABASE_URL to your PostgreSQL connection string:" -ForegroundColor Yellow
    Write-Host '  $env:DATABASE_URL = "postgresql://postgres:password@localhost:5432/wros_dev"'
    Write-Host ""
    exit 1
}

if (-not $env:DATABASE_URL.StartsWith("postgresql://")) {
    Write-Host "ERROR: DATABASE_URL must use PostgreSQL protocol!" -ForegroundColor Red
    Write-Host "Current: $($env:DATABASE_URL.Split('@')[0])@..."
    exit 1
}

Write-Host "Using database: $($env:DATABASE_URL.Split('@')[0])@..." -ForegroundColor Yellow

# Create superuser using SQLAlchemy
$PythonCode = @"
import os
import sys
sys.path.insert(0, '.')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.user import Users
from app.core.security import get_password_hash
import uuid
from datetime import datetime

email = '$SUPERUSER_EMAIL'
password = '$SUPERUSER_PASSWORD'

db_url = os.getenv('DATABASE_URL')
if not db_url:
    print('ERROR: DATABASE_URL not set')
    sys.exit(1)

if not db_url.startswith('postgresql://'):
    print('ERROR: DATABASE_URL must use PostgreSQL protocol')
    sys.exit(1)

try:
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Delete existing user if exists
    existing = session.query(Users).filter(Users.UserEmail == email).first()
    if existing:
        session.delete(existing)
        session.commit()
        print(f'Deleted existing user: {email}')

    # Create new superuser
    hashed_password = get_password_hash(password)
    user_id = str(uuid.uuid4())

    user = Users(
        UserID=user_id,
        UserEmail=email,
        UserPassword=hashed_password,
        UserName='Super User',
        UserRole='Super User',
        CreatedAt=datetime.utcnow(),
        mfa_enabled=False,
        digest_enabled=False,
        thunder_enabled=False,
    )

    session.add(user)
    session.commit()

    print(f'✓ Superuser created successfully!')
    print(f'  Email: {email}')
    print(f'  Password: {password}')
    print(f'  User ID: {user_id}')
    print(f'  Role: Super User')

except Exception as e:
    print(f'✗ Error creating superuser: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    session.close()
"@

# Run Python to create the user
python -c $PythonCode
