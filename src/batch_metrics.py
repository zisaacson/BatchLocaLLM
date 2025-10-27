"""
Batch Processing Metrics Tracker

Tracks all critical metrics for batch optimization:
- Token usage (prompt, completion, cached)
- Context window utilization
- VRAM usage
- Processing time and throughput
- Error rates
"""

import time
from dataclasses import dataclass, field
from typing import Optional
import subprocess


@dataclass
class BatchMetrics:
    """Comprehensive metrics for batch processing"""
    
    # Batch info
    batch_id: str
    total_requests: int
    start_time: float = field(default_factory=time.time)
    
    # Token metrics
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0  # Estimated tokens served from cache
    
    # Context metrics
    current_context_length: int = 0
    max_context_length: int = 32000  # Conservative limit
    peak_context_length: int = 0
    trim_count: int = 0
    
    # VRAM metrics (GB)
    model_vram_gb: float = 8.0  # Gemma 3 12B
    peak_vram_gb: float = 0.0
    
    # Performance metrics
    requests_completed: int = 0
    requests_failed: int = 0
    
    # Error metrics
    oom_errors: int = 0
    timeout_errors: int = 0
    model_errors: int = 0
    other_errors: int = 0
    
    # Timing
    total_processing_time_sec: float = 0.0
    
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate as % of prompt tokens"""
        if self.total_prompt_tokens == 0:
            return 0.0
        return (self.cached_tokens / self.total_prompt_tokens) * 100
    
    @property
    def context_utilization_pct(self) -> float:
        """Calculate context window utilization"""
        if self.max_context_length == 0:
            return 0.0
        return (self.current_context_length / self.max_context_length) * 100
    
    @property
    def vram_utilization_pct(self) -> float:
        """Calculate VRAM utilization (assumes 16GB total)"""
        total_vram_gb = 16.0  # RTX 4080
        return (self.peak_vram_gb / total_vram_gb) * 100
    
    @property
    def avg_time_per_request_sec(self) -> float:
        """Calculate average time per request"""
        if self.requests_completed == 0:
            return 0.0
        return self.total_processing_time_sec / self.requests_completed
    
    @property
    def requests_per_second(self) -> float:
        """Calculate throughput"""
        if self.total_processing_time_sec == 0:
            return 0.0
        return self.requests_completed / self.total_processing_time_sec
    
    @property
    def tokens_per_second(self) -> float:
        """Calculate token generation speed"""
        if self.total_processing_time_sec == 0:
            return 0.0
        return self.total_tokens / self.total_processing_time_sec
    
    @property
    def completion_pct(self) -> float:
        """Calculate batch completion percentage"""
        if self.total_requests == 0:
            return 0.0
        return (self.requests_completed / self.total_requests) * 100
    
    @property
    def eta_seconds(self) -> int:
        """Estimate time remaining"""
        if self.requests_completed == 0 or self.avg_time_per_request_sec == 0:
            return 0
        remaining = self.total_requests - self.requests_completed
        return int(remaining * self.avg_time_per_request_sec)
    
    @property
    def error_rate_pct(self) -> float:
        """Calculate error rate"""
        total_processed = self.requests_completed + self.requests_failed
        if total_processed == 0:
            return 0.0
        return (self.requests_failed / total_processed) * 100
    
    @property
    def token_savings_pct(self) -> float:
        """
        Calculate token savings vs baseline.
        
        Baseline: Each request tokenizes full prompt independently
        Optimized: System prompt tokenized once, reused across requests
        """
        if self.requests_completed == 0:
            return 0.0
        
        # Estimate baseline (each request tokenizes everything)
        avg_prompt_tokens = self.total_prompt_tokens / max(self.requests_completed, 1)
        baseline_tokens = self.requests_completed * avg_prompt_tokens
        
        # Actual tokens used
        actual_tokens = self.total_prompt_tokens
        
        if baseline_tokens == 0:
            return 0.0
        
        return ((baseline_tokens - actual_tokens) / baseline_tokens) * 100
    
    def update_request(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        processing_time_sec: float,
        success: bool = True,
        error_type: Optional[str] = None
    ):
        """Update metrics after processing a request"""
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_tokens += prompt_tokens + completion_tokens
        self.total_processing_time_sec += processing_time_sec
        
        if success:
            self.requests_completed += 1
        else:
            self.requests_failed += 1
            
            # Categorize error
            if error_type:
                if "oom" in error_type.lower() or "memory" in error_type.lower():
                    self.oom_errors += 1
                elif "timeout" in error_type.lower():
                    self.timeout_errors += 1
                elif "model" in error_type.lower():
                    self.model_errors += 1
                else:
                    self.other_errors += 1
    
    def update_context(self, context_length: int, was_trimmed: bool = False):
        """Update context metrics"""
        self.current_context_length = context_length
        self.peak_context_length = max(self.peak_context_length, context_length)
        
        if was_trimmed:
            self.trim_count += 1
    
    def update_vram(self, vram_gb: float):
        """Update VRAM metrics"""
        self.peak_vram_gb = max(self.peak_vram_gb, vram_gb)
    
    def estimate_cached_tokens(self, system_prompt_tokens: int):
        """
        Estimate cached tokens based on conversation batching.
        
        In conversation batching, system prompt is tokenized once,
        then reused for all subsequent requests.
        """
        if self.requests_completed > 1:
            # System prompt cached for all requests after the first
            self.cached_tokens = system_prompt_tokens * (self.requests_completed - 1)
    
    def get_vram_usage(self) -> Optional[float]:
        """
        Get current VRAM usage from nvidia-smi.
        
        Returns VRAM usage in GB, or None if unavailable.
        """
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                vram_mb = float(result.stdout.strip().split('\n')[0])
                return vram_mb / 1024  # Convert MB to GB
        except Exception:
            pass
        return None
    
    def to_dict(self) -> dict:
        """Convert metrics to dictionary for logging/API"""
        return {
            "batch_id": self.batch_id,
            "total_requests": self.total_requests,
            "requests_completed": self.requests_completed,
            "requests_failed": self.requests_failed,
            "completion_pct": round(self.completion_pct, 2),
            "error_rate_pct": round(self.error_rate_pct, 2),
            
            # Token metrics
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "cached_tokens": self.cached_tokens,
            "cache_hit_rate_pct": round(self.cache_hit_rate, 2),
            "token_savings_pct": round(self.token_savings_pct, 2),
            
            # Context metrics
            "current_context_length": self.current_context_length,
            "peak_context_length": self.peak_context_length,
            "context_utilization_pct": round(self.context_utilization_pct, 2),
            "trim_count": self.trim_count,
            
            # VRAM metrics
            "peak_vram_gb": round(self.peak_vram_gb, 2),
            "vram_utilization_pct": round(self.vram_utilization_pct, 2),
            
            # Performance metrics
            "total_processing_time_sec": round(self.total_processing_time_sec, 2),
            "avg_time_per_request_sec": round(self.avg_time_per_request_sec, 2),
            "requests_per_second": round(self.requests_per_second, 2),
            "tokens_per_second": round(self.tokens_per_second, 2),
            "eta_seconds": self.eta_seconds,
            
            # Error metrics
            "oom_errors": self.oom_errors,
            "timeout_errors": self.timeout_errors,
            "model_errors": self.model_errors,
            "other_errors": self.other_errors,
        }
    
    def log_summary(self) -> str:
        """Generate human-readable summary"""
        elapsed = time.time() - self.start_time
        
        return f"""
Batch Metrics Summary
=====================
Batch ID: {self.batch_id}
Progress: {self.requests_completed}/{self.total_requests} ({self.completion_pct:.1f}%)
Elapsed: {elapsed:.1f}s, ETA: {self.eta_seconds}s

Token Usage:
  Prompt: {self.total_prompt_tokens:,} tokens
  Completion: {self.total_completion_tokens:,} tokens
  Total: {self.total_tokens:,} tokens
  Cached: {self.cached_tokens:,} tokens ({self.cache_hit_rate:.1f}% hit rate)
  Savings: {self.token_savings_pct:.1f}% vs baseline

Context:
  Current: {self.current_context_length:,} / {self.max_context_length:,} tokens ({self.context_utilization_pct:.1f}%)
  Peak: {self.peak_context_length:,} tokens
  Trims: {self.trim_count}

VRAM:
  Peak: {self.peak_vram_gb:.2f} GB ({self.vram_utilization_pct:.1f}%)

Performance:
  Avg time/request: {self.avg_time_per_request_sec:.2f}s
  Throughput: {self.requests_per_second:.2f} req/s
  Token speed: {self.tokens_per_second:.1f} tokens/s

Errors:
  Failed: {self.requests_failed} ({self.error_rate_pct:.1f}%)
  OOM: {self.oom_errors}, Timeout: {self.timeout_errors}, Model: {self.model_errors}, Other: {self.other_errors}
"""

