#!/bin/bash

# SBMS Disaster Recovery Test Script
# Tests complete system restore from backup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🧪 Starting SBMS Disaster Recovery Test${NC}"

# Check if backup file is provided
if [ $# -ne 1 ]; then
    echo -e "${RED}Usage: $0 <backup_file.tar.gz>${NC}"
    echo "Example: $0 ./backups/sbms_backup_20251009_230903.tar.gz"
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}❌ Backup file not found: $BACKUP_FILE${NC}"
    exit 1
fi

echo -e "${YELLOW}📦 Testing restore of: $BACKUP_FILE${NC}"

# Store current data for comparison
echo -e "${YELLOW}📊 Recording current system state...${NC}"
CURRENT_USERS=$(docker exec -it sbms_db psql -U sbms_user -d sbms -t -c "SELECT COUNT(*) FROM users;" 2>/dev/null | tr -d ' \r\n' || echo "0")
CURRENT_RECIPES=$(docker exec -it sbms_db psql -U sbms_user -d sbms -t -c "SELECT COUNT(*) FROM recipe;" 2>/dev/null | tr -d ' \r\n' || echo "0")

echo -e "${YELLOW}   Current users: $CURRENT_USERS${NC}"
echo -e "${YELLOW}   Current recipes: $CURRENT_RECIPES${NC}"

# Perform restore
echo -e "${YELLOW}🔄 Performing restore...${NC}"
echo "yes" | timeout 300 ./restore_sbms.sh "$BACKUP_FILE" > /dev/null 2>&1

if [ $? -eq 124 ]; then
    echo -e "${RED}❌ Restore timed out after 5 minutes${NC}"
    exit 1
elif [ $? -ne 0 ]; then
    echo -e "${RED}❌ Restore failed${NC}"
    exit 1
fi

# Wait for system to be ready with timeout
echo -e "${YELLOW}⏳ Waiting for system to be ready...${NC}"
for i in {1..30}; do
    HTTP_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>/dev/null || echo "000")
    if [ "$HTTP_CHECK" = "200" ] || [ "$HTTP_CHECK" = "302" ]; then
        echo -e "${GREEN}✅ System ready after ${i} seconds${NC}"
        break
    fi
    sleep 2
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ System not ready after 60 seconds${NC}"
        exit 1
    fi
done

# Verify restore
echo -e "${YELLOW}🔍 Verifying restore...${NC}"
RESTORED_USERS=$(docker exec -it sbms_db psql -U sbms_user -d sbms -t -c "SELECT COUNT(*) FROM users;" | tr -d ' \r\n')
RESTORED_RECIPES=$(docker exec -it sbms_db psql -U sbms_user -d sbms -t -c "SELECT COUNT(*) FROM recipe;" | tr -d ' \r\n')

echo -e "${GREEN}   Restored users: $RESTORED_USERS${NC}"
echo -e "${GREEN}   Restored recipes: $RESTORED_RECIPES${NC}"

# Test web interface
echo -e "${YELLOW}🌐 Testing web interface...${NC}"
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/ 2>/dev/null || echo "000")

if [ "$HTTP_STATUS" = "200" ] || [ "$HTTP_STATUS" = "302" ]; then
    echo -e "${GREEN}✅ Web interface responding (HTTP $HTTP_STATUS)${NC}"
    WEB_STATUS="✅ Working"
else
    echo -e "${RED}❌ Web interface not responding (HTTP $HTTP_STATUS)${NC}"
    WEB_STATUS="❌ Failed"
fi

# Test database integrity
echo -e "${YELLOW}🔍 Testing database integrity...${NC}"
ADMIN_EXISTS=$(docker exec -it sbms_db psql -U sbms_user -d sbms -t -c "SELECT COUNT(*) FROM users WHERE username='admin';" | tr -d ' \r\n')

if [ "$ADMIN_EXISTS" = "1" ]; then
    echo -e "${GREEN}✅ Admin user exists${NC}"
else
    echo -e "${RED}❌ Admin user missing${NC}"
fi

# Summary
echo -e "${GREEN}"
echo "🧪 Disaster Recovery Test Complete!"
echo "===================================="
echo "📦 Backup file: $BACKUP_FILE"
echo "👥 Users restored: $RESTORED_USERS"
echo "📄 Recipes restored: $RESTORED_RECIPES"
echo "🌐 Web interface: $WEB_STATUS"
echo "👤 Admin account: $([ "$ADMIN_EXISTS" = "1" ] && echo "✅ Present" || echo "❌ Missing")"
echo ""
echo "💡 System ready at: http://localhost:8080"
echo "👤 Default login: admin / admin123"
echo -e "${NC}"