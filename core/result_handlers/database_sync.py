"""
Generic Database Sync Handler

Syncs batch results to external databases with configurable schema mapping.

Example Usage:
    # PostgreSQL sync
    handler = DatabaseSyncHandler(config={
        'db_url': 'postgresql://user:pass@localhost/mydb',
        'table_name': 'batch_results',
        'schema_mapping': {
            'batch_id': 'batch_id',
            'custom_id': 'request_id',
            'response.choices[0].message.content': 'llm_response',
            'metadata.user_id': 'user_id',
            'metadata.project': 'project_name'
        },
        'priority': 100
    })
    
    registry.register(handler)
"""

from typing import Dict, Any, List, Optional
from sqlalchemy import create_engine, Table, Column, String, Text, DateTime, MetaData, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timezone
import json

from .base import ResultHandler


class DatabaseSyncHandler(ResultHandler):
    """
    Generic database sync handler with configurable schema mapping.
    
    Supports:
    - PostgreSQL, MySQL, SQLite
    - Custom schema mapping (JSON path → column)
    - Automatic table creation
    - Batch inserts for performance
    - Error handling and retries
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        
        # Required config
        self.db_url = self.config.get('db_url')
        if not self.db_url:
            raise ValueError("db_url is required in config")
        
        self.table_name = self.config.get('table_name', 'batch_results')
        self.schema_mapping = self.config.get('schema_mapping', {})
        
        # Optional config
        self.batch_size = self.config.get('batch_size', 100)
        self.create_table = self.config.get('create_table', True)
        self.upsert = self.config.get('upsert', False)
        self.upsert_key = self.config.get('upsert_key', 'custom_id')
        
        # Initialize database connection
        self.engine = create_engine(self.db_url, pool_pre_ping=True)
        self.metadata = MetaData()
        
        # Create or reflect table
        if self.create_table:
            self._create_table()
        else:
            self.table = Table(self.table_name, self.metadata, autoload_with=self.engine)
    
    def _create_table(self):
        """Create table with schema based on mapping."""
        columns = [
            Column('id', Integer, primary_key=True, autoincrement=True),
            Column('batch_id', String(255), nullable=False, index=True),
            Column('custom_id', String(255), nullable=True, index=True),
            Column('created_at', DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
        ]
        
        # Add columns from schema mapping
        for target_col in set(self.schema_mapping.values()):
            if target_col not in ['batch_id', 'custom_id', 'created_at']:
                # Default to Text for flexibility
                columns.append(Column(target_col, Text, nullable=True))
        
        # Add raw_data column for full result
        columns.append(Column('raw_data', JSONB if 'postgresql' in self.db_url else Text, nullable=True))
        
        self.table = Table(self.table_name, self.metadata, *columns, extend_existing=True)
        self.metadata.create_all(self.engine)
    
    def name(self) -> str:
        return f"database_sync_{self.table_name}"
    
    def enabled(self, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Always enabled if db_url is configured."""
        return bool(self.db_url)
    
    def handle(
        self,
        batch_id: str,
        results: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Sync results to database.
        
        Args:
            batch_id: Batch identifier
            results: List of result dictionaries
            metadata: Batch metadata
            
        Returns:
            True if sync successful, False otherwise
        """
        if not results:
            self.logger.info(f"No results to sync for batch {batch_id}")
            return True
        
        try:
            # Prepare rows for insertion
            rows = []
            for result in results:
                row = self._map_result_to_row(batch_id, result, metadata)
                rows.append(row)
            
            # Insert in batches
            with self.engine.begin() as conn:
                for i in range(0, len(rows), self.batch_size):
                    batch = rows[i:i + self.batch_size]
                    
                    if self.upsert:
                        self._upsert_batch(conn, batch)
                    else:
                        conn.execute(self.table.insert(), batch)
            
            self.logger.info(
                f"Synced {len(rows)} results to {self.table_name}",
                extra={'batch_id': batch_id, 'table': self.table_name}
            )
            return True
            
        except SQLAlchemyError as e:
            self.logger.error(
                f"Database sync failed: {e}",
                extra={'batch_id': batch_id, 'error': str(e)},
                exc_info=True
            )
            return False
    
    def _map_result_to_row(
        self,
        batch_id: str,
        result: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Map result to database row using schema mapping.
        
        Supports JSON path notation:
        - 'response.choices[0].message.content' → nested dict access
        - 'metadata.user_id' → metadata field
        """
        row = {
            'batch_id': batch_id,
            'custom_id': result.get('custom_id'),
            'raw_data': json.dumps(result) if 'postgresql' not in self.db_url else result
        }
        
        # Apply schema mapping
        for source_path, target_col in self.schema_mapping.items():
            value = self._extract_value(result, source_path, metadata)
            row[target_col] = value
        
        return row
    
    def _extract_value(
        self,
        result: Dict[str, Any],
        path: str,
        metadata: Dict[str, Any]
    ) -> Any:
        """
        Extract value from result using JSON path.
        
        Examples:
            'custom_id' → result['custom_id']
            'response.choices[0].message.content' → result['response']['choices'][0]['message']['content']
            'metadata.user_id' → metadata['user_id']
        """
        # Handle metadata paths
        if path.startswith('metadata.'):
            key = path.replace('metadata.', '')
            return metadata.get(key)
        
        # Handle nested paths
        parts = path.replace('[', '.').replace(']', '').split('.')
        value = result
        
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            elif isinstance(value, list) and part.isdigit():
                idx = int(part)
                value = value[idx] if idx < len(value) else None
            else:
                return None
            
            if value is None:
                return None
        
        # Convert to string if complex type
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        
        return value
    
    def _upsert_batch(self, conn, batch: List[Dict[str, Any]]):
        """
        Upsert batch (insert or update on conflict).
        
        Note: Upsert syntax varies by database.
        This implementation uses PostgreSQL syntax.
        """
        # For PostgreSQL
        if 'postgresql' in self.db_url:
            from sqlalchemy.dialects.postgresql import insert
            
            for row in batch:
                stmt = insert(self.table).values(**row)
                stmt = stmt.on_conflict_do_update(
                    index_elements=[self.upsert_key],
                    set_={k: v for k, v in row.items() if k != self.upsert_key}
                )
                conn.execute(stmt)
        else:
            # Fallback: delete then insert
            for row in batch:
                conn.execute(
                    self.table.delete().where(
                        self.table.c[self.upsert_key] == row[self.upsert_key]
                    )
                )
                conn.execute(self.table.insert(), row)
    
    def on_error(self, error: Exception) -> None:
        """Log database errors."""
        self.logger.error(
            f"Database sync error: {error}",
            extra={'handler': self.name()},
            exc_info=True
        )

