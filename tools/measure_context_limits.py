#!/usr/bin/env python3
"""
Context Limit Measurement Tool

Empirically determines:
1. VRAM per token (KV cache growth rate)
2. Maximum safe context before OOM
3. Optimal chunk size for batch processing

Usage:
    python tools/measure_context_limits.py
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ollama_backend import OllamaBackend
from src.config import settings


class ContextLimitTester:
    """Empirically measure context limits and VRAM usage"""

    def __init__(self):
        self.backend = OllamaBackend(base_url=settings.ollama_base_url)
        self.model_name = settings.model_name
        self.measurements: List[Dict] = []
    
    def get_vram_usage(self) -> Tuple[float, float]:
        """Get current VRAM usage in GB"""
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
                used_gb = float(used) / 1024
                total_gb = float(total) / 1024
                return used_gb, total_gb
        except Exception as e:
            print(f"Warning: Failed to get VRAM usage: {e}")
        
        return 0.0, 0.0
    
    def build_test_conversation(self, target_tokens: int) -> List[Dict]:
        """Build a conversation with approximately target_tokens"""
        # Rough estimate: 1 token ≈ 4 characters
        chars_per_token = 4
        target_chars = target_tokens * chars_per_token
        
        # Build conversation
        conversation = [
            {
                "role": "system",
                "content": "You are a helpful assistant. Please respond concisely."
            },
            {
                "role": "user",
                "content": "Please repeat this text: " + ("test " * (target_chars // 5))
            }
        ]
        
        return conversation
    
    async def measure_vram_at_context_size(self, context_tokens: int) -> Dict:
        """Measure VRAM usage at specific context size"""
        print(f"\n{'='*60}")
        print(f"Testing context size: {context_tokens:,} tokens")
        print(f"{'='*60}")

        # Get baseline VRAM
        vram_before, total_vram = self.get_vram_usage()
        print(f"VRAM before: {vram_before:.2f} GB / {total_vram:.2f} GB")

        # Build test conversation
        conversation = self.build_test_conversation(context_tokens)

        try:
            # Send to Ollama via backend
            from src.models import ChatCompletionBody

            request = ChatCompletionBody(
                model=self.model_name,
                messages=conversation,
                temperature=0.1,
                max_tokens=100
            )

            start_time = time.time()
            response = await self.backend.generate_chat_completion(request)
            elapsed = time.time() - start_time
            
            # Get VRAM after
            time.sleep(1)  # Let VRAM settle
            vram_after, _ = self.get_vram_usage()
            
            # Calculate metrics
            vram_delta = vram_after - vram_before
            vram_per_token_mb = (vram_delta * 1024) / context_tokens if context_tokens > 0 else 0
            
            measurement = {
                'context_tokens': context_tokens,
                'vram_before_gb': vram_before,
                'vram_after_gb': vram_after,
                'vram_delta_gb': vram_delta,
                'vram_per_token_mb': vram_per_token_mb,
                'elapsed_sec': elapsed,
                'success': True,
                'error': None
            }
            
            print(f"VRAM after:  {vram_after:.2f} GB")
            print(f"VRAM delta:  {vram_delta:.2f} GB ({vram_delta*1024:.1f} MB)")
            print(f"VRAM/token:  {vram_per_token_mb:.4f} MB/token")
            print(f"Time:        {elapsed:.2f}s")
            print(f"✅ SUCCESS")
            
            return measurement
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            
            vram_after, _ = self.get_vram_usage()
            
            return {
                'context_tokens': context_tokens,
                'vram_before_gb': vram_before,
                'vram_after_gb': vram_after,
                'vram_delta_gb': vram_after - vram_before,
                'vram_per_token_mb': 0,
                'elapsed_sec': 0,
                'success': False,
                'error': str(e)
            }
    
    async def measure_vram_growth_rate(self) -> float:
        """Measure VRAM growth rate across multiple context sizes"""
        print("\n" + "="*60)
        print("PHASE 1: Measuring VRAM Growth Rate")
        print("="*60)
        
        # Test progressively larger contexts
        test_sizes = [1000, 5000, 10000, 20000, 40000, 60000, 80000, 100000]
        
        for size in test_sizes:
            measurement = await self.measure_vram_at_context_size(size)
            self.measurements.append(measurement)
            
            # Stop if we hit VRAM limit
            if measurement['vram_after_gb'] > 15.0:
                print(f"\n⚠️  Approaching VRAM limit (15GB), stopping tests")
                break
            
            # Stop if we hit an error
            if not measurement['success']:
                print(f"\n⚠️  Error encountered, stopping tests")
                break
            
            # Small delay between tests
            await asyncio.sleep(2)
        
        # Calculate average VRAM per token
        successful = [m for m in self.measurements if m['success'] and m['vram_per_token_mb'] > 0]
        
        if not successful:
            print("\n❌ No successful measurements!")
            return 0.0
        
        avg_vram_per_token = sum(m['vram_per_token_mb'] for m in successful) / len(successful)
        
        print(f"\n{'='*60}")
        print(f"VRAM Growth Rate Results")
        print(f"{'='*60}")
        print(f"Measurements: {len(successful)}")
        print(f"Average VRAM per token: {avg_vram_per_token:.4f} MB/token")
        print(f"{'='*60}")
        
        return avg_vram_per_token
    
    async def find_max_safe_context(self, vram_per_token_mb: float) -> int:
        """Calculate maximum safe context based on VRAM measurements"""
        print("\n" + "="*60)
        print("PHASE 2: Calculating Maximum Safe Context")
        print("="*60)
        
        # Get current VRAM usage
        vram_used, vram_total = self.get_vram_usage()
        vram_available = vram_total - vram_used
        
        print(f"VRAM total:     {vram_total:.2f} GB")
        print(f"VRAM used:      {vram_used:.2f} GB")
        print(f"VRAM available: {vram_available:.2f} GB")
        print(f"VRAM per token: {vram_per_token_mb:.4f} MB/token")
        
        # Calculate theoretical max
        if vram_per_token_mb > 0:
            vram_available_mb = vram_available * 1024
            theoretical_max = int(vram_available_mb / vram_per_token_mb)
        else:
            # If VRAM per token is negligible, use model's context window
            theoretical_max = 128000
        
        # Apply safety margins
        safe_max = int(theoretical_max * 0.8)  # 80% safety margin
        
        # Cap at model's context window
        model_max = 128000
        safe_max = min(safe_max, model_max)
        
        print(f"\nTheoretical max: {theoretical_max:,} tokens")
        print(f"Safe max (80%):  {safe_max:,} tokens")
        print(f"Model max:       {model_max:,} tokens")
        print(f"Recommended:     {safe_max:,} tokens")
        
        return safe_max
    
    def calculate_optimal_chunk_size(
        self,
        max_context: int,
        system_prompt_tokens: int = 2400,
        tokens_per_exchange: int = 900
    ) -> int:
        """Calculate optimal chunk size for batch processing"""
        print("\n" + "="*60)
        print("PHASE 3: Calculating Optimal Chunk Size")
        print("="*60)
        
        print(f"Max context:         {max_context:,} tokens")
        print(f"System prompt:       {system_prompt_tokens:,} tokens")
        print(f"Tokens per exchange: {tokens_per_exchange:,} tokens")
        
        # Available context for exchanges
        available = max_context - system_prompt_tokens
        
        # Max requests that fit
        max_requests = available // tokens_per_exchange
        
        # Apply safety margin
        safe_chunk_size = int(max_requests * 0.8)
        
        print(f"\nAvailable for exchanges: {available:,} tokens")
        print(f"Max requests:            {max_requests:,}")
        print(f"Safe chunk size (80%):   {safe_chunk_size:,} requests")
        
        # Calculate for 170K batch
        chunks_needed = (170000 + safe_chunk_size - 1) // safe_chunk_size
        
        print(f"\nFor 170K batch:")
        print(f"  Chunks needed:  {chunks_needed:,}")
        print(f"  Requests/chunk: {safe_chunk_size:,}")
        
        return safe_chunk_size
    
    def print_summary(self, vram_per_token: float, max_context: int, chunk_size: int):
        """Print final summary"""
        print("\n" + "="*60)
        print("FINAL RECOMMENDATIONS")
        print("="*60)
        
        print(f"""
Configuration to use in src/batch_processor.py:

MAX_CONTEXT_TOKENS = {max_context}
CHUNK_SIZE = {chunk_size}
VRAM_PER_TOKEN_MB = {vram_per_token:.4f}

Context Configuration:
  Model max:        128,000 tokens
  Measured safe:    {max_context:,} tokens
  Chunk size:       {chunk_size:,} requests
  VRAM per token:   {vram_per_token:.4f} MB/token

For 170K batch:
  Chunks needed:    {(170000 + chunk_size - 1) // chunk_size:,}
  System prompt tokenizations: {(170000 + chunk_size - 1) // chunk_size:,}
  Token savings:    {(1 - ((170000 + chunk_size - 1) // chunk_size) / 170000) * 100:.1f}%
""")
        
        print("="*60)


async def main():
    """Run context limit tests"""
    print("\n" + "="*60)
    print("CONTEXT LIMIT MEASUREMENT TOOL")
    print("="*60)
    print("\nThis will:")
    print("1. Measure VRAM growth rate per token")
    print("2. Calculate maximum safe context")
    print("3. Determine optimal chunk size")
    print("\nPress Ctrl+C to cancel...")
    print("="*60)
    
    await asyncio.sleep(3)
    
    tester = ContextLimitTester()
    
    # Phase 1: Measure VRAM growth
    vram_per_token = await tester.measure_vram_growth_rate()
    
    if vram_per_token == 0:
        print("\n❌ Failed to measure VRAM growth rate!")
        print("Using conservative defaults...")
        vram_per_token = 0.5  # Conservative guess
    
    # Phase 2: Calculate max safe context
    max_context = await tester.find_max_safe_context(vram_per_token)
    
    # Phase 3: Calculate optimal chunk size
    chunk_size = tester.calculate_optimal_chunk_size(max_context)
    
    # Print summary
    tester.print_summary(vram_per_token, max_context, chunk_size)


if __name__ == "__main__":
    asyncio.run(main())

