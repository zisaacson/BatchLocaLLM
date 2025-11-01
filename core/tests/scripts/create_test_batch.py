#!/usr/bin/env python3
"""Create a test batch file with 100 candidate evaluation requests."""

import json

# Simple candidate evaluation prompt
prompt = """You are evaluating candidates for software engineering roles.

CANDIDATE: John Doe
Email: john.doe@example.com
Headline: Senior Software Engineer at Google

Work Experience:
- Senior Software Engineer at Google (2020-01 - Present)
- Software Engineer at Microsoft (2017-01 - 2020-01)
- Junior Developer at Startup Inc (2015-01 - 2017-01)

Education:
- BS Computer Science, Stanford University (2011-2015)

Evaluate this candidate and provide:
1. Recommendation (Strong Yes/Yes/Maybe/No/Strong No)
2. Educational Pedigree (Exceptional/Strong/Good/Average/Weak)
3. Company Pedigree (Exceptional/Strong/Good/Average/Weak)
4. Trajectory (Exceptional/Strong/Good/Average/Weak)
5. Is Software Engineer (true/false)

Respond in JSON format:
{
  "recommendation": "...",
  "educational_pedigree": "...",
  "company_pedigree": "...",
  "trajectory": "...",
  "is_software_engineer": true/false
}
"""

# Create 100 requests
requests = []
for i in range(100):
    request = {
        "custom_id": f"test-{i}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "google/gemma-3-4b-it",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_completion_tokens": 2000
        }
    }
    requests.append(request)

# Write to file
with open("test_100_batch.jsonl", "w") as f:
    for req in requests:
        f.write(json.dumps(req) + "\n")

print(f"Created test_100_batch.jsonl with {len(requests)} requests")

