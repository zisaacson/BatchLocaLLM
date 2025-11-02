#!/bin/bash
set -e

# Automated Label Studio Setup Script
# This script sets up Label Studio with the correct configuration for vLLM Batch Server

LABEL_STUDIO_URL="http://localhost:4115"
PROJECT_NAME="vLLM Batch Results"
ADMIN_EMAIL="admin@vllm-batch.local"
ADMIN_PASSWORD="VllmBatch2024!"  # Change this to your secure password

echo "🚀 Label Studio Automated Setup"
echo "================================"
echo ""

# Step 1: Check if Label Studio is running
echo "📋 Step 1: Checking Label Studio status..."
if ! docker ps | grep -q vllm-label-studio; then
    echo "   Starting Label Studio container..."
    cd docker
    docker compose up -d label-studio
    cd ..
    echo "   Waiting 45 seconds for Label Studio to start..."
    sleep 45
else
    echo "   ✅ Label Studio is already running"
fi

# Step 2: Wait for health check
echo ""
echo "📋 Step 2: Waiting for Label Studio to be healthy..."
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s -f "$LABEL_STUDIO_URL/health" > /dev/null 2>&1; then
        echo "   ✅ Label Studio is healthy!"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "   Waiting... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "   ❌ Error: Label Studio failed to start"
    echo "   Check logs: docker logs vllm-label-studio"
    exit 1
fi

# Step 3: Check if already set up
echo ""
echo "📋 Step 3: Checking if Label Studio is already configured..."

# Try to get user info (will fail if not set up)
USER_INFO=$(curl -s "$LABEL_STUDIO_URL/api/current-user/whoami" 2>/dev/null || echo "")

if echo "$USER_INFO" | grep -q "email"; then
    echo "   ⚠️  Label Studio appears to be already configured"
    echo "   Found existing user setup"
    echo ""
    echo "   If you want to reconfigure, you need to:"
    echo "   1. Stop Label Studio: cd docker && docker compose down label-studio"
    echo "   2. Remove volume: docker volume rm vllm-label-studio-data"
    echo "   3. Run this script again"
    echo ""
    read -p "   Do you want to continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "   Exiting..."
        exit 0
    fi
fi

# Step 4: Create admin user via Django shell
echo ""
echo "📋 Step 4: Creating admin user..."

# Create user using Django management command
docker exec vllm-label-studio bash -c "
export DJANGO_SUPERUSER_PASSWORD='$ADMIN_PASSWORD'
python manage.py createsuperuser \
    --noinput \
    --email '$ADMIN_EMAIL' \
    2>/dev/null || echo 'User may already exist'
" > /dev/null 2>&1

echo "   ✅ Admin user created/verified"
echo "   Email: $ADMIN_EMAIL"
echo "   Password: $ADMIN_PASSWORD"
echo ""
echo "   ⚠️  IMPORTANT: Save these credentials in your password manager!"

# Step 5: Get API token
echo ""
echo "📋 Step 5: Getting API token..."

# Login and get token
TOKEN_RESPONSE=$(curl -s -X POST "$LABEL_STUDIO_URL/api/auth/login/" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
    2>/dev/null || echo "")

if echo "$TOKEN_RESPONSE" | grep -q "token"; then
    API_TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"token":"[^"]*' | cut -d'"' -f4)
    echo "   ✅ API token obtained"
else
    echo "   ❌ Failed to get API token"
    echo "   Response: $TOKEN_RESPONSE"
    echo ""
    echo "   You'll need to get the token manually:"
    echo "   1. Go to $LABEL_STUDIO_URL"
    echo "   2. Log in with: $ADMIN_EMAIL / $ADMIN_PASSWORD"
    echo "   3. Go to Account & Settings → Access Token"
    echo "   4. Copy the token and update .env file"
    exit 1
fi

# Step 6: Create project
echo ""
echo "📋 Step 6: Creating project..."

PROJECT_RESPONSE=$(curl -s -X POST "$LABEL_STUDIO_URL/api/projects/" \
    -H "Authorization: Token $API_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"title\":\"$PROJECT_NAME\",\"description\":\"Curation and quality control for vLLM batch processing results\"}" \
    2>/dev/null || echo "")

if echo "$PROJECT_RESPONSE" | grep -q "id"; then
    PROJECT_ID=$(echo "$PROJECT_RESPONSE" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
    echo "   ✅ Project created with ID: $PROJECT_ID"
else
    echo "   ⚠️  Project may already exist or creation failed"
    # Try to get existing project
    PROJECTS=$(curl -s -X GET "$LABEL_STUDIO_URL/api/projects/" \
        -H "Authorization: Token $API_TOKEN" 2>/dev/null || echo "")
    
    if echo "$PROJECTS" | grep -q "id"; then
        PROJECT_ID=$(echo "$PROJECTS" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
        echo "   Using existing project ID: $PROJECT_ID"
    else
        echo "   ❌ Could not determine project ID"
        PROJECT_ID=1
        echo "   Assuming project ID: $PROJECT_ID"
    fi
fi

# Step 7: Configure labeling interface
echo ""
echo "📋 Step 7: Configuring labeling interface..."

# Read the labeling config
LABELING_CONFIG='<View>
  <Header value="Candidate Evaluation Review"/>
  <View style="box-shadow: 2px 2px 5px #999; padding: 20px; margin-top: 2em; border-radius: 5px;">
    <Header value="Candidate Information"/>
    <Text name="candidate_name" value="$candidate_name"/>
    <Text name="candidate_title" value="$candidate_title"/>
    <Text name="candidate_company" value="$candidate_company"/>
  </View>
  <View style="box-shadow: 2px 2px 5px #999; padding: 20px; margin-top: 2em; border-radius: 5px;">
    <Header value="Model Response"/>
    <Text name="model_name" value="Model: $model_name"/>
    <TextArea name="response" value="$response" rows="10" editable="true"/>
  </View>
  <View style="box-shadow: 2px 2px 5px #999; padding: 20px; margin-top: 2em; border-radius: 5px;">
    <Header value="Evaluation"/>
    <Choices name="recommendation" toName="response" choice="single" showInline="true">
      <Header value="Recommendation"/>
      <Choice value="Strong Yes"/>
      <Choice value="Yes"/>
      <Choice value="Maybe"/>
      <Choice value="No"/>
      <Choice value="Strong No"/>
    </Choices>
    <Choices name="trajectory" toName="response" choice="single" showInline="true">
      <Header value="Career Trajectory"/>
      <Choice value="Exceptional"/>
      <Choice value="Strong"/>
      <Choice value="Good"/>
      <Choice value="Average"/>
      <Choice value="Weak"/>
    </Choices>
    <Choices name="company_pedigree" toName="response" choice="single" showInline="true">
      <Header value="Company Pedigree"/>
      <Choice value="Exceptional"/>
      <Choice value="Strong"/>
      <Choice value="Good"/>
      <Choice value="Average"/>
      <Choice value="Weak"/>
    </Choices>
    <Choices name="educational_pedigree" toName="response" choice="single" showInline="true">
      <Header value="Educational Pedigree"/>
      <Choice value="Exceptional"/>
      <Choice value="Strong"/>
      <Choice value="Good"/>
      <Choice value="Average"/>
      <Choice value="Weak"/>
    </Choices>
    <Checkbox name="is_software_engineer" toName="response">
      <Label value="Is Software Engineer"/>
    </Checkbox>
  </View>
  <View style="box-shadow: 2px 2px 5px #999; padding: 20px; margin-top: 2em; border-radius: 5px;">
    <Header value="Quality Control"/>
    <Rating name="quality" toName="response" maxRating="5" icon="star" size="large"/>
    <TextArea name="notes" toName="response" placeholder="Notes or corrections..." rows="3"/>
  </View>
</View>'

# Update project with labeling config
CONFIG_RESPONSE=$(curl -s -X PATCH "$LABEL_STUDIO_URL/api/projects/$PROJECT_ID/" \
    -H "Authorization: Token $API_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"label_config\":$(echo "$LABELING_CONFIG" | jq -Rs .)}" \
    2>/dev/null || echo "")

if echo "$CONFIG_RESPONSE" | grep -q "label_config"; then
    echo "   ✅ Labeling interface configured"
else
    echo "   ⚠️  Could not configure labeling interface automatically"
    echo "   You'll need to configure it manually (see docs/LABEL_STUDIO_SETUP.md)"
fi

# Step 8: Update .env file
echo ""
echo "📋 Step 8: Updating .env file..."

if [ -f .env ]; then
    # Backup existing .env
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo "   Backed up existing .env"
    
    # Update or add Label Studio settings
    if grep -q "LABEL_STUDIO_TOKEN=" .env; then
        sed -i "s|LABEL_STUDIO_TOKEN=.*|LABEL_STUDIO_TOKEN=$API_TOKEN|" .env
    else
        echo "LABEL_STUDIO_TOKEN=$API_TOKEN" >> .env
    fi
    
    if grep -q "LABEL_STUDIO_PROJECT_ID=" .env; then
        sed -i "s|LABEL_STUDIO_PROJECT_ID=.*|LABEL_STUDIO_PROJECT_ID=$PROJECT_ID|" .env
    else
        echo "LABEL_STUDIO_PROJECT_ID=$PROJECT_ID" >> .env
    fi
    
    echo "   ✅ .env file updated"
else
    echo "   ❌ .env file not found"
    echo "   Please create .env file with:"
    echo "   LABEL_STUDIO_TOKEN=$API_TOKEN"
    echo "   LABEL_STUDIO_PROJECT_ID=$PROJECT_ID"
fi

# Step 9: Test connection
echo ""
echo "📋 Step 9: Testing API connection..."

TEST_RESPONSE=$(curl -s -X GET "$LABEL_STUDIO_URL/api/projects/$PROJECT_ID/" \
    -H "Authorization: Token $API_TOKEN" 2>/dev/null || echo "")

if echo "$TEST_RESPONSE" | grep -q "title"; then
    echo "   ✅ API connection successful!"
else
    echo "   ❌ API connection failed"
    echo "   Response: $TEST_RESPONSE"
fi

# Summary
echo ""
echo "================================"
echo "✅ Label Studio Setup Complete!"
echo "================================"
echo ""
echo "📋 Configuration Summary:"
echo "   URL: $LABEL_STUDIO_URL"
echo "   Admin Email: $ADMIN_EMAIL"
echo "   Admin Password: $ADMIN_PASSWORD"
echo "   API Token: $API_TOKEN"
echo "   Project ID: $PROJECT_ID"
echo ""
echo "🔐 IMPORTANT: Save these credentials securely!"
echo ""
echo "📝 Next Steps:"
echo "   1. Open Label Studio: $LABEL_STUDIO_URL"
echo "   2. Log in with the credentials above"
echo "   3. Verify the project and labeling interface"
echo "   4. Run a test batch job to verify integration"
echo ""
echo "📚 Documentation: docs/LABEL_STUDIO_SETUP.md"
echo ""

