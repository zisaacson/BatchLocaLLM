#!/bin/bash
# Wait for PostgreSQL to be ready before starting services
# This prevents database connection failures on boot/restart

set -e

# Configuration
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-4332}"
POSTGRES_USER="${POSTGRES_USER:-vllm_batch_user}"
POSTGRES_DB="${POSTGRES_DB:-vllm_batch}"
MAX_RETRIES="${MAX_RETRIES:-30}"
RETRY_INTERVAL="${RETRY_INTERVAL:-2}"

echo "🔄 Waiting for PostgreSQL to be ready..."
echo "   Host: $POSTGRES_HOST"
echo "   Port: $POSTGRES_PORT"
echo "   Database: $POSTGRES_DB"
echo "   Max retries: $MAX_RETRIES (${RETRY_INTERVAL}s interval)"
echo ""

# Function to check if PostgreSQL is ready
check_postgres() {
    docker exec vllm-batch-postgres pg_isready -h localhost -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB" > /dev/null 2>&1
    return $?
}

# Wait for PostgreSQL
retry_count=0
while [ $retry_count -lt $MAX_RETRIES ]; do
    if check_postgres; then
        echo "✅ PostgreSQL is ready!"
        
        # Additional check: try to connect
        if docker exec vllm-batch-postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;" > /dev/null 2>&1; then
            echo "✅ Database connection verified!"
            exit 0
        else
            echo "⚠️  PostgreSQL is running but connection failed, retrying..."
        fi
    else
        retry_count=$((retry_count + 1))
        echo "⏳ Waiting for PostgreSQL... (attempt $retry_count/$MAX_RETRIES)"
        sleep $RETRY_INTERVAL
    fi
done

echo "❌ PostgreSQL did not become ready in time!"
echo "   Please check Docker logs: docker logs vllm-batch-postgres"
exit 1

