"""
Test suite for RAG service functionality.
Tests document processing, embedding, and retrieval.
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile
import shutil

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from services.rag_service import rag_service
from models.schemas import RAGQueryRequest, RAGResult
from config.rag_config import rag_config

class TestRAGService:
    """Test cases for RAG service."""
    
    @pytest.fixture
    def sample_rag_request(self):
        """Sample RAG query request for testing."""
        return RAGQueryRequest(
            question="What is your return policy?",
            include_sources=True
        )
    
    @pytest.fixture
    def temp_documents_dir(self):
        """Create temporary documents directory for testing."""
        temp_dir = tempfile.mkdtemp()
        
        # Create sample documents
        sample_docs = {
            'return_policy.txt': 'Our return policy allows returns within 30 days.',
            'shipping_info.txt': 'We offer standard and express shipping options.',
            'faq.txt': 'Frequently asked questions about our services.'
        }
        
        for filename, content in sample_docs.items():
            with open(Path(temp_dir) / filename, 'w') as f:
                f.write(content)
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir)
    
    def test_service_initialization(self):
        """Test RAG service initialization."""
        assert rag_service is not None
        
        # Test initialization status
        initial_status = rag_service._is_initialized
        assert isinstance(initial_status, bool)
    
    @patch('services.rag_service.rag_config')
    def test_initialize_success(self, mock_rag_config):
        """Test successful service initialization."""
        # Mock successful component initialization
        mock_rag_config.get_embeddings.return_value = Mock()
        mock_rag_config.get_vector_store.return_value = Mock()
        mock_rag_config.get_llm.return_value = Mock()
        mock_rag_config.get_qa_chain.return_value = Mock()
        mock_rag_config.get_collection_stats.return_value = {'total_chunks': 10}
        
        result = rag_service.initialize()
        assert result is True
    
    @patch('services.rag_service.rag_config')
    def test_initialize_failure(self, mock_rag_config):
        """Test initialization failure."""
        # Mock failed component initialization
        mock_rag_config.get_embeddings.side_effect = Exception("Embeddings failed")
        
        result = rag_service.initialize()
        assert result is False
    
    def test_validate_query_for_rag_suitable(self):
        """Test query validation for RAG-suitable queries."""
        test_cases = [
            "What is your return policy?",
            "How do I contact support?",
            "What are your business hours?",
            "How do I track my shipment?",
            "What payment methods do you accept?"
        ]
        
        for question in test_cases:
            result = rag_service.validate_query_for_rag(question)
            assert isinstance(result, dict)
            assert 'suitable_for_rag' in result
            assert 'confidence' in result
            assert result['suitable_for_rag'] is True
            assert result['confidence'] > 0.0
    
    def test_validate_query_for_rag_non_suitable(self):
        """Test query validation for non-RAG queries."""
        test_cases = [
            "Show me my orders from last month",
            "What's the status of order #100000123?",
            "How much did I spend this year?",
            "List my processing orders"
        ]
        
        for question in test_cases:
            result = rag_service.validate_query_for_rag(question)
            assert isinstance(result, dict)
            assert 'suitable_for_rag' in result
            # These should be less suitable for RAG
            assert result['suitable_for_rag'] is False or result['confidence'] < 0.5
    
    @patch('services.rag_service.rag_config')
    def test_process_rag_query_success(self, mock_rag_config, sample_rag_request):
        """Test successful RAG query processing."""
        # Mock initialization
        rag_service._is_initialized = True
        rag_service._documents_embedded = True
        
        # Mock successful query processing
        mock_rag_config.query_documents.return_value = {
            'success': True,
            'answer': 'Our return policy allows returns within 30 days of purchase.',
            'sources': [
                {
                    'filename': 'return_policy.txt',
                    'source': 'data/documents/return_policy.txt',
                    'content_preview': 'Our return policy allows returns...'
                }
            ]
        }
        
        result = rag_service.process_rag_query(sample_rag_request)
        
        assert isinstance(result, RAGResult)
        assert result.success is True
        assert len(result.answer) > 0
        assert len(result.sources) > 0
        assert result.confidence is not None
    
    @patch('services.rag_service.rag_config')
    def test_process_rag_query_no_documents(self, mock_rag_config, sample_rag_request):
        """Test RAG query processing when no documents are embedded."""
        # Mock initialization but no documents
        rag_service._is_initialized = True
        rag_service._documents_embedded = False
        
        result = rag_service.process_rag_query(sample_rag_request)
        
        assert isinstance(result, RAGResult)
        assert result.success is False
        assert "No documents available" in result.error
    
    @patch('services.rag_service.rag_config')
    def test_process_rag_query_failure(self, mock_rag_config, sample_rag_request):
        """Test RAG query processing failure."""
        # Mock initialization
        rag_service._is_initialized = True
        rag_service._documents_embedded = True
        
        # Mock failed query processing
        mock_rag_config.query_documents.return_value = {
            'success': False,
            'error': 'No relevant documents found'
        }
        
        result = rag_service.process_rag_query(sample_rag_request)
        
        assert isinstance(result, RAGResult)
        assert result.success is False
        assert result.error is not None
    
    def test_calculate_confidence(self):
        """Test confidence calculation for RAG results."""
        # Test with good sources
        good_result = {
            'answer': 'This is a comprehensive answer with good detail and explanation.',
            'sources': [
                {'filename': 'doc1.txt'},
                {'filename': 'doc2.txt'},
                {'filename': 'doc3.txt'}
            ]
        }
        
        confidence = rag_service._calculate_confidence(good_result)
        assert isinstance(confidence, float)
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.5  # Should be high confidence
        
        # Test with no sources
        no_sources_result = {
            'answer': 'Short answer',
            'sources': []
        }
        
        confidence = rag_service._calculate_confidence(no_sources_result)
        assert confidence < 0.5  # Should be low confidence
        
        # Test with uncertainty phrases
        uncertain_result = {
            'answer': 'I don\'t know the answer to this question.',
            'sources': [{'filename': 'doc1.txt'}]
        }
        
        confidence = rag_service._calculate_confidence(uncertain_result)
        assert confidence < 0.5  # Should be low due to uncertainty
    
    @patch('services.rag_service.rag_config')
    def test_search_documents(self, mock_rag_config):
        """Test document search functionality."""
        # Mock initialization
        rag_service._is_initialized = True
        
        # Mock vector store search
        mock_vector_store = Mock()
        mock_vector_store.similarity_search.return_value = [
            Mock(page_content="Return policy content", metadata={'filename': 'return_policy.txt'}),
            Mock(page_content="Shipping information", metadata={'filename': 'shipping_info.txt'})
        ]
        mock_rag_config.get_vector_store.return_value = mock_vector_store
        
        results = rag_service.search_documents("return policy", k=2)
        
        assert isinstance(results, list)
        assert len(results) == 2
        
        for result in results:
            assert 'content' in result
            assert 'metadata' in result
            assert 'preview' in result
    
    @patch('services.rag_service.rag_config')
    def test_embed_documents_success(self, mock_rag_config):
        """Test successful document embedding."""
        # Mock successful embedding
        mock_rag_config.embed_documents.return_value = True
        
        result = rag_service.embed_documents()
        
        assert result is True
        assert rag_service._documents_embedded is True
    
    @patch('services.rag_service.rag_config')
    def test_embed_documents_failure(self, mock_rag_config):
        """Test document embedding failure."""
        # Mock failed embedding
        mock_rag_config.embed_documents.return_value = False
        
        result = rag_service.embed_documents()
        
        assert result is False
    
    def test_get_sample_questions(self):
        """Test getting sample questions."""
        questions = rag_service.get_sample_questions()
        
        assert isinstance(questions, list)
        assert len(questions) > 0
        
        # Check that all questions are strings
        for question in questions:
            assert isinstance(question, str)
            assert len(question) > 0
    
    @patch('services.rag_service.rag_config')
    def test_get_document_stats(self, mock_rag_config):
        """Test getting document statistics."""
        # Mock initialization
        rag_service._is_initialized = True
        
        # Mock stats
        mock_rag_config.get_collection_stats.return_value = {
            'total_chunks': 25,
            'unique_sources': 5,
            'collection_name': 'test_collection'
        }
        
        stats = rag_service.get_document_stats()
        
        assert isinstance(stats, dict)
        assert 'total_chunks' in stats
        assert stats['total_chunks'] == 25
    
    def test_get_service_health(self):
        """Test service health check."""
        health = rag_service.get_service_health()
        
        assert isinstance(health, dict)
        assert 'service_name' in health
        assert 'initialized' in health
        assert 'healthy' in health
        assert 'timestamp' in health
        
        assert health['service_name'] == 'rag_service'

class TestRAGConfig:
    """Test cases for RAG configuration."""
    
    def test_rag_config_initialization(self):
        """Test RAG config initialization."""
        assert rag_config is not None
        assert hasattr(rag_config, 'documents_path')
        assert hasattr(rag_config, 'vector_db_path')
        assert hasattr(rag_config, 'collection_name')
    
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'})
    @patch('config.rag_config.OpenAIEmbeddings')
    def test_get_embeddings_openai(self, mock_openai_embeddings):
        """Test getting OpenAI embeddings."""
        mock_embeddings = Mock()
        mock_openai_embeddings.return_value = mock_embeddings
        
        # Reset embeddings to test initialization
        rag_config._embeddings = None
        rag_config.use_openai_embeddings = True
        rag_config.openai_api_key = 'test_key'
        
        embeddings = rag_config.get_embeddings()
        
        assert embeddings == mock_embeddings
        mock_openai_embeddings.assert_called_once()
    
    @patch('config.rag_config.HuggingFaceEmbeddings')
    def test_get_embeddings_local(self, mock_hf_embeddings):
        """Test getting local HuggingFace embeddings."""
        mock_embeddings = Mock()
        mock_hf_embeddings.return_value = mock_embeddings
        
        # Reset embeddings to test initialization
        rag_config._embeddings = None
        rag_config.use_openai_embeddings = False
        
        embeddings = rag_config.get_embeddings()
        
        assert embeddings == mock_embeddings
        mock_hf_embeddings.assert_called_once()
    
    def test_get_text_splitter(self):
        """Test text splitter initialization."""
        splitter = rag_config.get_text_splitter()
        
        assert splitter is not None
        assert hasattr(splitter, 'split_text')
    
    @patch('config.rag_config.chromadb')
    @patch('config.rag_config.Chroma')
    def test_get_vector_store(self, mock_chroma, mock_chromadb):
        """Test vector store initialization."""
        mock_client = Mock()
        mock_chromadb.PersistentClient.return_value = mock_client
        
        mock_vector_store = Mock()
        mock_chroma.return_value = mock_vector_store
        
        # Reset vector store to test initialization
        rag_config._vector_store = None
        
        with patch.object(rag_config, 'get_embeddings', return_value=Mock()):
            vector_store = rag_config.get_vector_store()
        
        assert vector_store == mock_vector_store
        mock_chroma.assert_called_once()
    
    def test_load_single_document_txt(self, temp_documents_dir):
        """Test loading a single text document."""
        # Temporarily set documents path
        original_path = rag_config.documents_path
        rag_config.documents_path = Path(temp_documents_dir)
        
        try:
            doc_path = Path(temp_documents_dir) / 'return_policy.txt'
            result = rag_config._load_single_document(doc_path)
            
            assert result is not None
            assert 'content' in result
            assert 'metadata' in result
            assert result['metadata']['filename'] == 'return_policy.txt'
            assert 'return policy' in result['content'].lower()
        finally:
            rag_config.documents_path = original_path
    
    def test_load_documents(self, temp_documents_dir):
        """Test loading all documents from directory."""
        # Temporarily set documents path
        original_path = rag_config.documents_path
        rag_config.documents_path = Path(temp_documents_dir)
        
        try:
            documents = rag_config.load_documents()
            
            assert isinstance(documents, list)
            assert len(documents) == 3  # Three sample documents
            
            for doc in documents:
                assert 'content' in doc
                assert 'metadata' in doc
                assert 'filename' in doc['metadata']
        finally:
            rag_config.documents_path = original_path
    
    @patch('config.rag_config.Chroma')
    def test_embed_documents(self, mock_chroma):
        """Test document embedding process."""
        # Mock vector store
        mock_vector_store = Mock()
        mock_chroma.return_value = mock_vector_store
        
        # Mock successful embedding
        with patch.object(rag_config, 'load_documents') as mock_load:
            mock_load.return_value = [
                {
                    'content': 'Test document content',
                    'metadata': {'filename': 'test.txt', 'source': 'test.txt'}
                }
            ]
            
            with patch.object(rag_config, 'get_text_splitter') as mock_splitter:
                mock_splitter.return_value.split_text.return_value = ['Test chunk 1', 'Test chunk 2']
                
                with patch.object(rag_config, 'get_vector_store', return_value=mock_vector_store):
                    result = rag_config.embed_documents()
        
        assert result is True
        mock_vector_store.add_texts.assert_called()
        mock_vector_store.persist.assert_called_once()

if __name__ == "__main__":
    pytest.main([__file__])


