#!/usr/bin/env python3
"""
Convert Aris candidate JSON to OpenAI batch format (JSONL)

Usage:
    python aris_to_batch.py candidates-batch-5000.json output.jsonl

Input Format:
    Aris inference-test-data format with gemData and swarmData

Output JSONL Format:
    {"custom_id": "aristotle-id", "method": "POST", "url": "/v1/chat/completions", "body": {...}}
"""

import json
import sys
from typing import Dict, List, Optional
from pathlib import Path

# Aris Praxis System Prompt (from praxis-prompt-template.json)
SYSTEM_PROMPT = """You are evaluating a candidate profile to decide if we should reach out.

Judge the candidate on:

**Educational Pedigree**
• Bachelor's degree is the strongest pedigree signal.
• Selectivity and prestige of the undergrad institution is weighted most heavily.
• A top-tier CS/Engineering bachelor's degree = Great.
• A mid-tier or unselective bachelor's program = Average/Weak, regardless of later graduate study.
• Graduate degrees (MS, MBA, etc.) add value only if earned at a top school.
• A top-tier MS in CS/Engineering = Good/Great.
• A mid-tier MS is not a strong signal and can actually lower pedigree compared to no MS.
• PhD in CS/Engineering = always Good, but from a top-tier school = Great or Excellent.
• Technical majors (CS, EE, Software Engineering, related fields) are favored. Non-technical degrees are weaker, even at strong schools.

**Company Pedigree**
• Brand and caliber of employers (tier-1 tech, high-growth startups, selective teams, notable acquisitions).

**Trajectory**
• Speed and consistency of promotions relative to years of experience.
• Engineers with >8 years should typically be ≥ Senior SWE.
• Engineers with >12 years should typically be ≥ Staff SWE.
• Faster than these milestones = stronger trajectory. Slower = weaker trajectory.

**Is Software Engineer**
• Confirm titles and responsibilities are software engineering.

Return a concise recommendation and rationales. Ground reasoning in evidence from the profile."""

EXPECTED_FORMAT = """**Required JSON Response Format:**
{
  "recommendation": "Strong Yes | Yes | Maybe | No | Strong No",
  "reasoning": "<1–2 sentence overall summary>",
  "analysis": {
    "educational_pedigree": {
      "rating": "Great | Good | Average | Weak | None",
      "reasoning": "<explain how bachelor's, grad, and/or PhD pedigree influenced the rating>"
    },
    "company_pedigree": {
      "rating": "Great | Good | Average | Weak | None",
      "reasoning": "<employer quality explanation>"
    },
    "trajectory": {
      "rating": "Great | Good | Average | Weak | None",
      "reasoning": "<promotion speed vs experience thresholds>"
    },
    "is_software_engineer": {
      "value": true,
      "reasoning": "<titles/responsibilities that confirm SWE focus>"
    }
  }
}

Analyze the candidate according to the criteria above and provide your evaluation in the exact JSON format specified."""


def format_work_history(work_info: List[Dict]) -> str:
    """Format work history from gemData"""
    if not work_info:
        return "No work history available"

    # Sort by start date (most recent first), handle None values
    sorted_work = sorted(
        work_info,
        key=lambda x: x.get('work_start_date') or '1970-01-01',
        reverse=True
    )
    
    lines = []
    for job in sorted_work:
        title = job.get('title', 'Unknown Title')
        company = job.get('company', 'Unknown Company')
        start = job.get('work_start_date', 'Unknown')
        end = job.get('work_end_date', 'Present') if job.get('is_current') else job.get('work_end_date', 'Unknown')

        # Format dates nicely (handle None values)
        if start and start != 'Unknown' and start != '1970-01-01':
            start = start[:7]  # YYYY-MM
        elif not start:
            start = 'Unknown'

        if end and end != 'Present' and end != 'Unknown' and end != '1970-01-01':
            end = end[:7]  # YYYY-MM
        elif not end:
            end = 'Unknown'

        lines.append(f"• {title} at {company} ({start} - {end})")
    
    return "\n".join(lines)


def format_education(education_info: List[Dict]) -> str:
    """Format education from gemData"""
    if not education_info:
        return "No education information available"
    
    # Filter out high school
    college_edu = [e for e in education_info if e.get('degree') not in ['High School', None]]
    
    if not college_edu:
        return "No college education listed"
    
    lines = []
    for edu in college_edu:
        degree = edu.get('degree', 'Unknown Degree')
        school = edu.get('school', 'Unknown School')
        field = edu.get('field_of_study', '')
        
        if field:
            lines.append(f"• {degree} in {field} from {school}")
        else:
            lines.append(f"• {degree} from {school}")
    
    return "\n".join(lines)


def build_candidate_context(candidate: Dict) -> str:
    """Build candidate context from Aris data"""

    gem_data = candidate.get('gemData', {})
    swarm_data = candidate.get('swarmData', {})

    # Extract basic info (handle None values)
    first_name = gem_data.get('first_name') or ''
    last_name = gem_data.get('last_name') or ''
    name = (first_name + ' ' + last_name).strip() or 'Unknown'

    current_title = gem_data.get('title') or 'Unknown Title'
    current_company = gem_data.get('company') or 'Unknown Company'
    location = gem_data.get('location') or 'Unknown Location'
    
    # Build context
    context_parts = [
        f"**Candidate:** {name}",
        f"**Current Role:** {current_title} at {current_company}",
        f"**Location:** {location}",
        "",
        "**Work History:**",
        format_work_history(gem_data.get('work_info', [])),
        "",
        "**Education:**",
        format_education(gem_data.get('education_info', [])),
    ]
    
    # Add skills if available
    if gem_data.get('skills'):
        skills = gem_data.get('skills', [])
        if isinstance(skills, list):
            context_parts.extend([
                "",
                f"**Skills:** {', '.join(skills)}"
            ])
    
    return "\n".join(context_parts)


def create_batch_request(candidate: Dict, model: str = "gemma3:12b") -> Dict:
    """Create a single batch request in OpenAI format"""
    
    aristotle_id = candidate.get('aristotleId', 'unknown')
    candidate_context = build_candidate_context(candidate)
    
    # Combine data prompt with expected format
    user_prompt = f"{candidate_context}\n\n{EXPECTED_FORMAT}"
    
    return {
        "custom_id": aristotle_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 2000,
            "temperature": 0.7
        }
    }


def convert_aris_to_batch(input_file: str, output_file: str, model: str = "gemma3:12b"):
    """Convert Aris JSON file to batch JSONL format"""
    
    print(f"Converting {input_file} to {output_file}...")
    
    # Read Aris data
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Extract metadata and candidates
    metadata = data.get('metadata', {})
    candidates = data.get('candidates', [])
    
    print(f"📊 Input Metadata:")
    print(f"   Batch size: {metadata.get('batchSize', 'unknown')}")
    print(f"   Exported at: {metadata.get('exportedAt', 'unknown')}")
    print(f"   Domain: {metadata.get('domain', 'unknown')}")
    
    data_quality = metadata.get('dataQuality', {})
    print(f"   Data quality:")
    print(f"     - With gemData: {data_quality.get('withGemData', 0)}")
    print(f"     - With swarmData: {data_quality.get('withSwarmData', 0)}")
    print(f"     - With cvData: {data_quality.get('withCvData', 0)}")
    print(f"     - With praxisData: {data_quality.get('withPraxisData', 0)}")
    
    print(f"\n🔄 Converting {len(candidates)} candidates...")
    
    requests_created = 0
    skipped = 0
    
    with open(output_file, 'w') as jsonl_f:
        for idx, candidate in enumerate(candidates, 1):
            # Skip candidates without gemData
            if not candidate.get('gemData'):
                skipped += 1
                continue
            
            # Create batch request
            request = create_batch_request(candidate, model)
            
            # Write to JSONL
            jsonl_f.write(json.dumps(request) + '\n')
            requests_created += 1
            
            # Progress update every 1000 rows
            if requests_created % 1000 == 0:
                print(f"  Processed {requests_created:,} candidates...")
    
    print(f"\n✅ Created {requests_created:,} batch requests")
    if skipped > 0:
        print(f"⚠️  Skipped {skipped} candidates (missing gemData)")
    print(f"✅ Output: {output_file}")
    
    # Calculate estimated metrics
    avg_system_tokens = 350  # System prompt
    avg_user_tokens = 800  # Candidate data + expected format
    avg_completion_tokens = 400  # JSON response
    
    total_tokens_baseline = requests_created * (avg_system_tokens + avg_user_tokens + avg_completion_tokens)
    total_tokens_optimized = avg_system_tokens + (requests_created * (avg_user_tokens + avg_completion_tokens))
    token_savings = ((total_tokens_baseline - total_tokens_optimized) / total_tokens_baseline) * 100
    
    print(f"\n📊 Estimated Metrics:")
    print(f"   Requests: {requests_created:,}")
    print(f"   Avg tokens per request: {avg_system_tokens + avg_user_tokens + avg_completion_tokens}")
    print(f"   Baseline tokens: {total_tokens_baseline:,}")
    print(f"   Optimized tokens: {total_tokens_optimized:,}")
    print(f"   Token savings: {token_savings:.1f}%")
    
    # Estimate processing time
    throughput = 3.5  # req/s (conservative from benchmarks)
    estimated_time_sec = requests_created / throughput
    estimated_time_min = estimated_time_sec / 60
    estimated_time_hours = estimated_time_sec / 3600
    
    print(f"\n⏱️  Estimated Processing Time:")
    print(f"   Throughput: {throughput} req/s")
    if estimated_time_hours >= 1:
        print(f"   Total time: {estimated_time_sec:,.0f}s ({estimated_time_hours:.1f} hours)")
    else:
        print(f"   Total time: {estimated_time_sec:,.0f}s ({estimated_time_min:.1f} minutes)")
    
    return requests_created


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Convert Aris JSON to batch JSONL:")
        print("    python aris_to_batch.py input.json output.jsonl [model]")
        print()
        print("Examples:")
        print("  python aris_to_batch.py candidates-batch-5000.json batch_5k.jsonl")
        print("  python aris_to_batch.py candidates-batch-5000.json batch_5k.jsonl gemma3:12b")
        sys.exit(1)
    
    # Parse arguments
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'batch_requests.jsonl'
    model = sys.argv[3] if len(sys.argv) > 3 else 'gemma3:12b'
    
    # Validate input file exists
    if not Path(input_file).exists():
        print(f"❌ Error: Input file not found: {input_file}")
        sys.exit(1)
    
    # Convert
    convert_aris_to_batch(input_file, output_file, model)


if __name__ == "__main__":
    main()

