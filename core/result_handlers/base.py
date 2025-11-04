"""
Base class for result handlers.

Result handlers are plugins that process batch results after completion.
They enable automatic integration with your data pipeline.

Examples:
- Import to Label Studio for curation
- Insert into your database
- Upload to S3
- Send to your ML pipeline
- Custom processing logic

To create a custom handler:
1. Subclass ResultHandler
2. Implement handle() method
3. Implement enabled() method
4. Register in config.py
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ResultHandler(ABC):
    """
    Abstract base class for result handlers.
    
    Result handlers are called when a batch job completes,
    allowing you to automatically process results.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the handler.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
    
    @abstractmethod
    def name(self) -> str:
        """
        Return the handler name.
        
        Returns:
            Handler name (e.g., "webhook", "label_studio", "custom")
        """
        pass
    
    @abstractmethod
    def enabled(self, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Check if this handler is enabled.

        Args:
            metadata: Optional metadata to determine if handler should run

        Returns:
            True if handler should run, False otherwise
        """
        pass
    
    @abstractmethod
    def handle(
        self,
        batch_id: str,
        results: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Process batch results.
        
        Args:
            batch_id: Unique batch identifier
            results: List of result objects in JSONL format
                Each result has:
                - custom_id: User-provided identifier
                - response: LLM response
                - error: Error message (if failed)
            metadata: User-provided metadata from batch submission
            
        Returns:
            True if handled successfully, False otherwise
        """
        pass
    
    def on_error(self, error: Exception) -> None:
        """
        Called when handler raises an exception.
        
        Override this to implement custom error handling.
        
        Args:
            error: The exception that was raised
        """
        logger.error(f"Handler {self.name()} failed: {error}")


class ResultHandlerRegistry:
    """
    Registry for result handlers.
    
    Manages registration and execution of result handlers.
    """
    
    def __init__(self):
        self.handlers: List[ResultHandler] = []
    
    def register(self, handler: ResultHandler) -> None:
        """
        Register a result handler.

        Args:
            handler: Handler instance to register
        """
        self.handlers.append(handler)
        logger.info(f"Registered result handler: {handler.name()}")
    
    def process_results(
        self,
        batch_id: str,
        results: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> Dict[str, bool]:
        """
        Process results through all enabled handlers.
        
        Args:
            batch_id: Unique batch identifier
            results: List of result objects
            metadata: User-provided metadata
            
        Returns:
            Dictionary mapping handler names to success status
        """
        handler_results: Dict[str, bool] = {}

        for handler in self.handlers:
            if not handler.enabled(metadata):
                logger.debug(f"Handler {handler.name()} is disabled, skipping")
                continue

            try:
                logger.info(f"Running handler: {handler.name()}")
                success = handler.handle(batch_id, results, metadata)
                handler_results[handler.name()] = success

                if success:
                    logger.info(f"✅ Handler {handler.name()} completed successfully")
                else:
                    logger.warning(f"⚠️  Handler {handler.name()} returned False")

            except Exception as e:
                logger.error(f"❌ Handler {handler.name()} failed: {e}")
                handler.on_error(e)
                handler_results[handler.name()] = False
        
        return handler_results


# Global registry instance
_registry = ResultHandlerRegistry()


def get_registry() -> ResultHandlerRegistry:
    """Get the global result handler registry."""
    return _registry


def register_handler(handler: ResultHandler) -> None:
    """
    Register a result handler with the global registry.
    
    Args:
        handler: Handler instance to register
    """
    _registry.register(handler)

