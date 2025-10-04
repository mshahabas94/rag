"""
Database configuration and connection management for MySQL.
Handles connection pooling, security, and Aurora migration readiness.
"""

import os
import logging
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, text, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import SQLAlchemyError
import pymysql
from contextlib import contextmanager
import time
from urllib.parse import quote_plus
logger = logging.getLogger(__name__)
import re

class DatabaseConfig:
    """Database configuration and connection management."""
    
    def __init__(self):
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = int(os.getenv('DB_PORT', '3306'))
        self.database = os.getenv('DB_NAME', 'loaded')
        self.username = os.getenv('DB_USER', 'root')
        self.password = os.getenv('DB_PASSWORD', '')
        
        # Connection pool settings
        self.pool_size = int(os.getenv('DB_POOL_SIZE', '5'))
        self.max_overflow = int(os.getenv('DB_MAX_OVERFLOW', '10'))
        self.pool_timeout = int(os.getenv('DB_POOL_TIMEOUT', '30'))
        self.pool_recycle = int(os.getenv('DB_POOL_RECYCLE', '3600'))
        
        # Query settings
        self.query_timeout = int(os.getenv('DB_QUERY_TIMEOUT', '30'))
        
        self._engine: Optional[Engine] = None
        self._connection_string = self._build_connection_string()
    
    def _build_connection_string(self) -> str:
        """Build MySQL connection string with proper encoding and settings."""
        encoded_password = quote_plus(self.password)
        return (
            f"mysql+pymysql://{self.username}:{encoded_password}@{self.host}:{self.port}/{self.database}"
            f"?charset=utf8mb4&autocommit=false"
        )
    
    def get_engine(self) -> Engine:
        """Get or create SQLAlchemy engine with connection pooling."""
        if self._engine is None:
            try:
                self._engine = create_engine(
                    self._connection_string,
                    poolclass=QueuePool,
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                    pool_timeout=self.pool_timeout,
                    pool_recycle=self.pool_recycle,
                    pool_pre_ping=True,  # Validate connections before use
                    echo=os.getenv('DB_ECHO', 'false').lower() == 'true',
                    connect_args={
                        'connect_timeout': 10,
                        'read_timeout': self.query_timeout,
                        'write_timeout': self.query_timeout,
                    }
                )
                
                # Add query timeout event listener
                @event.listens_for(self._engine, "before_cursor_execute")
                def set_query_timeout(conn, cursor, statement, parameters, context, executemany):
                    cursor.execute(f"SET SESSION max_execution_time = {self.query_timeout * 1000}")
                
                logger.info("Database engine created successfully")
                
            except Exception as e:
                logger.error(f"Failed to create database engine: {e}")
                raise
        
        return self._engine
    
    @contextmanager
    def get_connection(self):
        """Get database connection with automatic cleanup."""
        engine = self.get_engine()
        connection = None
        
        try:
            connection = engine.connect()
            yield connection
        except SQLAlchemyError as e:
            logger.error(f"Database connection error: {e}")
            if connection:
                connection.rollback()
            raise
        finally:
            if connection:
                connection.close()
    
    def test_connection(self) -> bool:
        """Test database connectivity."""
        try:
            with self.get_connection() as conn:
                result = conn.execute(text("SELECT 1"))
                return result.fetchone()[0] == 1
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get detailed schema information for a table."""
        try:
            with self.get_connection() as conn:
                # Get column information
                columns_query = text("""
                    SELECT 
                        COLUMN_NAME,
                        DATA_TYPE,
                        IS_NULLABLE,
                        COLUMN_DEFAULT,
                        COLUMN_KEY,
                        EXTRA,
                        COLUMN_COMMENT
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_SCHEMA = :database 
                    AND TABLE_NAME = :table_name
                    ORDER BY ORDINAL_POSITION
                """)
                
                columns_result = conn.execute(
                    columns_query, 
                    {"database": self.database, "table_name": table_name}
                )
                
                columns = []
                for row in columns_result:
                    columns.append({
                        'name': row[0],
                        'type': row[1],
                        'nullable': row[2] == 'YES',
                        'default': row[3],
                        'key': row[4],
                        'extra': row[5],
                        'comment': row[6]
                    })
                
                # Get indexes
                indexes_query = text("""
                    SELECT 
                        INDEX_NAME,
                        COLUMN_NAME,
                        NON_UNIQUE
                    FROM INFORMATION_SCHEMA.STATISTICS 
                    WHERE TABLE_SCHEMA = :database 
                    AND TABLE_NAME = :table_name
                    ORDER BY INDEX_NAME, SEQ_IN_INDEX
                """)
                
                indexes_result = conn.execute(
                    indexes_query,
                    {"database": self.database, "table_name": table_name}
                )
                
                indexes = {}
                for row in indexes_result:
                    index_name = row[0]
                    if index_name not in indexes:
                        indexes[index_name] = {
                            'columns': [],
                            'unique': row[2] == 0
                        }
                    indexes[index_name]['columns'].append(row[1])
                
                return {
                    'table_name': table_name,
                    'columns': columns,
                    'indexes': indexes
                }
                
        except Exception as e:
            logger.error(f"Failed to get schema for table {table_name}: {e}")
            raise
    
    def execute_safe_query(self, query: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a query safely with timeout and result limiting.
        Only allows SELECT statements.
        """
        # Security check - only allow SELECT statements
        query_upper = query.strip().upper()
        if not query_upper.startswith('SELECT'):
            raise ValueError("Only SELECT queries are allowed")
        
        # Check for dangerous keywords
        dangerous_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'TRUNCATE']
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                if re.search(r'\b' + keyword + r'\b', query_upper):
                    raise ValueError(f"Query contains forbidden keyword: {keyword}")
        
        try:
            with self.get_connection() as conn:
                start_time = time.time()
                
                # Add LIMIT if not present to prevent large result sets
                if 'LIMIT' not in query_upper:
                    query += ' LIMIT 100'
                
                result = conn.execute(text(query), params or {})
                rows = result.fetchall()
                columns = result.keys()
                
                execution_time = time.time() - start_time
                
                # Convert to list of dictionaries
                data = []
                for row in rows:
                    data.append(dict(zip(columns, row)))
                
                return {
                    'success': True,
                    'data': data,
                    'row_count': len(data),
                    'execution_time': execution_time,
                    'columns': list(columns)
                }
                
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': [],
                'row_count': 0,
                'execution_time': 0,
                'columns': []
            }
    
    def get_sales_order_key_columns(self) -> list:
        """Get the most important columns from sales_order table for Vanna training."""
        return [
            'entity_id', 'increment_id', 'customer_id', 'customer_email',
            'customer_firstname', 'customer_lastname', 'status', 'state',
            'grand_total', 'base_grand_total', 'subtotal', 'tax_amount',
            'discount_amount', 'shipping_amount', 'shipping_method',
            'coupon_code', 'created_at', 'updated_at', 'total_item_count',
            'total_qty_ordered', 'base_total_paid', 'total_paid'
        ]
    
    def close(self):
        """Close database engine and all connections."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            logger.info("Database engine closed")

# Global database instance
db_config = DatabaseConfig()
