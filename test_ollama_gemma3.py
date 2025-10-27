#!/usr/bin/env python3
"""
Quick test script to verify Ollama + Gemma 3 12B works
"""

import asyncio
import sys
sys.path.insert(0, '.')

from src.ollama_backend import OllamaBackend
from src.models import ChatCompletionBody, ChatMessage

async def main():
    print("=" * 80)
    print("Testing Ollama + Gemma 3 12B")
    print("=" * 80)
    
    # Initialize backend
    backend = OllamaBackend()
    
    # Health check
    print("\n1. Health Check...")
    healthy = await backend.health_check()
    print(f"   Ollama healthy: {healthy}")
    
    if not healthy:
        print("   ERROR: Ollama not running!")
        return
    
    # List models
    print("\n2. List Models...")
    models = await backend.list_models()
    print(f"   Available models: {models}")
    
    # Load Gemma 3 12B
    print("\n3. Load Gemma 3 12B...")
    try:
        await backend.load_model("gemma3:12b")
        print("   ✓ Model loaded successfully")
    except Exception as e:
        print(f"   ERROR: {e}")
        return
    
    # Test inference
    print("\n4. Test Inference...")
    request = ChatCompletionBody(
        model="gemma3:12b",
        messages=[
            ChatMessage(role="user", content="What is the capital of France? Answer in one sentence.")
        ],
        temperature=0.7,
        max_tokens=100
    )
    
    try:
        response = await backend.generate_chat_completion(request)
        print(f"   ✓ Response received")
        print(f"   Model: {response.model}")
        print(f"   Content: {response.choices[0].message.content}")
        print(f"   Tokens: prompt={response.usage.prompt_tokens}, completion={response.usage.completion_tokens}, total={response.usage.total_tokens}")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Close
    await backend.close()
    
    print("\n" + "=" * 80)
    print("✓ ALL TESTS PASSED!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())

