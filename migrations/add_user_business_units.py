"""Migration to add user_business_units junction table for multi-BU assignment."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import sqlite3


def upgrade():
    """Create the user_business_units table."""
    db_path = os.path.join(os.path.dirname(__file__), '..', 'local_dev.sqlite3')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create the junction table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_business_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(50) NOT NULL,
            business_unit_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(UserID) ON DELETE CASCADE,
            FOREIGN KEY (business_unit_id) REFERENCES business_units(id) ON DELETE CASCADE,
            UNIQUE(user_id, business_unit_id)
        )
    ''')

    # Create index for faster lookups
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_user_bu_user_id
        ON user_business_units(user_id)
    ''')

    conn.commit()
    conn.close()

    print("✓ Created user_business_units table")


def downgrade():
    """Drop the user_business_units table."""
    db_path = os.path.join(os.path.dirname(__file__), '..', 'local_dev.sqlite3')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('DROP TABLE IF EXISTS user_business_units')
    conn.commit()
    conn.close()

    print("✓ Dropped user_business_units table")


if __name__ == "__main__":
    print("Running migration: add_user_business_units")
    upgrade()
    print("Migration complete!")
