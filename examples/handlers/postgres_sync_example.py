"""
Example: PostgreSQL Sync Handler

Syncs batch results to PostgreSQL database with custom schema.

Use Case:
- Store LLM responses in your application database
- Track user requests and responses
- Build analytics on LLM usage

Setup:
    1. Install dependencies: pip install psycopg2-binary
    2. Create database: createdb my_llm_results
    3. Configure handler with your database URL
    4. Register handler in your application

Example Schema:
    CREATE TABLE llm_responses (
        id SERIAL PRIMARY KEY,
        batch_id VARCHAR(255) NOT NULL,
        request_id VARCHAR(255) NOT NULL,
        user_id VARCHAR(255),
        project_name VARCHAR(255),
        prompt TEXT,
        llm_response TEXT,
        model_name VARCHAR(255),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        raw_data JSONB
    );
"""

from core.result_handlers.database_sync import DatabaseSyncHandler
from core.result_handlers.base import get_registry


def register_postgres_sync():
    """
    Register PostgreSQL sync handler.
    
    This will automatically sync all batch results to your PostgreSQL database.
    """
    
    handler = DatabaseSyncHandler(config={
        # Database connection
        'db_url': 'postgresql://user:password@localhost:5432/my_llm_results',
        
        # Table name
        'table_name': 'llm_responses',
        
        # Schema mapping: source_path → target_column
        'schema_mapping': {
            # Basic fields
            'custom_id': 'request_id',
            
            # Extract from response
            'response.choices[0].message.content': 'llm_response',
            'response.model': 'model_name',
            
            # Extract from request body
            'body.messages[0].content': 'prompt',
            
            # Extract from metadata
            'metadata.user_id': 'user_id',
            'metadata.project': 'project_name',
        },
        
        # Options
        'create_table': True,  # Auto-create table if not exists
        'batch_size': 100,  # Insert 100 rows at a time
        'upsert': True,  # Update if request_id already exists
        'upsert_key': 'request_id',  # Use request_id for upsert
        
        # Handler priority (lower = runs first)
        'priority': 100
    })
    
    # Register handler
    registry = get_registry()
    registry.register(handler)
    
    print(f"✅ Registered PostgreSQL sync handler: {handler.name()}")


# Example: Register on application startup
if __name__ == '__main__':
    register_postgres_sync()
    
    # Test with sample data
    from core.result_handlers.base import get_registry
    
    registry = get_registry()
    
    sample_results = [
        {
            'custom_id': 'req_001',
            'body': {
                'messages': [
                    {'role': 'user', 'content': 'What is the capital of France?'}
                ]
            },
            'response': {
                'model': 'gemma-3-4b',
                'choices': [
                    {
                        'message': {
                            'content': 'The capital of France is Paris.'
                        }
                    }
                ]
            }
        }
    ]
    
    sample_metadata = {
        'user_id': 'user_123',
        'project': 'geography_qa'
    }
    
    # Process results
    success = registry.process_results(
        batch_id='test_batch_001',
        results=sample_results,
        metadata=sample_metadata
    )
    
    print(f"✅ Sync successful: {success}")

