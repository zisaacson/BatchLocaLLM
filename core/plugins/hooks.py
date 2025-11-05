"""
Plugin Hook System - Lifecycle hooks for plugins.

Allows plugins to hook into various lifecycle events:
- Task creation/update
- Annotation submission
- Export operations
- Batch job completion
- Model loading
"""

from typing import Any, Callable, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class HookRegistry:
    """Registry for plugin hooks"""
    
    def __init__(self):
        """Initialize hook registry"""
        self.hooks: Dict[str, List[Callable]] = {}
    
    def register(self, hook_name: str, callback: Callable, priority: int = 100):
        """
        Register a callback for a hook
        
        Args:
            hook_name: Hook identifier
            callback: Callback function
            priority: Priority (lower = earlier, default 100)
        """
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
        
        self.hooks[hook_name].append({
            "callback": callback,
            "priority": priority
        })
        
        # Sort by priority
        self.hooks[hook_name].sort(key=lambda x: x["priority"])
        
        logger.debug(f"Registered hook: {hook_name} (priority {priority})")
    
    def trigger(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """
        Trigger all callbacks for a hook
        
        Args:
            hook_name: Hook identifier
            *args: Positional arguments to pass to callbacks
            **kwargs: Keyword arguments to pass to callbacks
            
        Returns:
            List of results from all callbacks
        """
        results = []
        
        if hook_name not in self.hooks:
            return results
        
        logger.debug(f"Triggering hook: {hook_name}")
        
        for hook_info in self.hooks[hook_name]:
            callback = hook_info["callback"]
            try:
                result = callback(*args, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Hook {hook_name} callback failed: {e}")
        
        return results
    
    def trigger_first(self, hook_name: str, *args, **kwargs) -> Optional[Any]:
        """
        Trigger hook and return first non-None result
        
        Args:
            hook_name: Hook identifier
            *args: Positional arguments to pass to callbacks
            **kwargs: Keyword arguments to pass to callbacks
            
        Returns:
            First non-None result or None
        """
        results = self.trigger(hook_name, *args, **kwargs)
        for result in results:
            if result is not None:
                return result
        return None
    
    def trigger_filter(self, hook_name: str, value: Any, *args, **kwargs) -> Any:
        """
        Trigger hook as a filter chain (each callback modifies the value)
        
        Args:
            hook_name: Hook identifier
            value: Initial value to filter
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments
            
        Returns:
            Filtered value
        """
        if hook_name not in self.hooks:
            return value
        
        logger.debug(f"Triggering filter hook: {hook_name}")
        
        for hook_info in self.hooks[hook_name]:
            callback = hook_info["callback"]
            try:
                value = callback(value, *args, **kwargs)
            except Exception as e:
                logger.error(f"Filter hook {hook_name} callback failed: {e}")
        
        return value
    
    def unregister(self, hook_name: str, callback: Callable):
        """
        Unregister a callback from a hook
        
        Args:
            hook_name: Hook identifier
            callback: Callback function to remove
        """
        if hook_name not in self.hooks:
            return
        
        self.hooks[hook_name] = [
            h for h in self.hooks[hook_name]
            if h["callback"] != callback
        ]
        
        logger.debug(f"Unregistered hook: {hook_name}")
    
    def clear(self, hook_name: Optional[str] = None):
        """
        Clear all hooks or a specific hook
        
        Args:
            hook_name: Hook identifier (None = clear all)
        """
        if hook_name is None:
            self.hooks.clear()
            logger.debug("Cleared all hooks")
        elif hook_name in self.hooks:
            del self.hooks[hook_name]
            logger.debug(f"Cleared hook: {hook_name}")
    
    def list_hooks(self) -> List[str]:
        """
        List all registered hook names
        
        Returns:
            List of hook names
        """
        return list(self.hooks.keys())


# Global hook registry instance
hook_registry = HookRegistry()


# Available hooks:

def on_task_create(callback: Callable, priority: int = 100):
    """
    Register callback for task creation
    
    Callback signature: (task_data: dict) -> dict
    """
    hook_registry.register("on_task_create", callback, priority)


def on_task_update(callback: Callable, priority: int = 100):
    """
    Register callback for task update
    
    Callback signature: (task_id: str, updates: dict) -> dict
    """
    hook_registry.register("on_task_update", callback, priority)


def on_annotation_submit(callback: Callable, priority: int = 100):
    """
    Register callback for annotation submission
    
    Callback signature: (task_id: str, annotation: dict) -> None
    """
    hook_registry.register("on_annotation_submit", callback, priority)


def on_export(callback: Callable, priority: int = 100):
    """
    Register callback for export operation
    
    Callback signature: (tasks: list, format: str, **kwargs) -> list
    """
    hook_registry.register("on_export", callback, priority)


def on_batch_complete(callback: Callable, priority: int = 100):
    """
    Register callback for batch job completion
    
    Callback signature: (batch_id: str, results: dict) -> None
    """
    hook_registry.register("on_batch_complete", callback, priority)


def on_model_load(callback: Callable, priority: int = 100):
    """
    Register callback for model loading
    
    Callback signature: (model_id: str) -> None
    """
    hook_registry.register("on_model_load", callback, priority)


def on_response_parse(callback: Callable, priority: int = 100):
    """
    Register callback for response parsing
    
    Callback signature: (response: str, schema_type: str) -> dict
    """
    hook_registry.register("on_response_parse", callback, priority)


def on_quality_rate(callback: Callable, priority: int = 100):
    """
    Register callback for quality rating
    
    Callback signature: (task_id: str, rating: dict) -> None
    """
    hook_registry.register("on_quality_rate", callback, priority)


# Hook name constants
HOOK_TASK_CREATE = "on_task_create"
HOOK_TASK_UPDATE = "on_task_update"
HOOK_ANNOTATION_SUBMIT = "on_annotation_submit"
HOOK_EXPORT = "on_export"
HOOK_BATCH_COMPLETE = "on_batch_complete"
HOOK_MODEL_LOAD = "on_model_load"
HOOK_RESPONSE_PARSE = "on_response_parse"
HOOK_QUALITY_RATE = "on_quality_rate"

