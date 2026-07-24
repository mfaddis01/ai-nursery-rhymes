#!/bin/bash

echo "=========================================="
echo "  Google Drive Setup for Nursery Rhymes"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Step 1: Install dependencies
echo -e "${YELLOW}Step 1: Installing gcloud CLI...${NC}"
sudo apt-get update -qq
sudo apt-get install -y -qq google-cloud-sdk google-cloud-sdk-app-engine-python

# Verify installation
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}✗ gcloud installation failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ gcloud CLI installed${NC}"

# Step 2: Authenticate
echo ""
echo -e "${YELLOW}Step 2: Authenticate with Google${NC}"
echo "Run: gcloud auth application-default login"
echo "Then follow the browser prompt to sign in with your Google account"
echo ""
gcloud auth application-default login

# Step 3: Set up project
echo ""
echo -e "${YELLOW}Step 3: Creating Google Cloud Project${NC}"

read -p "Enter a project name (or press enter for 'nursery-rhymes'): " PROJECT_NAME
PROJECT_NAME=${PROJECT_NAME:-nursery-rhymes}

# Create unique project ID
PROJECT_ID="${PROJECT_NAME}-$(date +%s | tail -c 6)"

echo "Creating project: $PROJECT_ID"
gcloud projects create "$PROJECT_ID" --name="$PROJECT_NAME" 2>/dev/null || true

gcloud config set project "$PROJECT_ID"
echo -e "${GREEN}✓ Project created: $PROJECT_ID${NC}"

# Step 4: Enable APIs
echo ""
echo -e "${YELLOW}Step 4: Enabling Google Drive API${NC}"
gcloud services enable drive.googleapis.com --quiet
echo -e "${GREEN}✓ Google Drive API enabled${NC}"

# Step 5: Create service account
echo ""
echo -e "${YELLOW}Step 5: Creating Service Account${NC}"

SERVICE_ACCOUNT_NAME="nursery-rhymes-bot"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
    --display-name="Nursery Rhymes Video Bot" \
    --quiet 2>/dev/null || true

echo -e "${GREEN}✓ Service account created${NC}"

# Step 6: Create key
echo ""
echo -e "${YELLOW}Step 6: Creating Service Account Key${NC}"

SERVICE_ACCOUNT_KEY="service-account.json"

gcloud iam service-accounts keys create "$SERVICE_ACCOUNT_KEY" \
    --iam-account="$SERVICE_ACCOUNT_EMAIL" \
    --quiet

echo -e "${GREEN}✓ Key saved to: $SERVICE_ACCOUNT_KEY${NC}"

# Step 7: Update config
echo ""
echo -e "${YELLOW}Step 7: Updating Configuration${NC}"

# Create basic config if not exists
if [ ! -f "config.env" ]; then
    cp config.env.example config.env
fi

# Add GDrive config (remove old entries first)
sed -i '/^GOOGLE_DRIVE/d' config.env 2>/dev/null || true

cat >> config.env << CONFIGEOF

# Google Drive (auto-configured)
GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON=./service-account.json
GOOGLE_DRIVE_FOLDER_ID=PENDING
CONFIGEOF

echo -e "${GREEN}✓ Config.env updated${NC}"

# Step 8: Create Drive folder
echo ""
echo -e "${YELLOW}Step 8: Creating Google Drive Folder${NC}"
echo "A browser window will open for final authorization..."
echo ""

python3 << 'PYSCRIPT'
import json
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

try:
    # Load service account
    with open('service-account.json') as f:
        svc_info = json.load(f)

    # Create Drive client
    creds = service_account.Credentials.from_service_account_info(
        svc_info,
        scopes=['https://www.googleapis.com/auth/drive']
    )
    
    drive = build('drive', 'v3', credentials=creds)
    
    # Create folder
    folder = drive.files().create(
        body={
            'name': 'Nursery Rhymes Videos',
            'mimeType': 'application/vnd.google-apps.folder'
        },
        fields='id,webViewLink'
    ).execute()
    
    folder_id = folder['id']
    folder_link = folder.get('webViewLink', '')
    
    # Update config
    with open('config.env', 'r') as f:
        content = f.read()
    
    content = content.replace('GOOGLE_DRIVE_FOLDER_ID=PENDING', f'GOOGLE_DRIVE_FOLDER_ID={folder_id}')
    
    with open('config.env', 'w') as f:
        f.write(content)
    
    print(f"FOLDER_ID={folder_id}")
    print(f"FOLDER_LINK={folder_link}")
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
PYSCRIPT

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Drive folder created${NC}"
else
    echo -e "${RED}✗ Failed to create folder${NC}"
    exit 1
fi

# Final summary
echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}  ✓ Setup Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Configuration saved to: config.env"
echo "Service account key: service-account.json"
echo ""
echo "Next steps:"
echo "  1. Get API keys: ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, PEXELS_API_KEY"
echo "  2. Add to config.env"
echo "  3. Test: cd src && python daily_scheduler.py test"
echo ""

