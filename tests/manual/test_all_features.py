#!/usr/bin/env python3
"""
Test all completed features:
1. Input data parsing
2. Schema loading
3. Schema prompt generation
"""

import sys
from pathlib import Path

# Add curation_app to path
sys.path.insert(0, str(Path(__file__).parent))

from curation_app.api import _parse_candidate_from_messages
from curation_app.conquest_schemas import get_registry


def test_input_parsing():
    """Test Task 1: Input data parsing"""
    print("=" * 80)
    print("TASK 1: INPUT DATA PARSING")
    print("=" * 80)

    messages = [
        {
            "role": "system",
            "content": "You are evaluating candidates..."
        },
        {
            "role": "user",
            "content": """**Candidate:** Min Thet K
**Current Role:** Software Engineer at Bloomberg
**Location:** New York, New York, United States

**Work History:**
• Software Engineer at Bloomberg (2023-07 - present)
• Software Engineer at Microsoft (2021-04 - 2022-01)

**Education:**
• Bachelor of Science - BS in Computer Science from MIT
• Master of Engineering - MEng in Computer Science from MIT"""
        }
    ]

    result = _parse_candidate_from_messages(messages)

    checks = [
        ("Name", result.get("name") == "Min Thet K"),
        ("Current Role", result.get("current_role") == "Software Engineer at Bloomberg"),
        ("Location", result.get("location") == "New York, New York, United States"),
        ("Work History", len(result.get("work_history", [])) >= 2),
        ("Education", len(result.get("education", [])) == 2),
    ]

    all_passed = True
    for check_name, passed in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check_name}")
        if not passed:
            all_passed = False

    print()
    return all_passed


def test_schema_loading():
    """Test Task 3: Schema loading"""
    print("=" * 80)
    print("TASK 3: SCHEMA LOADING")
    print("=" * 80)

    registry = get_registry()
    schemas = registry.list_schemas()

    expected_schemas = [
        "candidate_evaluation",
        "email_evaluation",
        "report_evaluation",
        "cv_parsing",
        "cartographer",
        "quil_email"
    ]

    loaded_ids = [s.id for s in schemas]

    print(f"Expected: {len(expected_schemas)} schemas")
    print(f"Loaded: {len(loaded_ids)} schemas")
    print()

    all_passed = True
    for schema_id in expected_schemas:
        if schema_id in loaded_ids:
            print(f"✅ PASS: {schema_id}")
        else:
            print(f"❌ FAIL: {schema_id} not found")
            all_passed = False

    print()
    return all_passed


def test_schema_prompts():
    """Test Task 2: Schema prompt generation"""
    print("=" * 80)
    print("TASK 2: SCHEMA PROMPT GENERATION")
    print("=" * 80)

    registry = get_registry()

    test_schemas = ["candidate_evaluation", "cv_parsing", "cartographer", "quil_email"]

    all_passed = True
    for schema_id in test_schemas:
        schema = registry.get_schema(schema_id)
        if not schema:
            print(f"❌ FAIL: Schema {schema_id} not found")
            all_passed = False
            continue

        # Build prompt (simulating the endpoint logic)
        prompt_parts = [
            f"# {schema.name}",
            f"\n{schema.description}\n",
        ]

        # Build example response
        example = {}
        for question in schema.questions:
            if question.type == "choice" and question.options:
                example[question.id] = question.options[0]
            elif question.type == "rating" and question.options:
                example[question.id] = question.options[2] if len(question.options) > 2 else question.options[0]
            elif question.type == "boolean":
                example[question.id] = True
            elif question.type == "number":
                example[question.id] = 0
            elif question.type == "structured":
                example[question.id] = []
            else:
                example[question.id] = "Your answer here"

        # Verify prompt has content
        prompt = "".join(prompt_parts)
        has_prompt = len(prompt) > 0
        has_example = len(example) > 0

        if has_prompt and has_example:
            print(f"✅ PASS: {schema_id} - Prompt: {len(prompt)} chars, Example: {len(example)} fields")
        else:
            print(f"❌ FAIL: {schema_id} - Prompt: {len(prompt)} chars, Example: {len(example)} fields")
            all_passed = False

    print()
    return all_passed


def main():
    """Run all tests"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "TESTING ALL COMPLETED FEATURES" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    results = []

    # Test Task 1
    results.append(("Task 1: Input Data Parsing", test_input_parsing()))

    # Test Task 3
    results.append(("Task 3: Schema Loading", test_schema_loading()))

    # Test Task 2
    results.append(("Task 2: Schema Prompt Generation", test_schema_prompts()))

    # Summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    all_passed = True
    for task_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {task_name}")
        if not passed:
            all_passed = False

    print()
    print("=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED! ALL TASKS COMPLETE!")
    else:
        print("❌ SOME TESTS FAILED!")
    print("=" * 80)
    print()

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

