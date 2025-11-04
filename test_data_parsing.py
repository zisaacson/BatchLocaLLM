#!/usr/bin/env python3
"""
Test Data Parsing Logic

Tests the conquest data parsing without requiring a full batch job.
This verifies that our fixes work correctly.
"""

import json
import sys
from pathlib import Path

# Add core to path
sys.path.insert(0, str(Path(__file__).parent))

from core.result_handlers.label_studio import LabelStudioHandler

def print_section(title):
    """Print a section header."""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def test_parse_candidate_from_messages():
    """Test parsing candidate data from messages."""
    print_section("TEST 1: Parse Candidate Data from Messages")
    
    # Create test messages
    messages = [
        {
            "role": "system",
            "content": "You are an expert technical recruiter evaluating software engineering candidates."
        },
        {
            "role": "user",
            "content": """Evaluate this candidate:

Name: Jane Smith
Current Role: Senior Software Engineer
Location: San Francisco, CA

Work History:
- Senior Software Engineer at Google (2020-2024)
- Software Engineer at Meta (2018-2020)
- Junior Developer at Startup Inc (2016-2018)

Education:
- BS Computer Science, Stanford University (2016)
- MS Computer Science, MIT (2018)

Please evaluate:
1. Recommendation (Strong Yes/Yes/Maybe/No/Strong No)
2. Educational Pedigree (Exceptional/Strong/Good/Average/Weak)
3. Company Pedigree (Exceptional/Strong/Good/Average/Weak)
4. Trajectory (Exceptional/Strong/Good/Average/Weak)
5. Is Software Engineer (true/false)"""
        }
    ]
    
    # Create handler (without Label Studio connection)
    handler = LabelStudioHandler(config={
        'url': 'http://localhost:4115',
        'api_key': 'test',
        'project_id': 1
    })
    
    # Parse conquest data
    conquest_data = handler._parse_conquest_from_messages(messages, 'candidate_evaluation')
    
    # Print results
    print("✅ Parsed Conquest Data:")
    print(json.dumps(conquest_data, indent=2))
    
    # Verify fields
    print("\n📋 Verification:")
    checks = [
        ("name", "Jane Smith"),
        ("role", "Senior Software Engineer"),
        ("location", "San Francisco, CA"),
        ("work_history length", 3),
        ("education length", 2),
        ("system_prompt exists", True),
        ("user_prompt exists", True),
    ]
    
    all_passed = True
    for field, expected in checks:
        if "length" in field:
            field_name = field.replace(" length", "")
            actual = len(conquest_data.get(field_name, []))
            passed = actual == expected
        elif "exists" in field:
            field_name = field.replace(" exists", "")
            actual = bool(conquest_data.get(field_name))
            passed = actual == expected
        else:
            actual = conquest_data.get(field)
            passed = actual == expected
        
        status = "✅" if passed else "❌"
        print(f"{status} {field}: {actual} {'==' if passed else '!='} {expected}")
        
        if not passed:
            all_passed = False
    
    return all_passed

def test_task_data_structure():
    """Test that task_data has all required fields."""
    print_section("TEST 2: Task Data Structure")
    
    # Simulate what the handler does
    messages = [
        {
            "role": "system",
            "content": "You are an expert technical recruiter."
        },
        {
            "role": "user",
            "content": "Name: John Doe\nRole: Engineer\nLocation: NYC"
        }
    ]
    
    metadata = {
        'conquest_id': 'test_conquest_123',
        'philosopher': 'test@example.com',
        'domain': 'software_engineering',
        'schema_type': 'candidate_evaluation'
    }
    
    # Create handler
    handler = LabelStudioHandler(config={
        'url': 'http://localhost:4115',
        'api_key': 'test',
        'project_id': 1
    })
    
    # Parse conquest data
    conquest_data = handler._parse_conquest_from_messages(messages, metadata['schema_type'])
    
    # Build task_data (simulating what handle() does)
    task_data = {
        "custom_id": "test_123",
        "batch_id": "batch_abc",
        "conquest_id": metadata['conquest_id'],
        "philosopher": metadata['philosopher'],
        "domain": metadata['domain'],
        "schema_type": metadata['schema_type'],
        "model": "gemma-3-4b",
        **conquest_data,
        "llm_response": "Test response"
    }
    
    print("✅ Task Data Structure:")
    print(json.dumps(task_data, indent=2))
    
    # Verify required fields for bidirectional sync
    print("\n📋 Required Fields for Bidirectional Sync:")
    required_fields = [
        'conquest_id',
        'philosopher',
        'domain',
        'name',
        'user_prompt',
        'llm_response'
    ]
    
    all_passed = True
    for field in required_fields:
        exists = field in task_data
        has_value = bool(task_data.get(field))
        status = "✅" if (exists and has_value) else "❌"
        print(f"{status} {field}: {task_data.get(field, 'MISSING')}")
        
        if not (exists and has_value):
            all_passed = False
    
    return all_passed

def test_metadata_extraction():
    """Test metadata extraction from custom_id."""
    print_section("TEST 3: Metadata Extraction from Custom ID")
    
    test_cases = [
        {
            "custom_id": "test@example.com_engineering_candidate_123",
            "expected": {
                "philosopher": "test@example.com",
                "domain": "engineering",
                "conquest_id": "candidate_123"
            },
            "note": "Email format - domain should not contain underscores"
        },
        {
            "custom_id": "conquest_abc123",
            "expected": {
                "conquest_id": "abc123"
            }
        },
        {
            "custom_id": "candidate_456",
            "expected": {
                "conquest_type": "candidate_evaluation",
                "conquest_id": "456"
            }
        }
    ]
    
    all_passed = True
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['custom_id']}")
        
        custom_id = test_case['custom_id']

        extracted = {}

        # Parse logic (from api_server.py - UPDATED VERSION)
        if '@' in custom_id:
            # Format: email@domain.com_domain_name_conquest_id
            # Split only on first 2 underscores to preserve domain names with underscores
            parts = custom_id.split('_', 2)
            if len(parts) >= 1:
                extracted['philosopher'] = parts[0]
            if len(parts) >= 2:
                extracted['domain'] = parts[1]
            if len(parts) >= 3:
                extracted['conquest_id'] = parts[2]
        else:
            # No email, try other formats
            parts = custom_id.split('_')
            if parts[0] == 'conquest' and len(parts) > 1:
                extracted['conquest_id'] = '_'.join(parts[1:])
            elif parts[0] == 'candidate' and len(parts) > 1:
                extracted['conquest_type'] = 'candidate_evaluation'
                extracted['conquest_id'] = '_'.join(parts[1:])
        
        print(f"Extracted: {json.dumps(extracted, indent=2)}")
        print(f"Expected:  {json.dumps(test_case['expected'], indent=2)}")
        
        # Check if all expected fields match
        passed = all(
            extracted.get(k) == v 
            for k, v in test_case['expected'].items()
        )
        
        status = "✅" if passed else "❌"
        print(f"{status} Test Case {i}")
        
        if not passed:
            all_passed = False
    
    return all_passed

def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("  DATA PARSING TESTS")
    print("="*80)
    
    results = []
    
    # Test 1: Parse candidate from messages
    try:
        passed = test_parse_candidate_from_messages()
        results.append(("Parse Candidate Data", passed))
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Parse Candidate Data", False))
    
    # Test 2: Task data structure
    try:
        passed = test_task_data_structure()
        results.append(("Task Data Structure", passed))
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Task Data Structure", False))
    
    # Test 3: Metadata extraction
    try:
        passed = test_metadata_extraction()
        results.append(("Metadata Extraction", passed))
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Metadata Extraction", False))
    
    # Print summary
    print_section("TEST SUMMARY")
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*80)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")
    print("="*80 + "\n")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

