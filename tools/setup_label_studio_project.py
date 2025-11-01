#!/usr/bin/env python3
"""
Automatically set up Label Studio project for gold-star curation.
Uses the Label Studio API to create project, configure interface, and import data.
"""

import requests
import json
import sys

# Configuration
LABEL_STUDIO_URL = "http://localhost:4115"
TOKEN_FILE = ".label_studio_token"
CONFIG_FILE = "label_studio_config.xml"
DATA_FILE = "label_studio_tasks.json"
PROJECT_NAME = "Gold Star Candidate Curation"

def load_token():
    """Load API token from file."""
    try:
        with open(TOKEN_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"❌ Error: {TOKEN_FILE} not found")
        print("Please create a personal access token in Label Studio and save it to .label_studio_token")
        sys.exit(1)

def get_access_token(refresh_token):
    """Exchange refresh token for access token."""
    response = requests.post(
        f"{LABEL_STUDIO_URL}/api/token/refresh",
        headers={"Content-Type": "application/json"},
        json={"refresh": refresh_token}
    )

    if response.status_code == 200:
        access_token = response.json()["access"]
        print("   ✅ Access token obtained")
        return access_token
    else:
        print(f"   ❌ Failed to get access token: {response.status_code}")
        print(f"      Response: {response.text}")
        sys.exit(1)

def load_config():
    """Load labeling interface configuration."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print(f"❌ Error: {CONFIG_FILE} not found")
        sys.exit(1)

def load_data():
    """Load tasks data."""
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Error: {DATA_FILE} not found")
        print("Run: python3 prepare_label_studio_data.py")
        sys.exit(1)

def create_project(access_token, config):
    """Create a new Label Studio project."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    response = try_create_project(headers, config)

    if response.status_code == 201:
        project = response.json()
        print(f"✅ Created project: {PROJECT_NAME}")
        print(f"   Project ID: {project['id']}")
        return project['id']
    else:
        print(f"❌ Failed to create project: {response.status_code}")
        print(f"   Response: {response.text}")
        sys.exit(1)

def try_create_project(headers, config):
    """Try to create project with given headers."""
    data = {
        "title": PROJECT_NAME,
        "label_config": config,
        "description": "Curate 5,000 candidates for gold-star training data"
    }

    return requests.post(
        f"{LABEL_STUDIO_URL}/api/projects",
        headers=headers,
        json=data
    )

def import_tasks(access_token, project_id, tasks):
    """Import tasks into the project."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    print(f"📤 Importing {len(tasks)} tasks...")
    
    # Import in batches of 1000 to avoid timeouts
    batch_size = 1000
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i+batch_size]
        
        response = requests.post(
            f"{LABEL_STUDIO_URL}/api/projects/{project_id}/import",
            headers=headers,
            json=batch
        )
        
        if response.status_code in [200, 201]:
            print(f"   ✅ Imported batch {i//batch_size + 1}/{(len(tasks)-1)//batch_size + 1} ({len(batch)} tasks)")
        else:
            print(f"   ❌ Failed to import batch: {response.status_code}")
            print(f"      Response: {response.text}")
            sys.exit(1)
    
    print(f"✅ Successfully imported all {len(tasks)} tasks!")

def get_project_url(project_id):
    """Get the URL to the project."""
    return f"{LABEL_STUDIO_URL}/projects/{project_id}"

def main():
    print("🚀 Setting up Label Studio project...\n")

    # Load refresh token
    print("1️⃣ Loading API token...")
    refresh_token = load_token()
    print("   ✅ Refresh token loaded")

    # Get access token
    print("   Exchanging for access token...")
    access_token = get_access_token(refresh_token)
    print()

    # Load configuration
    print("2️⃣ Loading labeling interface configuration...")
    config = load_config()
    print("   ✅ Configuration loaded\n")

    # Load data
    print("3️⃣ Loading candidate data...")
    tasks = load_data()
    print(f"   ✅ Loaded {len(tasks)} candidates\n")

    # Create project
    print("4️⃣ Creating Label Studio project...")
    project_id = create_project(access_token, config)
    print()

    # Import tasks
    print("5️⃣ Importing tasks...")
    import_tasks(access_token, project_id, tasks)
    print()
    
    # Success!
    project_url = get_project_url(project_id)
    print("=" * 60)
    print("🎉 SUCCESS! Label Studio project is ready!")
    print("=" * 60)
    print()
    print(f"📊 Project: {PROJECT_NAME}")
    print(f"🔗 URL: {project_url}")
    print(f"📝 Tasks: {len(tasks)} candidates")
    print()
    print("🚀 Next steps:")
    print(f"1. Open: {project_url}")
    print("2. Click 'Label All Tasks'")
    print("3. Start curating!")
    print()
    print("⌨️  Keyboard shortcuts:")
    print("   Ctrl+Enter - Submit & Next")
    print("   Ctrl+Backspace - Skip")
    print()

if __name__ == '__main__':
    main()

