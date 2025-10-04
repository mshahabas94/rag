"""
Conversation memory service integrating LangChain's ConversationBufferMemory with persistent storage.
"""

import logging
from typing import Dict, Any, List, Optional
from langchain.memory import ConversationBufferMemory
from langchain.memory.chat_memory import BaseChatMemory
from langchain.schema import HumanMessage, AIMessage, BaseMessage

from services.chat_database_service import chat_db_service

logger = logging.getLogger(__name__)

class PersistentConversationMemory(ConversationBufferMemory):
    """Custom conversation memory that persists to database."""
    
    # Define session_id as a class field for Pydantic compatibility
    session_id: str = ""
    
    def __init__(self, session_id: str, return_messages: bool = True, **kwargs):
        # Initialize the parent class first with session_id as a field
        super().__init__(
            return_messages=return_messages,
            memory_key="history",
            human_prefix="Human",
            ai_prefix="Assistant",
            **kwargs
        )
        
        # Set session_id using object.__setattr__ to bypass Pydantic validation
        object.__setattr__(self, 'session_id', session_id)
        
        # Load existing messages from database
        self._load_messages_from_db()
    
    def _load_messages_from_db(self):
        """Load existing messages from database into memory."""
        try:
            messages = chat_db_service.get_session_messages(self.session_id)
            
            # Clear existing messages
            self.chat_memory.clear()
            
            # Add messages to memory
            for msg in messages:
                if msg['role'] == 'user':
                    self.chat_memory.add_user_message(msg['content'])
                else:
                    self.chat_memory.add_ai_message(msg['content'])
                    
            logger.info(f"Loaded {len(messages)} messages from session {self.session_id}")
            
        except Exception as e:
            logger.error(f"Failed to load messages from database: {e}")
            raise
    
    def _convert_message_to_dict(self, message: BaseMessage) -> Dict[str, Any]:
        """Convert a LangChain message to our database format."""
        return {
            'role': 'user' if isinstance(message, HumanMessage) else 'assistant',
            'content': message.content
        }
    
    def save_context(self, inputs: Dict[str, Any], outputs: Dict[str, Any]) -> None:
        """Save context from this conversation turn to memory and database."""
        try:
            # Get input/output text
            input_text = inputs.get('input', inputs.get('question'))
            output_text = outputs.get('output', outputs.get('answer'))
            
            if input_text:
                # Save user message
                chat_db_service.add_message(
                    session_id=self.session_id,
                    role='user',
                    content=input_text
                )
                self.chat_memory.add_user_message(input_text)
            
            if output_text:
                # Save assistant message
                chat_db_service.add_message(
                    session_id=self.session_id,
                    role='assistant',
                    content=output_text,
                    metadata=outputs.get('metadata', {})  # Store any additional metadata
                )
                self.chat_memory.add_ai_message(output_text)
                
        except Exception as e:
            logger.error(f"Failed to save context: {e}")
            raise
    
    def load_memory_variables(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Load memory variables from the stored context."""
        try:
            if self.return_messages:
                return {self.memory_key: self.chat_memory.messages}
            
            # Get string buffer of messages
            buffer = ''
            for msg in self.chat_memory.messages:
                role = self.human_prefix if isinstance(msg, HumanMessage) else self.ai_prefix
                buffer += f"{role}: {msg.content}\n"
            
            return {self.memory_key: buffer.strip()}
            
        except Exception as e:
            logger.error(f"Failed to load memory variables: {e}")
            raise
    
    def clear(self) -> None:
        """Clear memory contents from both memory and database."""
        try:
            self.chat_memory.clear()
            chat_db_service.clear_session_messages(self.session_id)
            logger.info(f"Cleared memory for session {self.session_id}")
            
        except Exception as e:
            logger.error(f"Failed to clear memory: {e}")
            raise
    
    @property
    def memory_variables(self) -> List[str]:
        """Return memory variables."""
        return [self.memory_key]
    
    def get_chat_history(self) -> List[Dict[str, Any]]:
        """Get formatted chat history for display."""
        messages = []
        for msg in self.chat_memory.messages:
            messages.append(self._convert_message_to_dict(msg))
        return messages
    
    class Config:
        """Pydantic config to allow arbitrary types."""
        arbitrary_types_allowed = True
        extra = 'allow'  # Allow extra fields like session_id