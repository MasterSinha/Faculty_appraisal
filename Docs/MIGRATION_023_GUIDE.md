# Database Migration Guide: MFA Support (023_add_mfa_support.sql)

This guide documents how to apply the SQL migration for Multi-Factor Authentication (MFA) table creation on the local VM.

---

## 1. The Migration File (SQL)
The migration SQL file is located at `migrations/023_add_mfa_support.sql`. It creates the `mfa_otps` table and corresponding indexes:

```sql
CREATE TABLE IF NOT EXISTS mfa_otps (
    id UUID PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    mfa_token VARCHAR(255) NOT NULL UNIQUE,
    otp_code VARCHAR(10) NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_mfa_otps_token ON mfa_otps(mfa_token);
CREATE INDEX IF NOT EXISTS idx_mfa_otps_email ON mfa_otps(email);
```

---

## 2. Instructions to Apply on the Local VM

### Option A: Python One-Liner (Recommended)
Run this command from the `Faculty_appraisal` root directory. It automatically loads your connection parameters from the local `.env` file and executes the SQL:

```bash
python -c "
import asyncio, os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
async def run():
    url = None
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if line.strip().startswith('DATABASE_URL='):
                    url = line.split('=', 1)[1].strip().strip('\"').strip(\"'\")
    if not url:
        url = os.getenv('DATABASE_URL')
    if not url:
        print('Error: DATABASE_URL not found in .env or environment.')
        return
    url = url.replace('postgresql://', 'postgresql+asyncpg://').replace('postgres://', 'postgresql+asyncpg://')
    engine = create_async_engine(url)
    with open('migrations/023_add_mfa_support.sql') as f:
        sql = f.read()
    async with engine.begin() as conn:
        for stmt in sql.split(';'):
            if stmt.strip():
                await conn.execute(text(stmt))
    print('MFA migration completed successfully!')
asyncio.run(run())
"
```

### Option B: Executing inside Docker (If PostgreSQL is in Docker)
If your database is running in a Docker container (e.g., `faculty_appraisal_postgres`):
1. Copy the SQL script into the container:
   ```bash
   sudo docker cp migrations/023_add_mfa_support.sql faculty_appraisal_postgres:/tmp/023_add_mfa_support.sql
   ```
2. Execute the file using `psql` inside the container:
   ```bash
   sudo docker exec -it faculty_appraisal_postgres psql -U app_user -d faculty_appraisal -f /tmp/023_add_mfa_support.sql
   ```

### Option C: Manual `psql` execution on VM Host
If PostgreSQL is running directly on the VM host:
```bash
PGPASSWORD="your_db_password" psql -h localhost -U app_user -d faculty_appraisal -f migrations/023_add_mfa_support.sql
```

---

## 3. Post-Migration Container Rebuild
Rebuild and run the backend container on the VM host to apply the python changes:
```bash
# Rebuild the backend container image
sudo docker build -t faculty_appraisal_backend .

# Recreate the container
sudo docker stop faculty_appraisal_backend || true
sudo docker rm faculty_appraisal_backend || true

sudo docker run -d \
  --name faculty_appraisal_backend \
  --add-host=host.docker.internal:host-gateway \
  -v /home/dypiu/uploads:/app/uploads \
  --env-file /home/dypiu/Faculty_appraisal/.env \
  -p 8000:8080 \
  faculty_appraisal_backend
```
