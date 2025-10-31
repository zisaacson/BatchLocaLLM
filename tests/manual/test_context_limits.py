#!/usr/bin/env python3
"""
Context Window & VRAM Limit Testing

Find the ACTUAL limits for Gemma 3 12B:
1. What's the maximum context length before OOM?
2. How does VRAM usage grow with context length?
3. What's the optimal context trim threshold?

This is CRITICAL for 170k request batches!
"""

import json
import subprocess
import time

import requests

BASE_URL = "http://localhost:4080"
OLLAMA_URL = "http://localhost:11434"

def get_vram_usage() -> float | None:
    """Get current VRAM usage in GB"""
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
    except Exception as e:
        print(f"⚠️  Could not get VRAM usage: {e}")
    return None

def test_context_length(num_exchanges: int, system_prompt_tokens: int = 100):
    """
    Test a specific context length by building a conversation.

    Args:
        num_exchanges: Number of user/assistant exchanges
        system_prompt_tokens: Approximate tokens in system prompt

    Returns:
        dict with results or None if OOM
    """
    print(f"\n{'='*80}")
    print(f"Testing {num_exchanges} exchanges (~{num_exchanges * 100 + system_prompt_tokens} tokens)")
    print(f"{'='*80}")

    # Build conversation
    conversation = [
        {"role": "system", "content": "You are a helpful assistant. " * (system_prompt_tokens // 10)}
    ]

    # Get baseline VRAM
    vram_start = get_vram_usage()
    print(f"VRAM before: {vram_start:.2f} GB" if vram_start else "VRAM: unknown")

    start_time = time.time()

    try:
        for i in range(num_exchanges):
            # Add user message
            user_msg = f"This is test message number {i+1}. " * 10  # ~10 tokens
            conversation.append({"role": "user", "content": user_msg})

            # Call Ollama
            response = requests.post(
                f"{OLLAMA_URL}/api/chat",
                json={
                    "model": "gemma3:12b",
                    "messages": conversation,
                    "stream": False,
                    "keep_alive": -1,
                    "options": {"num_predict": 10}
                },
                timeout=60
            )

            if response.status_code != 200:
                print(f"❌ Request failed: {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return None

            data = response.json()

            # Add assistant response
            assistant_msg = data.get("message", {}).get("content", "")
            conversation.append({"role": "assistant", "content": assistant_msg})

            # Get metrics
            prompt_tokens = data.get("prompt_eval_count", 0)
            completion_tokens = data.get("eval_count", 0)
            vram_current = get_vram_usage()

            # Log progress every 10 exchanges
            if (i + 1) % 10 == 0:
                elapsed = time.time() - start_time
                print(f"  Exchange {i+1}/{num_exchanges}: "
                      f"prompt={prompt_tokens}, "
                      f"completion={completion_tokens}, "
                      f"VRAM={vram_current:.2f}GB, "
                      f"time={elapsed:.1f}s")

        # Final metrics
        elapsed = time.time() - start_time
        vram_end = get_vram_usage()
        vram_delta = vram_end - vram_start if (vram_start and vram_end) else None

        result = {
            "num_exchanges": num_exchanges,
            "estimated_tokens": num_exchanges * 100 + system_prompt_tokens,
            "conversation_length": len(conversation),
            "success": True,
            "time_sec": elapsed,
            "vram_start_gb": vram_start,
            "vram_end_gb": vram_end,
            "vram_delta_gb": vram_delta,
            "final_prompt_tokens": prompt_tokens,
        }

        print("\n✅ SUCCESS")
        print(f"   Total time: {elapsed:.1f}s")
        print(f"   VRAM delta: {vram_delta:.2f} GB" if vram_delta else "   VRAM delta: unknown")
        print(f"   Final prompt tokens: {prompt_tokens}")

        return result

    except requests.exceptions.Timeout:
        print(f"❌ TIMEOUT after {time.time() - start_time:.1f}s")
        return None
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None

def find_max_context():
    """
    Binary search to find maximum context length before OOM.

    Strategy:
    1. Start with small context (10 exchanges)
    2. Double until we hit OOM
    3. Binary search to find exact limit
    """
    print("="*80)
    print("FINDING MAXIMUM CONTEXT LENGTH")
    print("="*80)

    results = []

    # Test increasing context lengths
    test_sizes = [10, 25, 50, 100, 200, 300, 400, 500]

    for size in test_sizes:
        result = test_context_length(size)

        if result:
            results.append(result)
        else:
            print(f"\n🚨 FAILED at {size} exchanges")
            print(f"   Maximum safe context: {results[-1]['num_exchanges']} exchanges" if results else "   No safe context found!")
            break

        # Wait between tests to let VRAM settle
        time.sleep(2)

    return results

def test_vram_growth():
    """
    Measure VRAM growth rate with context length.

    This tells us the KV cache size per token.
    """
    print("\n" + "="*80)
    print("MEASURING VRAM GROWTH RATE")
    print("="*80)

    results = []

    # Test specific context lengths
    test_points = [10, 50, 100, 200, 300]

    for num_exchanges in test_points:
        result = test_context_length(num_exchanges)
        if result:
            results.append(result)
            time.sleep(2)  # Let VRAM settle
        else:
            break

    # Analyze growth rate
    if len(results) >= 2:
        print("\n" + "="*80)
        print("VRAM GROWTH ANALYSIS")
        print("="*80)

        for i in range(1, len(results)):
            prev = results[i-1]
            curr = results[i]

            if prev["vram_delta_gb"] and curr["vram_delta_gb"]:
                token_delta = curr["estimated_tokens"] - prev["estimated_tokens"]
                vram_delta = curr["vram_delta_gb"] - prev["vram_delta_gb"]
                vram_per_token_mb = (vram_delta * 1024) / token_delta if token_delta > 0 else 0

                print(f"\n{prev['num_exchanges']} → {curr['num_exchanges']} exchanges:")
                print(f"  Token delta: {token_delta}")
                print(f"  VRAM delta: {vram_delta:.3f} GB")
                print(f"  VRAM per token: {vram_per_token_mb:.2f} MB/token")

    return results

def generate_recommendations(results):
    """Generate safe context limits based on test results"""
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)

    if not results:
        print("❌ No successful tests - cannot generate recommendations")
        return

    max_result = max(results, key=lambda r: r["num_exchanges"])
    max_exchanges = max_result["num_exchanges"]
    max_tokens = max_result["estimated_tokens"]
    max_vram = max_result["vram_end_gb"]

    print("\n✅ Maximum tested context:")
    print(f"   Exchanges: {max_exchanges}")
    print(f"   Estimated tokens: {max_tokens:,}")
    print(f"   VRAM usage: {max_vram:.2f} GB")

    # Calculate safe limits (80% of max)
    int(max_exchanges * 0.8)
    safe_tokens = int(max_tokens * 0.8)

    print("\n💡 Recommended safe limits (80% of max):")
    print(f"   MAX_CONTEXT_TOKENS = {safe_tokens:,}")
    print(f"   CONTEXT_TRIM_THRESHOLD = {int(safe_tokens * 0.875):,}  # 87.5% of max")
    print("   TRIM_INTERVAL = 50  # Trim every 50 requests")
    print("   KEEP_MESSAGES = 40  # Keep last 40 messages after trim")

    # Calculate for 170k requests
    print("\n📊 For 170,000 requests:")
    trims_needed = 170000 // 50
    print(f"   Context trims needed: {trims_needed:,}")
    print(f"   Max context will be: {safe_tokens:,} tokens")
    print(f"   VRAM usage: ~{max_vram:.2f} GB")

def main():
    print("="*80)
    print("CONTEXT WINDOW & VRAM LIMIT TESTING")
    print("="*80)
    print("\nThis test will:")
    print("1. Find maximum context length before OOM")
    print("2. Measure VRAM growth rate")
    print("3. Generate safe limit recommendations")
    print("\n⚠️  WARNING: This may cause OOM errors!")
    print("⚠️  Make sure no other GPU processes are running!")

    input("\nPress Enter to continue...")

    # Check Ollama is running
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if response.status_code != 200:
            print("❌ Ollama not running! Start with: ollama serve")
            return
    except Exception:
        print("❌ Cannot connect to Ollama! Start with: ollama serve")
        return

    # Run tests
    print("\n" + "="*80)
    print("PHASE 1: VRAM GROWTH RATE")
    print("="*80)
    growth_results = test_vram_growth()

    print("\n" + "="*80)
    print("PHASE 2: MAXIMUM CONTEXT LENGTH")
    print("="*80)
    max_results = find_max_context()

    # Combine results
    all_results = growth_results + [r for r in max_results if r not in growth_results]

    # Generate recommendations
    generate_recommendations(all_results)

    # Save results
    with open("context_limit_results.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print("\n💾 Results saved to: context_limit_results.json")

if __name__ == "__main__":
    main()

