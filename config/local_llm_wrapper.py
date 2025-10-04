"""
LangChain wrapper for local LLaMA model.
Allows using local llama.cpp model with LangChain chains.
"""

from typing import Any, List, Optional
from langchain.llms.base import LLM
from langchain.callbacks.manager import CallbackManagerForLLMRun
from .local_llm_config import local_llm_config

class LocalLlamaLLM(LLM):
    """LangChain wrapper for local LLaMA model using llama.cpp."""
    
    @property
    def _llm_type(self) -> str:
        return "local_llama"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """Call the local LLaMA model."""
        # Use the local LLM config to generate response
        response = local_llm_config.generate_response(
            prompt=prompt,
            max_tokens=kwargs.get('max_tokens', 512),
            temperature=kwargs.get('temperature', 0.1)
        )
        
        # Handle stop sequences
        if stop:
            for stop_seq in stop:
                if stop_seq in response:
                    response = response.split(stop_seq)[0]
        
        return response
    
    @property
    def _identifying_params(self) -> dict:
        """Get identifying parameters."""
        return {
            "model_path": local_llm_config.model_path,
            "n_ctx": local_llm_config.n_ctx,
            "temperature": local_llm_config.temperature
        }


