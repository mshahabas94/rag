"""
Initialize the chat database with required tables.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import logging
from sqlalchemy import text
from config.database import db_config 

# Configure logging to show output in console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def init_chat_database():
    """Initialize the chat database and required tables."""
    try:
        # Update database name to chatmemory
        db_config.database = 'chatmemory'
        
        # Read schema file
        with open('data/chat_schema.sql', 'r') as f:
            schema_sql = f.read()
        
        # Split into individual statements
        statements = [s.strip() for s in schema_sql.split(';') if s.strip()]
        
        # Execute each statement
        with db_config.get_connection() as conn:
            for statement in statements:
                conn.execute(text(statement))
            conn.commit()
            
        logger.info("Chat database tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize chat database: {e}")
        return False

if __name__ == "__main__":
    init_chat_database()