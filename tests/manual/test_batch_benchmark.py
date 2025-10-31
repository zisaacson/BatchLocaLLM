#!/usr/bin/env python3
"""
Batch Processing Benchmark - Measure Optimization Impact

Tests different optimization strategies:
1. Baseline (no optimization)
2. Keep-alive only
3. Full optimization (keep-alive + context caching)

Measures:
- Total processing time
- Tokens processed (prompt + completion)
- Tokens cached (reused)
- Cache hit rate
- Requests per second
- Model load count
"""

import sys
import time
import json
import argparse
import httpx
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

OLLAMA_URL = "http://localhost:11434"
MODEL = "gemma3:12b"

# Simulated candidate scoring scenario
SYSTEM_PROMPT = """You are a candidate scoring assistant. Use the following rubric to evaluate candidates:

SCORING RUBRIC:
1. Technical Skills (0-10): Evaluate programming proficiency, problem-solving ability, and technical knowledge
2. Communication (0-10): Assess clarity, articulation, and ability to explain complex concepts
3. Experience (0-10): Consider relevant work history, projects, and achievements
4. Cultural Fit (0-10): Evaluate alignment with company values and team dynamics
5. Growth Potential (0-10): Assess learning ability, adaptability, and career trajectory

INSTRUCTIONS:
- Provide a score for each category
- Give a brief justification for each score
- Calculate total score (sum of all categories)
- Provide final recommendation: STRONG_YES, YES, MAYBE, NO, STRONG_NO

Be objective, fair, and consistent in your evaluations."""

def generate_candidate_data(candidate_id: int) -> str:
    """Generate unique candidate data"""
    return f"""Candidate #{candidate_id}:
- Years of experience: {3 + (candidate_id % 10)}
- Primary language: Python
- Projects: {2 + (candidate_id % 5)}
- Education: BS Computer Science"""

@dataclass
class BenchmarkResult:
    """Results from a benchmark run"""
    strategy: str
    num_requests: int
    total_time_seconds: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    cached_tokens: int = 0
    cache_hit_rate: float = 0.0
    requests_per_second: float = 0.0
    avg_time_per_request_ms: float = 0.0
    model_loads: int = 0
    errors: int = 0
    
    def __post_init__(self):
        if self.total_time_seconds > 0:
            self.requests_per_second = self.num_requests / self.total_time_seconds
            self.avg_time_per_request_ms = (self.total_time_seconds / self.num_requests) * 1000
        if self.total_prompt_tokens > 0:
            self.cache_hit_rate = (self.cached_tokens / self.total_prompt_tokens) * 100

class OllamaBenchmark:
    """Benchmark Ollama batch processing with different optimization strategies"""
    
    def __init__(self, model: str = MODEL, base_url: str = OLLAMA_URL):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(timeout=300.0)
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        keep_alive: Optional[str] = None,
        context: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Call Ollama chat API"""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive
        
        if context is not None:
            payload["context"] = context
        
        response = self.client.post(f"{self.base_url}/api/chat", json=payload)
        response.raise_for_status()
        return response.json()
    
    def unload_model(self):
        """Unload model from memory"""
        try:
            self.chat(messages=[], keep_alive="0")
        except:
            pass
    
    def run_baseline(self, num_requests: int) -> BenchmarkResult:
        """Baseline: No optimization"""
        print(f"\n{'='*80}")
        print(f"BASELINE: No Optimization ({num_requests} requests)")
        print(f"{'='*80}")
        
        # Unload model first
        self.unload_model()
        time.sleep(2)
        
        total_prompt_tokens = 0
        total_completion_tokens = 0
        errors = 0
        model_loads = 0
        
        start_time = time.time()
        
        for i in range(num_requests):
            try:
                # Each request is independent
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Score this candidate:\n{generate_candidate_data(i+1)}"}
                ]
                
                # Track if model needs to load (first request or after timeout)
                req_start = time.time()
                response = self.chat(messages=messages)  # No keep_alive, no context
                req_time = time.time() - req_start
                
                # If request took >5 seconds, likely model loaded
                if req_time > 5:
                    model_loads += 1
                
                total_prompt_tokens += response.get("prompt_eval_count", 0)
                total_completion_tokens += response.get("eval_count", 0)
                
                if (i + 1) % 10 == 0:
                    elapsed = time.time() - start_time
                    rps = (i + 1) / elapsed
                    print(f"  Progress: {i+1}/{num_requests} ({rps:.2f} req/s)")
                
            except Exception as e:
                print(f"  Error on request {i+1}: {e}")
                errors += 1
        
        total_time = time.time() - start_time
        
        return BenchmarkResult(
            strategy="Baseline (No Optimization)",
            num_requests=num_requests,
            total_time_seconds=total_time,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            model_loads=model_loads,
            errors=errors
        )
    
    def run_keep_alive(self, num_requests: int) -> BenchmarkResult:
        """Optimization 1: Keep-alive only"""
        print(f"\n{'='*80}")
        print(f"KEEP-ALIVE ONLY ({num_requests} requests)")
        print(f"{'='*80}")
        
        # Unload model first
        self.unload_model()
        time.sleep(2)
        
        total_prompt_tokens = 0
        total_completion_tokens = 0
        errors = 0
        model_loads = 0
        
        start_time = time.time()
        
        for i in range(num_requests):
            try:
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Score this candidate:\n{generate_candidate_data(i+1)}"}
                ]
                
                req_start = time.time()
                response = self.chat(messages=messages, keep_alive="24h")  # Keep model loaded
                req_time = time.time() - req_start
                
                if req_time > 5:
                    model_loads += 1
                
                total_prompt_tokens += response.get("prompt_eval_count", 0)
                total_completion_tokens += response.get("eval_count", 0)
                
                if (i + 1) % 10 == 0:
                    elapsed = time.time() - start_time
                    rps = (i + 1) / elapsed
                    print(f"  Progress: {i+1}/{num_requests} ({rps:.2f} req/s)")
                
            except Exception as e:
                print(f"  Error on request {i+1}: {e}")
                errors += 1
        
        total_time = time.time() - start_time
        
        return BenchmarkResult(
            strategy="Keep-Alive Only",
            num_requests=num_requests,
            total_time_seconds=total_time,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            model_loads=model_loads,
            errors=errors
        )
    
    def run_optimized(self, num_requests: int) -> BenchmarkResult:
        """Optimization 2: Keep-alive + Context caching"""
        print(f"\n{'='*80}")
        print(f"FULL OPTIMIZATION: Keep-Alive + Context Caching ({num_requests} requests)")
        print(f"{'='*80}")
        
        # Unload model first
        self.unload_model()
        time.sleep(2)
        
        total_prompt_tokens = 0
        total_completion_tokens = 0
        cached_tokens = 0
        errors = 0
        model_loads = 0
        context = None
        
        start_time = time.time()
        
        for i in range(num_requests):
            try:
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Score this candidate:\n{generate_candidate_data(i+1)}"}
                ]
                
                req_start = time.time()
                response = self.chat(messages=messages, keep_alive="24h", context=context)
                req_time = time.time() - req_start
                
                if req_time > 5:
                    model_loads += 1
                
                # Save context for next request
                context = response.get("context")
                
                prompt_tokens = response.get("prompt_eval_count", 0)
                total_prompt_tokens += prompt_tokens
                total_completion_tokens += response.get("eval_count", 0)
                
                # If we have context and prompt_tokens is low, we're using cache
                if i > 0 and prompt_tokens < 100:  # Heuristic: <100 tokens means cache hit
                    cached_tokens += len(SYSTEM_PROMPT.split())  # Approximate
                
                if (i + 1) % 10 == 0:
                    elapsed = time.time() - start_time
                    rps = (i + 1) / elapsed
                    print(f"  Progress: {i+1}/{num_requests} ({rps:.2f} req/s, prompt_tokens={prompt_tokens})")
                
            except Exception as e:
                print(f"  Error on request {i+1}: {e}")
                errors += 1
                context = None  # Reset context on error
        
        total_time = time.time() - start_time
        
        return BenchmarkResult(
            strategy="Full Optimization (Keep-Alive + Context)",
            num_requests=num_requests,
            total_time_seconds=total_time,
            total_prompt_tokens=total_prompt_tokens,
            total_completion_tokens=total_completion_tokens,
            total_tokens=total_prompt_tokens + total_completion_tokens,
            cached_tokens=cached_tokens,
            model_loads=model_loads,
            errors=errors
        )

def print_results(results: List[BenchmarkResult]):
    """Print comparison table"""
    print(f"\n{'='*80}")
    print("BENCHMARK RESULTS")
    print(f"{'='*80}\n")
    
    for result in results:
        print(f"{result.strategy}:")
        print(f"  Requests: {result.num_requests}")
        print(f"  Total Time: {result.total_time_seconds:.2f}s")
        print(f"  Requests/sec: {result.requests_per_second:.2f}")
        print(f"  Avg Time/Request: {result.avg_time_per_request_ms:.0f}ms")
        print(f"  Prompt Tokens: {result.total_prompt_tokens:,}")
        print(f"  Completion Tokens: {result.total_completion_tokens:,}")
        print(f"  Total Tokens: {result.total_tokens:,}")
        if result.cached_tokens > 0:
            print(f"  Cached Tokens: {result.cached_tokens:,}")
            print(f"  Cache Hit Rate: {result.cache_hit_rate:.1f}%")
        print(f"  Model Loads: {result.model_loads}")
        print(f"  Errors: {result.errors}")
        print()
    
    # Comparison
    if len(results) > 1:
        baseline = results[0]
        print(f"{'='*80}")
        print("IMPROVEMENTS vs BASELINE")
        print(f"{'='*80}\n")
        
        for result in results[1:]:
            time_saved = baseline.total_time_seconds - result.total_time_seconds
            time_improvement = (time_saved / baseline.total_time_seconds) * 100
            
            tokens_saved = baseline.total_prompt_tokens - result.total_prompt_tokens
            token_improvement = (tokens_saved / baseline.total_prompt_tokens) * 100 if baseline.total_prompt_tokens > 0 else 0
            
            print(f"{result.strategy}:")
            print(f"  Time Saved: {time_saved:.2f}s ({time_improvement:.1f}% faster)")
            print(f"  Tokens Saved: {tokens_saved:,} ({token_improvement:.1f}% reduction)")
            print()

def main():
    parser = argparse.ArgumentParser(description="Benchmark Ollama batch processing optimizations")
    parser.add_argument("--requests", type=int, default=20, help="Number of requests to process")
    parser.add_argument("--strategy", choices=["baseline", "keep-alive", "optimized", "all"], default="all", help="Which strategy to test")
    args = parser.parse_args()
    
    benchmark = OllamaBenchmark()
    results = []
    
    if args.strategy in ["baseline", "all"]:
        results.append(benchmark.run_baseline(args.requests))
    
    if args.strategy in ["keep-alive", "all"]:
        results.append(benchmark.run_keep_alive(args.requests))
    
    if args.strategy in ["optimized", "all"]:
        results.append(benchmark.run_optimized(args.requests))
    
    print_results(results)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

