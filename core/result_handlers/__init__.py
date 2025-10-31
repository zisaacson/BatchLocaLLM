"""
Result Handlers - Plugin system for processing batch results.

This module provides an extensible plugin architecture for automatically
processing batch results when jobs complete.

Built-in handlers:
- webhook: Send HTTP POST notification (always enabled)
- label_studio: Import to Label Studio for curation (optional)

Custom handlers:
Users can create custom handlers by subclassing ResultHandler.
See examples/ directory for templates.
"""

from .base import ResultHandler, ResultHandlerRegistry, get_registry, register_handler
from .webhook import WebhookHandler

# Import optional handlers (only if dependencies available)
try:
    from .label_studio import LabelStudioHandler
    LABEL_STUDIO_AVAILABLE = True
except ImportError:
    LABEL_STUDIO_AVAILABLE = False


__all__ = [
    'ResultHandler',
    'ResultHandlerRegistry',
    'get_registry',
    'register_handler',
    'WebhookHandler',
    'LabelStudioHandler' if LABEL_STUDIO_AVAILABLE else None,
]


def setup_default_handlers(config: dict = None) -> None:
    """
    Register default result handlers.
    
    Args:
        config: Optional configuration dictionary
    """
    config = config or {}
    
    # Always register webhook handler
    webhook_handler = WebhookHandler(config.get('webhook', {}))
    register_handler(webhook_handler)
    
    # Register Label Studio handler if available and configured
    if LABEL_STUDIO_AVAILABLE:
        ls_config = config.get('label_studio', {})
        if ls_config.get('enabled', False):
            ls_handler = LabelStudioHandler(ls_config)
            register_handler(ls_handler)

