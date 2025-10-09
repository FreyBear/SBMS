#!/bin/bash

# SBMS Google Drive Setup Script
# Sets up rclone for Google Drive backup securely

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔧 SBMS Google Drive Setup${NC}"
echo -e "${GREEN}=========================${NC}"
echo ""

# Check if rclone is installed
if ! command -v rclone &> /dev/null; then
    echo -e "${RED}❌ rclone is not installed${NC}"
    echo -e "${YELLOW}💡 Install with: sudo apt install rclone${NC}"
    exit 1
fi

echo -e "${BLUE}📋 This script will help you set up Google Drive backup for SBMS${NC}"
echo ""
echo -e "${YELLOW}What you'll need:${NC}"
echo "  • Google account (dedicated backup account recommended)"
echo "  • Web browser access"
echo "  • 2-3 minutes for setup"
echo ""

read -p "Continue with setup? (y/n): " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo -e "${YELLOW}Setup cancelled${NC}"
    exit 0
fi

echo ""
echo -e "${YELLOW}🔒 Security Note:${NC}"
echo "  • rclone config will be stored in ~/.config/rclone/"
echo "  • This folder is protected by .gitignore"
echo "  • Only you can access these credentials"
echo ""

# Check if gdrive remote already exists
if rclone listremotes | grep -q "^gdrive:$"; then
    echo -e "${YELLOW}⚠️  Google Drive remote 'gdrive' already exists${NC}"
    read -p "Reconfigure it? (y/n): " reconfig
    if [ "$reconfig" = "y" ] || [ "$reconfig" = "Y" ]; then
        echo -e "${YELLOW}🔄 Reconfiguring Google Drive...${NC}"
        rclone config delete gdrive
    else
        echo -e "${GREEN}✅ Using existing configuration${NC}"
        echo ""
        echo -e "${BLUE}💡 Test your backup with:${NC}"
        echo "   ./backup_to_gdrive.sh"
        exit 0
    fi
fi

echo -e "${YELLOW}🚀 Starting rclone configuration...${NC}"
echo ""
echo -e "${BLUE}Follow these steps:${NC}"
echo "1. Choose 'n' for new remote"
echo "2. Enter name: gdrive"
echo "3. Choose 'drive' for Google Drive"
echo "4. Leave client_id blank (press Enter)"
echo "5. Leave client_secret blank (press Enter)"
echo "6. Choose '1' for full access"
echo "7. Leave root_folder_id blank (press Enter)"
echo "8. Leave service_account_file blank (press Enter)"
echo "9. Choose 'n' for advanced config"
echo "10. Choose 'y' for auto config (opens browser)"
echo "11. Sign in to Google Drive in browser"
echo "12. Choose 'n' for team drive"
echo "13. Choose 'y' to confirm"
echo "14. Choose 'q' to quit config"
echo ""

read -p "Ready to start configuration? (y/n): " ready
if [ "$ready" != "y" ] && [ "$ready" != "Y" ]; then
    echo -e "${YELLOW}Setup cancelled${NC}"
    exit 0
fi

# Run rclone config
rclone config

# Verify the configuration
echo ""
echo -e "${YELLOW}🔍 Verifying Google Drive connection...${NC}"

if rclone listremotes | grep -q "^gdrive:$"; then
    echo -e "${GREEN}✅ Google Drive remote configured successfully${NC}"
    
    # Test connection
    echo -e "${YELLOW}📡 Testing connection...${NC}"
    if rclone lsd gdrive: &>/dev/null; then
        echo -e "${GREEN}✅ Connection test successful${NC}"
        
        # Create backup folder
        echo -e "${YELLOW}📁 Creating SBMS_Backups folder...${NC}"
        rclone mkdir gdrive:SBMS_Backups
        echo -e "${GREEN}✅ Backup folder created${NC}"
        
    else
        echo -e "${RED}❌ Connection test failed${NC}"
        echo -e "${YELLOW}💡 Try running: rclone config reconnect gdrive${NC}"
        exit 1
    fi
else
    echo -e "${RED}❌ Google Drive remote not found${NC}"
    echo -e "${YELLOW}💡 Configuration may have failed. Try again with: rclone config${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}🎉 Google Drive Setup Complete!${NC}"
echo -e "${GREEN}================================${NC}"
echo ""
echo -e "${BLUE}💡 Next steps:${NC}"
echo "   • Test backup: ./backup_to_gdrive.sh"
echo "   • Set up automated backups: ./setup_auto_backup.sh"
echo "   • View Google Drive files: rclone ls gdrive:SBMS_Backups/"
echo ""
echo -e "${YELLOW}🔒 Security reminders:${NC}"
echo "   • rclone config is stored securely in ~/.config/rclone/"
echo "   • This folder is excluded from git commits"
echo "   • Consider enabling 2FA on your Google account"
echo ""