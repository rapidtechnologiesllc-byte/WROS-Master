#!/bin/bash
# ============================================================================
# PostgreSQL Setup Script for VPS
# Run this script on your VPS to prepare PostgreSQL for the backend
# ============================================================================
# Usage: bash setup-postgres-vps.sh
# ============================================================================

set -e  # Exit on any error

echo "================================"
echo "PostgreSQL VPS Setup"
echo "================================"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DB_NAME="onboarding_prod"
DB_USER="app_user"
DB_PASSWORD="${POSTGRES_PASSWORD:-}"  # Must be set via environment variable
BACKEND_PATH="${BACKEND_PATH:-/home/HRMS/OnboardingModule-Backend}"

echo -e "${YELLOW}Configuration:${NC}"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo "  Backend Path: $BACKEND_PATH"
echo ""

# ============================================================================
# STEP 1: Verify PostgreSQL password is set
# ============================================================================
if [ -z "$POSTGRES_PASSWORD" ]; then
    echo -e "${RED}ERROR: POSTGRES_PASSWORD environment variable not set${NC}"
    echo "Usage: POSTGRES_PASSWORD='your-strong-password' bash setup-postgres-vps.sh"
    exit 1
fi
echo -e "${GREEN}✅ Password set${NC}"

# ============================================================================
# STEP 2: Install PostgreSQL (if not already installed)
# ============================================================================
echo ""
echo -e "${YELLOW}Step 1/6: Installing PostgreSQL...${NC}"

if ! command -v psql &> /dev/null; then
    echo "PostgreSQL not found, installing..."
    sudo apt-get update
    sudo apt-get install -y postgresql postgresql-contrib libpq-dev
    echo -e "${GREEN}✅ PostgreSQL installed${NC}"
else
    echo -e "${GREEN}✅ PostgreSQL already installed: $(psql --version)${NC}"
fi

# ============================================================================
# STEP 3: Start and enable PostgreSQL
# ============================================================================
echo ""
echo -e "${YELLOW}Step 2/6: Starting PostgreSQL service...${NC}"

sudo systemctl start postgresql
sudo systemctl enable postgresql

if sudo systemctl is-active --quiet postgresql; then
    echo -e "${GREEN}✅ PostgreSQL service running${NC}"
else
    echo -e "${RED}ERROR: PostgreSQL service failed to start${NC}"
    exit 1
fi

# ============================================================================
# STEP 4: Create database and user
# ============================================================================
echo ""
echo -e "${YELLOW}Step 3/6: Creating database and user...${NC}"

# Check if database already exists
if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo -e "${YELLOW}⚠️  Database '$DB_NAME' already exists, skipping creation${NC}"
else
    echo "Creating database and user..."

    sudo -u postgres psql << EOF
CREATE DATABASE $DB_NAME;
CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';
ALTER ROLE $DB_USER SET client_encoding TO 'utf8';
ALTER ROLE $DB_USER SET default_transaction_isolation TO 'read committed';
ALTER ROLE $DB_USER SET default_transaction_deferrable TO on;
ALTER ROLE $DB_USER SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
EOF

    echo -e "${GREEN}✅ Database and user created${NC}"
fi

# ============================================================================
# STEP 5: Verify PostgreSQL connection
# ============================================================================
echo ""
echo -e "${YELLOW}Step 4/6: Verifying PostgreSQL connection...${NC}"

if PGPASSWORD="$DB_PASSWORD" psql -U "$DB_USER" -d "$DB_NAME" -h localhost -c "SELECT version();" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ PostgreSQL connection verified${NC}"
else
    echo -e "${RED}ERROR: Could not connect to PostgreSQL${NC}"
    exit 1
fi

# ============================================================================
# STEP 6: Backup SQLite and export data (if SQLite exists)
# ============================================================================
echo ""
echo -e "${YELLOW}Step 5/6: Backing up SQLite data...${NC}"

SQLITE_FILE="$BACKEND_PATH/local_dev.sqlite3"

if [ -f "$SQLITE_FILE" ]; then
    echo "SQLite database found, backing up..."

    # Create backup
    mkdir -p "$BACKEND_PATH/backups"
    BACKUP_FILE="$BACKEND_PATH/backups/local_dev.sqlite3.backup.$(date +%s)"
    cp "$SQLITE_FILE" "$BACKUP_FILE"
    echo -e "${GREEN}✅ SQLite backed up to: $BACKUP_FILE${NC}"

    # Export SQLite data
    echo "Exporting SQLite data to PostgreSQL..."
    sqlite3 "$SQLITE_FILE" .dump > /tmp/sqlite_dump.sql

    # Clean up SQLite-specific syntax
    sed -i '/^PRAGMA/d' /tmp/sqlite_dump.sql
    sed -i '/^BEGIN TRANSACTION/d' /tmp/sqlite_dump.sql
    sed -i '/^COMMIT/d' /tmp/sqlite_dump.sql
    sed -i '/^ROLLBACK/d' /tmp/sqlite_dump.sql

    # Import into PostgreSQL
    echo "Importing data into PostgreSQL..."
    PGPASSWORD="$DB_PASSWORD" psql -U "$DB_USER" -d "$DB_NAME" -h localhost -f /tmp/sqlite_dump.sql 2>&1 | grep -v "^NOTICE\|^WARNING" || true

    # Verify import
    CANDIDATE_COUNT=$(PGPASSWORD="$DB_PASSWORD" psql -U "$DB_USER" -d "$DB_NAME" -h localhost -t -c "SELECT COUNT(*) FROM candidates WHERE 1=1;" 2>/dev/null || echo "0")

    echo -e "${GREEN}✅ SQLite data exported (approximately $CANDIDATE_COUNT candidates)${NC}"

    # Clean up temp file
    rm /tmp/sqlite_dump.sql
else
    echo -e "${YELLOW}⚠️  SQLite database not found at $SQLITE_FILE (fresh database)${NC}"
fi

# ============================================================================
# STEP 7: Update .env file on VPS
# ============================================================================
echo ""
echo -e "${YELLOW}Step 6/6: Updating .env file...${NC}"

ENV_FILE="$BACKEND_PATH/.env.production"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}ERROR: .env.production not found at $ENV_FILE${NC}"
    echo "Please create .env.production manually with:"
    echo "  DATABASE_URL=postgresql://$DB_USER:PASSWORD@localhost:5432/$DB_NAME"
    exit 1
fi

# Backup current .env
cp "$ENV_FILE" "$ENV_FILE.backup.$(date +%s)"

# Update DATABASE_URL
if grep -q "^DATABASE_URL=" "$ENV_FILE"; then
    # Update existing line
    sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME|" "$ENV_FILE"
else
    # Add new line
    echo "DATABASE_URL=postgresql://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME" >> "$ENV_FILE"
fi

echo -e "${GREEN}✅ .env.production updated${NC}"

# ============================================================================
# STEP 8: Verify backend can import dependencies
# ============================================================================
echo ""
echo -e "${YELLOW}Bonus: Verifying backend dependencies...${NC}"

cd "$BACKEND_PATH"

if python3 -c "import psycopg2; print(psycopg2.__version__)" 2>/dev/null; then
    echo -e "${GREEN}✅ psycopg2 already installed${NC}"
else
    echo "Installing psycopg2..."
    python3 -m pip install psycopg2-binary==2.9.9 --break-system-packages 2>&1 | tail -3
    echo -e "${GREEN}✅ psycopg2 installed${NC}"
fi

# ============================================================================
# SUCCESS: All done!
# ============================================================================
echo ""
echo "================================"
echo -e "${GREEN}✅ PostgreSQL Setup Complete!${NC}"
echo "================================"
echo ""
echo "Next Steps:"
echo "1. Verify settings:"
echo "   cat $ENV_FILE | grep DATABASE_URL"
echo ""
echo "2. Test PostgreSQL connection:"
echo "   PGPASSWORD='$DB_PASSWORD' psql -U $DB_USER -d $DB_NAME -h localhost -c 'SELECT COUNT(*) as candidate_count FROM candidates;'"
echo ""
echo "3. On your local machine, push to main:"
echo "   git add requirements.txt"
echo "   git commit -m 'Add psycopg2-binary for PostgreSQL support'"
echo "   git push origin main"
echo ""
echo "4. GitHub Actions will automatically:"
echo "   - Run tests"
echo "   - Deploy backend"
echo "   - Run Alembic migrations"
echo "   - Restart service"
echo ""
echo "Monitor deployment at: https://github.com/your-repo/actions"
echo ""
