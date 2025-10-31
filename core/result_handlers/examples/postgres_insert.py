"""
Example: PostgreSQL Insert Handler

Automatically insert batch results into your PostgreSQL database.

This is a template showing how to create a custom result handler
that integrates with your application's database.

Configuration:
- POSTGRES_HOST: Database host
- POSTGRES_PORT: Database port
- POSTGRES_DB: Database name
- POSTGRES_USER: Database user
- POSTGRES_PASSWORD: Database password
- POSTGRES_TABLE: Table name for results (default: ml_results)
"""

import os
from typing import List, Dict, Any
import logging
from datetime import datetime

# Optional: Only import if psycopg2 is available
try:
    import psycopg2
    from psycopg2.extras import execute_batch
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False

from result_handlers.base import ResultHandler

logger = logging.getLogger(__name__)


class PostgresInsertHandler(ResultHandler):
    """
    Insert batch results into PostgreSQL database.
    
    Table schema (example):
    CREATE TABLE ml_results (
        id SERIAL PRIMARY KEY,
        batch_id VARCHAR(255) NOT NULL,
        custom_id VARCHAR(255) NOT NULL,
        input_text TEXT,
        output_text TEXT,
        model VARCHAR(255),
        metadata JSONB,
        created_at TIMESTAMP DEFAULT NOW(),
        INDEX idx_batch_id (batch_id),
        INDEX idx_custom_id (custom_id)
    );
    """
    
    def name(self) -> str:
        return "postgres_insert"
    
    def enabled(self) -> bool:
        """Check if PostgreSQL is configured and available."""
        if not POSTGRES_AVAILABLE:
            logger.warning("psycopg2 not installed, PostgresInsertHandler disabled")
            return False
        
        required_vars = ['POSTGRES_HOST', 'POSTGRES_DB', 'POSTGRES_USER', 'POSTGRES_PASSWORD']
        return all(os.getenv(var) for var in required_vars)
    
    def handle(
        self,
        batch_id: str,
        results: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Insert results into PostgreSQL.
        
        Args:
            batch_id: Batch identifier
            results: List of batch results
            metadata: Batch metadata
            
        Returns:
            True if insert successful, False otherwise
        """
        # Get database configuration
        db_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': int(os.getenv('POSTGRES_PORT', '5432')),
            'database': os.getenv('POSTGRES_DB'),
            'user': os.getenv('POSTGRES_USER'),
            'password': os.getenv('POSTGRES_PASSWORD')
        }
        
        table_name = os.getenv('POSTGRES_TABLE', 'ml_results')
        
        try:
            # Connect to database
            conn = psycopg2.connect(**db_config)
            cursor = conn.cursor()
            
            # Prepare insert data
            insert_data = []
            for result in results:
                # Skip failed results
                if 'error' in result:
                    continue
                
                custom_id = result.get('custom_id', 'unknown')
                response = result.get('response', {})
                body = response.get('body', {})
                
                # Extract input and output
                input_messages = result.get('input', {}).get('messages', [])
                input_text = '\n'.join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in input_messages])
                
                output_text = body.get('choices', [{}])[0].get('message', {}).get('content', '')
                model = body.get('model', 'unknown')
                
                insert_data.append((
                    batch_id,
                    custom_id,
                    input_text,
                    output_text,
                    model,
                    metadata  # Store as JSONB
                ))
            
            if not insert_data:
                logger.warning("No valid results to insert")
                return True
            
            # Batch insert
            insert_query = f"""
                INSERT INTO {table_name} 
                (batch_id, custom_id, input_text, output_text, model, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            execute_batch(cursor, insert_query, insert_data)
            conn.commit()
            
            logger.info(f"✅ Inserted {len(insert_data)} results into {table_name}")
            
            cursor.close()
            conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ PostgreSQL insert failed: {e}")
            return False


# Example usage:
# from result_handlers import register_handler
# from result_handlers.examples.postgres_insert import PostgresInsertHandler
#
# handler = PostgresInsertHandler()
# register_handler(handler)

