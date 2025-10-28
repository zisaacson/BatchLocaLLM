"""
Context Window and Memory Management

BUSINESS_CONTEXT: Intelligent context window management for batch processing
- Monitors context length and VRAM usage in real-time
- Implements adaptive trimming strategies based on model capabilities
- Prevents OOM errors while maximizing context utilization
- Supports multiple trimming strategies (sliding window, importance-based, etc.)

ARCHITECTURE:
- ContextWindow: Tracks current context state and enforces limits
- MemoryMonitor: Monitors VRAM usage via nvidia-smi
- ContextTrimmer: Implements various trimming strategies
- AdaptiveManager: Dynamically adjusts limits based on observed behavior
"""

import logging
import subprocess
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TrimStrategy(Enum):
    """Context trimming strategies"""
    SLIDING_WINDOW = "sliding_window"  # Keep most recent N messages
    IMPORTANCE_BASED = "importance_based"  # Keep system + important messages
    HYBRID = "hybrid"  # Combine sliding window + importance
    AGGRESSIVE = "aggressive"  # Trim more aggressively when VRAM is high


@dataclass
class ContextConfig:
    """Configuration for context window management"""

    # Model capabilities
    model_name: str = "gemma3:12b"
    max_context_tokens: int = 32000  # Conservative limit (Gemma 3 supports 128K)
    max_output_tokens: int = 8192  # Gemma 3 max output

    # Trimming thresholds
    trim_threshold_pct: float = 0.875  # Trim at 87.5% of max
    aggressive_trim_threshold_pct: float = 0.75  # More aggressive trimming

    # Trimming behavior
    trim_strategy: TrimStrategy = TrimStrategy.HYBRID
    trim_interval: int = 50  # Trim every N requests
    keep_recent_messages: int = 40  # Keep last N messages when trimming
    always_keep_system: bool = True  # Always preserve system message

    # VRAM management
    max_vram_gb: float = 15.0  # Safe limit for RTX 4080 16GB
    vram_warning_threshold_gb: float = 14.0  # Warn at 14GB
    enable_vram_monitoring: bool = True

    # Adaptive behavior
    enable_adaptive: bool = True  # Dynamically adjust limits
    adaptive_safety_margin: float = 0.9  # Use 90% of observed max


@dataclass
class ContextState:
    """Current state of the context window"""

    current_tokens: int = 0
    peak_tokens: int = 0
    message_count: int = 0
    trim_count: int = 0
    last_trim_at: int = 0  # Request number of last trim

    # VRAM tracking
    current_vram_gb: float = 0.0
    peak_vram_gb: float = 0.0

    # Adaptive learning
    observed_max_tokens: int = 0
    observed_max_vram_gb: float = 0.0
    oom_count: int = 0


class MemoryMonitor:
    """Monitor VRAM usage via nvidia-smi"""

    @staticmethod
    def get_vram_usage() -> tuple[float, float]:
        """
        Get current VRAM usage in GB

        Returns:
            Tuple of (used_gb, total_gb)
        """
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=2
            )

            if result.returncode == 0:
                used, total = result.stdout.strip().split(',')
                used_gb = float(used) / 1024  # Convert MB to GB
                total_gb = float(total) / 1024
                return used_gb, total_gb

        except Exception as e:
            logger.warning(f"Failed to get VRAM usage: {e}")

        return 0.0, 0.0

    @staticmethod
    def check_vram_available(required_gb: float, max_gb: float) -> bool:
        """Check if enough VRAM is available"""
        used_gb, total_gb = MemoryMonitor.get_vram_usage()
        available_gb = total_gb - used_gb

        if available_gb < required_gb:
            logger.warning(
                f"Insufficient VRAM: {available_gb:.1f}GB available, "
                f"{required_gb:.1f}GB required"
            )
            return False

        if used_gb > max_gb:
            logger.warning(
                f"VRAM usage too high: {used_gb:.1f}GB / {total_gb:.1f}GB "
                f"(max: {max_gb:.1f}GB)"
            )
            return False

        return True


class ContextTrimmer:
    """Implements various context trimming strategies"""

    @staticmethod
    def sliding_window(
        messages: list[dict],
        keep_recent: int,
        keep_system: bool = True
    ) -> list[dict]:
        """
        Keep system message + most recent N messages

        Args:
            messages: List of conversation messages
            keep_recent: Number of recent messages to keep
            keep_system: Whether to always keep system message

        Returns:
            Trimmed message list
        """
        if len(messages) <= keep_recent + 1:  # +1 for system
            return messages

        # Extract system message if present
        system_msg = None
        other_messages = messages

        if keep_system and messages and messages[0].get("role") == "system":
            system_msg = messages[0]
            other_messages = messages[1:]

        # Keep most recent messages
        trimmed = other_messages[-keep_recent:]

        # Prepend system message
        if system_msg:
            trimmed = [system_msg] + trimmed

        return trimmed

    @staticmethod
    def importance_based(
        messages: list[dict],
        target_count: int,
        keep_system: bool = True
    ) -> list[dict]:
        """
        Keep system + important messages (errors, warnings, key decisions)

        This is a placeholder for more sophisticated importance scoring
        """
        # For now, just use sliding window
        # TODO: Implement importance scoring based on:
        # - Message length (longer = more important)
        # - Keywords (error, warning, success, etc.)
        # - User vs assistant messages
        return ContextTrimmer.sliding_window(messages, target_count, keep_system)

    @staticmethod
    def hybrid(
        messages: list[dict],
        keep_recent: int,
        keep_system: bool = True
    ) -> list[dict]:
        """
        Hybrid strategy: Keep system + recent + important messages
        """
        # For now, same as sliding window
        # TODO: Implement hybrid approach
        return ContextTrimmer.sliding_window(messages, keep_recent, keep_system)

    @staticmethod
    def aggressive(
        messages: list[dict],
        keep_recent: int,
        keep_system: bool = True
    ) -> list[dict]:
        """
        Aggressive trimming: Keep fewer messages
        """
        # Keep half the normal amount
        aggressive_keep = max(10, keep_recent // 2)
        return ContextTrimmer.sliding_window(messages, aggressive_keep, keep_system)


class ContextManager:
    """
    Manages context window and memory for batch processing

    Features:
    - Real-time context length tracking
    - VRAM monitoring
    - Adaptive trimming based on observed limits
    - Multiple trimming strategies
    - OOM prevention
    """

    def __init__(self, config: ContextConfig | None = None):
        self.config = config or ContextConfig()
        self.state = ContextState()
        self.trimmer = ContextTrimmer()
        self.monitor = MemoryMonitor()

        logger.info(
            f"ContextManager initialized: "
            f"max_tokens={self.config.max_context_tokens}, "
            f"max_vram={self.config.max_vram_gb}GB, "
            f"strategy={self.config.trim_strategy.value}"
        )

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text

        Simple heuristic: ~4 chars per token for English
        TODO: Use actual tokenizer for accurate counts
        """
        return len(text) // 4

    def estimate_message_tokens(self, messages: list[dict]) -> int:
        """Estimate total tokens in message list"""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            total += self.estimate_tokens(content)
            total += 4  # Overhead for role, formatting, etc.
        return total

    def update_state(
        self,
        current_tokens: int,
        request_num: int,
        was_trimmed: bool = False
    ) -> None:
        """Update context state after processing a request"""
        self.state.current_tokens = current_tokens
        self.state.peak_tokens = max(self.state.peak_tokens, current_tokens)
        self.state.message_count += 1

        if was_trimmed:
            self.state.trim_count += 1
            self.state.last_trim_at = request_num

        # Update VRAM if monitoring enabled
        if self.config.enable_vram_monitoring:
            used_gb, _ = self.monitor.get_vram_usage()
            self.state.current_vram_gb = used_gb
            self.state.peak_vram_gb = max(self.state.peak_vram_gb, used_gb)

        # Adaptive learning
        if self.config.enable_adaptive:
            self.state.observed_max_tokens = max(
                self.state.observed_max_tokens,
                current_tokens
            )
            self.state.observed_max_vram_gb = max(
                self.state.observed_max_vram_gb,
                self.state.current_vram_gb
            )

    def should_trim(self, request_num: int, current_tokens: int) -> bool:
        """
        Determine if context should be trimmed

        Trim if:
        1. Periodic interval reached (every N requests)
        2. Token threshold exceeded
        3. VRAM threshold exceeded
        """
        # Check periodic interval
        if request_num % self.config.trim_interval == 0:
            return True

        # Check token threshold
        trim_threshold = int(
            self.config.max_context_tokens * self.config.trim_threshold_pct
        )
        if current_tokens >= trim_threshold:
            logger.warning(
                f"Token threshold exceeded: {current_tokens} >= {trim_threshold}"
            )
            return True

        # Check VRAM threshold
        if self.config.enable_vram_monitoring:
            if self.state.current_vram_gb >= self.config.vram_warning_threshold_gb:
                logger.warning(
                    f"VRAM threshold exceeded: "
                    f"{self.state.current_vram_gb:.1f}GB >= "
                    f"{self.config.vram_warning_threshold_gb:.1f}GB"
                )
                return True

        return False

    def trim_context(
        self,
        messages: list[dict],
        aggressive: bool = False
    ) -> list[dict]:
        """
        Trim context using configured strategy

        Args:
            messages: Current conversation messages
            aggressive: Use aggressive trimming

        Returns:
            Trimmed message list
        """
        strategy = self.config.trim_strategy

        if aggressive:
            strategy = TrimStrategy.AGGRESSIVE

        if strategy == TrimStrategy.SLIDING_WINDOW:
            return self.trimmer.sliding_window(
                messages,
                self.config.keep_recent_messages,
                self.config.always_keep_system
            )
        elif strategy == TrimStrategy.IMPORTANCE_BASED:
            return self.trimmer.importance_based(
                messages,
                self.config.keep_recent_messages,
                self.config.always_keep_system
            )
        elif strategy == TrimStrategy.HYBRID:
            return self.trimmer.hybrid(
                messages,
                self.config.keep_recent_messages,
                self.config.always_keep_system
            )
        elif strategy == TrimStrategy.AGGRESSIVE:
            return self.trimmer.aggressive(
                messages,
                self.config.keep_recent_messages,
                self.config.always_keep_system
            )
        else:
            # Default to sliding window
            return self.trimmer.sliding_window(
                messages,
                self.config.keep_recent_messages,
                self.config.always_keep_system
            )

    def get_metrics(self) -> dict:
        """Get current context metrics"""
        return {
            "current_tokens": self.state.current_tokens,
            "peak_tokens": self.state.peak_tokens,
            "max_tokens": self.config.max_context_tokens,
            "utilization_pct": (
                self.state.current_tokens / self.config.max_context_tokens * 100
            ),
            "trim_count": self.state.trim_count,
            "message_count": self.state.message_count,
            "current_vram_gb": self.state.current_vram_gb,
            "peak_vram_gb": self.state.peak_vram_gb,
            "max_vram_gb": self.config.max_vram_gb,
            "vram_utilization_pct": (
                self.state.current_vram_gb / self.config.max_vram_gb * 100
                if self.config.max_vram_gb > 0 else 0
            ),
            "strategy": self.config.trim_strategy.value,
        }

