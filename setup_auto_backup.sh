#!/bin/bash

# SBMS Automated Backup Setup
# Sets up cron jobs for regular backups

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SBMS_DIR=$(pwd)

echo -e "${GREEN}🔄 Setting up automated SBMS backups...${NC}"

# Show current cron jobs
echo -e "${YELLOW}📋 Current cron jobs:${NC}"
crontab -l 2>/dev/null || echo "No cron jobs found"

echo ""
echo -e "${YELLOW}🕐 Backup schedule options:${NC}"
echo "1. Daily at 2:00 AM (recommended for production)"
echo "2. Weekly on Sunday at 2:00 AM (for smaller systems)" 
echo "3. Twice daily at 2:00 AM and 2:00 PM (high activity)"
echo "4. Custom schedule"
echo "5. Remove existing SBMS backup jobs"

read -p "Choose an option (1-5): " choice

case $choice in
    1)
        CRON_SCHEDULE="0 2 * * *"
        DESCRIPTION="Daily at 2:00 AM"
        ;;
    2)
        CRON_SCHEDULE="0 2 * * 0"
        DESCRIPTION="Weekly on Sunday at 2:00 AM"
        ;;
    3)
        CRON_SCHEDULE="0 2,14 * * *"
        DESCRIPTION="Daily at 2:00 AM and 2:00 PM"
        ;;
    4)
        echo -e "${YELLOW}💡 Cron format: minute hour day month day-of-week${NC}"
        echo "Examples:"
        echo "  0 2 * * *     = Daily at 2:00 AM"
        echo "  0 */6 * * *   = Every 6 hours"
        echo "  0 2 * * 1     = Every Monday at 2:00 AM"
        read -p "Enter cron schedule: " CRON_SCHEDULE
        DESCRIPTION="Custom: $CRON_SCHEDULE"
        ;;
    5)
        echo -e "${YELLOW}🗑️  Removing existing SBMS backup jobs...${NC}"
        crontab -l 2>/dev/null | grep -v "SBMS Backup" | crontab -
        echo -e "${GREEN}✅ SBMS backup jobs removed${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}❌ Invalid option${NC}"
        exit 1
        ;;
esac

# Ask about Google Drive integration
echo ""
read -p "Include Google Drive upload? (y/n): " gdrive_choice

if [ "$gdrive_choice" = "y" ] || [ "$gdrive_choice" = "Y" ]; then
    BACKUP_COMMAND="$SBMS_DIR/backup_to_gdrive.sh"
    BACKUP_TYPE="local + Google Drive"
else
    BACKUP_COMMAND="$SBMS_DIR/backup_sbms.sh"
    BACKUP_TYPE="local only"
fi

# Create the cron job
CRON_JOB="$CRON_SCHEDULE cd $SBMS_DIR && $BACKUP_COMMAND >> $SBMS_DIR/backup.log 2>&1 # SBMS Backup"

# Add to crontab
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo -e "${GREEN}"
echo "🎉 Automated Backup Setup Complete!"
echo "==================================="
echo "📅 Schedule: $DESCRIPTION"
echo "💾 Type: $BACKUP_TYPE"
echo "📁 Location: $SBMS_DIR/backups/"
echo "📝 Log file: $SBMS_DIR/backup.log"
echo ""
echo "💡 Useful commands:"
echo "   • View cron jobs: crontab -l"
echo "   • Check backup log: tail -f $SBMS_DIR/backup.log"
echo "   • Manual backup: $BACKUP_COMMAND"
echo "   • Remove backups: $0 (choose option 5)"
echo -e "${NC}"

# Create a backup log file with initial entry
echo "SBMS Automated Backup Log" > backup.log
echo "=========================" >> backup.log
echo "Setup date: $(date)" >> backup.log
echo "Schedule: $DESCRIPTION" >> backup.log
echo "Type: $BACKUP_TYPE" >> backup.log
echo "" >> backup.log