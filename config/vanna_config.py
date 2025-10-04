"""
Vanna.ai configuration for Text-to-SQL functionality.
Handles model initialization, training, and query generation.
"""

import os
import logging
from typing import Optional, List, Dict, Any
import vanna
from vanna.remote import VannaDefault
from vanna.base import VannaBase
from .database import db_config
from .local_llm_config import local_llm_config

logger = logging.getLogger(__name__)

class VannaConfig:
    """Vanna.ai configuration and model management."""
    
    def __init__(self):
        self.model_name = os.getenv('VANNA_MODEL', 'local_ecommerce_chatbot')
        self.api_key = os.getenv('VANNA_API_KEY', '')  # Optional for local mode
        self.openai_api_key = os.getenv('OPENAI_API_KEY', '')
        
        # Use local context with OpenAI for better control
        self.use_local = os.getenv('VANNA_USE_LOCAL', 'true').lower() == 'true'
        
        self._vn: Optional[vanna.base.VannaBase] = None
        self._is_trained = False
    
    def get_vanna_instance(self) -> vanna.base.VannaBase:
        """Get or create Vanna instance."""
        if self._vn is None:
            try:
                # Use local LLaMA model instead of OpenAI
                from .local_vanna import get_local_vanna_instance
                self._vn = get_local_vanna_instance()
                logger.info("Initialized Vanna with local LLaMA model")
                
                # Connect to database
                self._connect_to_database()
                
            except Exception as e:
                logger.error(f"Failed to initialize Vanna: {e}")
                raise
        
        return self._vn
    
    def _connect_to_database(self):
        """Connect Vanna to the MySQL database."""
        try:
            engine = db_config.get_engine()
            self._vn.connect_to_mysql(
                host=db_config.host,
                dbname=db_config.database,
                user=db_config.username,
                password=db_config.password,
                port=db_config.port
            )
            logger.info("Vanna connected to MySQL database")
        except Exception as e:
            logger.error(f"Failed to connect Vanna to database: {e}")
            raise
    
    def train_on_sales_order_schema(self) -> bool:
        """Train Vanna on the sales_order table schema."""
        try:
            vn = self.get_vanna_instance()
            
            # Get table schema
            schema_info = db_config.get_table_schema('sales_order')
            
            # Create DDL statement for training
            ddl = self._generate_ddl_from_schema(schema_info)
            
            # Train on DDL
            vn.train(ddl=ddl)
            logger.info("Trained Vanna on sales_order DDL")
            
            # Train on sample queries
            self._train_sample_queries(vn)
            
            self._is_trained = True
            return True
            
        except Exception as e:
            logger.error(f"Failed to train Vanna on schema: {e}")
            return False
    
    def _generate_ddl_from_schema(self, schema_info: Dict[str, Any]) -> str:
        """Generate DDL statement from schema information."""
        table_name = schema_info['table_name']
        columns = schema_info['columns']
        
        ddl_parts = [f"CREATE TABLE {table_name} ("]
        
        column_definitions = []
        for col in columns:
            col_def = f"  {col['name']} {col['type']}"
            
            if not col['nullable']:
                col_def += " NOT NULL"
            
            if col['default'] is not None:
                col_def += f" DEFAULT {col['default']}"
            
            if col['extra']:
                col_def += f" {col['extra']}"
            
            if col['comment']:
                col_def += f" COMMENT '{col['comment']}'"
            
            column_definitions.append(col_def)
        
        ddl_parts.append(",\n".join(column_definitions))
        ddl_parts.append(");")
        
        return "\n".join(ddl_parts)
    
    def _train_sample_queries(self, vn):
        """Train Vanna on sample e-commerce queries."""
        sample_queries = [
            # Order lookups
            {
                "question": "Show me order details for order number 100000123",
                "sql": "SELECT * FROM sales_order WHERE increment_id = '100000123' AND customer_id = :customer_id"
            },
            {
                "question": "What is the status of my recent orders?",
                "sql": "SELECT increment_id, status, state, grand_total, created_at FROM sales_order WHERE customer_id = :customer_id ORDER BY created_at DESC LIMIT 10"
            },
            {
                "question": "Show my orders from last month",
                "sql": "SELECT increment_id, status, grand_total, created_at FROM sales_order WHERE customer_id = :customer_id AND created_at >= DATE_SUB(NOW(), INTERVAL 1 MONTH)"
            },
            
            # Financial queries
            {
                "question": "How much have I spent this year?",
                "sql": "SELECT SUM(grand_total) as total_spent FROM sales_order WHERE customer_id = :customer_id AND YEAR(created_at) = YEAR(NOW()) AND status IN ('complete', 'processing')"
            },
            {
                "question": "What's my average order value?",
                "sql": "SELECT AVG(grand_total) as avg_order_value FROM sales_order WHERE customer_id = :customer_id AND status IN ('complete', 'processing')"
            },
            {
                "question": "Show orders above $100",
                "sql": "SELECT increment_id, grand_total, status, created_at FROM sales_order WHERE customer_id = :customer_id AND grand_total > 100 ORDER BY grand_total DESC"
            },
            
            # Status and filtering
            {
                "question": "Show my processing orders",
                "sql": "SELECT increment_id, status, grand_total, created_at FROM sales_order WHERE customer_id = :customer_id AND status = 'processing'"
            },
            {
                "question": "How many orders do I have?",
                "sql": "SELECT COUNT(*) as order_count FROM sales_order WHERE customer_id = :customer_id"
            },
            {
                "question": "Show orders with discounts",
                "sql": "SELECT increment_id, grand_total, discount_amount, coupon_code FROM sales_order WHERE customer_id = :customer_id AND discount_amount > 0"
            },
            
            # Date range queries
            {
                "question": "Show orders from January 2024",
                "sql": "SELECT increment_id, status, grand_total, created_at FROM sales_order WHERE customer_id = :customer_id AND created_at >= '2024-01-01' AND created_at < '2024-02-01'"
            },
            {
                "question": "What's my most recent order total?",
                "sql": "SELECT grand_total FROM sales_order WHERE customer_id = :customer_id ORDER BY created_at DESC LIMIT 1"
            }
        ]
        
        for query in sample_queries:
            try:
                vn.train(question=query["question"], sql=query["sql"])
                logger.debug(f"Trained query: {query['question']}")
            except Exception as e:
                logger.warning(f"Failed to train query '{query['question']}': {e}")
        
        logger.info(f"Trained {len(sample_queries)} sample queries")
    
    def generate_sql(self, question: str, customer_id: str = None, customer_email: str = None) -> Dict[str, Any]:
        """
        Generate SQL from natural language question with customer isolation.
        """
        try:
            vn = self.get_vanna_instance()
            
            if not self._is_trained:
                logger.warning("Vanna model not trained, attempting to train now")
                if not self.train_on_sales_order_schema():
                    raise ValueError("Model not trained and training failed")
            
            # Generate SQL
            sql = vn.generate_sql(question)
            
            # Add customer isolation if not present
            sql_secured = self._add_customer_isolation(sql, customer_id, customer_email)
            
            # Validate the generated SQL
            validation_result = self._validate_sql(sql_secured)
            
            return {
                'success': True,
                'sql': sql_secured,
                'original_sql': sql,
                'validation': validation_result,
                'question': question
            }
            
        except Exception as e:
            logger.error(f"Failed to generate SQL for question '{question}': {e}")
            return {
                'success': False,
                'error': str(e),
                'sql': '',
                'original_sql': '',
                'validation': {'valid': False, 'errors': [str(e)]},
                'question': question
            }
    
    def _add_customer_isolation(self, sql: str, customer_id: str = None, customer_email: str = None) -> str:
        """Add customer isolation to SQL query."""
        sql_upper = sql.upper()
        
        # Check if customer isolation already exists
        if 'CUSTOMER_ID' in sql_upper or 'CUSTOMER_EMAIL' in sql_upper:
            return sql
        
        # Add WHERE clause for customer isolation
        if 'WHERE' in sql_upper:
            if customer_id:
                sql += f" AND customer_id = '{customer_id}'"
            elif customer_email:
                sql += f" AND customer_email = '{customer_email}'"
        else:
            if customer_id:
                sql += f" WHERE customer_id = '{customer_id}'"
            elif customer_email:
                sql += f" WHERE customer_email = '{customer_email}'"
        
        return sql
    
    def _validate_sql(self, sql: str) -> Dict[str, Any]:
        """Validate generated SQL for security and correctness."""
        errors = []
        warnings = []
        
        sql_upper = sql.strip().upper()
        
        # Check if it's a SELECT statement
        if not sql_upper.startswith('SELECT'):
            errors.append("Only SELECT statements are allowed")
        
        # Check for dangerous keywords
        dangerous_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'TRUNCATE', 'EXEC']
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                errors.append(f"Forbidden keyword detected: {keyword}")
        
        # Check for customer isolation
        if 'CUSTOMER_ID' not in sql_upper and 'CUSTOMER_EMAIL' not in sql_upper:
            errors.append("Query must include customer isolation (customer_id or customer_email)")
        
        # Check for potential SQL injection patterns
        injection_patterns = ["'", '"', ';', '--', '/*', '*/', 'UNION', 'OR 1=1']
        for pattern in injection_patterns:
            if pattern in sql and pattern not in ['SELECT', 'FROM', 'WHERE', 'ORDER BY']:
                warnings.append(f"Potential injection pattern detected: {pattern}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def explain_sql(self, sql: str) -> str:
        """Get explanation of generated SQL."""
        try:
            vn = self.get_vanna_instance()
            return vn.generate_explanation(sql)
        except Exception as e:
            logger.error(f"Failed to explain SQL: {e}")
            return f"Unable to explain SQL: {str(e)}"
    
    def is_trained(self) -> bool:
        """Check if the model is trained."""
        return self._is_trained

# Global Vanna instance
vanna_config = VannaConfig()
