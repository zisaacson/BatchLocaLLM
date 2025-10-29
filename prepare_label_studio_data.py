#!/usr/bin/env python3
"""
Prepare candidate data for Label Studio import.
Converts batch_5k.jsonl to Label Studio JSON format.
"""

import json
import sys

def extract_candidate_info(candidate):
    """Extract candidate information from batch request."""
    user_msg = None
    for msg in candidate.get('body', {}).get('messages', []):
        if msg.get('role') == 'user':
            user_msg = msg.get('content', '')
            break
    
    if not user_msg:
        return None
    
    # Extract basic info
    lines = user_msg.split('\n')
    info = {
        'name': '',
        'role': '',
        'location': '',
        'work_history': [],
        'education': []
    }
    
    for line in lines:
        if line.startswith('**Candidate:**'):
            info['name'] = line.replace('**Candidate:**', '').strip()
        elif line.startswith('**Current Role:**'):
            info['role'] = line.replace('**Current Role:**', '').strip()
        elif line.startswith('**Location:**'):
            info['location'] = line.replace('**Location:**', '').strip()
    
    # Extract work history
    in_work = False
    in_edu = False
    for line in lines:
        if '**Work History:**' in line:
            in_work = True
            in_edu = False
            continue
        elif '**Education:**' in line:
            in_work = False
            in_edu = True
            continue
        elif line.startswith('**'):
            in_work = False
            in_edu = False
            continue
        
        if in_work and line.strip().startswith('•'):
            info['work_history'].append(line.strip()[1:].strip())
        elif in_edu and line.strip().startswith('•'):
            info['education'].append(line.strip()[1:].strip())
    
    return info

def load_llm_results(results_file):
    """Load LLM evaluation results."""
    results = {}
    try:
        with open(results_file, 'r') as f:
            for line in f:
                if line.strip():
                    result = json.loads(line)
                    custom_id = result.get('custom_id')
                    if custom_id:
                        # Extract evaluation from response
                        try:
                            content = result['response']['body']['choices'][0]['message']['content']
                            # Content is a JSON string, parse it
                            evaluation = json.loads(content.strip())
                            results[custom_id] = evaluation
                        except (KeyError, json.JSONDecodeError, TypeError) as e:
                            # Skip if parsing fails
                            pass
    except FileNotFoundError:
        print(f"Warning: Results file {results_file} not found", file=sys.stderr)

    return results

def convert_to_label_studio(batch_file, results_file, output_file, limit=None):
    """Convert batch data to Label Studio format."""
    
    # Load LLM results
    llm_results = load_llm_results(results_file)
    
    # Convert candidates
    tasks = []
    with open(batch_file, 'r') as f:
        for i, line in enumerate(f):
            if limit and i >= limit:
                break
            
            candidate = json.loads(line)
            custom_id = candidate.get('custom_id')
            
            # Extract candidate info
            info = extract_candidate_info(candidate)
            if not info:
                continue
            
            # Get LLM evaluation if available
            llm_eval = llm_results.get(custom_id, {})

            # Extract LLM evaluation fields safely
            if llm_eval and isinstance(llm_eval, dict):
                llm_rec = llm_eval.get('recommendation', 'N/A')
                llm_reason = llm_eval.get('reasoning', 'N/A')
                analysis = llm_eval.get('analysis', {})

                if isinstance(analysis, dict):
                    edu_pedigree = analysis.get('educational_pedigree', {})
                    company_pedigree = analysis.get('company_pedigree', {})
                    trajectory = analysis.get('trajectory', {})
                    is_swe = analysis.get('is_software_engineer', {})

                    llm_edu = edu_pedigree.get('rating', 'N/A') if isinstance(edu_pedigree, dict) else 'N/A'
                    llm_company = company_pedigree.get('rating', 'N/A') if isinstance(company_pedigree, dict) else 'N/A'
                    llm_traj = trajectory.get('rating', 'N/A') if isinstance(trajectory, dict) else 'N/A'
                    llm_swe = is_swe.get('value', False) if isinstance(is_swe, dict) else False
                else:
                    llm_edu = llm_company = llm_traj = 'N/A'
                    llm_swe = False
            else:
                llm_rec = llm_reason = llm_edu = llm_company = llm_traj = 'N/A'
                llm_swe = False

            # Create Label Studio task
            task = {
                'data': {
                    'custom_id': custom_id,
                    'name': info['name'],
                    'role': info['role'],
                    'location': info['location'],
                    'work_history': info['work_history'][:5],  # Top 5 positions
                    'education': info['education'],
                    'llm_recommendation': llm_rec,
                    'llm_reasoning': llm_reason,
                    'llm_educational_pedigree': llm_edu,
                    'llm_company_pedigree': llm_company,
                    'llm_trajectory': llm_traj,
                    'llm_is_swe': llm_swe,
                }
            }
            
            tasks.append(task)
    
    # Write output
    with open(output_file, 'w') as f:
        json.dump(tasks, f, indent=2)
    
    print(f"✅ Converted {len(tasks)} candidates to Label Studio format")
    print(f"📄 Output: {output_file}")
    return len(tasks)

if __name__ == '__main__':
    import sys

    batch_file = 'batch_5k.jsonl'
    results_file = 'qwen3_4b_5k_offline_results.jsonl'  # Using Qwen 3 4B results (has valid evaluations)
    output_file = 'label_studio_tasks.json'

    # Allow command line override
    if len(sys.argv) > 1:
        results_file = sys.argv[1]

    print(f"📊 Using results from: {results_file}")

    # Convert all 5000
    count = convert_to_label_studio(batch_file, results_file, output_file, limit=None)

    print(f"\n🎯 Next steps:")
    print(f"1. Go to http://localhost:4015")
    print(f"2. Create a new project")
    print(f"3. Import {output_file}")
    print(f"4. Start labeling!")

