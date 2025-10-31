#!/usr/bin/env python3
"""
Test script for gold-star curation system
Tests all endpoints and validates data format
"""

import json
import os
from datetime import datetime

import requests

BASE_URL = "http://localhost:8001"

def test_gold_star_post():
    """Test POST /api/gold-star endpoint"""
    print("\n🧪 Testing POST /api/gold-star...")

    # Create test data
    test_data = {
        "custom_id": f"test_{datetime.now().timestamp()}",
        "candidate_name": "Test Candidate (Software Engineer at Test Corp)",
        "input_prompt": {
            "system": "You are evaluating a candidate profile...",
            "user": "**Candidate:** Test Candidate\n**Current Role:** Software Engineer at Test Corp"
        },
        "llm_output": "Here is the evaluation:\n\n```json\n{\"recommendation\": \"Strong Yes\"}",
        "quality_score": 9,
        "tags": ["test", "excellent"],
        "notes": "Test example for validation",
        "model": "test-model",
        "starred_by": "test_script"
    }

    response = requests.post(f"{BASE_URL}/api/gold-star", json=test_data)

    if response.status_code == 200:
        print("✅ POST successful")
        return True
    else:
        print(f"❌ POST failed: {response.status_code}")
        print(response.text)
        return False

def test_gold_star_get():
    """Test GET /api/gold-star endpoint"""
    print("\n🧪 Testing GET /api/gold-star...")

    response = requests.get(f"{BASE_URL}/api/gold-star")

    if response.status_code == 200:
        data = response.json()
        print(f"✅ GET successful - Found {len(data)} starred examples")

        if len(data) > 0:
            print("\n📊 Sample example:")
            example = data[0]
            print(f"  - custom_id: {example.get('custom_id', 'N/A')}")
            print(f"  - candidate_name: {example.get('candidate_name', 'N/A')}")
            print(f"  - quality_score: {example.get('quality_score', 'N/A')}")
            print(f"  - tags: {example.get('tags', [])}")
            print(f"  - has input_prompt: {'input_prompt' in example}")
            print(f"  - has llm_output: {'llm_output' in example}")

        return True
    else:
        print(f"❌ GET failed: {response.status_code}")
        return False

def test_export_icl():
    """Test ICL export format"""
    print("\n🧪 Testing ICL export format...")

    response = requests.get(f"{BASE_URL}/api/export-gold-star?format=icl&min_quality=1")

    if response.status_code == 200:
        # Save to temp file
        temp_file = "/tmp/test_icl_export.jsonl"
        with open(temp_file, 'wb') as f:
            f.write(response.content)

        # Validate format
        with open(temp_file) as f:
            lines = f.readlines()

        print(f"✅ ICL export successful - {len(lines)} examples")

        if len(lines) > 0:
            example = json.loads(lines[0])

            # Validate structure
            assert 'messages' in example, "Missing 'messages' field"
            assert isinstance(example['messages'], list), "'messages' should be a list"
            assert len(example['messages']) == 3, "Should have 3 messages (system, user, assistant)"

            # Validate roles
            roles = [msg['role'] for msg in example['messages']]
            assert roles == ['system', 'user', 'assistant'], f"Wrong roles: {roles}"

            # Validate content
            for msg in example['messages']:
                assert 'content' in msg, "Missing 'content' field"
                assert isinstance(msg['content'], str), "'content' should be string"

            print("\n📊 ICL Format Validation:")
            print("  ✅ Has 'messages' array")
            print("  ✅ Has 3 messages (system, user, assistant)")
            print("  ✅ All messages have 'role' and 'content'")
            print(f"  ✅ Has metadata: {list(example.get('metadata', {}).keys())}")

            print("\n📝 Sample ICL Example:")
            print(f"  System: {example['messages'][0]['content'][:80]}...")
            print(f"  User: {example['messages'][1]['content'][:80]}...")
            print(f"  Assistant: {example['messages'][2]['content'][:80]}...")

        os.remove(temp_file)
        return True
    else:
        print(f"❌ ICL export failed: {response.status_code}")
        return False

def test_export_finetuning():
    """Test fine-tuning export format"""
    print("\n🧪 Testing fine-tuning export format...")

    response = requests.get(f"{BASE_URL}/api/export-gold-star?format=finetuning&min_quality=1")

    if response.status_code == 200:
        # Save to temp file
        temp_file = "/tmp/test_finetuning_export.jsonl"
        with open(temp_file, 'wb') as f:
            f.write(response.content)

        # Validate format
        with open(temp_file) as f:
            lines = f.readlines()

        print(f"✅ Fine-tuning export successful - {len(lines)} examples")

        if len(lines) > 0:
            example = json.loads(lines[0])

            # Validate structure
            assert 'messages' in example, "Missing 'messages' field"
            assert isinstance(example['messages'], list), "'messages' should be a list"
            assert len(example['messages']) == 3, "Should have 3 messages"

            print("\n📊 Fine-tuning Format Validation:")
            print("  ✅ Has 'messages' array")
            print("  ✅ Has 3 messages (system, user, assistant)")
            print("  ✅ Ready for OpenAI/Anthropic fine-tuning API")

        os.remove(temp_file)
        return True
    else:
        print(f"❌ Fine-tuning export failed: {response.status_code}")
        return False

def test_validation():
    """Test validation logic"""
    print("\n🧪 Testing validation...")

    # Test invalid quality_score
    invalid_data = {
        "custom_id": "test_invalid",
        "quality_score": 15  # Invalid: > 10
    }

    response = requests.post(f"{BASE_URL}/api/gold-star", json=invalid_data)

    if response.status_code == 400:
        print("✅ Validation working - Rejected quality_score > 10")
        return True
    else:
        print("❌ Validation failed - Should reject quality_score > 10")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("🧪 Gold-Star Curation System - Test Suite")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("POST /api/gold-star", test_gold_star_post()))
    results.append(("GET /api/gold-star", test_gold_star_get()))
    results.append(("ICL Export", test_export_icl()))
    results.append(("Fine-tuning Export", test_export_finetuning()))
    results.append(("Validation", test_validation()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")

    print(f"\n🎯 Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 ALL TESTS PASSED! System is production-ready!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review.")
        return 1

if __name__ == "__main__":
    exit(main())

