-- 1. Create the new user role with the same password (if not already existing)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'fac_user') THEN
    CREATE ROLE fac_user WITH LOGIN PASSWORD 'dypiu#2020$';
  END IF;
END
$$;

-- 2. Revoke app_user's default privileges in the faculty_appraisal database to prevent conflicts
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE, SELECT ON SEQUENCES FROM app_user;
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM app_user;
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM app_user;
REVOKE ALL PRIVILEGES ON SCHEMA public FROM app_user;

-- 3. Reassign ownership of all database objects currently owned by 'app_user' to 'fac_user'
REASSIGN OWNED BY app_user TO fac_user;

-- 4. Force-change ownership of all existing tables, sequences, and views in the public schema to 'fac_user'
DO $$
DECLARE
  r RECORD;
BEGIN
  -- Reassign all tables in public schema
  FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
    EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' OWNER TO fac_user;';
  END LOOP;
  
  -- Reassign all sequences in public schema
  FOR r IN (SELECT sequencename FROM pg_sequences WHERE schemaname = 'public') LOOP
    EXECUTE 'ALTER SEQUENCE public.' || quote_ident(r.sequencename) || ' OWNER TO fac_user;';
  END LOOP;

  -- Reassign all views in public schema
  FOR r IN (SELECT viewname FROM pg_views WHERE schemaname = 'public') LOOP
    EXECUTE 'ALTER VIEW public.' || quote_ident(r.viewname) || ' OWNER TO fac_user;';
  END LOOP;
END
$$;

-- 5. Grant full schema privileges to the new dedicated fac_user
GRANT USAGE ON SCHEMA public TO fac_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO fac_user;

-- 6. Grant ALL PRIVILEGES (including REFERENCES) on existing tables/sequences
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO fac_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO fac_user;

-- 7. Configure default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO fac_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO fac_user;
