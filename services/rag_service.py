"""
RAG (Retrieval Augmented Generation) service for knowledge base queries.
Handles document retrieval and answer generation for policy/FAQ questions.
"""

import logging
from typing import Dict, Any, List, Optional
import time
from datetime import datetime

from config.rag_config import rag_config
from models.schemas import RAGQueryRequest, RAGResult
from utils.query_logger import query_logger
from services.qdrant_bridge_service import qdrant_bridge_service

logger = logging.getLogger(__name__)

class RAGService:
    """Service for handling RAG-based knowledge queries."""
    
    def __init__(self):
        self.rag_config = rag_config
        self.bridge_service = qdrant_bridge_service
        self._is_initialized = False
        self._initialization_error = None
        self._documents_embedded = False
        self._use_existing_setup = False
    
    def initialize(self) -> bool:
        """Initialize the RAG service."""
        try:
            if self._is_initialized:
                return True
            
            logger.info("Initializing RAG service...")
            
            # First, try to use your existing Qdrant setup
            if self.bridge_service.initialize():
                logger.info("✅ Using existing Qdrant setup from chunking.py and generation.py")
                self._use_existing_setup = True
                self._documents_embedded = True
                self._is_initialized = True
                return True
            
            # Fallback to new RAG config if existing setup fails
            logger.info("Existing setup not available, initializing new RAG configuration...")
            
            # Initialize embeddings
            embeddings = self.rag_config.get_embeddings()
            logger.info("Embeddings initialized")
            
            # Initialize vector store
            vector_store = self.rag_config.get_vector_store()
            logger.info("Vector store initialized")
            
            # Initialize LLM
            llm = self.rag_config.get_llm()
            logger.info("LLM initialized")
            
            # Initialize QA chain
            qa_chain = self.rag_config.get_qa_chain()
            logger.info("QA chain initialized")
            
            # Check if documents are embedded
            if self.rag_config.check_existing_collection():
                self._documents_embedded = True
                logger.info("Found existing Qdrant collection")
            else:
                logger.warning("No documents found in vector store. Run embed_documents() to add documents.")
            
            self._is_initialized = True
            logger.info("RAG service initialized successfully")
            return True
            
        except Exception as e:
            self._initialization_error = str(e)
            logger.error(f"Failed to initialize RAG service: {e}")
            return False
    
    def embed_documents(self, force_rebuild: bool = False) -> bool:
        """
        Embed documents into the vector store.
        
        Args:
            force_rebuild: Whether to rebuild the entire collection
            
        Returns:
            True if embedding was successful
        """
        try:
            logger.info("Starting document embedding process...")
            
            if not self._is_initialized:
                if not self.initialize():
                    return False
            
            success = self.rag_config.embed_documents(force_rebuild=force_rebuild)
            
            if success:
                self._documents_embedded = True
                logger.info("Document embedding completed successfully")
            else:
                logger.error("Document embedding failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to embed documents: {e}")
            return False
    
    def process_rag_query(self, request: RAGQueryRequest, session_id: str = None) -> RAGResult:
        """
        Process a knowledge base query using RAG.
        
        Args:
            request: RAG query request
            session_id: Session ID for logging
            
        Returns:
            RAGResult with answer and sources
        """
        start_time = time.time()
        
        try:
            # Ensure service is initialized
            if not self._is_initialized:
                if not self.initialize():
                    return RAGResult(
                        success=False,
                        error=f"Service initialization failed: {self._initialization_error}"
                    )
            
            # Check if documents are available
            if not self._documents_embedded:
                return RAGResult(
                    success=False,
                    error="No documents available. Please embed documents first."
                )
            
            # Process the query using existing setup if available
            if self._use_existing_setup:
                logger.info(f"Processing RAG query with existing setup: {request.question[:100]}...")
                return self.bridge_service.process_rag_query(request, session_id)
            
            # Fallback to new RAG config
            logger.info(f"Processing RAG query with new config: {request.question[:100]}...")
            
            result = self.rag_config.query_documents(request.question)
            
            processing_time = time.time() - start_time
            
            if result['success']:
                logger.info(
                    f"RAG query processed successfully. "
                    f"Sources: {len(result['sources'])}, "
                    f"Time: {processing_time:.2f}s"
                )
                
                # Filter sources if not requested
                sources = result['sources'] if request.include_sources else []
                
                return RAGResult(
                    success=True,
                    answer=result['answer'],
                    sources=sources,
                    confidence=self._calculate_confidence(result)
                )
            else:
                logger.warning(f"RAG query failed: {result['error']}")
                return RAGResult(
                    success=False,
                    error=result['error']
                )
            
        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = f"Unexpected error in RAG processing: {str(e)}"
            
            logger.error(error_msg)
            
            return RAGResult(
                success=False,
                error=error_msg
            )
    
    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        """
        Calculate confidence score for RAG result.
        
        Args:
            result: Query result from RAG system
            
        Returns:
            Confidence score between 0 and 1
        """
        try:
            # Base confidence on number and quality of sources
            sources = result.get('sources', [])
            
            if not sources:
                return 0.1  # Low confidence if no sources
            
            # More sources generally means higher confidence
            source_score = min(1.0, len(sources) / 3.0)  # Max at 3 sources
            
            # Check answer length (very short answers might be less reliable)
            answer = result.get('answer', '')
            length_score = min(1.0, len(answer) / 100.0)  # Max at 100 chars
            
            # Check for uncertainty phrases in the answer
            uncertainty_phrases = [
                "i don't know", "not sure", "unclear", "might be",
                "possibly", "perhaps", "i cannot find", "no information"
            ]
            
            uncertainty_penalty = 0.0
            answer_lower = answer.lower()
            for phrase in uncertainty_phrases:
                if phrase in answer_lower:
                    uncertainty_penalty += 0.2
            
            # Calculate final confidence
            confidence = (source_score * 0.6 + length_score * 0.4) - uncertainty_penalty
            return max(0.0, min(1.0, confidence))
            
        except Exception as e:
            logger.warning(f"Failed to calculate confidence: {e}")
            return 0.5  # Default moderate confidence
    
    def validate_query_for_rag(self, question: str) -> Dict[str, Any]:
        """
        Validate if a question is suitable for RAG processing.
        
        Args:
            question: Natural language question
            
        Returns:
            Dict with validation results
        """
        try:
            # Keywords that suggest knowledge base queries
            rag_keywords = [
                'policy', 'return', 'refund', 'shipping', 'delivery',
                'how to', 'what is', 'can i', 'help', 'support',
                'contact', 'phone', 'email', 'address', 'procedure',
                'process', 'rule', 'guideline', 'information', 'about'
            ]
            
            # Keywords that suggest database queries
            non_rag_keywords = [
                'my order', 'my orders', 'order #', 'spent', 'total',
                'payment', 'status', 'recent', 'last month', 'count',
                'how many', 'show me', 'list my', 'find my'
            ]
            
            question_lower = question.lower()
            
            rag_score = sum(1 for keyword in rag_keywords if keyword in question_lower)
            non_rag_score = sum(1 for keyword in non_rag_keywords if keyword in question_lower)
            
            # Check for question words that suggest informational queries
            question_words = ['what', 'how', 'why', 'when', 'where', 'which']
            has_question_word = any(word in question_lower for word in question_words)
            if has_question_word:
                rag_score += 1
            
            # Check for specific order references (suggests database query)
            import re
            has_order_reference = bool(re.search(r'#?\d{8,}|my order|my recent', question_lower))
            if has_order_reference:
                non_rag_score += 2
            
            is_rag_suitable = rag_score > non_rag_score and rag_score > 0
            confidence = min(1.0, max(rag_score, non_rag_score) / 5.0)
            
            return {
                'suitable_for_rag': is_rag_suitable,
                'confidence': confidence,
                'rag_indicators': rag_score,
                'non_rag_indicators': non_rag_score,
                'reasoning': self._get_rag_validation_reasoning(rag_score, non_rag_score, has_question_word, has_order_reference)
            }
            
        except Exception as e:
            logger.error(f"Failed to validate query for RAG: {e}")
            return {
                'suitable_for_rag': False,
                'confidence': 0.0,
                'error': str(e)
            }
    
    def _get_rag_validation_reasoning(self, rag_score: int, non_rag_score: int,
                                    has_question_word: bool, has_order_reference: bool) -> str:
        """Generate reasoning for RAG validation."""
        reasons = []
        
        if has_question_word:
            reasons.append("contains question words (what, how, etc.)")
        if rag_score > 2:
            reasons.append("contains multiple policy/procedure keywords")
        if has_order_reference:
            reasons.append("references specific orders (better for database)")
        if non_rag_score > rag_score:
            reasons.append("appears to be asking about personal order data")
        
        if not reasons:
            reasons.append("no clear indicators found")
        
        return "; ".join(reasons)
    
    def get_document_stats(self) -> Dict[str, Any]:
        """Get statistics about the document collection."""
        try:
            if not self._is_initialized:
                return {'error': 'Service not initialized'}
            
            return self.rag_config.get_collection_stats()
            
        except Exception as e:
            logger.error(f"Failed to get document stats: {e}")
            return {'error': str(e)}
    
    def search_documents(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for relevant documents without generating an answer.
        
        Args:
            query: Search query
            k: Number of documents to return
            
        Returns:
            List of relevant document chunks
        """
        try:
            if not self._is_initialized:
                if not self.initialize():
                    return []
            
            vector_store = self.rag_config.get_vector_store()
            
            # Perform similarity search
            docs = vector_store.similarity_search(query, k=k)
            
            results = []
            for doc in docs:
                results.append({
                    'content': doc.page_content,
                    'metadata': doc.metadata,
                    'preview': doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            return []
    
    def get_sample_questions(self) -> List[str]:
        """Get sample questions that work well with the RAG system."""
        return [
            "What is your return policy?",
            "How do I track my shipment?",
            "What payment methods do you accept?",
            "How long does shipping take?",
            "Can I cancel my order?",
            "How do I apply a coupon code?",
            "What are your business hours?",
            "How do I contact customer support?",
            "What is your refund policy?",
            "Do you ship internationally?",
            "How do I create an account?",
            "What if my item is damaged?"
        ]
    
    def get_service_health(self) -> Dict[str, Any]:
        """Get health status of the RAG service."""
        try:
            health = {
                'service_name': 'rag_service',
                'initialized': self._is_initialized,
                'initialization_error': self._initialization_error,
                'documents_embedded': self._documents_embedded,
                'vector_store_healthy': False,
                'llm_healthy': False,
                'timestamp': datetime.now().isoformat()
            }
            
            if self._is_initialized:
                try:
                    # Test vector store
                    stats = self.rag_config.get_collection_stats()
                    health['vector_store_healthy'] = stats.get('total_chunks', 0) > 0
                    health['document_count'] = stats.get('total_chunks', 0)
                except:
                    health['vector_store_healthy'] = False
                
                try:
                    # Test LLM (simple test)
                    llm = self.rag_config.get_llm()
                    health['llm_healthy'] = llm is not None
                except:
                    health['llm_healthy'] = False
            
            # Overall health status
            health['healthy'] = (
                health['initialized'] and 
                health['documents_embedded'] and
                health['vector_store_healthy'] and
                health['llm_healthy']
            )
            
            return health
            
        except Exception as e:
            logger.error(f"Failed to get RAG service health: {e}")
            return {
                'service_name': 'rag_service',
                'healthy': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

# Global service instance
rag_service = RAGService()
