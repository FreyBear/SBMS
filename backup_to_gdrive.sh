#!/bin/bash

# SBMS Google Drive Backup Script
# Requires rclone to be installed and configured for Google Drive

# Configuration
GDRIVE_REMOTE="gdrive"  # Change this to your rclone remote name
GDRIVE_FOLDER="SBMS_Backups"
LOCAL_BACKUP_DIR="./backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔄 Starting SBMS Google Drive backup...${NC}"

# Check if rclone is installed
if ! command -v rclone &> /dev/null; then
    echo -e "${RED}❌ rclone is not installed${NC}"
    echo -e "${YELLOW}💡 Install rclone: https://rclone.org/install/${NC}"
    echo -e "${YELLOW}💡 Configure Google Drive: rclone config${NC}"
    exit 1
fi

# Check if rclone remote exists
if ! rclone listremotes | grep -q "^${GDRIVE_REMOTE}:$"; then
    echo -e "${RED}❌ rclone remote '${GDRIVE_REMOTE}' not found${NC}"
    echo -e "${YELLOW}💡 Configure remote: rclone config${NC}"
    exit 1
fi

# Create local backup first
echo -e "${YELLOW}📦 Creating local backup first...${NC}"
./backup_sbms.sh

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Local backup failed${NC}"
    exit 1
fi

# Get the latest backup file
LATEST_BACKUP=$(ls -t ./backups/sbms_backup_*.tar.gz 2>/dev/null | head -n1)

if [ -z "$LATEST_BACKUP" ]; then
    echo -e "${RED}❌ No backup file found${NC}"
    exit 1
fi

echo -e "${YELLOW}☁️  Uploading to Google Drive...${NC}"
echo -e "${YELLOW}📁 Remote folder: ${GDRIVE_REMOTE}:${GDRIVE_FOLDER}${NC}"
echo -e "${YELLOW}📦 File: $(basename "$LATEST_BACKUP")${NC}"

# Upload to Google Drive
rclone copy "$LATEST_BACKUP" "${GDRIVE_REMOTE}:${GDRIVE_FOLDER}/" --progress

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Backup uploaded to Google Drive successfully${NC}"
    
    # Show remote files
    echo -e "${YELLOW}☁️  Google Drive backup files:${NC}"
    rclone ls "${GDRIVE_REMOTE}:${GDRIVE_FOLDER}/" | grep "sbms_backup_" | sort -r | head -5
    
    # Optional: Clean up old local backups (keep last 3)
    echo -e "${YELLOW}🧹 Cleaning up old local backups (keeping last 3)...${NC}"
    ls -t ./backups/sbms_backup_*.tar.gz | tail -n +4 | xargs rm -f 2>/dev/null
    
else
    echo -e "${RED}❌ Upload to Google Drive failed${NC}"
    exit 1
fi

echo -e "${GREEN}"
echo "🎉 Google Drive Backup Complete!"
echo "================================"
echo "☁️  Location: ${GDRIVE_REMOTE}:${GDRIVE_FOLDER}/"
echo "📦 File: $(basename "$LATEST_BACKUP")"
echo "📏 Size: $(ls -lh "$LATEST_BACKUP" | awk '{print $5}')"
echo ""
echo "💡 To restore from Google Drive:"
echo "   1. Download: rclone copy \"${GDRIVE_REMOTE}:${GDRIVE_FOLDER}/$(basename "$LATEST_BACKUP")\" ./"
echo "   2. Restore: ./restore_sbms.sh $(basename "$LATEST_BACKUP")"
echo -e "${NC}"