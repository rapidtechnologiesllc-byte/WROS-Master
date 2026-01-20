# Quick Reference Card - Cloud Deployment

---

## Required Environment Variables

```bash
DATABASE_URL=mssql+pyodbc://USER@SERVER:PASS@SERVER.database.windows.net/DB?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30
TENANT_ID=your-tenant-id
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
REDIRECT_URI=https://your-app.azurewebsites.net/msgraph/auth/callback
AUTHORITY=https://login.microsoftonline.com/your-tenant-id
SCOPES=User.Read Mail.Send
JWT_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
JWT_PUBLIC_KEY=-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----
```

---

## Database Configuration

**Type**: Microsoft SQL Server (Azure SQL Database)  
**Driver**: ODBC Driver 17 for SQL Server  
**Min Tier**: Standard S0 (10 DTUs)  
**Recommended**: Standard S2 (50 DTUs) for production

**Connection String Format**:
```
mssql+pyodbc://{user}@{server}:{password}@{server}.database.windows.net/{database}?driver=ODBC+Driver+17+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30
```

**Important**: URL-encode special characters in password!


## Generate JWT Keys

```bash
# Generate private key
openssl genrsa -out private_key.pem 2048

# Generate public key
openssl rsa -in private_key.pem -pubout -out public_key.pem

# Format for environment variable (single line with \n)
awk 'NF {sub(/\r/, ""); printf "%s\\n",$0;}' private_key.pem
```
