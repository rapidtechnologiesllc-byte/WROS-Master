"""
Database migration utility that handles both Alembic migrations and direct SQL migrations.
This module is imported by main.py to automatically apply migrations on startup.
"""
import os
import sys
import pyodbc
from urllib.parse import unquote
from alembic import command
from alembic.config import Config
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def parse_database_url(database_url):
    """Parse the DATABASE_URL to extract connection parameters."""
    # Remove the mssql+pyodbc:// prefix
    url = database_url.replace('mssql+pyodbc://', '')
    
    # Split credentials and rest
    credentials, rest = url.split('@')
    username, password = credentials.split(':')
    
    # Split host/database and parameters
    host_db, params = rest.split('?')
    host, database = host_db.split('/')
    
    # Parse parameters
    param_dict = {}
    for param in params.split('&'):
        if '=' in param:
            key, value = param.split('=', 1)
            param_dict[key] = unquote(value.replace('+', ' '))
    
    return {
        'username': unquote(username),
        'password': unquote(password),
        'host': host,
        'database': database,
        'driver': param_dict.get('driver', 'ODBC Driver 18 for SQL Server'),
        'trust_cert': param_dict.get('TrustServerCertificate', 'yes')
    }


def get_connection():
    """Create a database connection."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment variables")
    
    conn_params = parse_database_url(database_url)
    
    connection_string = (
        f"DRIVER={{{conn_params['driver']}}};"
        f"SERVER={conn_params['host']};"
        f"DATABASE={conn_params['database']};"
        f"UID={conn_params['username']};"
        f"PWD={conn_params['password']};"
        f"TrustServerCertificate={conn_params['trust_cert']};"
    )
    
    return pyodbc.connect(connection_string)


def column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table."""
    cursor.execute("""
        SELECT COUNT(*) 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
    """, table_name, column_name)
    
    return cursor.fetchone()[0] > 0


def table_exists(cursor, table_name):
    """Check if a table exists in the database."""
    cursor.execute("""
        SELECT COUNT(*) 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_NAME = ?
    """, table_name)
    
    return cursor.fetchone()[0] > 0


def ensure_schema_updated():
    """
    Ensure the database schema matches the current models.
    This is a safety check that runs before Alembic migrations.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        migrations_applied = []
        
        # Check and update Jobs table
        if table_exists(cursor, 'jobs'):
            jobs_columns = [
                ("companyType", "VARCHAR(50) NOT NULL DEFAULT 'Internal'"),
                ("companyName", "VARCHAR(50) NOT NULL DEFAULT ''"),
                ("contactPerson", "VARCHAR(100) NULL"),
                ("jobStatus", "VARCHAR(50) NOT NULL DEFAULT 'Draft'"),
                ("noOfPositions", "INT NOT NULL DEFAULT 1"),
                ("startDate", "DATE NULL"),
                ("endDate", "DATE NULL"),
                ("hiringManagerID", "VARCHAR(50) NULL"),
            ]
            
            for column_name, column_definition in jobs_columns:
                if not column_exists(cursor, 'jobs', column_name):
                    try:
                        sql = f"ALTER TABLE jobs ADD {column_name} {column_definition}"
                        cursor.execute(sql)
                        conn.commit()
                        migrations_applied.append(f"Added column 'jobs.{column_name}'")
                    except Exception as e:
                        print(f"Warning: Could not add column 'jobs.{column_name}': {e}")
                        conn.rollback()
            
            # Add foreign key constraint if hiringManagerID exists and constraint doesn't
            if column_exists(cursor, 'jobs', 'hiringManagerID'):
                try:
                    # Check if constraint exists
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS 
                        WHERE CONSTRAINT_NAME = 'FK_jobs_hiringManagerID'
                    """)
                    
                    if cursor.fetchone()[0] == 0:
                        cursor.execute("""
                            ALTER TABLE jobs 
                            ADD CONSTRAINT FK_jobs_hiringManagerID 
                            FOREIGN KEY (hiringManagerID) REFERENCES users(UserID)
                        """)
                        conn.commit()
                        migrations_applied.append("Added foreign key constraint 'FK_jobs_hiringManagerID'")
                except Exception as e:
                    # Constraint might already exist or there might be data issues
                    conn.rollback()
        
        cursor.close()
        conn.close()
        
        if migrations_applied:
            print("[Migration] Applied schema updates:")
            for migration in migrations_applied:
                print(f"  - {migration}")
        
        return True
        
    except Exception as e:
        print(f"Warning: Could not verify/update schema: {e}")
        return False


def run_migrations():
    """
    Run database migrations to upgrade the database to the latest version.
    This function is called automatically when the application starts.
    """
    # First, ensure basic schema is up to date
    print("Checking database schema...")
    ensure_schema_updated()
    
    # Then try to run Alembic migrations if configured
    try:
        # Get the directory where this script is located
        base_dir = Path(__file__).parent
        
        # Path to alembic.ini
        alembic_ini_path = base_dir / "alembic.ini"
        
        if not alembic_ini_path.exists():
            print("Note: alembic.ini not found - skipping Alembic migrations")
            print("Database schema check completed.")
            return
        
        # Check if versions directory exists
        versions_dir = base_dir / "alembic" / "versions"
        if not versions_dir.exists():
            print("Note: No migration versions found - creating versions directory")
            versions_dir.mkdir(parents=True, exist_ok=True)
        
        # Create Alembic configuration
        alembic_cfg = Config(str(alembic_ini_path))
        
        # Set the script location (alembic directory)
        alembic_cfg.set_main_option("script_location", str(base_dir / "alembic"))
        
        print("Running Alembic migrations...")
        
        # Run the upgrade command to apply all pending migrations
        command.upgrade(alembic_cfg, "head")
        
        print("[OK] Database migrations completed successfully")
        
    except Exception as e:
        error_msg = str(e)
        
        # Check if it's a known error
        if "is dependent on column" in error_msg or "FK__candidate" in error_msg:
            print("\n" + "="*60)
            print("[!] Migration Error: Foreign Key Constraint Conflict")
            print("="*60)
            print("\nYour database has existing tables with old schema.")
            print("\nOptions to fix:")
            print("1. Reset database (DEVELOPMENT ONLY):")
            print("   python reset_database.py")
            print("\n2. Mark current schema as baseline:")
            print("   alembic stamp head")
            print("\n3. Manually update your database schema")
            print("="*60)
        elif "Can't locate revision identified by" in error_msg:
            print("\n[!] No migrations to apply - database is up to date")
        else:
            print(f"[!] Error running Alembic migrations: {e}")
        
        print("\nThe application will continue with current schema.")
        # Don't exit - let the application start even if migrations fail


if __name__ == "__main__":
    # Allow running this script directly for testing
    run_migrations()
