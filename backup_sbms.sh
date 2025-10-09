#!/bin/bash

# SBMS Backup Script
# Creates comprehensive backups of database and uploaded files

# Configuration
BACKUP_DIR="./backups"
DATE=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="sbms_backup_${DATE}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔄 Starting SBMS backup process...${NC}"

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Create timestamped backup folder
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"
mkdir -p "$BACKUP_PATH"

echo -e "${YELLOW}📁 Backup location: $BACKUP_PATH${NC}"

# 1. Database backup
echo -e "${YELLOW}💾 Backing up PostgreSQL database...${NC}"
docker exec sbms_db pg_dump -U sbms_user sbms > "$BACKUP_PATH/database.sql"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Database backup completed${NC}"
else
    echo -e "${RED}❌ Database backup failed${NC}"
    exit 1
fi

# 2. Backup uploaded receipts
echo -e "${YELLOW}📎 Backing up receipt files...${NC}"
if [ -d "./backend/uploads" ]; then
    cp -r ./backend/uploads "$BACKUP_PATH/"
    echo -e "${GREEN}✅ Receipt files backed up${NC}"
else
    echo -e "${YELLOW}⚠️  No uploads directory found${NC}"
fi

# 3. Backup configuration files
echo -e "${YELLOW}⚙️  Backing up configuration...${NC}"
cp docker-compose.yml "$BACKUP_PATH/" 2>/dev/null
cp .env "$BACKUP_PATH/.env.backup" 2>/dev/null || echo -e "${YELLOW}⚠️  .env file not found (this is normal if using defaults)${NC}"

# 4. Create backup metadata
cat > "$BACKUP_PATH/backup_info.txt" << EOF
SBMS Backup Information
======================
Backup Date: $(date)
Backup Name: $BACKUP_NAME
Database: PostgreSQL dump included
Uploads: $([ -d "./backend/uploads" ] && echo "Included" || echo "Not found")
Configuration: docker-compose.yml included

Restore Instructions:
1. Stop SBMS: docker-compose down
2. Remove old data volume: docker volume rm sbms_postgres_data
3. Start database: docker-compose up -d db
4. Wait 10 seconds, then restore: docker exec -i sbms_db psql -U sbms_user sbms < database.sql
5. Restore uploads: cp -r uploads/* ./backend/uploads/
6. Start full system: docker-compose up -d

Created by: SBMS Backup Script v1.0
EOF

# 5. Create compressed archive
echo -e "${YELLOW}🗜️  Creating compressed archive...${NC}"
cd "$BACKUP_DIR"
tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
if [ $? -eq 0 ]; then
    # Remove uncompressed folder to save space
    rm -rf "$BACKUP_NAME"
    echo -e "${GREEN}✅ Compressed backup created: ${BACKUP_NAME}.tar.gz${NC}"
else
    echo -e "${RED}❌ Compression failed${NC}"
fi

cd ..

# 6. Backup summary
BACKUP_SIZE=$(du -h "$BACKUP_DIR/${BACKUP_NAME}.tar.gz" 2>/dev/null | cut -f1)
echo -e "${GREEN}"
echo "🎉 SBMS Backup Complete!"
echo "===================="
echo "📦 File: $BACKUP_DIR/${BACKUP_NAME}.tar.gz"
echo "📏 Size: ${BACKUP_SIZE:-Unknown}"
echo "📅 Date: $(date)"
echo ""
echo "💡 Next steps:"
echo "   • Copy to Google Drive or external storage"
echo "   • Test restore procedure in development"
echo "   • Schedule regular backups (cron/systemd)"
echo -e "${NC}"