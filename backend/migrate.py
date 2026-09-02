"""
Database Migration Utility
===========================
import logging
Easy-to-use script for managing Alembic database migrations.

Usage:
    python migrate.py              # Show status and run migrations
    python migrate.py --status     # Show current migration status
    python migrate.py --history    # Show migration history
    python migrate.py --upgrade    # Upgrade to latest version
    python migrate.py --downgrade  # Downgrade one version
    python migrate.py --create "description"  # Create new migration
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
CYAN = '\033[96m'
RESET = '\033[0m'
BOLD = '\033[1m'


def print_header(text):
    """Print section header"""
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}{text:^70}{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")


def print_success(text):
    """Print success message"""
    print(f"{GREEN}[SUCCESS] {text}{RESET}")


def print_error(text):
    """Print error message"""
    print(f"{RED}[ERROR] {text}{RESET}")


def print_warning(text):
    """Print warning message"""
    print(f"{YELLOW}[WARNING] {text}{RESET}")


def print_info(text):
    """Print info message"""
    print(f"{CYAN}[INFO] {text}{RESET}")


def run_alembic_command(command, description=None):
    """Run an Alembic command and return the result"""
    import subprocess
    
    if description:
        print_info(description)
    
    try:
        result = subprocess.run(
            f"python -m alembic {command}",
            shell=True,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr
    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error: {str(e)}", exc_info=True)
        return False, str(e)


def check_database_connection():
    """Check if database is accessible"""
    print_info("Checking database connection...")
    
    try:
        from app.core.database import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT @@VERSION"))
            version = result.fetchone()[0]
            
            # Extract SQL Server version
            if "SQL Server" in version:
                version_line = version.split('\n')[0]
                print_success(f"Database connected: {version_line}")
                return True
            else:
                print_success("Database connected successfully")
                return True
                
    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error: {str(e)}", exc_info=True)
        print_error(f"Database connection failed: {str(e)}")
        print_warning("Migrations may not work without database access")
        return False


def show_current_status():
    """Show current migration status"""
    print_header("Current Migration Status")
    
    success, output = run_alembic_command("current", "Fetching current migration...")
    
    if success:
        if output.strip():
            # Parse the output
            lines = output.strip().split('\n')
            for line in lines:
                if line.strip() and not line.startswith('C:'):  # Skip warning lines
                    if '(head)' in line:
                        print_success(f"Current: {line.strip()}")
                    else:
                        print_info(line.strip())
        else:
            print_warning("No migrations have been applied yet")
    else:
        print_error(f"Failed to get current status:\n{output}")
    
    return success


def show_migration_history():
    """Show migration history"""
    print_header("Migration History")
    
    success, output = run_alembic_command("history --verbose", "Fetching migration history...")
    
    if success:
        if output.strip():
            # Parse and format the output
            lines = output.strip().split('\n')
            current_migration = None
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('C:'):  # Skip empty lines and warnings
                    continue
                    
                if line.startswith('Rev:'):
                    if current_migration:
                        print()  # Blank line between migrations
                    print(f"{BOLD}{CYAN}{line}{RESET}")
                    current_migration = line
                elif line.startswith('Parent:'):
                    print(f"{YELLOW}{line}{RESET}")
                elif line.startswith('Path:'):
                    print(f"{BLUE}{line}{RESET}")
                elif line.startswith('Revision ID:') or line.startswith('Revises:') or line.startswith('Create Date:'):
                    print(f"  {line}")
                else:
                    print(f"  {GREEN}{line}{RESET}")
        else:
            print_warning("No migration history found")
    else:
        print_error(f"Failed to get history:\n{output}")
    
    return success


def upgrade_database():
    """Upgrade database to latest version"""
    print_header("Upgrading Database")
    
    # First check current status
    success, current = run_alembic_command("current")
    if success and '(head)' in current:
        print_success("Database is already at the latest version")
        return True
    
    # Run upgrade
    success, output = run_alembic_command("upgrade head", "Running database upgrade...")
    
    if success:
        print_success("Database upgraded successfully")
        print_info("Output:")
        for line in output.strip().split('\n'):
            if line.strip() and not line.startswith('C:'):
                print(f"  {line}")
        return True
    else:
        # Check if it's because table already exists
        if "already an object named" in output or "already exists" in output:
            print_warning("Some tables already exist - marking migration as complete")
            success, _ = run_alembic_command("stamp head", "Marking current state...")
            if success:
                print_success("Migration marked as complete")
                return True
        
        print_error(f"Upgrade failed:\n{output}")
        return False


def downgrade_database():
    """Downgrade database by one version"""
    print_header("Downgrading Database")
    
    print_warning("This will downgrade the database by one migration")
    confirm = input(f"{YELLOW}Are you sure? (yes/no): {RESET}").strip().lower()
    
    if confirm != 'yes':
        print_info("Downgrade cancelled")
        return False
    
    success, output = run_alembic_command("downgrade -1", "Running database downgrade...")
    
    if success:
        print_success("Database downgraded successfully")
        return True
    else:
        print_error(f"Downgrade failed:\n{output}")
        return False


def create_migration(description):
    """Create a new migration"""
    print_header("Creating New Migration")
    
    if not description:
        print_error("Migration description is required")
        print_info("Usage: python migrate.py --create \"description\"")
        return False
    
    # Auto-generate migration from model changes
    success, output = run_alembic_command(
        f'revision --autogenerate -m "{description}"',
        f"Creating migration: {description}"
    )
    
    if success:
        print_success("Migration created successfully")
        print_info("Output:")
        for line in output.strip().split('\n'):
            if line.strip():
                print(f"  {line}")
        return True
    else:
        print_error(f"Failed to create migration:\n{output}")
        return False


def show_database_info():
    """Show database configuration information"""
    print_header("Database Configuration")
    
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # Parse and display (hide password)
        if '@' in database_url:
            parts = database_url.split('@')
            if ':' in parts[0]:
                user_part = parts[0].split(':')[0].replace('mssql+pyodbc://', '')
                server_part = parts[1].split('/')[0] if '/' in parts[1] else parts[1]
                db_part = parts[1].split('/')[1].split('?')[0] if '/' in parts[1] else 'unknown'
                
                print_info(f"Database: {db_part}")
                print_info(f"Server: {server_part}")
                print_info(f"User: {user_part}")
                print_info(f"Password: {'*' * 10}")
            else:
                print_info(f"Connection: {database_url[:50]}...")
        else:
            print_info(f"Connection: {database_url[:50]}...")
    else:
        print_error("DATABASE_URL not set in environment")
    
    # Check alembic.ini
    alembic_ini = Path(__file__).parent / "alembic.ini"
    if alembic_ini.exists():
        print_success(f"Alembic config: {alembic_ini}")
    else:
        print_error("alembic.ini not found")
    
    # Check versions directory
    versions_dir = Path(__file__).parent / "alembic" / "versions"
    if versions_dir.exists():
        migrations = list(versions_dir.glob("*.py"))
        migrations = [m for m in migrations if m.name != "__pycache__"]
        print_success(f"Migrations found: {len(migrations)}")
    else:
        print_warning("No migrations directory found")


def run_interactive_mode():
    """Run interactive migration management"""
    print_header("Database Migration Manager")
    
    # Show database info
    show_database_info()
    
    # Check connection
    db_connected = check_database_connection()
    
    if not db_connected:
        print_warning("\nContinuing without database connection...")
        print_info("Some operations may not work correctly\n")
    
    # Show current status
    show_current_status()
    
    # Ask what to do
    print(f"\n{BOLD}What would you like to do?{RESET}")
    print(f"  {CYAN}1.{RESET} Upgrade to latest version")
    print(f"  {CYAN}2.{RESET} Show migration history")
    print(f"  {CYAN}3.{RESET} Create new migration")
    print(f"  {CYAN}4.{RESET} Downgrade one version")
    print(f"  {CYAN}5.{RESET} Exit")
    
    choice = input(f"\n{YELLOW}Enter choice (1-5): {RESET}").strip()
    
    if choice == '1':
        upgrade_database()
    elif choice == '2':
        show_migration_history()
    elif choice == '3':
        description = input(f"{YELLOW}Enter migration description: {RESET}").strip()
        create_migration(description)
    elif choice == '4':
        downgrade_database()
    elif choice == '5':
        print_info("Exiting...")
    else:
        print_error("Invalid choice")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Database Migration Utility',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python migrate.py                    # Interactive mode
  python migrate.py --status           # Show current status
  python migrate.py --history          # Show migration history
  python migrate.py --upgrade          # Upgrade to latest
  python migrate.py --create "add users table"  # Create migration
        """
    )
    
    parser.add_argument('--status', action='store_true', help='Show current migration status')
    parser.add_argument('--history', action='store_true', help='Show migration history')
    parser.add_argument('--upgrade', action='store_true', help='Upgrade to latest version')
    parser.add_argument('--downgrade', action='store_true', help='Downgrade one version')
    parser.add_argument('--create', type=str, metavar='DESCRIPTION', help='Create new migration')
    parser.add_argument('--info', action='store_true', help='Show database configuration')
    
    args = parser.parse_args()
    
    # If no arguments, run interactive mode
    if len(sys.argv) == 1:
        run_interactive_mode()
        return
    
    # Handle specific commands
    if args.info:
        show_database_info()
    
    if args.status:
        show_current_status()
    
    if args.history:
        show_migration_history()
    
    if args.upgrade:
        upgrade_database()
    
    if args.downgrade:
        downgrade_database()
    
    if args.create:
        create_migration(args.create)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Operation cancelled by user{RESET}")
        sys.exit(0)
    except Exception as e:
       logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Error: {str(e)}", exc_info=True)
        print_error(f"Unexpected error: {str(e)}")
        sys.exit(1)
