"""
Local Vanna implementation using llama.cpp instead of OpenAI.
Custom Vanna class that uses local LLM for SQL generation.
"""

import logging
from typing import Dict, Any, List, Optional
from vanna.base import VannaBase
from .local_llm_config import local_llm_config
from .database import db_config

logger = logging.getLogger(__name__)

class LocalVanna(VannaBase):
    """Custom Vanna implementation using local LLaMA model."""
    
    def __init__(self):
        super().__init__()
        self.local_llm = local_llm_config
        self.training_data = {
            'ddl': [],
            'documentation': [],
            'sql': []
        }
        self._is_trained = False
    
    # ===== Required Abstract Methods from VannaBase =====
    
    def generate_embedding(self, data: str, **kwargs) -> List[float]:
        """Generate embeddings for similarity search (simplified for local use)."""
        # For a simple implementation, we can return a dummy embedding
        # In production, you'd use a proper embedding model
        return [0.0] * 384  # Return zero vector of typical embedding dimension
    
    def add_question_sql(self, question: str, sql: str, **kwargs) -> str:
        """Add a question-SQL pair to training data."""
        self.training_data['sql'].append({
            'question': question,
            'sql': sql
        })
        logger.debug(f"Added SQL training pair: {question[:50]}...")
        self._is_trained = True
        return f"sql_{len(self.training_data['sql'])}"
    
    def add_ddl(self, ddl: str, **kwargs) -> str:
        """Add DDL statement to training data."""
        self.training_data['ddl'].append(ddl)
        logger.debug("Added DDL to training data")
        self._is_trained = True
        return f"ddl_{len(self.training_data['ddl'])}"
    
    def add_documentation(self, documentation: str, **kwargs) -> str:
        """Add documentation to training data."""
        self.training_data['documentation'].append(documentation)
        logger.debug("Added documentation to training data")
        return f"doc_{len(self.training_data['documentation'])}"
    
    def get_similar_question_sql(self, question: str, **kwargs) -> List[Dict[str, Any]]:
        """Get similar question-SQL pairs (simplified - returns most recent)."""
        # In production, you'd use embeddings to find similar questions
        return self.training_data['sql'][-5:] if self.training_data['sql'] else []
    
    def get_related_ddl(self, question: str, **kwargs) -> List[str]:
        """Get related DDL statements."""
        # Return all DDL for now (in production, filter by relevance)
        return self.training_data['ddl']
    
    def get_related_documentation(self, question: str, **kwargs) -> List[str]:
        """Get related documentation."""
        # Return all documentation for now
        return self.training_data['documentation']
    
    def remove_training_data(self, id: str, **kwargs) -> bool:
        """Remove training data by ID."""
        try:
            if id.startswith('sql_'):
                idx = int(id.split('_')[1]) - 1
                if 0 <= idx < len(self.training_data['sql']):
                    self.training_data['sql'].pop(idx)
                    return True
            elif id.startswith('ddl_'):
                idx = int(id.split('_')[1]) - 1
                if 0 <= idx < len(self.training_data['ddl']):
                    self.training_data['ddl'].pop(idx)
                    return True
            elif id.startswith('doc_'):
                idx = int(id.split('_')[1]) - 1
                if 0 <= idx < len(self.training_data['documentation']):
                    self.training_data['documentation'].pop(idx)
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove training data: {e}")
            return False
    
    def submit_prompt(self, prompt: List[Dict[str, str]], **kwargs) -> str:
        """Submit prompt to local LLM."""
        # Convert message format to simple prompt string
        prompt_text = ""
        for message in prompt:
            role = message.get('role', 'user')
            content = message.get('content', '')
            if role == 'system':
                prompt_text += f"<|start_header_id|>system<|end_header_id|>\n{content}\n\n"
            elif role == 'user':
                prompt_text += f"<|start_header_id|>user<|end_header_id|>\n{content}\n\n"
            elif role == 'assistant':
                prompt_text += f"<|start_header_id|>assistant<|end_header_id|>\n{content}\n\n"
        
        return self.local_llm.generate_response(prompt_text, max_tokens=512, temperature=0.1)
    
    def system_message(self, message: str) -> Dict[str, str]:
        """Create a system message."""
        return {"role": "system", "content": message}
    
    def user_message(self, message: str) -> Dict[str, str]:
        """Create a user message."""
        return {"role": "user", "content": message}
    
    def assistant_message(self, message: str) -> Dict[str, str]:
        """Create an assistant message."""
        return {"role": "assistant", "content": message}
    
    # ===== Custom Methods (Your Original Implementation) =====
    
    def connect_to_mysql(self, host: str, dbname: str, user: str, password: str, port: int = 3306):
        """Connect to MySQL database (using existing db_config)."""
        logger.info(f"Using existing database connection to {host}:{port}/{dbname}")
        return True
    
    def train(self, question: str = None, sql: str = None, ddl: str = None, documentation: str = None):
        """Train the model with question-SQL pairs, DDL, or documentation."""
        try:
            if question and sql:
                self.add_question_sql(question, sql)
            
            if ddl:
                self.add_ddl(ddl)
            
            if documentation:
                self.add_documentation(documentation)
            
            return True
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            return False
    
    def generate_sql(self, question: str, customer_id: str = None, customer_email: str = None) -> str:
        """Generate SQL from natural language question using local LLM."""
        try:
            schema_context = self._build_schema_context()
            prompt = self._create_sql_prompt(question, schema_context, customer_id, customer_email)
            sql = self.local_llm.generate_response(prompt, max_tokens=256, temperature=0.1)
            sql = self._clean_generated_sql(sql)
            
            logger.info(f"Generated SQL for question: {question[:50]}...")
            return sql
            
        except Exception as e:
            logger.error(f"SQL generation failed: {e}")
            raise
    
    def generate_explanation(self, sql: str) -> str:
        """Generate explanation for SQL query using local LLM."""
        return self.local_llm.generate_sql_explanation(sql)
    
    def _build_schema_context(self) -> str:
        """Build schema context from training data."""
        context_parts = []
        
        if self.training_data['ddl']:
            context_parts.append("Database Schema:")
            for ddl in self.training_data['ddl'][:2]:
                context_parts.append(ddl[:1000])
        
        if self.training_data['documentation']:
            context_parts.append("\nBusiness Rules:")
            for doc in self.training_data['documentation'][:3]:
                context_parts.append(doc[:500])
        
        if self.training_data['sql']:
            context_parts.append("\nExample Queries:")
            for example in self.training_data['sql'][-5:]:
                context_parts.append(f"Q: {example['question']}")
                context_parts.append(f"SQL: {example['sql']}")
        
        return "\n".join(context_parts)
    
    def _create_sql_prompt(self, question: str, schema_context: str,customer_id: str = None, customer_email: str = None) -> str:

        """Create prompt for SQL generation."""
        customer_filter = ""
        if customer_id:
            customer_filter = f"customer_id = '{customer_id}'"
        elif customer_email:
            customer_filter = f"customer_email = '{customer_email}'"
        else:
            customer_filter = "customer_id = 'CUSTOMER_ID_HERE'"
        prompt = f"""<|start_header_id|>system<|end_header_id|>
You are an expert SQL generator for loaded databases. Generate ONLY valid SQL SELECT statements.

{schema_context}

CRITICAL RULES:
1. Only generate SELECT statements
2. Always include customer isolation in WHERE clause: {customer_filter}
3. Use proper table and column names from the schema
4. For order numbers, use increment_id (customer-facing) not entity_id
5. For financial calculations, use grand_total (final amount paid)
6. Only include orders with status 'complete' or 'processing' for spending totals
7. Return ONLY the SQL query, no explanations or markdown

<|start_header_id|>user<|end_header_id|>
Generate SQL for: {question}

<|start_header_id|>assistant<|end_header_id|>
SELECT"""
        
        return prompt
    
    def _clean_generated_sql(self, sql: str) -> str:
        """Clean and validate generated SQL."""
        if not sql.upper().strip().startswith('SELECT'):
            sql = 'SELECT ' + sql
        
        sql = sql.replace('```sql', '').replace('```', '')
        sql = sql.replace('`', '')
        
        lines = sql.split('\n')
        clean_lines = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith('--') and not line.lower().startswith('this query'):
                clean_lines.append(line)
            elif line.startswith('--'):
                break
        
        sql = ' '.join(clean_lines)
        
        sql_upper = sql.upper()
        if any(keyword in sql_upper for keyword in ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER']):
            raise ValueError("Generated SQL contains forbidden keywords")
        
        return sql.strip()
    
    def get_training_data(self) -> Dict[str, Any]:
        """Get current training data statistics."""
        return {
            'ddl_count': len(self.training_data['ddl']),
            'documentation_count': len(self.training_data['documentation']),
            'sql_examples_count': len(self.training_data['sql']),
            'is_trained': self._is_trained
        }
    
    def is_trained(self) -> bool:
        """Check if model has been trained."""
        return self._is_trained and (
            len(self.training_data['ddl']) > 0 or 
            len(self.training_data['sql']) > 0
        )


def get_local_vanna_instance() -> LocalVanna:
    """Get or create local Vanna instance."""
    if not hasattr(get_local_vanna_instance, '_instance'):
        get_local_vanna_instance._instance = LocalVanna()
    return get_local_vanna_instance._instance