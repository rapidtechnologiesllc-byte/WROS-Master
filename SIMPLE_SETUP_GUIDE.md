# Simple Setup Guide - Environment & Database

##  What You Need

This guide helps you set up:
1. **.env file** - Configuration for your application
2. **Database** - Microsoft SQL Server setup
3. **Connection URL** - How to connect to the database

---

## Part 1: Database Information

### What Database to Use?

**Database Type**: Microsoft SQL Server (Azure SQL Database)

**Recommended Version**:
- **Azure SQL Database** (always latest version automatically)
- **Or SQL Server 2019** or newer if using on-premises

**Minimum Requirements**:
- **Service Tier**: Standard S0 (for Azure)
- **DTUs**: 10 DTUs minimum, 50 DTUs recommended for production
- **Driver**: ODBC Driver 17 for SQL Server

---

## Part 2: Setting Up .env File

### Step 1: Create .env File

In your project root, create a file named `.env` (exactly this name, with the dot)

### Step 2: Add These Variables

Copy this template and fill in your values:

```env
# ============================================
# DATABASE CONNECTION
# ============================================
DATABASE_URL=mssql+pyodbc://USERNAME@SERVERNAME:PASSWORD@SERVERNAME.database.windows.net/DBNAME?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30

# ============================================
# MICROSOFT AUTHENTICATION
# ============================================
TENANT_ID=your-tenant-id-here
CLIENT_ID=your-client-id-here
CLIENT_SECRET=your-client-secret-here
REDIRECT_URI=https://your-app-url.com/msgraph/auth/callback
AUTHORITY=https://login.microsoftonline.com/your-tenant-id-here
SCOPES=User.Read Mail.Send

# ============================================
# JWT SECURITY KEYS
# ============================================
JWT_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_CONTENT\n-----END PRIVATE KEY-----
JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----\nYOUR_PUBLIC_KEY_CONTENT\n-----END PUBLIC KEY-----
```

---

## Part 3: Building the DATABASE_URL

### The Format

```
mssql+pyodbc://USERNAME@SERVERNAME:PASSWORD@SERVERNAME.database.windows.net/DBNAME?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30
```

### Fill in These Parts

| Part | What to Put | Example |
|------|-------------|---------|
| `USERNAME` | Database admin username | `sqladmin` |
| `SERVERNAME` | SQL Server name (appears twice!) | `onboard-sql-server` |
| `PASSWORD` | Database password | `MyPassword123!` |
| `DBNAME` | Database name | `onboard-db` |

### Real Example

If your database details are:
- Server: `onboard-sql-server`
- Username: `sqladmin`
- Password: `SecurePass123!`
- Database: `onboard-db`

Your DATABASE_URL would be:
```
DATABASE_URL=mssql+pyodbc://sqladmin@onboard-sql-server:SecurePass123!@onboard-sql-server.database.windows.net/onboard-db?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30
```

###  Important: Special Characters in Password

If your password has these characters, replace them:

| Character | Replace With |
|-----------|--------------|
| `@` | `%40` |
| `#` | `%23` |
| `$` | `%24` |
| `%` | `%25` |
| `&` | `%26` |

**Example**: Password `Pass@123#` becomes `Pass%40123%23`

---

## Part 4: Getting Microsoft Authentication Values

### Where to Find These Values

1. **TENANT_ID**:
   - Go to Azure Portal → Azure Active Directory → Overview
   - Copy the "Tenant ID"

2. **CLIENT_ID**:
   - Azure Portal → Azure Active Directory → App registrations
   - Select your app
   - Copy "Application (client) ID"

3. **CLIENT_SECRET**:
   - In your app registration → Certificates & secrets
   - Click "New client secret"
   - Copy the secret value (save it now, you can't see it again!)

4. **REDIRECT_URI**:
   - Use your app's URL + `/msgraph/auth/callback`
   - Example: `https://myapp.azurewebsites.net/msgraph/auth/callback`
   - Must match exactly what's in Azure AD App Registration

5. **AUTHORITY**:
   - Use: `https://login.microsoftonline.com/` + your TENANT_ID
   - Example: `https://login.microsoftonline.com/abc123-def456-...`

6. **SCOPES**:
   - Use exactly: `User.Read Mail.Send`

---

##  Part 5: Generating JWT Keys

### Option 1: Using OpenSSL (Easiest)

```bash
# Generate private key
openssl genrsa -out private_key.pem 2048

# Generate public key
openssl rsa -in private_key.pem -pubout -out public_key.pem
```

### Option 2: Using Python

```python
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# Generate keys
private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

# Get private key
private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

# Get public key
public_key = private_key.public_key()
public_pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

print("Private Key:")
print(private_pem.decode())
print("\nPublic Key:")
print(public_pem.decode())
```

### Formatting Keys for .env

Your keys will look like this (multiple lines):
```
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEF...
(more lines)
-----END PRIVATE KEY-----
```

**Convert to single line with `\n`**:
```
-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEF...\n-----END PRIVATE KEY-----
```

Replace each actual line break with `\n` (backslash-n)

---

##  Part 6: Complete Example .env File

Here's a complete example with fake values:

```env
# Database
DATABASE_URL=mssql+pyodbc://sqladmin@onboard-sql-server:MyPass123!@onboard-sql-server.database.windows.net/onboard-db?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30

# Microsoft Authentication
TENANT_ID=abc12345-def6-7890-ghij-klmnopqrstuv
CLIENT_ID=xyz98765-abc1-2345-defg-hijklmnopqrs
CLIENT_SECRET=Rf48Q~3ThTPoJvD1hVJMCZgJPNrJ13tgRtL9QbV2
REDIRECT_URI=https://myapp.azurewebsites.net/msgraph/auth/callback
AUTHORITY=https://login.microsoftonline.com/abc12345-def6-7890-ghij-klmnopqrstuv
SCOPES=User.Read Mail.Send

# JWT Keys
JWT_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC82yKd...\n-----END PRIVATE KEY-----
JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAvNsinY5SUJz...\n-----END PUBLIC KEY-----
```

---

##  Part 7: Testing Your Setup

### 1. Test Database Connection

```python
# Run this Python script to test
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

try:
    engine = create_engine(DATABASE_URL)
    connection = engine.connect()
    print(" Database connection successful!")
    connection.close()
except Exception as e:
    print(f" Database connection failed: {e}")
```

### 2. Test Environment Variables

```python
import os
from dotenv import load_dotenv

load_dotenv()

# Check all variables are loaded
required_vars = [
    "DATABASE_URL", "TENANT_ID", "CLIENT_ID", "CLIENT_SECRET",
    "REDIRECT_URI", "AUTHORITY", "SCOPES",
    "JWT_PRIVATE_KEY", "JWT_PUBLIC_KEY"
]

for var in required_vars:
    value = os.getenv(var)
    if value:
        print(f" {var}: Set ({len(value)} characters)")
    else:
        print(f" {var}: NOT SET")
```

---


**That's it! Your .env file should now be ready to use.** 🎉
