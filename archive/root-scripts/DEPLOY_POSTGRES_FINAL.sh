#!/bin/bash
# ============================================================================
# PostgreSQL Migration Final Deployment Script
# Complete automation for SQLite → PostgreSQL migration
# ============================================================================
# Usage:
#   On your VPS:
#   export POSTGRES_PASSWORD="your-strong-password"
#   bash DEPLOY_POSTGRES_FINAL.sh
# ============================================================================

set -e  # Exit on any error

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DB_NAME="onboarding_prod"
DB_USER="app_user"
BACKEND_PATH="${BACKEND_PATH:-/home/HRMS/OnboardingModule-Backend}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     PostgreSQL Migration - Complete Deployment Script          ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================
echo -e "${YELLOW}▶ PRE-FLIGHT CHECKS${NC}"
echo ""

# Check password
if [ -z "$POSTGRES_PASSWORD" ]; then
    echo -e "${RED}✗ ERROR: POSTGRES_PASSWORD environment variable not set${NC}"
    echo ""
    echo "Usage:"
    echo "  export POSTGRES_PASSWORD='your-strong-password'"
    echo "  bash DEPLOY_POSTGRES_FINAL.sh"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓ Password set${NC}"

# Check backend path
if [ ! -d "$BACKEND_PATH" ]; then
    echo -e "${RED}✗ ERROR: Backend path not found: $BACKEND_PATH${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Backend path exists: $BACKEND_PATH${NC}"

# Check SQLite file exists
SQLITE_FILE="$BACKEND_PATH/local_dev.sqlite3"
if [ ! -f "$SQLITE_FILE" ]; then
    echo -e "${YELLOW}⚠ SQLite file not found: $SQLITE_FILE${NC}"
    echo "  (This is OK if it's a fresh database)"
else
    echo -e "${GREEN}✓ SQLite file found: $SQLITE_FILE${NC}"
fi

# Check .env file
ENV_FILE="$BACKEND_PATH/.env.production"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}✗ ERROR: .env.production not found: $ENV_FILE${NC}"
    exit 1
fi
echo -e "${GREEN}✓ .env.production found${NC}"

echo ""

# ============================================================================
# STEP 1: Install PostgreSQL
# ============================================================================
echo -e "${YELLOW}▶ STEP 1/6: Installing PostgreSQL${NC}"

if command -v psql &> /dev/null; then
    echo -e "${GREEN}✓ PostgreSQL already installed: $(psql --version)${NC}"
else
    echo "  Installing PostgreSQL..."
    sudo apt-get update > /dev/null 2>&1
    sudo apt-get install -y postgresql postgresql-contrib libpq-dev > /dev/null 2>&1
    echo -e "${GREEN}✓ PostgreSQL installed${NC}"
fi

echo ""

# ============================================================================
# STEP 2: Start PostgreSQL Service
# ============================================================================
echo -e "${YELLOW}▶ STEP 2/6: Starting PostgreSQL Service${NC}"

sudo systemctl start postgresql
sudo systemctl enable postgresql

if sudo systemctl is-active --quiet postgresql; then
    echo -e "${GREEN}✓ PostgreSQL service running${NC}"
else
    echo -e "${RED}✗ ERROR: PostgreSQL failed to start${NC}"
    exit 1
fi

echo ""

# ============================================================================
# STEP 3: Create Database and User
# ============================================================================
echo -e "${YELLOW}▶ STEP 3/6: Creating Database and User${NC}"

# Check if database already exists
if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo -e "${GREEN}✓ Database '$DB_NAME' already exists${NC}"
else
    echo "  Creating database and user..."

    sudo -u postgres psql << PSQL_EOF > /dev/null 2>&1
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD '$POSTGRES_PASSWORD';
ALTER ROLE $DB_USER SET client_encoding TO 'utf8';
ALTER ROLE $DB_USER SET default_transaction_isolation TO 'read committed';
ALTER ROLE $DB_USER SET default_transaction_deferrable TO on;
ALTER ROLE $DB_USER SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
PSQL_EOF

    echo -e "${GREEN}✓ Database and user created${NC}"
fi

# Verify connection
echo "  Verifying connection..."
if PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$DB_USER" -d "$DB_NAME" -h localhost -c "SELECT version();" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL connection verified${NC}"
else
    echo -e "${RED}✗ ERROR: Cannot connect to PostgreSQL${NC}"
    exit 1
fi

echo ""

# ============================================================================
# STEP 4: Backup and Export SQLite Data
# ============================================================================
echo -e "${YELLOW}▶ STEP 4/6: Backing Up SQLite Data${NC}"

if [ -f "$SQLITE_FILE" ]; then
    echo "  Creating backup..."

    mkdir -p "$BACKEND_PATH/backups"
    BACKUP_FILE="$BACKEND_PATH/backups/local_dev.sqlite3.backup.$TIMESTAMP"
    cp "$SQLITE_FILE" "$BACKUP_FILE"

    echo -e "${GREEN}✓ SQLite backed up to: $BACKUP_FILE${NC}"

    # Export data
    echo "  Exporting SQLite data..."
    sqlite3 "$SQLITE_FILE" .dump > /tmp/sqlite_dump_$TIMESTAMP.sql

    # Clean up SQLite-specific syntax
    sed -i '/^PRAGMA/d' /tmp/sqlite_dump_$TIMESTAMP.sql
    sed -i '/^BEGIN TRANSACTION/d' /tmp/sqlite_dump_$TIMESTAMP.sql
    sed -i '/^COMMIT/d' /tmp/sqlite_dump_$TIMESTAMP.sql
    sed -i '/^ROLLBACK/d' /tmp/sqlite_dump_$TIMESTAMP.sql

    echo -e "${GREEN}✓ SQLite data exported and cleaned${NC}"

    # Import into PostgreSQL
    echo "  Importing into PostgreSQL..."
    PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$DB_USER" -d "$DB_NAME" -h localhost -f /tmp/sqlite_dump_$TIMESTAMP.sql > /dev/null 2>&1 || true

    # Verify import
    CANDIDATE_COUNT=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$DB_USER" -d "$DB_NAME" -h localhost -t -c "SELECT COUNT(*) FROM candidates WHERE 1=1;" 2>/dev/null || echo "0")

    echo -e "${GREEN}✓ Data imported to PostgreSQL (≈ $CANDIDATE_COUNT candidates)${NC}"

    # Cleanup
    rm -f /tmp/sqlite_dump_$TIMESTAMP.sql
else
    echo -e "${YELLOW}⚠ SQLite file not found (fresh database)${NC}"
fi

echo ""

# ============================================================================
# STEP 5: Update .env File
# ============================================================================
echo -e "${YELLOW}▶ STEP 5/6: Updating .env.production${NC}"

# Backup current .env
cp "$ENV_FILE" "$ENV_FILE.backup.$TIMESTAMP"
echo -e "${GREEN}✓ .env.production backed up to: $ENV_FILE.backup.$TIMESTAMP${NC}"

# Update DATABASE_URL
if grep -q "^DATABASE_URL=" "$ENV_FILE"; then
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://$DB_USER:$POSTGRES_PASSWORD@localhost:5432/$DB_NAME|" "$ENV_FILE"
else
    echo "DATABASE_URL=postgresql://$DB_USER:$POSTGRES_PASSWORD@localhost:5432/$DB_NAME" >> "$ENV_FILE"
fi

echo -e "${GREEN}✓ .env.production updated with PostgreSQL URL${NC}"

echo ""

# ============================================================================
# STEP 6: Verify Everything
# ============================================================================
echo -e "${YELLOW}▶ STEP 6/6: Final Verification${NC}"

# Verify PostgreSQL connection
if PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$DB_USER" -d "$DB_NAME" -h localhost -c "SELECT COUNT(*) as tables FROM information_schema.tables WHERE table_schema='public';" > /dev/null 2>&1; then
    TABLE_COUNT=$(PGPASSWORD="$POSTGRES_PASSWORD" psql -U "$DB_USER" -d "$DB_NAME" -h localhost -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';")
    echo -e "${GREEN}✓ PostgreSQL connection verified ($TABLE_COUNT tables)${NC}"
else
    echo -e "${RED}✗ ERROR: PostgreSQL connection failed${NC}"
    exit 1
fi

echo ""

# ============================================================================
# SUCCESS!
# ============================================================================
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}${GREEN}    ✅ PostgreSQL Migration Complete! ✅${NC}${BLUE}                  ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}📋 SUMMARY:${NC}"
echo "  Database:      $DB_NAME"
echo "  User:          $DB_USER"
echo "  Host:          localhost:5432"
echo "  Tables:        $TABLE_COUNT"
echo "  .env file:     $ENV_FILE"
echo "  Backup:        $ENV_FILE.backup.$TIMESTAMP"
if [ -f "$SQLITE_FILE" ]; then
    echo "  SQLite backup: $BACKUP_FILE"
fi
echo ""

echo -e "${YELLOW}📌 NEXT STEPS:${NC}"
echo ""
echo "1. Verify database contents (optional):"
echo "   PGPASSWORD='$POSTGRES_PASSWORD' psql -U $DB_USER -d $DB_NAME -h localhost"
echo ""
echo "2. On your local machine, push code to GitHub:"
echo "   git add requirements.txt alembic/versions/2026_08_14_postgresql_migration.py"
echo "   git commit -m 'Deploy PostgreSQL migration'"
echo "   git push origin main"
echo ""
echo "3. Watch GitHub Actions deploy automatically:"
echo "   https://github.com/your-repo/actions"
echo ""
echo "4. Backend will restart with PostgreSQL connection"
echo ""
echo "5. Monitor logs:"
echo "   pm2 logs onboarding-backend --lines 50"
echo ""

echo -e "${YELLOW}⚠️  IMPORTANT:${NC}"
echo "  • SQLite file remains as backup: $SQLITE_FILE"
echo "  • Do NOT delete it until you've verified PostgreSQL is working"
echo "  • After 24-48 hours of smooth operation, you can safely delete it"
echo ""

echo -e "${GREEN}🎉 Deployment Ready! 🎉${NC}"
echo ""
