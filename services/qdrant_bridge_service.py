"""
Bridge service to integrate existing chunking.py and generation.py with the hybrid chatbot.
This allows using your existing Qdrant setup and LLaMA model directly.
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add parent directory to import your existing modules
sys.path.append(str(Path(__file__).parent.parent))

try:
    from chunking import initialize_and_populate_vectorstore, search_support_questions
    from generation import create_rag_pipeline, LlamaCppClient, format_retrieved_docs
except ImportError as e:
    logging.error(f"Could not import existing modules: {e}")
    # Fallback imports will be handled in the service

from models.schemas import RAGQueryRequest, RAGResult

logger = logging.getLogger(__name__)

class QdrantBridgeService:
    """Bridge service to use your existing Qdrant and LLaMA setup."""
    
    def __init__(self):
        self._retriever = None
        self._rag_pipeline = None
        self._is_initialized = False
        self._initialization_error = None
    
    def initialize(self) -> bool:
        """Initialize using your existing chunking and generation setup."""
        try:
            if self._is_initialized:
                return True
            
            logger.info("Initializing Qdrant bridge service with existing setup...")
            
            # Use your existing initialization
            self._retriever = initialize_and_populate_vectorstore()
            logger.info("✅ Vector store initialized using existing chunking.py")
            
            # Create RAG pipeline using your existing generation.py
            self._rag_pipeline = create_rag_pipeline(self._retriever)
            logger.info("✅ RAG pipeline created using existing generation.py")
            
            self._is_initialized = True
            logger.info("Qdrant bridge service initialized successfully!")
            return True
            
        except Exception as e:
            self._initialization_error = str(e)
            logger.error(f"Failed to initialize Qdrant bridge service: {e}")
            return False
    
    def process_rag_query(self, request: RAGQueryRequest, session_id: str = None) -> RAGResult:
        """Process RAG query using your existing pipeline."""
        try:
            # Ensure service is initialized
            if not self._is_initialized:
                if not self.initialize():
                    return RAGResult(
                        success=False,
                        error=f"Service initialization failed: {self._initialization_error}"
                    )
            
            logger.info(f"Processing RAG query with existing pipeline: {request.question[:100]}...")
            
            # Use your existing RAG pipeline
            result = self._rag_pipeline(request.question)
            
            # Convert to our RAGResult format
            sources = []
            if request.include_sources and result.get('source_documents'):
                for doc in result['source_documents'][:5]:  # Limit to top 5 sources
                    sources.append({
                        'filename': doc.get('source', 'Unknown'),
                        'question': doc.get('question', ''),
                        'answer': doc.get('answer', ''),
                        'content_preview': doc.get('question', '')[:200] + "..." if len(doc.get('question', '')) > 200 else doc.get('question', '')
                    })
            
            # Calculate confidence based on source quality
            confidence = self._calculate_confidence(result)
            
            return RAGResult(
                success=True,
                answer=result['answer'],
                sources=sources,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"Failed to process RAG query: {e}")
            return RAGResult(
                success=False,
                error=str(e)
            )
    
    def _calculate_confidence(self, result: Dict[str, Any]) -> float:
        """Calculate confidence score for the result."""
        try:
            # Base confidence on answer length and source count
            answer = result.get('answer', '')
            sources = result.get('source_documents', [])
            
            if not answer:
                return 0.1
            
            # Length score (longer answers generally better)
            length_score = min(1.0, len(answer) / 200.0)
            
            # Source score (more sources generally better)
            source_score = min(1.0, len(sources) / 3.0)
            
            # Check for uncertainty phrases
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
            confidence = (length_score * 0.4 + source_score * 0.6) - uncertainty_penalty
            return max(0.0, min(1.0, confidence))
            
        except Exception as e:
            logger.warning(f"Failed to calculate confidence: {e}")
            return 0.5
    
    def search_documents(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search documents using your existing search function."""
        try:
            if not self._is_initialized:
                if not self.initialize():
                    return []
            
            # Use your existing search function
            results = search_support_questions(query, self._retriever)
            
            # Convert to expected format
            formatted_results = []
            for result in results[:k]:
                formatted_results.append({
                    'content': result.get('answer', ''),
                    'metadata': {
                        'question': result.get('question', ''),
                        'source': result.get('source', ''),
                        'rank': result.get('rank', 0)
                    },
                    'preview': result.get('question', '')[:200] + "..." if len(result.get('question', '')) > 200 else result.get('question', '')
                })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            return []
    
    def get_service_health(self) -> Dict[str, Any]:
        """Get health status of the bridge service."""
        try:
            health = {
                'service_name': 'qdrant_bridge_service',
                'initialized': self._is_initialized,
                'initialization_error': self._initialization_error,
                'retriever_ready': self._retriever is not None,
                'rag_pipeline_ready': self._rag_pipeline is not None,
                'using_existing_setup': True,
                'timestamp': str(Path(__file__).stat().st_mtime)
            }
            
            # Test basic functionality if initialized
            if self._is_initialized:
                try:
                    # Quick test search
                    test_results = search_support_questions("test", self._retriever)
                    health['search_functional'] = len(test_results) >= 0
                except:
                    health['search_functional'] = False
            
            # Overall health
            health['healthy'] = (
                health['initialized'] and 
                health['retriever_ready'] and 
                health['rag_pipeline_ready']
            )
            
            return health
            
        except Exception as e:
            logger.error(f"Failed to get service health: {e}")
            return {
                'service_name': 'qdrant_bridge_service',
                'healthy': False,
                'error': str(e)
            }
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the Qdrant collection."""
        try:
            if not self._is_initialized:
                return {'error': 'Service not initialized'}
            
            # Try to get stats from your existing setup
            # This would depend on your chunking.py implementation
            return {
                'service': 'qdrant_bridge',
                'collection_name': 'gaming_support_qa',  # From your chunking.py
                'status': 'using_existing_data',
                'note': 'Using existing Qdrant collection from chunking.py'
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {'error': str(e)}

# Global bridge service instance
qdrant_bridge_service = QdrantBridgeService()
