"""
Chat database service for managing persistent chat sessions and messages.
Handles CRUD operations for chat sessions and message storage.
"""

import logging
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime
import json

from sqlalchemy import text
from config.database import db_config

logger = logging.getLogger(__name__)

class ChatDatabaseService:
    """Service for managing chat sessions and messages in the database."""
    
    def create_session(self, session_name: Optional[str] = None, metadata: Optional[Dict] = None) -> str:
        """Create a new chat session."""
        try:
            session_id = str(uuid.uuid4())
            with db_config.get_connection() as conn:
                query = text("""
                    INSERT INTO chat_sessions (session_id, session_name, metadata)
                    VALUES (:session_id, :session_name, :metadata)
                """)
                
                conn.execute(query, {
                    'session_id': session_id,
                    'session_name': session_name,
                    'metadata': json.dumps(metadata or {})
                })
                conn.commit()
                
                logger.info(f"Created new chat session: {session_id}")
                return session_id
                
        except Exception as e:
            logger.error(f"Failed to create chat session: {e}")
            raise
    
    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get all chat sessions ordered by most recent first."""
        try:
            with db_config.get_connection() as conn:
                query = text("""
                    SELECT session_id, created_at, updated_at, session_name, metadata
                    FROM chat_sessions
                    ORDER BY updated_at DESC
                """)
                
                result = conn.execute(query)
                sessions = []
                
                for row in result:
                    session = {
                        'session_id': row[0],
                        'created_at': row[1].isoformat(),
                        'updated_at': row[2].isoformat(),
                        'session_name': row[3],
                        'metadata': json.loads(row[4]) if row[4] else {}
                    }
                    sessions.append(session)
                
                return sessions
                
        except Exception as e:
            logger.error(f"Failed to get chat sessions: {e}")
            return []
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific chat session by ID."""
        try:
            with db_config.get_connection() as conn:
                query = text("""
                    SELECT session_id, created_at, updated_at, session_name, metadata
                    FROM chat_sessions
                    WHERE session_id = :session_id
                """)
                
                result = conn.execute(query, {'session_id': session_id})
                row = result.fetchone()
                
                if row:
                    return {
                        'session_id': row[0],
                        'created_at': row[1].isoformat(),
                        'updated_at': row[2].isoformat(),
                        'session_name': row[3],
                        'metadata': json.loads(row[4]) if row[4] else {}
                    }
                return None
                
        except Exception as e:
            logger.error(f"Failed to get chat session {session_id}: {e}")
            return None
    
    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None) -> str:
        """Add a new message to a chat session."""
        try:
            message_id = str(uuid.uuid4())
            with db_config.get_connection() as conn:
                query = text("""
                    INSERT INTO chat_messages (message_id, session_id, role, content, metadata)
                    VALUES (:message_id, :session_id, :role, :content, :metadata)
                """)
                
                conn.execute(query, {
                    'message_id': message_id,
                    'session_id': session_id,
                    'role': role,
                    'content': content,
                    'metadata': json.dumps(metadata or {})
                })
                
                # Update session updated_at timestamp
                update_query = text("""
                    UPDATE chat_sessions
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = :session_id
                """)
                conn.execute(update_query, {'session_id': session_id})
                
                conn.commit()
                logger.info(f"Added message {message_id} to session {session_id}")
                return message_id
                
        except Exception as e:
            logger.error(f"Failed to add message to session {session_id}: {e}")
            raise
    
    def get_session_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a chat session in chronological order."""
        try:
            with db_config.get_connection() as conn:
                query = text("""
                    SELECT message_id, role, content, created_at, metadata
                    FROM chat_messages
                    WHERE session_id = :session_id
                    ORDER BY created_at ASC
                """)
                
                result = conn.execute(query, {'session_id': session_id})
                messages = []
                
                for row in result:
                    message = {
                        'message_id': row[0],
                        'role': row[1],
                        'content': row[2],
                        'created_at': row[3].isoformat(),
                        'metadata': json.loads(row[4]) if row[4] else {}
                    }
                    messages.append(message)
                
                return messages
                
        except Exception as e:
            logger.error(f"Failed to get messages for session {session_id}: {e}")
            return []
    
    def update_session_name(self, session_id: str, session_name: str) -> bool:
        """Update the name of a chat session."""
        try:
            with db_config.get_connection() as conn:
                query = text("""
                    UPDATE chat_sessions
                    SET session_name = :session_name
                    WHERE session_id = :session_id
                """)
                
                result = conn.execute(query, {
                    'session_id': session_id,
                    'session_name': session_name
                })
                
                conn.commit()
                return result.rowcount > 0
                
        except Exception as e:
            logger.error(f"Failed to update session name for {session_id}: {e}")
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session and all its messages."""
        try:
            with db_config.get_connection() as conn:
                query = text("""
                    DELETE FROM chat_sessions
                    WHERE session_id = :session_id
                """)
                
                result = conn.execute(query, {'session_id': session_id})
                conn.commit()
                
                success = result.rowcount > 0
                if success:
                    logger.info(f"Deleted chat session {session_id}")
                return success
                
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False
    
    def clear_session_messages(self, session_id: str) -> bool:
        """Clear all messages from a chat session but keep the session."""
        try:
            with db_config.get_connection() as conn:
                query = text("""
                    DELETE FROM chat_messages
                    WHERE session_id = :session_id
                """)
                
                result = conn.execute(query, {'session_id': session_id})
                conn.commit()
                
                logger.info(f"Cleared messages from session {session_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to clear messages from session {session_id}: {e}")
            return False

# Global service instance
chat_db_service = ChatDatabaseService()