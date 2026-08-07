# PowerShell script to create a superuser in WROS
# This script uses Python to hash the password with bcrypt, ensuring compatibility with the backend

$DBPath = ".\local_dev.sqlite3"
$SUPERUSER_EMAIL = "superuser@blitzenx.com"
$SUPERUSER_PASSWORD = "Superuser!123"

Write-Host "Creating superuser: $SUPERUSER_EMAIL" -ForegroundColor Cyan

# Use Python to hash the password with bcrypt
$PythonCode = @"
import bcrypt
import sys

password = '$SUPERUSER_PASSWORD'
# Generate bcrypt hash with salt
salt = bcrypt.gensalt(rounds=12)
hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
# Print the hash as a string
print(hashed.decode('utf-8'))
"@

# Run Python to generate the hash
$HashedPassword = python -c $PythonCode

Write-Host "Generated bcrypt hash: $($HashedPassword.Substring(0, 50))..." -ForegroundColor Green

# Create the superuser in the database
$SqliteCode = @"
import sqlite3
import uuid
from datetime import datetime

db_path = r'$DBPath'
email = '$SUPERUSER_EMAIL'
hashed_password = '$HashedPassword'

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Delete existing superuser if exists
    cursor.execute('DELETE FROM users WHERE UserEmail = ?', (email,))
    conn.commit()
    print(f'Deleted existing user: {email}')

    # Create new superuser
    user_id = str(uuid.uuid4())
    created_at = datetime.utcnow().isoformat()

    cursor.execute('''
        INSERT INTO users
        (UserID, UserEmail, UserPassword, UserName, UserRole, CreatedAt, mfa_enabled, digest_enabled, thunder_enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        email,
        hashed_password,
        'Super User',
        'Super User',
        created_at,
        0,
        0,
        0
    ))

    conn.commit()
    print(f'✓ Superuser created successfully!')
    print(f'  Email: {email}')
    print(f'  Password: $SUPERUSER_PASSWORD')
    print(f'  User ID: {user_id}')
    print(f'  Role: Super User')

except Exception as e:
    print(f'✗ Error creating superuser: {e}')
    conn.rollback()
finally:
    conn.close()
"@

# Run Python to create the user
python -c $SqliteCode
