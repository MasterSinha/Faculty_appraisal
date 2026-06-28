#!/bin/bash
# ==============================================================================
# Faculty Appraisal System — Local VM Automated Backup Script
# ==============================================================================
# This script performs automated backups of the database and uploaded files.
# It should be placed on the VM host at /opt/faculty_appraisal/backup_local.sh
# and scheduled with crontab (e.g. nightly at 3:00 AM).
# ==============================================================================

# Configurations
PROJECT_DIR="/opt/faculty_appraisal"
BACKUP_DIR="$PROJECT_DIR/backups"
UPLOADS_DIR="$PROJECT_DIR/uploads"
DB_CONTAINER="faculty_appraisal_db"
DB_USER="app_user"
DB_NAME="faculty_appraisal"
DATE=$(date +%Y-%m-%d_%H%M%S)

# Create backup directory if not exists
mkdir -p "$BACKUP_DIR"

echo "=== Starting Backup process: $DATE ==="

# 1. Backup PostgreSQL Database
echo "Exporting database from container '$DB_CONTAINER'..."
docker exec -t "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" -F p > "$BACKUP_DIR/db_$DATE.sql"

if [ $? -eq 0 ]; then
    gzip "$BACKUP_DIR/db_$DATE.sql"
    echo "Database backup successful: db_$DATE.sql.gz"
else
    echo "ERROR: Database backup failed!"
    exit 1
fi

# 2. Backup Uploaded Files
if [ -d "$UPLOADS_DIR" ]; then
    echo "Compressing uploads directory..."
    tar -czf "$BACKUP_DIR/uploads_$DATE.tar.gz" -C "$UPLOADS_DIR" .
    echo "Uploads backup successful: uploads_$DATE.tar.gz"
else
    echo "WARNING: Uploads directory '$UPLOADS_DIR' not found. Skipping uploads backup."
fi

# 3. Retention Cleanup (Keep backups for 14 days)
echo "Cleaning up backups older than 14 days..."
find "$BACKUP_DIR" -type f -name "db_*.sql.gz" -mtime +14 -delete
find "$BACKUP_DIR" -type f -name "uploads_*.tar.gz" -mtime +14 -delete

echo "=== Backup completed successfully ==="
