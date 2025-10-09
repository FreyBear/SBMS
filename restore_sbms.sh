#!/bin/bash

# SBMS Restore Script
# Restores database and files from backup

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if backup file is provided
if [ $# -ne 1 ]; then
    echo -e "${RED}Usage: $0 <backup_file.tar.gz>${NC}"
    echo "Example: $0 ./backups/sbms_backup_20251009_220500.tar.gz"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}❌ Backup file not found: $BACKUP_FILE${NC}"
    exit 1
fi

echo -e "${YELLOW}⚠️  WARNING: This will replace all current SBMS data!${NC}"
echo -e "${YELLOW}📦 Restoring from: $BACKUP_FILE${NC}"
read -p "Are you sure you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo -e "${YELLOW}🚫 Restore cancelled${NC}"
    exit 0
fi

echo -e "${GREEN}🔄 Starting SBMS restore process...${NC}"

# Create temporary directory
TEMP_DIR=$(mktemp -d)
echo -e "${YELLOW}📁 Extracting backup to: $TEMP_DIR${NC}"

# Extract backup
tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Failed to extract backup file${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Find the backup directory (should be only one)
BACKUP_DIR=$(find "$TEMP_DIR" -maxdepth 1 -type d -name "sbms_backup_*" | head -1)
if [ -z "$BACKUP_DIR" ]; then
    echo -e "${RED}❌ Invalid backup file structure${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

echo -e "${GREEN}✅ Backup extracted successfully${NC}"

# Stop current system
echo -e "${YELLOW}🛑 Stopping SBMS containers...${NC}"
docker-compose down

# Remove old database volume
echo -e "${YELLOW}🗑️  Removing old database volume...${NC}"
docker volume rm sbms_postgres_data 2>/dev/null || true

# Start database only
echo -e "${YELLOW}🚀 Starting database container...${NC}"
docker-compose up -d db

# Wait for database to be ready
echo -e "${YELLOW}⏳ Waiting for database to initialize...${NC}"
sleep 15

# Clear the database schema to avoid conflicts
echo -e "${YELLOW}🧹 Clearing existing database schema...${NC}"
docker exec -i sbms_db psql -U sbms_user sbms -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" >/dev/null 2>&1

# Restore database
echo -e "${YELLOW}💾 Restoring database...${NC}"
if [ -f "$BACKUP_DIR/database.sql" ]; then
    docker exec -i sbms_db psql -U sbms_user sbms < "$BACKUP_DIR/database.sql"
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Database restored successfully${NC}"
    else
        echo -e "${RED}❌ Database restore failed${NC}"
        rm -rf "$TEMP_DIR"
        exit 1
    fi
else
    echo -e "${RED}❌ Database backup file not found${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Restore uploaded files
echo -e "${YELLOW}📎 Restoring receipt files...${NC}"
if [ -d "$BACKUP_DIR/uploads" ]; then
    mkdir -p ./backend/uploads
    cp -r "$BACKUP_DIR/uploads"/* ./backend/uploads/ 2>/dev/null
    echo -e "${GREEN}✅ Receipt files restored${NC}"
else
    echo -e "${YELLOW}⚠️  No receipt files found in backup${NC}"
fi

# Start full system
echo -e "${YELLOW}🚀 Starting full SBMS system...${NC}"
docker-compose up -d

# Wait for system to be ready
echo -e "${YELLOW}⏳ Waiting for system to start...${NC}"
sleep 10

# Cleanup
rm -rf "$TEMP_DIR"

echo -e "${GREEN}"
echo "🎉 SBMS Restore Complete!"
echo "======================="
echo "🌐 System should be available at: http://localhost:8080"
echo "👤 Default login: admin / admin123"
echo ""
echo "💡 Recommended next steps:"
echo "   • Verify system is working correctly"
echo "   • Check that all users can log in"
echo "   • Verify expense data and receipts"
echo "   • Test keg management functions"
echo -e "${NC}"