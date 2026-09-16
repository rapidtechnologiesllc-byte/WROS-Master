"""PostgreSQL Backup & Recovery Automation

Phase 5: Backup & Recovery
Automated daily backups with retention policy and restore procedures.

Schedule via cron:
0 2 * * * python /app/backend/scripts/postgres_backup_automation.py backup daily
0 3 * * 0 python /app/backend/scripts/postgres_backup_automation.py backup weekly
"""
import os
import sys
import subprocess
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class PostgresBackupManager:
    """PostgreSQL backup and recovery automation."""

    def __init__(self):
        self.db_host = os.getenv("DATABASE_URL", "localhost")
        self.db_user = os.getenv("DB_USER", "postgres")
        self.db_password = os.getenv("DB_PASSWORD", "")
        self.db_name = os.getenv("DB_NAME", "blitzenx")
        self.backup_dir = os.getenv("BACKUP_DIR", "/var/backups/postgres")
        self.retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))

        # Create backup directory
        Path(self.backup_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"[Backup] Backup directory: {self.backup_dir}")

    def _get_backup_filename(self, backup_type: str) -> str:
        """Generate backup filename with timestamp."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"{self.db_name}_{backup_type}_{timestamp}.sql.gz"

    def backup(self, backup_type: str = "daily") -> bool:
        """
        Create compressed database backup.

        Args:
            backup_type: "daily", "weekly", or "manual"

        Returns:
            True if successful, False otherwise
        """
        backup_file = os.path.join(self.backup_dir, self._get_backup_filename(backup_type))

        try:
            logger.info(f"[Backup] Starting {backup_type} backup to {backup_file}")

            # Prepare pg_dump command
            env = os.environ.copy()
            if self.db_password:
                env["PGPASSWORD"] = self.db_password

            cmd = [
                "pg_dump",
                f"--host={self.db_host}",
                f"--username={self.db_user}",
                f"--dbname={self.db_name}",
                "--verbose",
                "--format=plain"
            ]

            # Compress with gzip
            with open(backup_file, 'wb') as backup_f:
                process = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    text=True,
                    timeout=3600  # 1 hour timeout
                )

                if process.returncode != 0:
                    logger.error(f"[Backup] pg_dump failed: {process.stderr}")
                    return False

                # Pipe through gzip
                gzip_process = subprocess.run(
                    ["gzip", "--stdout"],
                    input=process.stdout.encode('utf-8'),
                    stdout=backup_f,
                    stderr=subprocess.PIPE
                )

                if gzip_process.returncode != 0:
                    logger.error(f"[Backup] gzip failed: {gzip_process.stderr}")
                    return False

            file_size = os.path.getsize(backup_file) / (1024 * 1024)  # MB
            logger.info(f"[Backup] ✅ Backup successful: {backup_file} ({file_size:.2f} MB)")
            return True

        except subprocess.TimeoutExpired:
            logger.error(f"[Backup] Backup timeout (exceeded 1 hour)")
            return False
        except Exception as e:
            logger.error(f"[Backup] Backup failed: {e}", exc_info=True)
            return False

    def restore(self, backup_file: str) -> bool:
        """
        Restore database from backup.

        Args:
            backup_file: Path to backup file (must be gzipped)

        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(backup_file):
                logger.error(f"[Restore] Backup file not found: {backup_file}")
                return False

            logger.warning(f"[Restore] ⚠️  DESTRUCTIVE: Restoring database from {backup_file}")
            logger.warning(f"[Restore] This will overwrite the current database!")
            confirmation = input("[Restore] Type 'YES' to confirm restore: ")

            if confirmation != "YES":
                logger.info("[Restore] Restore cancelled by user")
                return False

            logger.info(f"[Restore] Starting restore from {backup_file}")

            env = os.environ.copy()
            if self.db_password:
                env["PGPASSWORD"] = self.db_password

            # Drop all connections to database
            drop_cmd = f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{self.db_name}'
            AND pid <> pg_backend_pid();
            """

            psql = subprocess.run(
                ["psql", f"--host={self.db_host}", f"--username={self.db_user}", "-d", "postgres"],
                input=drop_cmd,
                env=env,
                capture_output=True,
                text=True
            )

            if psql.returncode != 0:
                logger.warning(f"[Restore] Failed to drop connections: {psql.stderr}")

            # Drop and recreate database
            recreate_cmd = f"DROP DATABASE IF EXISTS {self.db_name}; CREATE DATABASE {self.db_name};"

            psql = subprocess.run(
                ["psql", f"--host={self.db_host}", f"--username={self.db_user}", "-d", "postgres"],
                input=recreate_cmd,
                env=env,
                capture_output=True,
                text=True
            )

            if psql.returncode != 0:
                logger.error(f"[Restore] Failed to recreate database: {psql.stderr}")
                return False

            # Restore from backup
            with open(backup_file, 'rb') as f:
                restore_process = subprocess.run(
                    ["gunzip", "--stdout"],
                    stdin=f,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                if restore_process.returncode != 0:
                    logger.error(f"[Restore] gunzip failed: {restore_process.stderr}")
                    return False

                psql = subprocess.run(
                    ["psql", f"--host={self.db_host}", f"--username={self.db_user}", f"--dbname={self.db_name}"],
                    input=restore_process.stdout,
                    env=env,
                    capture_output=True,
                    text=True
                )

                if psql.returncode != 0:
                    logger.error(f"[Restore] Restore failed: {psql.stderr}")
                    return False

            logger.info(f"[Restore] ✅ Restore successful from {backup_file}")
            return True

        except Exception as e:
            logger.error(f"[Restore] Restore failed: {e}", exc_info=True)
            return False

    def cleanup_old_backups(self) -> int:
        """
        Delete backups older than retention period.

        Returns:
            Number of backups deleted
        """
        try:
            deleted_count = 0
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)

            for backup_file in Path(self.backup_dir).glob("*.sql.gz"):
                file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)

                if file_mtime < cutoff_date:
                    backup_file.unlink()
                    deleted_count += 1
                    logger.info(f"[Cleanup] Deleted old backup: {backup_file.name}")

            logger.info(f"[Cleanup] ✅ Removed {deleted_count} old backups (retention: {self.retention_days} days)")
            return deleted_count

        except Exception as e:
            logger.error(f"[Cleanup] Failed to cleanup old backups: {e}", exc_info=True)
            return 0

    def list_backups(self) -> list:
        """List all available backups."""
        try:
            backups = sorted(Path(self.backup_dir).glob("*.sql.gz"), reverse=True)
            logger.info(f"[List] Available backups ({len(backups)} total):")

            for backup in backups:
                size_mb = backup.stat().st_size / (1024 * 1024)
                mtime = datetime.fromtimestamp(backup.stat().st_mtime)
                logger.info(f"  {backup.name} ({size_mb:.2f} MB) - {mtime.isoformat()}")

            return [str(b) for b in backups]
        except Exception as e:
            logger.error(f"[List] Failed to list backups: {e}")
            return []


def main():
    """Main entry point for backup automation."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python postgres_backup_automation.py backup [daily|weekly|manual]")
        print("  python postgres_backup_automation.py restore <backup_file>")
        print("  python postgres_backup_automation.py cleanup")
        print("  python postgres_backup_automation.py list")
        sys.exit(1)

    manager = PostgresBackupManager()
    command = sys.argv[1]

    if command == "backup":
        backup_type = sys.argv[2] if len(sys.argv) > 2 else "manual"
        success = manager.backup(backup_type)
        manager.cleanup_old_backups()
        sys.exit(0 if success else 1)

    elif command == "restore":
        if len(sys.argv) < 3:
            print("Usage: python postgres_backup_automation.py restore <backup_file>")
            sys.exit(1)
        success = manager.restore(sys.argv[2])
        sys.exit(0 if success else 1)

    elif command == "cleanup":
        manager.cleanup_old_backups()
        sys.exit(0)

    elif command == "list":
        manager.list_backups()
        sys.exit(0)

    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
