"""
Test suite for Vanna service functionality.
Tests SQL generation, validation, and execution.
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from services.vanna_service import vanna_service
from models.schemas import SQLQueryRequest, SQLResult, CustomerInfo
from config.vanna_config import vanna_config
from config.database import db_config

class TestVannaService:
    """Test cases for Vanna service."""
    
    @pytest.fixture
    def sample_sql_request(self):
        """Sample SQL query request for testing."""
        return SQLQueryRequest(
            question="Show me my recent orders",
            customer_id="test_customer_123",
            customer_email="test@example.com"
        )
    
    @pytest.fixture
    def mock_vanna_instance(self):
        """Mock Vanna instance for testing."""
        mock_vn = Mock()
        mock_vn.generate_sql.return_value = "SELECT * FROM sales_order WHERE customer_id = 'test_customer_123'"
        mock_vn.explain_sql.return_value = "This query retrieves all orders for the specified customer"
        return mock_vn
    
    def test_service_initialization(self):
        """Test Vanna service initialization."""
        # Test that service can be initialized
        assert vanna_service is not None
        
        # Test initialization status
        initial_status = vanna_service._is_initialized
        assert isinstance(initial_status, bool)
    
    @patch('services.vanna_service.vanna_config')
    @patch('services.vanna_service.db_config')
    def test_initialize_success(self, mock_db_config, mock_vanna_config):
        """Test successful service initialization."""
        # Mock successful database connection
        mock_db_config.test_connection.return_value = True
        
        # Mock successful Vanna initialization
        mock_vanna_config.get_vanna_instance.return_value = Mock()
        mock_vanna_config.is_trained.return_value = True
        
        # Test initialization
        result = vanna_service.initialize()
        assert result is True
    
    @patch('services.vanna_service.vanna_config')
    @patch('services.vanna_service.db_config')
    def test_initialize_database_failure(self, mock_db_config, mock_vanna_config):
        """Test initialization failure due to database issues."""
        # Mock failed database connection
        mock_db_config.test_connection.return_value = False
        
        # Test initialization
        result = vanna_service.initialize()
        assert result is False
    
    def test_validate_query_syntax_sql_suitable(self):
        """Test query syntax validation for SQL-suitable queries."""
        test_cases = [
            "Show me my orders from last month",
            "What's the status of order #100000123?",
            "How much did I spend this year?",
            "List my processing orders"
        ]
        
        for question in test_cases:
            result = vanna_service.validate_query_syntax(question)
            assert isinstance(result, dict)
            assert 'suitable_for_sql' in result
            assert 'confidence' in result
            assert result['suitable_for_sql'] is True
            assert result['confidence'] > 0.0
    
    def test_validate_query_syntax_non_sql(self):
        """Test query syntax validation for non-SQL queries."""
        test_cases = [
            "What is your return policy?",
            "How do I contact support?",
            "What are your business hours?",
            "How do I track my shipment?"
        ]
        
        for question in test_cases:
            result = vanna_service.validate_query_syntax(question)
            assert isinstance(result, dict)
            assert 'suitable_for_sql' in result
            # These should be less suitable for SQL
            assert result['suitable_for_sql'] is False or result['confidence'] < 0.5
    
    @patch('services.vanna_service.vanna_config')
    def test_explain_sql(self, mock_vanna_config):
        """Test SQL explanation functionality."""
        mock_vn = Mock()
        mock_vn.explain_sql.return_value = "This query retrieves customer orders"
        mock_vanna_config.get_vanna_instance.return_value = mock_vn
        
        # Mock initialization
        vanna_service._is_initialized = True
        
        sql = "SELECT * FROM sales_order WHERE customer_id = '123'"
        explanation = vanna_service.explain_sql(sql)
        
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        mock_vn.explain_sql.assert_called_once_with(sql)
    
    @patch('services.vanna_service.vanna_config')
    @patch('services.vanna_service.db_config')
    @patch('services.vanna_service.validate_sql_security')
    @patch('services.vanna_service.ensure_customer_isolation')
    def test_process_sql_query_success(self, mock_ensure_isolation, mock_validate_security,
                                     mock_db_config, mock_vanna_config, sample_sql_request):
        """Test successful SQL query processing."""
        # Mock initialization
        vanna_service._is_initialized = True
        
        # Mock Vanna SQL generation
        mock_vanna_config.generate_sql.return_value = {
            'success': True,
            'sql': "SELECT * FROM sales_order WHERE customer_id = 'test_customer_123'"
        }
        
        # Mock security validation
        mock_validate_security.return_value = {
            'valid': True,
            'errors': [],
            'warnings': []
        }
        
        # Mock customer isolation
        mock_ensure_isolation.return_value = "SELECT * FROM sales_order WHERE customer_id = 'test_customer_123'"
        
        # Mock database execution
        mock_db_config.execute_safe_query.return_value = {
            'success': True,
            'data': [{'increment_id': '100000123', 'status': 'complete', 'grand_total': 125.99}],
            'row_count': 1,
            'execution_time': 0.1,
            'columns': ['increment_id', 'status', 'grand_total']
        }
        
        # Test query processing
        result = vanna_service.process_sql_query(sample_sql_request)
        
        assert isinstance(result, SQLResult)
        assert result.success is True
        assert len(result.data) == 1
        assert result.row_count == 1
    
    @patch('services.vanna_service.vanna_config')
    def test_process_sql_query_no_customer_info(self):
        """Test SQL query processing without customer information."""
        request = SQLQueryRequest(
            question="Show me orders",
            customer_id=None,
            customer_email=None
        )
        
        # Mock initialization
        vanna_service._is_initialized = True
        
        result = vanna_service.process_sql_query(request)
        
        assert isinstance(result, SQLResult)
        assert result.success is False
        assert "Customer ID or email required" in result.error
    
    @patch('services.vanna_service.vanna_config')
    def test_process_sql_query_generation_failure(self, mock_vanna_config, sample_sql_request):
        """Test SQL query processing when SQL generation fails."""
        # Mock initialization
        vanna_service._is_initialized = True
        
        # Mock failed SQL generation
        mock_vanna_config.generate_sql.return_value = {
            'success': False,
            'error': 'Failed to generate SQL'
        }
        
        result = vanna_service.process_sql_query(sample_sql_request)
        
        assert isinstance(result, SQLResult)
        assert result.success is False
        assert "SQL generation failed" in result.error
    
    def test_get_sample_questions(self):
        """Test getting sample questions."""
        questions = vanna_service.get_sample_questions()
        
        assert isinstance(questions, list)
        assert len(questions) > 0
        
        # Check that all questions are strings
        for question in questions:
            assert isinstance(question, str)
            assert len(question) > 0
    
    def test_get_service_health(self):
        """Test service health check."""
        health = vanna_service.get_service_health()
        
        assert isinstance(health, dict)
        assert 'service_name' in health
        assert 'initialized' in health
        assert 'healthy' in health
        assert 'timestamp' in health
        
        assert health['service_name'] == 'vanna_service'

class TestVannaConfig:
    """Test cases for Vanna configuration."""
    
    def test_vanna_config_initialization(self):
        """Test Vanna config initialization."""
        assert vanna_config is not None
        assert hasattr(vanna_config, 'model_name')
        assert hasattr(vanna_config, 'use_local')
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'})
    @patch('config.vanna_config.LocalContext_OpenAI')
    def test_get_vanna_instance_local(self, mock_local_openai):
        """Test getting Vanna instance with local OpenAI."""
        mock_instance = Mock()
        mock_local_openai.return_value = mock_instance
        
        # Reset the instance to test initialization
        vanna_config._vn = None
        vanna_config.use_local = True
        vanna_config.openai_api_key = 'test_key'
        
        with patch.object(vanna_config, '_connect_to_database'):
            instance = vanna_config.get_vanna_instance()
            
        assert instance == mock_instance
        mock_local_openai.assert_called_once()
    
    def test_validate_sql_basic(self):
        """Test basic SQL validation."""
        # Test valid SQL
        valid_sql = "SELECT * FROM sales_order WHERE customer_id = '123'"
        result = vanna_config._validate_sql(valid_sql)
        
        assert isinstance(result, dict)
        assert 'valid' in result
        assert 'errors' in result
        assert 'warnings' in result
        
        # Test invalid SQL (non-SELECT)
        invalid_sql = "DELETE FROM sales_order WHERE customer_id = '123'"
        result = vanna_config._validate_sql(invalid_sql)
        
        assert result['valid'] is False
        assert len(result['errors']) > 0
    
    def test_add_customer_isolation(self):
        """Test adding customer isolation to SQL."""
        base_sql = "SELECT * FROM sales_order"
        
        # Test with customer_id
        result = vanna_config._add_customer_isolation(base_sql, customer_id="123")
        assert "customer_id = '123'" in result
        
        # Test with customer_email
        result = vanna_config._add_customer_isolation(base_sql, customer_email="test@example.com")
        assert "customer_email = 'test@example.com'" in result
        
        # Test with existing WHERE clause
        sql_with_where = "SELECT * FROM sales_order WHERE status = 'complete'"
        result = vanna_config._add_customer_isolation(sql_with_where, customer_id="123")
        assert "AND customer_id = '123'" in result

class TestDatabaseConfig:
    """Test cases for database configuration."""
    
    def test_database_config_initialization(self):
        """Test database config initialization."""
        assert db_config is not None
        assert hasattr(db_config, 'host')
        assert hasattr(db_config, 'port')
        assert hasattr(db_config, 'database')
    
    def test_connection_string_building(self):
        """Test database connection string building."""
        connection_string = db_config._build_connection_string()
        
        assert isinstance(connection_string, str)
        assert 'mysql+pymysql://' in connection_string
        assert 'charset=utf8mb4' in connection_string
    
    def test_get_sales_order_key_columns(self):
        """Test getting key columns for sales_order table."""
        columns = db_config.get_sales_order_key_columns()
        
        assert isinstance(columns, list)
        assert len(columns) > 0
        
        # Check for essential columns
        essential_columns = ['entity_id', 'customer_id', 'increment_id', 'status', 'grand_total']
        for col in essential_columns:
            assert col in columns
    
    @patch('config.database.create_engine')
    def test_get_engine(self, mock_create_engine):
        """Test engine creation."""
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        
        # Reset engine to test creation
        db_config._engine = None
        
        engine = db_config.get_engine()
        
        assert engine == mock_engine
        mock_create_engine.assert_called_once()
    
    def test_execute_safe_query_validation(self):
        """Test safe query execution validation."""
        # Test non-SELECT query
        result = db_config.execute_safe_query("DELETE FROM sales_order")
        
        assert result['success'] is False
        assert 'Only SELECT queries are allowed' in result['error']
        
        # Test query with dangerous keywords
        result = db_config.execute_safe_query("SELECT * FROM sales_order; DROP TABLE sales_order;")
        
        assert result['success'] is False

if __name__ == "__main__":
    pytest.main([__file__])


