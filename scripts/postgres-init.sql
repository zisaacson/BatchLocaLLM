-- PostgreSQL Initialization Script for vLLM Batch Server
-- This script runs automatically when the container is first created

-- Enable UUID extension for generating UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_stat_statements for query performance monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Create indexes for common query patterns (will be created by SQLAlchemy migrations)
-- This file is a placeholder for any custom PostgreSQL setup

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE vllm_batch TO vllm_batch_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO vllm_batch_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO vllm_batch_user;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO vllm_batch_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO vllm_batch_user;

-- Performance tuning settings (these are set in docker-compose, but documented here)
-- shared_buffers = 256MB (25% of RAM for small instances)
-- effective_cache_size = 1GB (50-75% of RAM)
-- work_mem = 16MB (for sorting/hashing operations)
-- maintenance_work_mem = 128MB (for VACUUM, CREATE INDEX)
-- max_connections = 100 (default, adjust based on connection pooling)

-- Connection pooling recommendation:
-- Use PgBouncer or Supabase Pooler for production
-- This allows 1000+ app connections → 20-50 database connections

