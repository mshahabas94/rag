"""
Vanna.ai service for Text-to-SQL functionality.
Handles SQL generation, validation, and execution with security measures.
"""

import logging
from typing import Dict, Any, Optional
from typing import List
import time
from datetime import datetime

from config.vanna_config import vanna_config
from config.database import db_config
from models.schemas import SQLQueryRequest, SQLResult, CustomerInfo
from utils.security import (
    validate_sql_security, 
    ensure_customer_isolation,
    log_security_event
)
from utils.query_logger import query_logger

logger = logging.getLogger(__name__)

class VannaService:
    """Service for handling Text-to-SQL operations using Vanna.ai."""
    
    def __init__(self):
        self.vanna_config = vanna_config
        self.db_config = db_config
        self._is_initialized = False
        self._initialization_error = None
    
    def initialize(self) -> bool:
        """Initialize the Vanna service."""
        try:
            if self._is_initialized:
                return True
            
            logger.info("Initializing Vanna service...")
            
            # Test database connection
            if not self.db_config.test_connection():
                raise Exception("Database connection test failed")
            
            # Initialize Vanna
            vanna_instance = self.vanna_config.get_vanna_instance()
            
            # Train if not already trained
            if not self.vanna_config.is_trained():
                logger.info("Training Vanna on sales_order schema...")
                if not self.vanna_config.train_on_sales_order_schema():
                    raise Exception("Failed to train Vanna on schema")
            
            self._is_initialized = True
            logger.info("Vanna service initialized successfully")
            return True
            
        except Exception as e:
            self._initialization_error = str(e)
            logger.error(f"Failed to initialize Vanna service: {e}")
            return False
    
    def process_sql_query(self, request: SQLQueryRequest, session_id: str = None) -> SQLResult:
        """
        Process a natural language query and return SQL results.
        
        Args:
            request: SQL query request
            session_id: Session ID for logging
            
        Returns:
            SQLResult with query results or error information
        """
        start_time = time.time()
        
        try:
            # Ensure service is initialized
            if not self._is_initialized:
                if not self.initialize():
                    return SQLResult(
                        success=False,
                        error=f"Service initialization failed: {self._initialization_error}"
                    )
            
            # Validate customer information
            customer_info = CustomerInfo(
                customer_id=request.customer_id,
                customer_email=request.customer_email
            )
            
            if not customer_info.has_identifier():
                log_security_event(
                    'missing_customer_isolation',
                    {'question': request.question, 'session_id': session_id},
                    'high'
                )
                return SQLResult(
                    success=False,
                    error="Customer ID or email required for database queries"
                )
            
            # Generate SQL using Vanna
            logger.info(f"Generating SQL for question: {request.question[:100]}...")
            
            sql_generation_result = self.vanna_config.generate_sql(
                question=request.question,
                customer_id=request.customer_id,
                customer_email=request.customer_email
            )
            
            if not sql_generation_result['success']:
                log_security_event(
                    'sql_generation_failed',
                    {
                        'question': request.question,
                        'error': sql_generation_result['error'],
                        'session_id': session_id
                    },
                    'medium'
                )
                return SQLResult(
                    success=False,
                    error=f"SQL generation failed: {sql_generation_result['error']}"
                )
            
            generated_sql = sql_generation_result['sql']
            
            # Validate SQL security
            validation_result = validate_sql_security(
                generated_sql,
                request.customer_id,
                request.customer_email
            )
            
            if not validation_result['valid']:
                log_security_event(
                    'sql_validation_failed',
                    {
                        'question': request.question,
                        'sql': generated_sql,
                        'errors': validation_result['errors'],
                        'session_id': session_id
                    },
                    'high'
                )
                return SQLResult(
                    success=False,
                    error=f"SQL validation failed: {'; '.join(validation_result['errors'])}",
                    sql=generated_sql
                )
            
            # Log security warnings if any
            if validation_result['warnings']:
                log_security_event(
                    'sql_validation_warnings',
                    {
                        'question': request.question,
                        'sql': generated_sql,
                        'warnings': validation_result['warnings'],
                        'session_id': session_id
                    },
                    'medium'
                )
            
            # Ensure customer isolation (double-check)
            secured_sql = ensure_customer_isolation(
                generated_sql,
                request.customer_id,
                request.customer_email
            )
            
            # Execute SQL query
            logger.info(f"Executing SQL query: {secured_sql[:200]}...")
            
            execution_result = self.db_config.execute_safe_query(secured_sql)
            
            processing_time = time.time() - start_time
            
            if execution_result['success']:
                logger.info(
                    f"SQL query executed successfully. "
                    f"Rows: {execution_result['row_count']}, "
                    f"Time: {processing_time:.2f}s"
                )
                
                return SQLResult(
                    success=True,
                    sql=secured_sql,
                    data=execution_result['data'],
                    row_count=execution_result['row_count'],
                    execution_time=execution_result['execution_time'],
                    columns=execution_result['columns']
                )
            else:
                log_security_event(
                    'sql_execution_failed',
                    {
                        'question': request.question,
                        'sql': secured_sql,
                        'error': execution_result['error'],
                        'session_id': session_id
                    },
                    'medium'
                )
                
                return SQLResult(
                    success=False,
                    sql=secured_sql,
                    error=f"Query execution failed: {execution_result['error']}"
                )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Unexpected error in SQL processing: {str(e)}"
            
            logger.error(error_msg)
            log_security_event(
                'sql_processing_error',
                {
                    'question': request.question,
                    'error': str(e),
                    'session_id': session_id
                },
                'high'
            )
            
            return SQLResult(
                success=False,
                error=error_msg
            )
    
    def explain_sql(self, sql: str) -> str:
        """
        Get explanation of SQL query.
        
        Args:
            sql: SQL query to explain
            
        Returns:
            Human-readable explanation of the SQL query
        """
        try:
            if not self._is_initialized:
                return "Service not initialized"
            
            return self.vanna_config.explain_sql(sql)
            
        except Exception as e:
            logger.error(f"Failed to explain SQL: {e}")
            return f"Unable to explain SQL: {str(e)}"
    
    def validate_query_syntax(self, question: str) -> Dict[str, Any]:
        """
        Validate if a question is suitable for SQL generation.
        
        Args:
            question: Natural language question
            
        Returns:
            Dict with validation results
        """
        try:
            # Keywords that suggest database queries
            sql_keywords = [
                'order', 'orders', 'purchase', 'bought', 'spent', 'total',
                'payment', 'status', 'recent', 'last', 'count', 'how many',
                'show me', 'list', 'find', 'search', 'when did', 'amount'
            ]
            
            # Keywords that suggest non-database queries
            non_sql_keywords = [
                'policy', 'return', 'refund', 'shipping', 'delivery',
                'how to', 'what is', 'can i', 'help', 'support',
                'contact', 'phone', 'email', 'address'
            ]
            
            question_lower = question.lower()
            
            sql_score = sum(1 for keyword in sql_keywords if keyword in question_lower)
            non_sql_score = sum(1 for keyword in non_sql_keywords if keyword in question_lower)
            
            # Check for order numbers (common pattern)
            import re
            has_order_number = bool(re.search(r'#?\d{8,}', question))
            if has_order_number:
                sql_score += 2
            
            # Check for monetary amounts
            has_money = bool(re.search(r'\$\d+|\d+\s*dollars?', question))
            if has_money:
                sql_score += 1
            
            # Check for date references
            has_date = bool(re.search(r'last\s+(month|week|year)|this\s+(month|week|year)|\d{4}', question))
            if has_date:
                sql_score += 1
            
            is_sql_suitable = sql_score > non_sql_score and sql_score > 0
            confidence = min(1.0, max(sql_score, non_sql_score) / 5.0)
            
            return {
                'suitable_for_sql': is_sql_suitable,
                'confidence': confidence,
                'sql_indicators': sql_score,
                'non_sql_indicators': non_sql_score,
                'reasoning': self._get_validation_reasoning(sql_score, non_sql_score, has_order_number, has_money, has_date)
            }
            
        except Exception as e:
            logger.error(f"Failed to validate query syntax: {e}")
            return {
                'suitable_for_sql': False,
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _get_validation_reasoning(self, sql_score: int, non_sql_score: int, 
                                has_order_number: bool, has_money: bool, has_date: bool) -> str:
        """Generate reasoning for query validation."""
        reasons = []
        
        if has_order_number:
            reasons.append("contains order number")
        if has_money:
            reasons.append("mentions monetary amounts")
        if has_date:
            reasons.append("references dates/time periods")
        if sql_score > 2:
            reasons.append("contains multiple database-related keywords")
        if non_sql_score > sql_score:
            reasons.append("appears to be asking about policies or procedures")
        
        if not reasons:
            reasons.append("no clear indicators found")
        
        return "; ".join(reasons)
    
    def get_sample_questions(self) -> List[str]:
        """Get sample questions that work well with the SQL system."""
        return [
            "Show me my orders from last month",
            "What's the status of order #100000123?",
            "How much did I spend this year?",
            "List my orders with status 'processing'",
            "What discounts did I get on my orders?",
            "Show my orders above $100",
            "How many orders do I have?",
            "What's my most recent order total?",
            "Show orders from January 2024",
            "List my cancelled orders",
            "What's my average order value?",
            "Show orders with free shipping"
        ]
    
    def get_service_health(self) -> Dict[str, Any]:
        """Get health status of the Vanna service."""
        try:
            health = {
                'service_name': 'vanna_service',
                'initialized': self._is_initialized,
                'initialization_error': self._initialization_error,
                'database_connected': False,
                'vanna_trained': False,
                'timestamp': datetime.now().isoformat()
            }
            
            if self._is_initialized:
                # Test database connection
                health['database_connected'] = self.db_config.test_connection()
                
                # Check if Vanna is trained
                health['vanna_trained'] = self.vanna_config.is_trained()
            
            # Overall health status
            health['healthy'] = (
                health['initialized'] and 
                health['database_connected'] and 
                health['vanna_trained']
            )
            
            return health
            
        except Exception as e:
            logger.error(f"Failed to get service health: {e}")
            return {
                'service_name': 'vanna_service',
                'healthy': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

# Global service instance
vanna_service = VannaService()
