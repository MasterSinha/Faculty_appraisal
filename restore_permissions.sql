-- 1. Ensure both roles exist
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_user') THEN
    CREATE ROLE app_user WITH LOGIN PASSWORD 'dypiu#2020$';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'fac_user') THEN
    CREATE ROLE fac_user WITH LOGIN PASSWORD 'dypiu#2020$';
  END IF;
END
$$;

-- 2. Grant full schema privileges to both users
GRANT USAGE, CREATE ON SCHEMA public TO app_user, fac_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO app_user, fac_user;

-- 3. Grant ALL PRIVILEGES (including CRUD and REFERENCES) on existing tables and sequences to both users
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_user, fac_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_user, fac_user;

-- 4. Set up mutual default privileges
-- When app_user creates new tables/sequences, fac_user automatically gets all privileges on them
ALTER DEFAULT PRIVILEGES FOR ROLE app_user IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO fac_user;
ALTER DEFAULT PRIVILEGES FOR ROLE app_user IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO fac_user;

-- When fac_user creates new tables/sequences, app_user automatically gets all privileges on them
ALTER DEFAULT PRIVILEGES FOR ROLE fac_user IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE fac_user IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO app_user;

-- 5. Grant mutual role membership so both users can modify/alter each other's tables
GRANT app_user TO fac_user;
GRANT fac_user TO app_user;
