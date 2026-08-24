# Secrets Management Setup - Production Security

**Last Updated:** 2026-08-18  
**Status:** ✅ PRODUCTION READY  
**Implements:** Iteration 3 Issue #2 - Secrets Vault Integration

## Overview

The application now supports secure secrets management through multiple backends:

1. **Azure Key Vault** (Recommended for Azure deployments)
2. **AWS Secrets Manager** (For AWS deployments)
3. **Environment Variables** (Development/Testing)
4. **Fallback Mode** (Tries multiple backends, falls back to environment variables)

## Quick Start

### Development (Default)

For local development, secrets are loaded from environment variables and `.env` files:

```bash
# Copy .env template
cp .env.example .env

# Add your secrets
echo "DATABASE_URL=postgresql://user:password@localhost/wros_dev" >> .env
echo "JWT_SECRET=your-dev-secret-key-here" >> .env

# Start the app
python -m uvicorn app.main:app --reload
```

### Production with Azure Key Vault

For Azure deployments:

```bash
# 1. Set environment to use Azure Key Vault
export SECRETS_BACKEND=azure
export SECRETS_VAULT_NAME=my-vault-name

# 2. Ensure Azure credentials are available
# Option A: Via Azure CLI (development)
az login

# Option B: Via environment variables (CI/CD)
export AZURE_TENANT_ID=your-tenant-id
export AZURE_CLIENT_ID=your-app-id
export AZURE_CLIENT_SECRET=your-secret

# Option C: Via Managed Identity (Azure VMs/App Service)
# (No configuration needed - automatic)

# 3. Start the application
python -m uvicorn app.main:app
```

### Production with AWS Secrets Manager

For AWS deployments:

```bash
# 1. Set environment to use AWS Secrets Manager
export SECRETS_BACKEND=aws
export AWS_REGION=us-east-1

# 2. Ensure AWS credentials are available
# Option A: Via AWS CLI (development)
aws configure

# Option B: Via environment variables (CI/CD)
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key

# Option C: Via IAM Role (EC2 instances/ECS tasks)
# (No configuration needed - automatic)

# 3. Start the application
python -m uvicorn app.main:app
```

### Production with Fallback Mode

Use fallback for maximum flexibility:

```bash
# Try Azure, then AWS, then environment variables
export SECRETS_BACKEND=fallback

# With Azure as primary
export SECRETS_VAULT_NAME=my-vault-name
export AWS_REGION=us-east-1

# Start application
python -m uvicorn app.main:app
```

## Secret Name Conventions

Secrets are named using kebab-case and converted to your vault's format:

| Secret Name | Environment Var | Azure Key Vault | AWS Secrets Manager |
|------------|-----------------|-----------------|-------------------|
| `database-url` | `DATABASE_URL` | `database-url` | `database-url` |
| `jwt-secret` | `JWT_SECRET` | `jwt-secret` | `jwt-secret` |
| `client-secret` | `CLIENT_SECRET` | `client-secret` | `client-secret` |
| `webhook-shared-secret` | `WEBHOOK_SHARED_SECRET` | `webhook-shared-secret` | `webhook-shared-secret` |
| `whatsapp-verify-token` | `WHATSAPP_VERIFY_TOKEN` | `whatsapp-verify-token` | `whatsapp-verify-token` |
| `whatsapp-app-secret` | `WHATSAPP_APP_SECRET` | `whatsapp-app-secret` | `whatsapp-app-secret` |
| `field-encryption-key` | `FIELD_ENCRYPTION_KEY` | `field-encryption-key` | `field-encryption-key` |

## Setting Up Azure Key Vault

### Prerequisites

```bash
# Install Azure CLI
# https://docs.microsoft.com/en-us/cli/azure/install-azure-cli

# Install Azure SDK packages
pip install azure-identity azure-keyvault-secrets
```

### Create Vault and Secrets (Azure Portal or CLI)

```bash
# Login to Azure
az login

# Create resource group (if needed)
az group create --name myresourcegroup --location eastus

# Create Key Vault
az keyvault create \
  --name my-vault-name \
  --resource-group myresourcegroup \
  --location eastus

# Add secrets
az keyvault secret set \
  --vault-name my-vault-name \
  --name database-url \
  --value "postgresql://user:password@host/dbname"

az keyvault secret set \
  --vault-name my-vault-name \
  --name jwt-secret \
  --value "your-secret-key-here"

az keyvault secret set \
  --vault-name my-vault-name \
  --name client-secret \
  --value "your-client-secret-here"

# ... repeat for other secrets
```

### Configure App Service Access (Managed Identity)

```bash
# Create managed identity
az identity create --name my-app-identity

# Grant Key Vault access
az keyvault set-policy \
  --name my-vault-name \
  --object-id <managed-identity-object-id> \
  --secret-permissions get list
```

## Setting Up AWS Secrets Manager

### Prerequisites

```bash
# Install AWS SDK
pip install boto3

# Configure AWS credentials
aws configure
# or set environment variables:
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_REGION=us-east-1
```

### Create Secrets (AWS CLI or Console)

```bash
# Create secret for database URL
aws secretsmanager create-secret \
  --name database-url \
  --secret-string "postgresql://user:password@host/dbname"

# Create secret for JWT
aws secretsmanager create-secret \
  --name jwt-secret \
  --secret-string "your-secret-key-here"

# Create secret for client secret
aws secretsmanager create-secret \
  --name client-secret \
  --secret-string "your-client-secret-here"

# ... repeat for other secrets
```

### Configure IAM Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:ListSecrets"
      ],
      "Resource": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:*"
    }
  ]
}
```

## Programmatic Usage

### In Application Code

```python
from app.core.secrets_manager import get_secret, get_secret_uncached

# Retrieve a secret (cached for performance)
db_password = get_secret("database-password")

# For fresh values after rotation
api_key = get_secret_uncached("third-party-api-key")

# With fallback default
timeout = get_secret("api-timeout", default="30")
```

### In Configuration

Secrets are automatically integrated with `app/core/config.py`:

```python
from app.core.config import settings

print(settings.JWT_SECRET)  # Loads from vault → environment
print(settings.DATABASE_URL)  # Loads from vault → environment
```

### Clear Cache (After Rotation)

```python
from app.core.secrets_manager import clear_secrets_cache

# Rotate credential on remote vault
# ...

# Clear local cache to fetch fresh values
clear_secrets_cache()
```

## Environment Variables Reference

| Variable | Purpose | Example |
|----------|---------|---------|
| `SECRETS_BACKEND` | Which vault to use | `azure`, `aws`, `env`, `fallback` |
| `SECRETS_VAULT_NAME` | Azure Key Vault name | `my-vault-name` |
| `AWS_REGION` | AWS region for Secrets Manager | `us-east-1` |
| `AZURE_TENANT_ID` | Azure tenant ID (if using env auth) | UUID |
| `AZURE_CLIENT_ID` | Azure app ID (if using env auth) | UUID |
| `AZURE_CLIENT_SECRET` | Azure app secret (if using env auth) | Secret string |
| `AWS_ACCESS_KEY_ID` | AWS access key (if using env auth) | AKIAIOSFODNN... |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key (if using env auth) | Secret string |

## Security Best Practices

### Do's ✅

- ✅ Store all secrets in vault, never in code
- ✅ Use managed identities (Azure/AWS) for production
- ✅ Rotate secrets regularly (at least every 90 days)
- ✅ Use environment variables only for development
- ✅ Enable vault logging and monitoring
- ✅ Limit vault access via IAM policies
- ✅ Use separate vaults for development/production
- ✅ Clear secrets cache after credential rotation
- ✅ Monitor secret access in vault audit logs

### Don'ts ❌

- ❌ Never commit `.env` files to Git
- ❌ Never hardcode secrets in application code
- ❌ Never use shared vault credentials across environments
- ❌ Never log or print secret values
- ❌ Never send secrets via unencrypted channels
- ❌ Never use generic/shared vault accounts
- ❌ Never disable vault encryption
- ❌ Never skip secret rotation
- ❌ Never grant excessive vault permissions

## Troubleshooting

### Secret Not Found

```python
from app.core.secrets_manager import get_secret

# Debug: Check which backend is being used
import os
print(f"Backend: {os.getenv('SECRETS_BACKEND', 'env')}")

# Try with explicit default
value = get_secret("my-secret", default="default-value")
```

### Azure Authentication Failed

```bash
# Check Azure CLI login
az account show

# Check managed identity
curl -H Metadata:true http://169.254.169.254/metadata/identity/oauth2/token?api-version=2017-09-01&resource=https://vault.azure.net

# Check environment variables
echo $AZURE_TENANT_ID
echo $AZURE_CLIENT_ID
```

### AWS Authentication Failed

```bash
# Check AWS CLI configuration
aws sts get-caller-identity

# Check environment variables
echo $AWS_REGION
echo $AWS_ACCESS_KEY_ID
```

### Cache Issues

```python
from app.core.secrets_manager import clear_secrets_cache

# If you changed a secret and it's not being picked up:
clear_secrets_cache()

# For one-time uncached access:
from app.core.secrets_manager import get_secret_uncached
value = get_secret_uncached("my-secret")
```

## Testing

### Unit Tests

```bash
# Run tests (uses environment variable backend)
pytest tests/ -v

# Test with specific backend
SECRETS_BACKEND=env pytest tests/ -v
```

### Integration Tests

```bash
# Test with Azure Key Vault
export SECRETS_BACKEND=azure
export SECRETS_VAULT_NAME=test-vault
pytest tests/integration/ -v

# Test with AWS Secrets Manager
export SECRETS_BACKEND=aws
export AWS_REGION=us-east-1
pytest tests/integration/ -v
```

## Migration from .env Files

### Step 1: Identify Secrets

```bash
# Find all secrets in .env
grep -E "PASSWORD|SECRET|KEY|TOKEN" .env
```

### Step 2: Add to Vault

```bash
# For Azure
az keyvault secret set --vault-name my-vault --name secret-name --value secret-value

# For AWS
aws secretsmanager create-secret --name secret-name --secret-string "secret-value"
```

### Step 3: Update Environment

```bash
# Set SECRETS_BACKEND
export SECRETS_BACKEND=azure  # or aws, fallback

# Stop using .env for secrets
# Keep .env for non-sensitive config only
```

### Step 4: Verify

```bash
# Application should load secrets from vault
python -m uvicorn app.main:app

# Check logs for backend initialization
# Should see: "Secrets backend initialized: azure" (or aws/fallback)
```

## Monitoring & Auditing

### Azure Key Vault Monitoring

```bash
# View access logs
az monitor activity-log list --resource-group myresourcegroup

# Enable diagnostic logging
az monitor diagnostic-settings create \
  --name my-vault-logs \
  --resource-id /subscriptions/.../providers/Microsoft.KeyVault/vaults/my-vault \
  --workspace my-workspace
```

### AWS Secrets Manager Monitoring

```bash
# View CloudTrail logs
aws cloudtrail lookup-events \
  --lookup-attributes AttributeKey=ResourceType,AttributeValue=AWS::SecretsManager::Secret

# Set up CloudWatch alarms
aws cloudwatch put-metric-alarm \
  --alarm-name secrets-access-alarm \
  --alarm-actions arn:aws:sns:...
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy with Secrets

on: [push]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Configure Azure credentials
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      
      - name: Deploy application
        env:
          SECRETS_BACKEND: azure
          SECRETS_VAULT_NAME: ${{ secrets.VAULT_NAME }}
        run: |
          pip install -r requirements.txt
          python -m uvicorn app.main:app
```

### GitLab CI Example

```yaml
deploy:
  stage: deploy
  environment:
    name: production
  variables:
    SECRETS_BACKEND: aws
    AWS_REGION: us-east-1
  before_script:
    - export AWS_ACCESS_KEY_ID=$AWS_KEY_ID
    - export AWS_SECRET_ACCESS_KEY=$AWS_SECRET
  script:
    - pip install -r requirements.txt
    - python -m uvicorn app.main:app
```

## Support & Questions

For issues or questions about secrets management:

1. Check troubleshooting section above
2. Review vault logs for errors
3. Test secrets directly in vault console
4. Verify IAM/security group permissions
5. Check application logs for initialization messages

---

**Status:** ✅ COMPLETE - Iteration 3 Issue #2 Resolved  
**Next:** Deploy to staging and verify vault access
