# Backup and Restore Guide: Database & Uploaded Files

This guide details how to perform backups and restores for the **Faculty Appraisal System** database and uploaded proof documents (e.g. PDFs). 

There are two supported methods depending on your access level and the size of the data:
1. **Super Admin API (Web UI / Swagger)** — Best for database backups and small uploads folders (<100MB).
2. **CLI / SSH Commands (Command Line)** — Required for large upload folders (e.g. 6GB of files) and automated cron jobs.

---

## Architecture & Configuration

* **DB Connection:** Configured via `DATABASE_URL` (uses asyncpg natively, but parsed for standard TCP tools).
* **Uploaded Files:** Stored in `./uploads` inside the container, which should be bind-mounted in `compose.yaml` to the host VM:
  ```yaml
  volumes:
    - /opt/faculty_appraisal/uploads:/app/uploads
  ```

---

## Method 1: Super Admin API Endpoints

These endpoints are strictly gated and only accessible by users authenticated with the `super_admin` role. 

> [!WARNING]
> Web-based file uploads/downloads are subject to Nginx configuration (`client_max_body_size`), FastAPI timeouts, and container RAM. Do not use the uploads endpoints for folder sizes exceeding **500MB**. Use CLI commands (Method 2) instead.

### 1. Database Backup & Restore

#### Export (Backup) DB
* **Endpoint:** `GET /api/v1/admin/backup/db`
* **Description:** Runs `pg_dump` internally and streams back a raw `.sql` file.
* **How to use:**
  1. Go to Swagger UI (`/docs`) and authorize as a `super_admin`.
  2. Execute the `GET /api/v1/admin/backup/db` endpoint.
  3. Click **Download file** to save the SQL dump locally.

#### Import (Restore) DB
* **Endpoint:** `POST /api/v1/admin/restore/db`
* **Description:** Restores the schema and database entries from an uploaded SQL script.
* **How to use:**
  1. Execute `POST /api/v1/admin/restore/db` in Swagger UI.
  2. Select the SQL dump file.
  3. Submit. The API returns `{"message": "Database restored successfully"}`.

---

### 2. Uploads Zip Backup & Restore

#### Export Uploads
* **Endpoint:** `GET /api/v1/admin/backup/uploads`
* **Description:** Creates a zipped archive of the uploads directory and streams it.
* **How to use:** Execute the endpoint and download the `.zip` file.

#### Import Uploads
* **Endpoint:** `POST /api/v1/admin/restore/uploads`
* **Description:** Accepts a `.zip` file and extracts it directly into the uploads directory, overwriting/merging files.
* **How to use:** Upload your `.zip` archive via the endpoint.

---

## Method 2: CLI / SSH (Command Line)

This is the most secure and robust approach for migrating large directories (like 6GB of PDF proofs) and setting up automated cron jobs.

### 1. Transferring the 6GB Uploads Folder

Because of the folder size, you should compress the directory and transfer it directly to/from the host VM using **SCP (Secure Copy)** or **SFTP**.

#### Step 1: Compress the Uploads Folder
On the source machine (your laptop or old server):
```bash
# Compress the folder into a tarball
tar -czf uploads.tar.gz -C /path/to/local/uploads .
```

#### Step 2: Transfer to the target VM Host
```bash
# Replace 'user' and 'vm-ip' with target VM details
scp uploads.tar.gz user@vm-ip-address:/opt/faculty_appraisal/
```

#### Step 3: Extract on the target VM Host
SSH into the target VM and extract the files directly into the bind-mounted directory:
```bash
ssh user@vm-ip-address

# Ensure target folder exists
mkdir -p /opt/faculty_appraisal/uploads

# Extract files
tar -xzf /opt/faculty_appraisal/uploads.tar.gz -C /opt/faculty_appraisal/uploads/

# (Optional) Set correct permissions so the container can read/write files
sudo chown -R 1000:1000 /opt/faculty_appraisal/uploads
```

---

### 2. Database Backup & Restore via CLI

If you run PostgreSQL on the host VM or inside a separate Docker container, you can run native postgres commands.

#### Step 1: Export (Dump) Database
Run `pg_dump` directly from the host (assuming connection variables match your config):
```bash
# If Postgres is running directly on the host or external host:
PGPASSWORD="your_db_password" pg_dump -h localhost -p 5432 -U postgres -d faculty_appraisal_db -F p -f db_backup.sql

# If Postgres is running inside a Docker container:
docker exec -t postgres_container_name pg_dump -U postgres -d faculty_appraisal_db -F p > db_backup.sql
```

#### Step 2: Transfer SQL file via SCP
```bash
scp db_backup.sql user@vm-ip-address:/opt/faculty_appraisal/
```

#### Step 3: Import (Restore) Database
```bash
# Restore on the target host Postgres:
PGPASSWORD="target_db_password" psql -h localhost -p 5432 -U postgres -d faculty_appraisal_db -f /opt/faculty_appraisal/db_backup.sql

# Restore inside a target Postgres Docker container:
cat db_backup.sql | docker exec -i target_postgres_container psql -U postgres -d faculty_appraisal_db
```

---

## Automating Backups (Cron Job Script)

You can place this shell script on the VM host at `/opt/faculty_appraisal/backup.sh` to run automated backups.

```bash
#!/bin/bash
# Backup Configuration
BACKUP_DIR="/opt/faculty_appraisal/backups"
UPLOADS_DIR="/opt/faculty_appraisal/uploads"
DATE=$(date +%Y-%m-%d_%H%M%S)

# DB Credentials (adjust to match your .env values)
DB_USER="postgres"
DB_NAME="faculty_appraisal_db"
DB_HOST="localhost"
DB_PORT="5432"
export PGPASSWORD="your_db_password"

# Create directories if they don't exist
mkdir -p "$BACKUP_DIR"

echo "Starting backup for $DATE..."

# 1. Backup DB
pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F p -f "$BACKUP_DIR/db_$DATE.sql"
gzip "$BACKUP_DIR/db_$DATE.sql"
echo "Database backed up: db_$DATE.sql.gz"

# 2. Backup Uploads
tar -czf "$BACKUP_DIR/uploads_$DATE.tar.gz" -C "$UPLOADS_DIR" .
echo "Uploads backed up: uploads_$DATE.tar.gz"

# 3. Clean up backups older than 14 days
find "$BACKUP_DIR" -type f -mtime +14 -name "*.tar.gz" -delete
find "$BACKUP_DIR" -type f -mtime +14 -name "*.sql.gz" -delete

echo "Backup process finished."
```

Make the script executable:
```bash
chmod +x /opt/faculty_appraisal/backup.sh
```

To run this backup every night at 3:00 AM, add the following line to the host's `/etc/crontab`:
```cron
0 3 * * * root /bin/bash /opt/faculty_appraisal/backup.sh >/dev/null 2>&1
```
