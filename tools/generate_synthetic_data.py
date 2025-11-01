#!/usr/bin/env python3
"""
Generate synthetic candidate evaluation data for demonstrations and benchmarks.

This creates realistic but completely fake candidate profiles for testing
the batch processing system without exposing real candidate information.
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

# Synthetic data pools
FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Avery", "Quinn",
    "Sam", "Jamie", "Drew", "Blake", "Cameron", "Dakota", "Emerson", "Finley"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas"
]

COMPANIES = [
    "TechCorp", "DataSystems Inc", "CloudNine Solutions", "InnovateLabs",
    "DigitalWorks", "CodeCraft", "ByteBuilders", "AlgoTech", "DevOps Pro",
    "ScaleUp Systems", "AgileMinds", "FutureStack", "NexGen Software"
]

TITLES = [
    "Software Engineer", "Senior Software Engineer", "Staff Software Engineer",
    "Backend Developer", "Full Stack Developer", "Frontend Engineer",
    "DevOps Engineer", "Data Engineer", "ML Engineer", "Platform Engineer"
]

UNIVERSITIES = [
    "State University", "Tech Institute", "Metropolitan University",
    "National Polytechnic", "City College", "Regional University",
    "Institute of Technology", "Public University"
]

DEGREES = [
    "BS Computer Science", "BS Software Engineering", "BS Electrical Engineering",
    "MS Computer Science", "BS Information Systems", "BS Data Science"
]

SKILLS = [
    "Python", "JavaScript", "TypeScript", "Go", "Rust", "Java", "C++",
    "React", "Node.js", "Django", "FastAPI", "PostgreSQL", "MongoDB",
    "Docker", "Kubernetes", "AWS", "GCP", "Azure", "Git", "CI/CD"
]

CITIES = [
    "San Francisco, CA", "New York, NY", "Seattle, WA", "Austin, TX",
    "Boston, MA", "Denver, CO", "Portland, OR", "Chicago, IL",
    "Los Angeles, CA", "Atlanta, GA", "Remote"
]


def generate_candidate(candidate_id: int) -> dict:
    """Generate a single synthetic candidate profile."""
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    name = f"{first_name} {last_name}"
    
    # Generate work history (1-4 positions)
    num_positions = random.randint(1, 4)
    work_history = []
    
    current_year = 2025
    years_back = 0
    
    for i in range(num_positions):
        company = random.choice(COMPANIES)
        title = random.choice(TITLES)
        
        start_year = current_year - years_back - random.randint(1, 3)
        if i == 0:  # Current position
            end_year = "Present"
        else:
            end_year = start_year + random.randint(1, 3)
            years_back = current_year - end_year
        
        work_history.append(f"• {title} at {company} ({start_year}-{end_year})")
    
    # Generate education
    university = random.choice(UNIVERSITIES)
    degree = random.choice(DEGREES)
    grad_year = current_year - random.randint(2, 10)
    education = f"• {degree}, {university} ({grad_year})"
    
    # Generate skills (5-10 random skills)
    num_skills = random.randint(5, 10)
    skills = random.sample(SKILLS, num_skills)
    skills_str = ", ".join(skills)
    
    # Generate location
    location = random.choice(CITIES)
    
    # Create candidate profile text
    profile = f"""**Candidate:** {name}
**Current Role:** {work_history[0].replace('• ', '')}
**Location:** {location}

**Work History:**
{chr(10).join(work_history)}

**Education:**
{education}

**Skills:** {skills_str}

**Years of Experience:** {random.randint(2, 15)}

Please evaluate this candidate for a senior software engineering role. Assess their:
1. Technical trajectory and growth
2. Company pedigree and experience quality
3. Educational background
4. Overall fit for the position

Provide ratings and a brief explanation for each criterion."""
    
    return {
        "custom_id": f"candidate-{candidate_id:05d}",
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": "google/gemma-3-4b-it",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert technical recruiter evaluating candidates for software engineering positions."
                },
                {
                    "role": "user",
                    "content": profile
                }
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
    }


def generate_batch_file(num_candidates: int, output_path: str):
    """Generate a batch file with synthetic candidates."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        for i in range(num_candidates):
            candidate = generate_candidate(i + 1)
            f.write(json.dumps(candidate) + '\n')
    
    print(f"✅ Generated {num_candidates} synthetic candidates")
    print(f"📁 Saved to: {output_file}")
    print(f"📊 File size: {output_file.stat().st_size / 1024:.1f} KB")


def generate_benchmark_metadata(dataset_name: str, num_requests: int, models: list[str]):
    """Generate metadata for synthetic benchmark."""
    metadata = {
        "dataset": dataset_name,
        "description": f"Synthetic candidate evaluations for benchmarking ({num_requests} requests)",
        "created_at": datetime.now().isoformat(),
        "total_requests": num_requests,
        "models_tested": models,
        "data_type": "synthetic",
        "note": "This is completely synthetic data generated for demonstration purposes. No real candidate information is included."
    }
    
    metadata_path = Path(f"benchmarks/metadata/{dataset_name}.json")
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Generated metadata: {metadata_path}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate synthetic candidate data")
    parser.add_argument("--count", type=int, default=100, help="Number of candidates to generate")
    parser.add_argument("--output", type=str, default="examples/datasets/synthetic_candidates.jsonl", help="Output file path")
    parser.add_argument("--metadata", action="store_true", help="Also generate benchmark metadata")
    
    args = parser.parse_args()
    
    # Generate batch file
    generate_batch_file(args.count, args.output)
    
    # Generate metadata if requested
    if args.metadata:
        dataset_name = Path(args.output).stem
        models = ["gemma-3-4b", "llama-3.2-3b", "qwen-3-4b"]
        generate_benchmark_metadata(dataset_name, args.count, models)
    
    print("\n🎉 Synthetic data generation complete!")
    print("\n📝 Example usage:")
    print(f"   curl -X POST http://localhost:4080/v1/files \\")
    print(f"     -F 'file=@{args.output}' \\")
    print(f"     -F 'purpose=batch'")

