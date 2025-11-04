"""
Single inference module for real-time predictions.

Used by:
- Label Studio ML Backend for interactive labeling
- API endpoints for single-request inference

This is separate from the batch worker to avoid conflicts.
"""

import time
from typing import Dict, Any, List, Optional, cast
from vllm import LLM, SamplingParams
from pathlib import Path

from core.config import settings
from core.batch_app.logging_config import get_logger
from core.batch_app.database import SessionLocal, ModelRegistry

logger = get_logger(__name__)


class InferenceEngine:
    """
    Lightweight inference engine for single requests.
    
    Unlike the batch worker, this:
    - Keeps model loaded in memory
    - Processes single requests quickly
    - Doesn't do chunking or batching
    - Optimized for low latency
    """
    
    def __init__(self):
        self.current_llm: Optional[LLM] = None
        self.current_model: Optional[str] = None
        self.load_time: Optional[float] = None
    
    def load_model(self, model_id: str) -> None:
        """
        Load model if not already loaded.
        
        Args:
            model_id: Model identifier (HuggingFace ID or local path)
        """
        # If model already loaded, skip
        if self.current_model == model_id and self.current_llm is not None:
            logger.info(f"Model {model_id} already loaded, reusing")
            return
        
        logger.info(f"Loading model: {model_id}")
        start_time = time.time()
        
        # Check if model is in registry (get local path if GGUF)
        db = SessionLocal()
        try:
            model_entry = db.query(ModelRegistry).filter(
                ModelRegistry.model_id == model_id
            ).first()
            
            if model_entry and model_entry.local_path:
                # Use local GGUF file
                model_path = model_entry.local_path
                logger.info(f"Using local model: {model_path}")
            else:
                # Use HuggingFace model ID
                model_path = model_id
                logger.info(f"Using HuggingFace model: {model_path}")
        finally:
            db.close()
        
        # Configure vLLM
        vllm_config = {
            "model": model_path,
            "gpu_memory_utilization": settings.GPU_MEMORY_UTILIZATION,
            "max_model_len": 8192,  # Reasonable default for single inference
            "trust_remote_code": True,
        }
        
        # Load model
        try:
            self.current_llm = LLM(**cast(Any, vllm_config))
            self.current_model = model_id
            self.load_time = time.time() - start_time
            logger.info(f"Model loaded in {self.load_time:.1f}s")
        except Exception as e:
            logger.error(f"Failed to load model {model_id}: {e}")
            raise
    
    def generate(
        self,
        prompt: str,
        model_id: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate completion for a single prompt.
        
        Args:
            prompt: Input prompt
            model_id: Model to use
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            stop: Stop sequences
        
        Returns:
            {
                "text": "Generated text",
                "model": "model_id",
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150
                },
                "latency_ms": 1234
            }
        """
        # Load model if needed
        self.load_model(model_id)
        
        # Configure sampling
        sampling_params = SamplingParams(
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop=stop or []
        )
        
        # Generate
        start_time = time.time()
        try:
            if self.current_llm is None:
                return {
                    'error': 'Model not loaded',
                    'model': model_id
                }

            outputs = self.current_llm.generate([prompt], sampling_params)
            latency_ms = (time.time() - start_time) * 1000
            
            # Extract result
            output = outputs[0]
            generated_text = output.outputs[0].text
            
            # Calculate token counts (approximate)
            prompt_tokens = len(output.prompt_token_ids) if hasattr(output, 'prompt_token_ids') and output.prompt_token_ids is not None else 0
            completion_tokens = len(output.outputs[0].token_ids) if hasattr(output.outputs[0], 'token_ids') else 0
            
            return {
                "text": generated_text,
                "model": model_id,
                "usage": {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens
                },
                "latency_ms": int(latency_ms)
            }
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            raise
    
    def generate_chat(
        self,
        messages: List[Dict[str, str]],
        model_id: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        stop: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate completion for chat messages.
        
        Args:
            messages: List of {"role": "user/assistant/system", "content": "..."}
            model_id: Model to use
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            stop: Stop sequences
        
        Returns:
            Same format as generate()
        """
        # Convert messages to prompt
        # Simple format: concatenate with role prefixes
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        prompt_parts.append("Assistant:")  # Prompt for response
        prompt = "\n\n".join(prompt_parts)
        
        # Generate
        return self.generate(
            prompt=prompt,
            model_id=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop=stop
        )
    
    def unload_model(self) -> None:
        """Unload current model to free GPU memory."""
        if self.current_llm is not None:
            logger.info(f"Unloading model: {self.current_model}")
            del self.current_llm
            self.current_llm = None
            self.current_model = None
            self.load_time = None
            
            # Force garbage collection
            import gc
            gc.collect()
            
            # Clear CUDA cache
            try:
                import torch
                torch.cuda.empty_cache()
            except:
                pass


# Global inference engine instance
_inference_engine: Optional[InferenceEngine] = None


def get_inference_engine() -> InferenceEngine:
    """Get or create global inference engine instance."""
    global _inference_engine
    if _inference_engine is None:
        _inference_engine = InferenceEngine()
    return _inference_engine

