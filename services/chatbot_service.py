"""
Enhanced RAG chatbot service integrating conversation memory with RAG.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from config.rag_config import rag_config
from models.schemas import RAGQueryRequest, RAGResult
from services.rag_service import rag_service
from services.chat_database_service import chat_db_service
from services.conversation_memory_service import PersistentConversationMemory

logger = logging.getLogger(__name__)

class ChatbotService:
    """Service for handling conversational RAG interactions."""
    
    def __init__(self):
        self.rag_service = rag_service
        self._session_memories: Dict[str, PersistentConversationMemory] = {}
    
    def create_session(self, session_name: Optional[str] = None) -> str:
        """Create a new chat session."""
        try:
            # Create session in database
            session_id = chat_db_service.create_session(session_name=session_name)
            
            # Initialize memory for session
            self._get_or_create_memory(session_id)
            
            logger.info(f"Created new chat session: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to create chat session: {e}")
            raise
    
    def _get_or_create_memory(self, session_id: str) -> PersistentConversationMemory:
        """Get or create conversation memory for a session."""
        if session_id not in self._session_memories:
            memory = PersistentConversationMemory(session_id=session_id)
            self._session_memories[session_id] = memory
        return self._session_memories[session_id]
    
    def process_message(self, session_id: str, message: str) -> Dict[str, Any]:
        """Process a user message with RAG and conversation memory."""
        try:
            # Get session memory
            memory = self._get_or_create_memory(session_id)
            
            # Create RAG request
            request = RAGQueryRequest(
                question=message,
                include_sources=True  # Always include sources for tracking
            )
            
            # Get conversation history
            conversation_context = memory.load_memory_variables({})
            
            # Enhance prompt with conversation context
            enhanced_prompt = self._build_enhanced_prompt(
                question=message,
                conversation=conversation_context.get('history', '')
            )
            request.question = enhanced_prompt
            
            # Process through RAG
            result = self.rag_service.process_rag_query(request, session_id)
            
            if result.success:
                # Save interaction to memory
                memory.save_context(
                    inputs={'question': message},
                    outputs={
                        'answer': result.answer,
                        'metadata': {'sources': result.sources}
                    }
                )
                
                response = {
                    'success': True,
                    'answer': result.answer,
                    'sources': result.sources,
                    'confidence': result.confidence
                }
            else:
                response = {
                    'success': False,
                    'error': result.error
                }
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to process message: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _build_enhanced_prompt(self, question: str, conversation: str) -> str:
        """Build an enhanced prompt including conversation context."""
        prompt = f"""Context from previous conversation:
{conversation}

Current question: {question}

Please provide a response that:
1. Is consistent with the previous conversation
2. Directly answers the current question
3. Uses relevant information from the knowledge base
"""
        return prompt
    
    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get chat history for a session."""
        try:
            memory = self._get_or_create_memory(session_id)
            return memory.get_chat_history()
            
        except Exception as e:
            logger.error(f"Failed to get session history: {e}")
            return []
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """Get all available chat sessions."""
        return chat_db_service.get_all_sessions()
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific session."""
        return chat_db_service.get_session(session_id)
    
    def update_session_name(self, session_id: str, name: str) -> bool:
        """Update the name of a chat session."""
        return chat_db_service.update_session_name(session_id, name)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session and its memory."""
        try:
            # Remove from memory cache
            self._session_memories.pop(session_id, None)
            
            # Delete from database
            return chat_db_service.delete_session(session_id)
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    def clear_session_history(self, session_id: str) -> bool:
        """Clear chat history for a session but keep the session."""
        try:
            # Clear memory
            if session_id in self._session_memories:
                self._session_memories[session_id].clear()
            
            # Clear database
            return chat_db_service.clear_session_messages(session_id)
            
        except Exception as e:
            logger.error(f"Failed to clear session history: {e}")
            return False

# Global service instance
chatbot_service = ChatbotService()