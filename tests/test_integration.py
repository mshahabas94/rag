"""
Integration tests for the hybrid chatbot system.
Tests end-to-end functionality and service interactions.
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from main import HybridChatbot
from models.schemas import ChatRequest, ChatResponse, QueryType
from services.intent_classifier import intent_classifier

class TestHybridChatbot:
    """Integration tests for the main chatbot orchestrator."""
    
    @pytest.fixture
    def chatbot(self):
        """Create chatbot instance for testing."""
        return HybridChatbot()
    
    @pytest.fixture
    def sample_sql_request(self):
        """Sample request for SQL processing."""
        return ChatRequest(
            question="Show me my orders from last month",
            customer_id="test_customer_123",
            session_id="test_session"
        )
    
    @pytest.fixture
    def sample_rag_request(self):
        """Sample request for RAG processing."""
        return ChatRequest(
            question="What is your return policy?",
            customer_id="test_customer_123",
            session_id="test_session"
        )
    
    @pytest.fixture
    def sample_hybrid_request(self):
        """Sample request for hybrid processing."""
        return ChatRequest(
            question="Can I return order #100000123?",
            customer_id="test_customer_123",
            session_id="test_session"
        )
    
    @pytest.mark.asyncio
    async def test_chatbot_initialization(self, chatbot):
        """Test chatbot initialization."""
        with patch('main.vanna_service') as mock_vanna, \
             patch('main.rag_service') as mock_rag:
            
            mock_vanna.initialize.return_value = True
            mock_rag.initialize.return_value = True
            
            result = await chatbot.initialize()
            
            assert result is True
            assert chatbot.is_initialized is True
            mock_vanna.initialize.assert_called_once()
            mock_rag.initialize.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_chatbot_initialization_partial_failure(self, chatbot):
        """Test chatbot initialization with partial service failure."""
        with patch('main.vanna_service') as mock_vanna, \
             patch('main.rag_service') as mock_rag:
            
            mock_vanna.initialize.return_value = True
            mock_rag.initialize.return_value = False  # RAG fails
            
            result = await chatbot.initialize()
            
            assert result is True  # Should still succeed if one service works
            assert len(chatbot.initialization_errors) > 0
    
    @pytest.mark.asyncio
    async def test_chatbot_initialization_complete_failure(self, chatbot):
        """Test chatbot initialization with complete failure."""
        with patch('main.vanna_service') as mock_vanna, \
             patch('main.rag_service') as mock_rag:
            
            mock_vanna.initialize.return_value = False
            mock_rag.initialize.return_value = False
            
            result = await chatbot.initialize()
            
            assert result is False
            assert chatbot.is_initialized is False
    
    @pytest.mark.asyncio
    async def test_process_sql_query_success(self, chatbot, sample_sql_request):
        """Test successful SQL query processing."""
        with patch('main.vanna_service') as mock_vanna, \
             patch('main.rag_service') as mock_rag, \
             patch('main.intent_classifier') as mock_classifier, \
             patch('main.enforce_rate_limit') as mock_rate_limit, \
             patch('main.query_logger') as mock_logger:
            
            # Mock initialization
            chatbot.is_initialized = True
            
            # Mock rate limiting
            mock_rate_limit.return_value = (True, {})
            
            # Mock intent classification
            mock_classifier.classify_intent.return_value = Mock(
                query_type=QueryType.SQL,
                confidence=0.9,
                reasoning="Contains order-related keywords"
            )
            
            # Mock successful SQL processing
            mock_vanna.process_sql_query.return_value = Mock(
                success=True,
                sql="SELECT * FROM sales_order WHERE customer_id = 'test_customer_123'",
                data=[{'increment_id': '100000123', 'status': 'complete'}],
                row_count=1,
                execution_time=0.1
            )
            
            # Mock logging
            mock_logger.log_query.return_value = True
            
            response = await chatbot.process_chat_request(sample_sql_request)
            
            assert isinstance(response, ChatResponse)
            assert response.success is True
            assert response.query_type == QueryType.SQL
            assert len(response.answer) > 0
            assert response.sql_result is not None
    
    @pytest.mark.asyncio
    async def test_process_rag_query_success(self, chatbot, sample_rag_request):
        """Test successful RAG query processing."""
        with patch('main.vanna_service') as mock_vanna, \
             patch('main.rag_service') as mock_rag, \
             patch('main.intent_classifier') as mock_classifier, \
             patch('main.enforce_rate_limit') as mock_rate_limit, \
             patch('main.query_logger') as mock_logger:
            
            # Mock initialization
            chatbot.is_initialized = True
            
            # Mock rate limiting
            mock_rate_limit.return_value = (True, {})
            
            # Mock intent classification
            mock_classifier.classify_intent.return_value = Mock(
                query_type=QueryType.RAG,
                confidence=0.9,
                reasoning="Contains policy-related keywords"
            )
            
            # Mock successful RAG processing
            mock_rag.process_rag_query.return_value = Mock(
                success=True,
                answer="Our return policy allows returns within 30 days.",
                sources=[{'filename': 'return_policy.txt'}],
                confidence=0.8
            )
            
            # Mock logging
            mock_logger.log_query.return_value = True
            
            response = await chatbot.process_chat_request(sample_rag_request)
            
            assert isinstance(response, ChatResponse)
            assert response.success is True
            assert response.query_type == QueryType.RAG
            assert len(response.answer) > 0
            assert response.rag_result is not None
    
    @pytest.mark.asyncio
    async def test_process_hybrid_query_success(self, chatbot, sample_hybrid_request):
        """Test successful hybrid query processing."""
        with patch('main.vanna_service') as mock_vanna, \
             patch('main.rag_service') as mock_rag, \
             patch('main.intent_classifier') as mock_classifier, \
             patch('main.enforce_rate_limit') as mock_rate_limit, \
             patch('main.query_logger') as mock_logger:
            
            # Mock initialization
            chatbot.is_initialized = True
            
            # Mock rate limiting
            mock_rate_limit.return_value = (True, {})
            
            # Mock intent classification
            mock_classifier.classify_intent.return_value = Mock(
                query_type=QueryType.HYBRID,
                confidence=0.8,
                reasoning="Combines order and policy information"
            )
            
            # Mock successful SQL processing
            mock_vanna.process_sql_query.return_value = Mock(
                success=True,
                sql="SELECT * FROM sales_order WHERE increment_id = '100000123'",
                data=[{'increment_id': '100000123', 'status': 'complete', 'created_at': '2024-01-15'}],
                row_count=1
            )
            
            # Mock successful RAG processing
            mock_rag.process_rag_query.return_value = Mock(
                success=True,
                answer="Returns are allowed within 30 days of delivery.",
                sources=[{'filename': 'return_policy.txt'}]
            )
            
            # Mock logging
            mock_logger.log_query.return_value = True
            
            response = await chatbot.process_chat_request(sample_hybrid_request)
            
            assert isinstance(response, ChatResponse)
            assert response.success is True
            assert response.query_type == QueryType.HYBRID
            assert len(response.answer) > 0
            assert response.sql_result is not None
            assert response.rag_result is not None
            assert "Order Information:" in response.answer
            assert "Policy Information:" in response.answer
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, chatbot, sample_sql_request):
        """Test rate limiting functionality."""
        with patch('main.enforce_rate_limit') as mock_rate_limit, \
             patch('main.log_security_event') as mock_log_security:
            
            # Mock initialization
            chatbot.is_initialized = True
            
            # Mock rate limit exceeded
            mock_rate_limit.return_value = (False, {'current_count': 100, 'reset_time': 3600})
            
            response = await chatbot.process_chat_request(sample_sql_request)
            
            assert isinstance(response, ChatResponse)
            assert response.success is False
            assert "Rate limit exceeded" in response.answer
            mock_log_security.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_sql_fallback_to_rag(self, chatbot, sample_sql_request):
        """Test fallback from SQL to RAG when SQL fails."""
        with patch('main.vanna_service') as mock_vanna, \
             patch('main.rag_service') as mock_rag, \
             patch('main.intent_classifier') as mock_classifier, \
             patch('main.enforce_rate_limit') as mock_rate_limit, \
             patch('main.query_logger') as mock_logger:
            
            # Mock initialization
            chatbot.is_initialized = True
            
            # Mock rate limiting
            mock_rate_limit.return_value = (True, {})
            
            # Mock intent classification
            mock_classifier.classify_intent.return_value = Mock(
                query_type=QueryType.SQL,
                confidence=0.7
            )
            
            # Mock failed SQL processing
            mock_vanna.process_sql_query.return_value = Mock(
                success=False,
                error="SQL generation failed"
            )
            
            # Mock successful RAG fallback
            mock_rag.process_rag_query.return_value = Mock(
                success=True,
                answer="I couldn't find specific data, but here's general information...",
                sources=[]
            )
            
            # Mock logging
            mock_logger.log_query.return_value = True
            
            response = await chatbot.process_chat_request(sample_sql_request)
            
            assert isinstance(response, ChatResponse)
            assert response.success is True
            assert response.query_type == QueryType.RAG  # Changed to RAG due to fallback
            assert "couldn't find specific data" in response.answer
    
    @pytest.mark.asyncio
    async def test_unknown_query_handling(self, chatbot):
        """Test handling of unknown query types."""
        unknown_request = ChatRequest(
            question="Random unclear question",
            customer_id="test_customer_123",
            session_id="test_session"
        )
        
        with patch('main.intent_classifier') as mock_classifier, \
             patch('main.rag_service') as mock_rag, \
             patch('main.enforce_rate_limit') as mock_rate_limit, \
             patch('main.query_logger') as mock_logger:
            
            # Mock initialization
            chatbot.is_initialized = True
            
            # Mock rate limiting
            mock_rate_limit.return_value = (True, {})
            
            # Mock unknown intent classification
            mock_classifier.classify_intent.return_value = Mock(
                query_type=QueryType.UNKNOWN,
                confidence=0.1
            )
            
            # Mock RAG attempt with low confidence
            mock_rag.process_rag_query.return_value = Mock(
                success=True,
                answer="I'm not sure about that.",
                confidence=0.3
            )
            
            # Mock logging
            mock_logger.log_query.return_value = True
            
            response = await chatbot.process_chat_request(unknown_request)
            
            assert isinstance(response, ChatResponse)
            assert response.success is False
            assert "not sure how to help" in response.answer.lower()
    
    def test_format_sql_answer_single_result(self, chatbot):
        """Test formatting of single SQL result."""
        mock_sql_result = Mock(
            data=[{
                'increment_id': '100000123',
                'status': 'complete',
                'grand_total': 125.99,
                'created_at': '2024-01-15'
            }],
            row_count=1
        )
        
        answer = chatbot._format_sql_answer(mock_sql_result)
        
        assert isinstance(answer, str)
        assert '100000123' in answer
        assert 'complete' in answer
        assert '125.99' in answer
    
    def test_format_sql_answer_multiple_results(self, chatbot):
        """Test formatting of multiple SQL results."""
        mock_sql_result = Mock(
            data=[
                {'increment_id': '100000123', 'status': 'complete', 'grand_total': 125.99},
                {'increment_id': '100000124', 'status': 'processing', 'grand_total': 89.50},
                {'increment_id': '100000125', 'status': 'shipped', 'grand_total': 67.25}
            ],
            row_count=3
        )
        
        answer = chatbot._format_sql_answer(mock_sql_result)
        
        assert isinstance(answer, str)
        assert '100000123' in answer
        assert '100000124' in answer
        assert '100000125' in answer
    
    def test_format_sql_answer_no_results(self, chatbot):
        """Test formatting when no SQL results found."""
        mock_sql_result = Mock(data=[], row_count=0)
        
        answer = chatbot._format_sql_answer(mock_sql_result)
        
        assert isinstance(answer, str)
        assert "No results found" in answer
    
    def test_get_health_status(self, chatbot):
        """Test health status reporting."""
        with patch('main.vanna_service') as mock_vanna, \
             patch('main.rag_service') as mock_rag, \
             patch('main.system_monitor') as mock_monitor:
            
            # Mock service health
            mock_vanna.get_service_health.return_value = {
                'healthy': True,
                'database_connected': True
            }
            mock_rag.get_service_health.return_value = {
                'healthy': True
            }
            mock_monitor.get_system_health.return_value = {
                'memory': {'used_mb': 512}
            }
            
            # Mock initialization
            chatbot.is_initialized = True
            
            health = chatbot.get_health_status()
            
            assert hasattr(health, 'status')
            assert hasattr(health, 'database_healthy')
            assert hasattr(health, 'vanna_healthy')
            assert hasattr(health, 'rag_healthy')
    
    def test_get_stats(self, chatbot):
        """Test statistics reporting."""
        with patch('main.query_logger') as mock_logger, \
             patch('main.system_monitor') as mock_monitor:
            
            # Mock stats
            mock_logger.get_stats.return_value = Mock(
                dict=lambda: {'total_queries': 100, 'successful_queries': 95}
            )
            mock_logger.get_performance_metrics.return_value = {
                'avg_response_time': 0.5
            }
            
            with patch.object(chatbot, 'get_health_status') as mock_health:
                mock_health.return_value = Mock(dict=lambda: {'status': 'healthy'})
                
                stats = chatbot.get_stats()
            
            assert isinstance(stats, dict)
            assert 'system_stats' in stats
            assert 'performance_metrics' in stats
            assert 'health_status' in stats

class TestIntentClassifier:
    """Integration tests for intent classification."""
    
    def test_classify_sql_queries(self):
        """Test classification of SQL-suitable queries."""
        sql_queries = [
            "Show me my orders from last month",
            "What's the status of order #100000123?",
            "How much did I spend this year?",
            "List my processing orders"
        ]
        
        for query in sql_queries:
            result = intent_classifier.classify_intent(query)
            
            assert result.query_type == QueryType.SQL
            assert result.confidence > 0.5
    
    def test_classify_rag_queries(self):
        """Test classification of RAG-suitable queries."""
        rag_queries = [
            "What is your return policy?",
            "How do I contact support?",
            "What are your business hours?",
            "How do I track my shipment?"
        ]
        
        for query in rag_queries:
            result = intent_classifier.classify_intent(query)
            
            assert result.query_type == QueryType.RAG
            assert result.confidence > 0.5
    
    def test_classify_hybrid_queries(self):
        """Test classification of hybrid queries."""
        hybrid_queries = [
            "Can I return order #100000123?",
            "Why was my recent order cancelled?",
            "Is my order eligible for refund?",
            "How do I cancel order #100000456?"
        ]
        
        for query in hybrid_queries:
            result = intent_classifier.classify_intent(query)
            
            # Should be classified as hybrid or have reasonable confidence
            assert result.query_type in [QueryType.HYBRID, QueryType.SQL, QueryType.RAG]
            assert result.confidence > 0.3
    
    def test_validate_classification(self):
        """Test classification validation."""
        query = "Show me my recent orders"
        
        result = intent_classifier.validate_classification(query, QueryType.SQL)
        
        assert isinstance(result, dict)
        assert 'predicted_type' in result
        assert 'validations' in result
        assert 'recommendations' in result
    
    def test_get_sample_queries_by_type(self):
        """Test getting sample queries organized by type."""
        samples = intent_classifier.get_sample_queries_by_type()
        
        assert isinstance(samples, dict)
        assert 'sql' in samples
        assert 'rag' in samples
        assert 'hybrid' in samples
        
        for query_type, queries in samples.items():
            assert isinstance(queries, list)
            assert len(queries) > 0

if __name__ == "__main__":
    pytest.main([__file__])


