#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}  AI Nursery Rhymes - Google Drive Setup${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Step 1: Check prerequisites
echo -e "${YELLOW}[Step 1] Checking prerequisites...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 found${NC}"

# Step 2: Install gcloud CLI
echo ""
echo -e "${YELLOW}[Step 2] Installing Google Cloud CLI...${NC}"

if ! command -v gcloud &> /dev/null; then
    echo "Installing gcloud CLI..."
    curl https://sdk.cloud.google.com | bash
    exec -l $SHELL
    
    if ! command -v gcloud &> /dev/null; then
        echo -e "${RED}✗ Failed to install gcloud${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✓ Google Cloud CLI ready${NC}"

# Step 3: Authenticate with Google
echo ""
echo -e "${YELLOW}[Step 3] Authenticating with Google...${NC}"
echo -e "${BLUE}A browser will open. Please sign in with your Google account.${NC}"
echo ""

gcloud auth application-default login

echo -e "${GREEN}✓ Authentication complete${NC}"

# Step 4: Create Google Cloud Project
echo ""
echo -e "${YELLOW}[Step 4] Creating Google Cloud Project...${NC}"

PROJECT_NAME="nursery-rhymes-videos"
PROJECT_ID="nursery-rhymes-$(date +%s)"

echo "Project ID: $PROJECT_ID"
gcloud projects create "$PROJECT_ID" --name="$PROJECT_NAME" || true

# Set project
gcloud config set project "$PROJECT_ID"
echo -e "${GREEN}✓ Project created: $PROJECT_ID${NC}"

# Step 5: Enable Google Drive API
echo ""
echo -e "${YELLOW}[Step 5] Enabling Google Drive API...${NC}"

gcloud services enable drive.googleapis.com
echo -e "${GREEN}✓ Google Drive API enabled${NC}"

# Step 6: Create Service Account
echo ""
echo -e "${YELLOW}[Step 6] Creating Service Account...${NC}"

SERVICE_ACCOUNT_EMAIL="nursery-rhymes-bot@${PROJECT_ID}.iam.gserviceaccount.com"

# Create service account
gcloud iam service-accounts create nursery-rhymes-bot \
    --display-name="Nursery Rhymes Bot" \
    || true

echo -e "${GREEN}✓ Service account created${NC}"

# Step 7: Create and Download Service Account Key
echo ""
echo -e "${YELLOW}[Step 7] Creating service account key...${NC}"

SERVICE_ACCOUNT_KEY="service-account.json"

gcloud iam service-accounts keys create "$SERVICE_ACCOUNT_KEY" \
    --iam-account="$SERVICE_ACCOUNT_EMAIL"

echo -e "${GREEN}✓ Service account key saved to: $SERVICE_ACCOUNT_KEY${NC}"

# Step 8: Create Google Drive Folder
echo ""
echo -e "${YELLOW}[Step 8] Creating Google Drive folder...${NC}"

FOLDER_NAME="Nursery Rhymes Videos"

# Use Python to create folder (requires google-api-python-client)
python3 << 'PYSCRIPT'
import json
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load service account
with open('service-account.json') as f:
    service_account_info = json.load(f)

credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=['https://www.googleapis.com/auth/drive.file']
)

service = build('drive', 'v3', credentials=credentials)

# Create folder
file_metadata = {
    'name': 'Nursery Rhymes Videos',
    'mimeType': 'application/vnd.google-apps.folder'
}

try:
    folder = service.files().create(body=file_metadata, fields='id').execute()
    folder_id = folder.get('id')
    
    print(f"FOLDER_ID={folder_id}")
    
    # Save folder ID
    with open('.gdrive_folder_id', 'w') as f:
        f.write(folder_id)
        
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
PYSCRIPT

# Read folder ID
FOLDER_ID=$(cat .gdrive_folder_id 2>/dev/null)
if [ -z "$FOLDER_ID" ]; then
    echo -e "${RED}✗ Failed to create folder${NC}"
    exit 1
fi
rm -f .gdrive_folder_id

echo -e "${GREEN}✓ Drive folder created${NC}"
echo "  Folder ID: $FOLDER_ID"

# Step 9: Configure project
echo ""
echo -e "${YELLOW}[Step 9] Configuring project...${NC}"

# Update config.env
if [ -f "config.env" ]; then
    # Remove old GDrive settings
    sed -i '/GOOGLE_DRIVE/d' config.env
else
    cp config.env.example config.env
fi

# Add new settings
cat >> config.env << CONFIGEOF

# Google Drive Integration
GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON=./service-account.json
GOOGLE_DRIVE_FOLDER_ID=${FOLDER_ID}
CONFIGEOF

echo -e "${GREEN}✓ Config updated${NC}"

# Step 10: Grant Service Account Access to Folder
echo ""
echo -e "${YELLOW}[Step 10] Setting folder permissions...${NC}"

python3 << 'PYSCRIPT'
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Load service account
with open('service-account.json') as f:
    service_account_info = json.load(f)

SERVICE_ACCOUNT_EMAIL = service_account_info['client_email']
FOLDER_ID = open('.gdrive_setup').read().strip()

credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=['https://www.googleapis.com/auth/drive.file']
)

service = build('drive', 'v3', credentials=credentials)

# Give service account editor access
permission = {
    'type': 'user',
    'role': 'editor',
    'emailAddress': SERVICE_ACCOUNT_EMAIL
}

try:
    service.permissions().create(
        fileId=FOLDER_ID,
        body=permission,
        fields='id'
    ).execute()
    print("✓ Permissions set")
except Exception as e:
    print(f"✗ Failed to set permissions: {e}")
PYSCRIPT

echo -e "${GREEN}✓ Service account has editor access${NC}"

# Step 11: Test Connection
echo ""
echo -e "${YELLOW}[Step 11] Testing connection...${NC}"

python3 << 'PYSCRIPT'
import os
import sys
os.environ['GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON'] = './service-account.json'

# Get folder ID from config
import re
with open('config.env') as f:
    for line in f:
        if 'GOOGLE_DRIVE_FOLDER_ID=' in line:
            os.environ['GOOGLE_DRIVE_FOLDER_ID'] = line.split('=')[1].strip()
            break

from src.drive_sync import DriveSync

drive = DriveSync('./service-account.json', os.environ.get('GOOGLE_DRIVE_FOLDER_ID'))
if drive.is_authenticated():
    print("✓ Google Drive authenticated!")
else:
    print("✗ Authentication failed")
    sys.exit(1)
PYSCRIPT

# Final Summary
echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}  ✓ Google Drive Integration Complete!${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo -e "${BLUE}Configuration Summary:${NC}"
echo "  Project ID: $PROJECT_ID"
echo "  Service Account: $SERVICE_ACCOUNT_EMAIL"
echo "  Folder ID: $FOLDER_ID"
echo "  Config File: config.env"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "  1. Test generation: cd src && python daily_scheduler.py test"
echo "  2. Videos will auto-upload to your Drive folder"
echo "  3. Deploy: python daily_scheduler.py"
echo ""

