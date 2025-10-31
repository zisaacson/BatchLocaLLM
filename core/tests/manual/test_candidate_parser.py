#!/usr/bin/env python3
"""
Test the candidate data parser
"""

import json
import sys
from pathlib import Path

# Add curation_app to path
sys.path.insert(0, str(Path(__file__).parent))

from curation_app.api import _parse_candidate_from_messages


def test_parser():
    """Test parsing candidate data from real batch input"""

    # Sample messages from real batch input
    messages = [
        {
            "role": "system",
            "content": "You are evaluating a candidate profile to decide if we should reach out.\n\nJudge the candidate on:\n\n**Educational Pedigree**\n• Bachelor's degree is the strongest pedigree signal."
        },
        {
            "role": "user",
            "content": """**Candidate:** Min Thet K
**Current Role:** Software Engineer at Bloomberg
**Location:** New York, New York, United States

**Work History:**
• Software Engineer at Bloomberg (2023-07 - 1970-01-01)
• Graduate Teaching Assistant - 6.1910 (Computation Structures) at Massachusetts Institute of Technology (2023-02 - 2023-05)
• Software Engineer Intern at Bloomberg (2022-06 - 2022-08)
• Software Engineer at Microsoft (2021-04 - 2022-01)
• Software Engineer Intern at Microsoft (2019-05 - 2019-08)
• Robotics Engineering Intern at Dexai Robotics (2018-06 - 2018-08)

**Education:**
• Bachelor of Science - BS in Computer Science from Massachusetts Institute of Technology
• Master of Engineering - MEng in Computer Science from Massachusetts Institute of Technology

**Required JSON Response Format:**
{
  "recommendation": "Strong Yes | Yes | Maybe | No | Strong No",
  "reasoning": "<1–2 sentence overall summary>"
}

Analyze the candidate according to the criteria above and provide your evaluation in the exact JSON format specified."""
        }
    ]

    # Parse candidate data
    result = _parse_candidate_from_messages(messages)

    # Print results
    print("=" * 80)
    print("CANDIDATE DATA PARSER TEST")
    print("=" * 80)
    print()
    print(json.dumps(result, indent=2))
    print()

    # Verify expected fields
    print("=" * 80)
    print("VERIFICATION")
    print("=" * 80)

    checks = [
        ("Name", result.get("name") == "Min Thet K"),
        ("Current Role", result.get("current_role") == "Software Engineer at Bloomberg"),
        ("Location", result.get("location") == "New York, New York, United States"),
        ("Work History Count", len(result.get("work_history", [])) >= 5),
        ("Education Count", len(result.get("education", [])) == 2),
        ("System Prompt", len(result.get("system_prompt", "")) > 0),
        ("User Prompt", len(result.get("user_prompt", "")) > 0),
    ]

    all_passed = True
    for check_name, passed in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check_name}")
        if not passed:
            all_passed = False

    print()
    print("=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED!")
    print("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = test_parser()
    sys.exit(0 if success else 1)

