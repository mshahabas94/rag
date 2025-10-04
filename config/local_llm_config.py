"""
Local LLM configuration using llama.cpp for both Vanna and RAG.
Replaces OpenAI dependency with local model inference.
"""

import os
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from llama_cpp import Llama

logger = logging.getLogger(__name__)

class LocalLLMConfig:
    """Configuration for local LLaMA model using llama.cpp."""
    
    def __init__(self):
        self.model_path = os.getenv('LOCAL_MODEL_PATH', 'llama.cpp/models/llama-3.1-8b-q4.gguf')
        self.n_ctx = int(os.getenv('LOCAL_MODEL_CTX', '4096'))
        self.n_gpu_layers = int(os.getenv('LOCAL_MODEL_GPU_LAYERS', '-1'))
        self.temperature = float(os.getenv('LOCAL_MODEL_TEMPERATURE', '0.1'))
        self.max_tokens = int(os.getenv('LOCAL_MODEL_MAX_TOKENS', '512'))
        
        self._llm_instance = None
        self._is_initialized = False
    
    def get_llm_instance(self) -> Llama:
        """Get or create LLaMA instance."""
        if self._llm_instance is None:
            try:
                model_full_path = Path(self.model_path)
                if not model_full_path.is_absolute():
                    # Make path relative to project root
                    model_full_path = Path(__file__).parent.parent / self.model_path
                
                if not model_full_path.exists():
                    raise FileNotFoundError(f"Model file not found: {model_full_path}")
                
                logger.info(f"Loading LLaMA model from: {model_full_path}")
                
                self._llm_instance = Llama(
                    model_path=str(model_full_path),
                    n_ctx=self.n_ctx,
                    n_gpu_layers=self.n_gpu_layers,
                    verbose=False
                )
                
                self._is_initialized = True
                logger.info("LLaMA model loaded successfully!")
                
            except Exception as e:
                logger.error(f"Failed to load LLaMA model: {e}")
                raise
        
        return self._llm_instance
    
    def generate_response(self, prompt: str, max_tokens: Optional[int] = None, 
                         temperature: Optional[float] = None) -> str:
        """Generate response using local LLaMA model."""
        try:
            llm = self.get_llm_instance()
            
            response = llm(
                prompt=prompt,
                max_tokens=max_tokens or self.max_tokens,
                temperature=temperature or self.temperature,
                top_p=0.9,
                echo=False,
                stop=["</s>", "###", "\n\n\n", "Human:", "Assistant:"]
            )
            
            return response['choices'][0]['text'].strip()
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Error generating response: {str(e)}"
    
    def generate_sql_explanation(self, sql: str) -> str:
        """Generate SQL explanation using local model."""
        prompt = f"""<|start_header_id|>system<|end_header_id|>
You are a helpful SQL expert. Explain the following SQL query in simple terms for a business user.

<|start_header_id|>user<|end_header_id|>
Please explain this SQL query:

{sql}

<|start_header_id|>assistant<|end_header_id|>
This SQL query"""
        
        return self.generate_response(prompt, max_tokens=256)
    
    def generate_sql_from_question(self, question: str, schema_context: str = "") -> str:
        """Generate SQL from natural language question."""
        prompt = f"""<|start_header_id|>system<|end_header_id|>
You are an expert SQL generator for e-commerce databases. Generate ONLY valid SQL SELECT statements.

Database Schema Context:
{schema_context}

Rules:
- Only generate SELECT statements
- Always include customer isolation (WHERE customer_id = ? OR customer_email = ?)
- Use proper table and column names
- Return only the SQL query, no explanations

<|start_header_id|>user<|end_header_id|>
Generate SQL for: {question}

<|start_header_id|>assistant<|end_header_id|>
SELECT"""
        
        response = self.generate_response(prompt, max_tokens=256)
        
        # Ensure response starts with SELECT
        if not response.upper().startswith('SELECT'):
            response = 'SELECT ' + response
        
        return response
    
    def generate_rag_answer(self, question: str, context: str) -> str:
        """Generate answer for RAG queries using retrieved context."""
        prompt = f"""<|start_header_id|>system<|end_header_id|>
You are a helpful customer service assistant for an e-commerce platform. 
Use the following context to answer the user's question accurately and helpfully.
If the answer isn't in the context, say you don't know but offer to help in other ways.

Context:
{context}

<|start_header_id|>user<|end_header_id|>
{question}

<|start_header_id|>assistant<|end_header_id|>"""
        
        return self.generate_response(prompt, max_tokens=512)
    
    def is_initialized(self) -> bool:
        """Check if the model is initialized."""
        return self._is_initialized
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        return {
            'model_path': self.model_path,
            'context_size': self.n_ctx,
            'gpu_layers': self.n_gpu_layers,
            'initialized': self._is_initialized,
            'temperature': self.temperature,
            'max_tokens': self.max_tokens
        }

# Global instance
local_llm_config = LocalLLMConfig()


