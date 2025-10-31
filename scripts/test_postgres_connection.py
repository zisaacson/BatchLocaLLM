#!/usr/bin/env python3
"""
Test PostgreSQL connection and verify database setup.
"""

import sys
from sqlalchemy import create_engine, text
from core.config import settings

def test_connection():
    """Test PostgreSQL connection"""
    print("=" * 80)
    print("PostgreSQL Connection Test")
    print("=" * 80)
    
    print(f"\nDatabase URL: {settings.DATABASE_URL}")
    print(f"Pool Size: {settings.DATABASE_POOL_SIZE}")
    print(f"Max Overflow: {settings.DATABASE_MAX_OVERFLOW}")
    
    try:
        # Create engine with connection pooling
        engine = create_engine(
            settings.DATABASE_URL,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            pool_timeout=settings.DATABASE_POOL_TIMEOUT,
            pool_recycle=settings.DATABASE_POOL_RECYCLE,
            echo=settings.DATABASE_ECHO,
        )
        
        print("\n✅ Engine created successfully")
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"\n✅ Connected to PostgreSQL!")
            print(f"Version: {version}")
            
            # Test basic query
            result = conn.execute(text("SELECT 1 as test"))
            test_value = result.scalar()
            print(f"\n✅ Basic query works (SELECT 1 = {test_value})")
            
            # Check extensions
            result = conn.execute(text("""
                SELECT extname, extversion 
                FROM pg_extension 
                WHERE extname IN ('uuid-ossp', 'pg_stat_statements')
                ORDER BY extname
            """))
            extensions = result.fetchall()
            print(f"\n✅ Extensions installed:")
            for ext_name, ext_version in extensions:
                print(f"   - {ext_name} (v{ext_version})")
            
            # Check connection pool info
            print(f"\n✅ Connection pool info:")
            print(f"   - Pool size: {engine.pool.size()}")
            print(f"   - Checked out connections: {engine.pool.checkedout()}")
            print(f"   - Overflow: {engine.pool.overflow()}")
        
        print("\n" + "=" * 80)
        print("✅ All tests passed! PostgreSQL is ready.")
        print("=" * 80)
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check if PostgreSQL container is running:")
        print("   docker compose -f docker-compose.postgres.yml ps")
        print("2. Check PostgreSQL logs:")
        print("   docker logs vllm-batch-postgres")
        print("3. Verify DATABASE_URL in .env file")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

