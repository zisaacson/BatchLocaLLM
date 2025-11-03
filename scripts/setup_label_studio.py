#!/usr/bin/env python3
"""
Setup Label Studio for vLLM Batch Server integration.
Creates a project and generates an API token.
"""

import requests
import json
import sys

LABEL_STUDIO_URL = "http://localhost:4115"
EMAIL = "admin@example.com"  # Change this to your email
PASSWORD = "vllm_batch_2024"  # Change this to your password

def login():
    """Login to Label Studio and get session cookies."""
    print("🔐 Logging in to Label Studio...")

    # Use API login endpoint instead of web form
    session = requests.Session()

    login_data = {
        "email": EMAIL,
        "password": PASSWORD
    }

    response = session.post(
        f"{LABEL_STUDIO_URL}/api/auth/login",
        json=login_data,
        headers={"Content-Type": "application/json"}
    )

    if response.status_code == 200:
        print("✅ Logged in successfully")
        return session
    else:
        print(f"❌ Login failed: {response.status_code}")
        print(response.text[:500])
        return None

def get_user_info(session):
    """Get current user information."""
    print("\n📊 Getting user information...")
    
    response = session.get(f"{LABEL_STUDIO_URL}/api/current-user/whoami")
    
    if response.status_code == 200:
        user_info = response.json()
        print(f"✅ User: {user_info.get('email')}")
        print(f"   Token: {user_info.get('token', 'N/A')}")
        return user_info
    else:
        print(f"❌ Failed to get user info: {response.status_code}")
        return None

def create_project(session):
    """Create a Label Studio project for batch results."""
    print("\n📦 Creating Label Studio project...")
    
    # Label config for batch results
    label_config = """
<View>
  <Header value="Batch Job Result"/>
  
  <Text name="input" value="$input_text"/>
  <Header value="Model Response:"/>
  <Text name="output" value="$output_text"/>
  
  <Header value="Evaluation:"/>
  <Choices name="quality" toName="output" choice="single">
    <Choice value="Excellent"/>
    <Choice value="Good"/>
    <Choice value="Fair"/>
    <Choice value="Poor"/>
  </Choices>
  
  <TextArea name="notes" toName="output" placeholder="Notes or corrections..."/>
  
  <Checkbox name="use_for_training" toName="output">
    <Choice value="Use for training"/>
  </Checkbox>
</View>
"""
    
    project_data = {
        "title": "vLLM Batch Results",
        "description": "Batch inference results for curation and training data collection",
        "label_config": label_config,
        "is_published": True,
        "maximum_annotations": 1,
        "show_annotation_history": True,
        "show_collab_predictions": False
    }
    
    response = session.post(
        f"{LABEL_STUDIO_URL}/api/projects",
        json=project_data
    )
    
    if response.status_code == 201:
        project = response.json()
        print(f"✅ Project created: ID={project['id']}, Title='{project['title']}'")
        return project
    else:
        print(f"❌ Failed to create project: {response.status_code}")
        print(response.text[:500])
        
        # Try to get existing projects
        response = session.get(f"{LABEL_STUDIO_URL}/api/projects")
        if response.status_code == 200:
            projects = response.json().get('results', [])
            if projects:
                print(f"\n📋 Existing projects:")
                for p in projects:
                    print(f"   - ID={p['id']}, Title='{p['title']}'")
                return projects[0]
        
        return None

def main():
    print("=" * 70)
    print("🚀 Label Studio Setup for vLLM Batch Server")
    print("=" * 70)
    
    # Login
    session = login()
    if not session:
        sys.exit(1)
    
    # Get user info and token
    user_info = get_user_info(session)
    if not user_info:
        sys.exit(1)
    
    token = user_info.get('token')
    if not token:
        print("❌ No API token found in user info")
        sys.exit(1)
    
    # Create project
    project = create_project(session)
    if not project:
        print("⚠️  Using existing project or continuing without project")
    
    # Print summary
    print("\n" + "=" * 70)
    print("✅ SETUP COMPLETE!")
    print("=" * 70)
    print(f"\n📝 Configuration:")
    print(f"   LABEL_STUDIO_URL={LABEL_STUDIO_URL}")
    print(f"   LABEL_STUDIO_API_KEY={token}")
    if project:
        print(f"   LABEL_STUDIO_PROJECT_ID={project['id']}")
    print(f"\n🔧 Update your .env file with these values")
    print(f"\n🔐 Update GCP Secret Manager:")
    print(f"   ./scripts/manage_gcp_secrets.sh add label-studio-token \"{token}\"")
    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()

