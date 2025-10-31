"""
Migration script to convert database from custom format to OpenAI-compatible format.

This script:
1. Creates the new 'files' table
2. Adds new columns to 'batch_jobs' table
3. Migrates existing data to new format
4. Preserves all existing batch jobs
"""

import os
import shutil
import sqlite3
from datetime import datetime

DATABASE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'database', 'batch_jobs.db')


def backup_database():
    """Create backup of database before migration."""
    if not os.path.exists(DATABASE_PATH):
        print("⚠️  No database found - will create new one")
        return

    backup_path = DATABASE_PATH + f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    shutil.copy2(DATABASE_PATH, backup_path)
    print(f"✅ Database backed up to: {backup_path}")


def migrate_database():
    """Migrate database to OpenAI-compatible format."""

    # Backup first
    backup_database()

    # Connect to database
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    print("\n🔄 Starting migration to OpenAI-compatible format...")

    # Step 1: Create files table
    print("\n1️⃣  Creating 'files' table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            file_id VARCHAR(64) PRIMARY KEY,
            object VARCHAR(32) NOT NULL DEFAULT 'file',
            bytes INTEGER NOT NULL,
            created_at INTEGER NOT NULL,
            filename VARCHAR(512) NOT NULL,
            purpose VARCHAR(32) NOT NULL,
            file_path VARCHAR(512) NOT NULL,
            deleted BOOLEAN DEFAULT 0
        )
    """)
    print("✅ Files table created")

    # Step 2: Check if batch_jobs needs migration
    cursor.execute("PRAGMA table_info(batch_jobs)")
    columns = {row[1] for row in cursor.fetchall()}

    if 'input_file_id' in columns:
        print("\n✅ Database already migrated!")
        conn.close()
        return

    # Step 3: Create new batch_jobs table with OpenAI format
    print("\n2️⃣  Creating new batch_jobs table...")
    cursor.execute("DROP TABLE IF EXISTS batch_jobs_new")
    cursor.execute("""
        CREATE TABLE batch_jobs_new (
            batch_id VARCHAR(64) PRIMARY KEY,
            object VARCHAR(32) NOT NULL DEFAULT 'batch',
            endpoint VARCHAR(128) NOT NULL DEFAULT '/v1/chat/completions',
            input_file_id VARCHAR(64) NOT NULL,
            completion_window VARCHAR(16) NOT NULL DEFAULT '24h',
            status VARCHAR(32) NOT NULL DEFAULT 'validating',
            output_file_id VARCHAR(64),
            error_file_id VARCHAR(64),
            created_at INTEGER NOT NULL,
            in_progress_at INTEGER,
            expires_at INTEGER NOT NULL,
            finalizing_at INTEGER,
            completed_at INTEGER,
            failed_at INTEGER,
            expired_at INTEGER,
            cancelling_at INTEGER,
            cancelled_at INTEGER,
            total_requests INTEGER DEFAULT 0,
            completed_requests INTEGER DEFAULT 0,
            failed_requests INTEGER DEFAULT 0,
            errors TEXT,
            metadata_json TEXT,
            model VARCHAR(256),
            log_file VARCHAR(512),
            throughput_tokens_per_sec FLOAT,
            total_tokens INTEGER,
            webhook_url VARCHAR(512),
            webhook_status VARCHAR(32),
            webhook_attempts INTEGER DEFAULT 0,
            webhook_last_attempt DATETIME,
            webhook_error TEXT,
            FOREIGN KEY (input_file_id) REFERENCES files(file_id),
            FOREIGN KEY (output_file_id) REFERENCES files(file_id),
            FOREIGN KEY (error_file_id) REFERENCES files(file_id)
        )
    """)
    print("✅ New batch_jobs table created")

    # Step 4: Migrate existing batch jobs
    print("\n3️⃣  Migrating existing batch jobs...")
    cursor.execute("SELECT * FROM batch_jobs")
    old_jobs = cursor.fetchall()

    if old_jobs:
        print(f"   Found {len(old_jobs)} existing batch jobs to migrate")

        # Get column names from old table
        cursor.execute("PRAGMA table_info(batch_jobs)")
        old_columns = [row[1] for row in cursor.fetchall()]

        migrated = 0
        for job in old_jobs:
            job_dict = dict(zip(old_columns, job))

            # Create file entry for input file
            input_file_id = f"file-{job_dict['batch_id'].replace('batch_', '')}"
            input_file_path = job_dict.get('input_file', '')

            if input_file_path and os.path.exists(input_file_path):
                file_size = os.path.getsize(input_file_path)
                file_created = int(job_dict.get('created_at', datetime.now()).timestamp()) if isinstance(job_dict.get('created_at'), datetime) else int(datetime.now().timestamp())

                cursor.execute("""
                    INSERT OR IGNORE INTO files (file_id, object, bytes, created_at, filename, purpose, file_path, deleted)
                    VALUES (?, 'file', ?, ?, ?, 'batch', ?, 0)
                """, (input_file_id, file_size, file_created, os.path.basename(input_file_path), input_file_path))

            # Create file entry for output file if exists
            output_file_id = None
            output_file_path = job_dict.get('output_file', '')
            if output_file_path and os.path.exists(output_file_path):
                output_file_id = f"file-out-{job_dict['batch_id'].replace('batch_', '')}"
                file_size = os.path.getsize(output_file_path)
                file_created = int(job_dict.get('completed_at', datetime.now()).timestamp()) if isinstance(job_dict.get('completed_at'), datetime) else int(datetime.now().timestamp())

                cursor.execute("""
                    INSERT OR IGNORE INTO files (file_id, object, bytes, created_at, filename, purpose, file_path, deleted)
                    VALUES (?, 'file', ?, ?, ?, 'batch', ?, 0)
                """, (output_file_id, file_size, file_created, os.path.basename(output_file_path), output_file_path))

            # Convert status
            old_status = job_dict.get('status', 'pending')
            status_map = {
                'pending': 'validating',
                'running': 'in_progress',
                'completed': 'completed',
                'failed': 'failed'
            }
            new_status = status_map.get(old_status, old_status)

            # Convert timestamps
            created_at = job_dict.get('created_at')
            if isinstance(created_at, datetime):
                created_at = int(created_at.timestamp())
            elif isinstance(created_at, str):
                # Parse ISO format string
                try:
                    created_at = int(datetime.fromisoformat(created_at.replace('Z', '+00:00')).timestamp())
                except:
                    created_at = int(datetime.now().timestamp())
            elif created_at is None:
                created_at = int(datetime.now().timestamp())
            else:
                created_at = int(created_at)  # Already an int

            started_at = job_dict.get('started_at')
            in_progress_at = None
            if isinstance(started_at, datetime):
                in_progress_at = int(started_at.timestamp())
            elif isinstance(started_at, str):
                try:
                    in_progress_at = int(datetime.fromisoformat(started_at.replace('Z', '+00:00')).timestamp())
                except:
                    pass

            completed_at_dt = job_dict.get('completed_at')
            completed_at = None
            if isinstance(completed_at_dt, datetime):
                completed_at = int(completed_at_dt.timestamp())
            elif isinstance(completed_at_dt, str):
                try:
                    completed_at = int(datetime.fromisoformat(completed_at_dt.replace('Z', '+00:00')).timestamp())
                except:
                    pass

            expires_at = int(created_at) + 86400  # 24 hours

            # Insert into new table
            cursor.execute("""
                INSERT INTO batch_jobs_new (
                    batch_id, object, endpoint, input_file_id, completion_window, status,
                    output_file_id, error_file_id, created_at, in_progress_at, expires_at,
                    finalizing_at, completed_at, failed_at, expired_at, cancelling_at, cancelled_at,
                    total_requests, completed_requests, failed_requests, errors, metadata_json,
                    model, log_file, throughput_tokens_per_sec, total_tokens,
                    webhook_url, webhook_status, webhook_attempts, webhook_last_attempt, webhook_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_dict['batch_id'],
                'batch',
                '/v1/chat/completions',
                input_file_id,
                '24h',
                new_status,
                output_file_id,
                None,  # error_file_id
                created_at,
                in_progress_at,
                expires_at,
                None,  # finalizing_at
                completed_at,
                None,  # failed_at
                None,  # expired_at
                None,  # cancelling_at
                None,  # cancelled_at
                job_dict.get('total_requests', 0),
                job_dict.get('completed_requests', 0),
                job_dict.get('failed_requests', 0),
                None,  # errors
                job_dict.get('metadata_json'),
                job_dict.get('model'),
                job_dict.get('log_file'),
                job_dict.get('throughput_tokens_per_sec'),
                job_dict.get('total_tokens'),
                job_dict.get('webhook_url'),
                job_dict.get('webhook_status'),
                job_dict.get('webhook_attempts', 0),
                job_dict.get('webhook_last_attempt'),
                job_dict.get('webhook_error')
            ))
            migrated += 1

        print(f"✅ Migrated {migrated} batch jobs")
    else:
        print("   No existing batch jobs to migrate")

    # Step 5: Replace old table with new table
    print("\n4️⃣  Replacing old table with new table...")
    cursor.execute("DROP TABLE batch_jobs")
    cursor.execute("ALTER TABLE batch_jobs_new RENAME TO batch_jobs")
    print("✅ Table replaced")

    # Commit changes
    conn.commit()
    conn.close()

    print("\n✅ Migration completed successfully!")
    print("\n📊 Summary:")
    print("   - Files table created")
    print("   - Batch jobs table updated to OpenAI format")
    print(f"   - {len(old_jobs) if old_jobs else 0} existing jobs migrated")
    print("   - Database backup created")


if __name__ == '__main__':
    print("=" * 60)
    print("DATABASE MIGRATION: Custom → OpenAI-Compatible Format")
    print("=" * 60)

    migrate_database()

    print("\n" + "=" * 60)
    print("✅ MIGRATION COMPLETE")
    print("=" * 60)

