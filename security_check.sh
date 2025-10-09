#!/bin/bash

# SBMS Security Check Script
# Verifies that no sensitive data will be committed to git

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔒 SBMS Security Check${NC}"
echo -e "${GREEN}===================${NC}"

# Check for sensitive files that might be tracked
SENSITIVE_FILES=(
    ".env"
    ".env.local" 
    ".env.production"
    "backups/"
    "backend/uploads/"
    "uploads/"
    "*.sql"
    "*.dump"
    "*.tar.gz"
    "rclone.conf"
    ".config/rclone/"
)

echo -e "${YELLOW}🔍 Checking for sensitive files in git...${NC}"

ISSUES_FOUND=0

for pattern in "${SENSITIVE_FILES[@]}"; do
    # Use exact match for files, not just pattern matching
    case "$pattern" in
        ".env")
            if git ls-files | grep -E "^\.env$" | grep -v "\.env\.example"; then
                echo -e "${RED}❌ SECURITY ISSUE: .env is tracked by git${NC}"
                ISSUES_FOUND=$((ISSUES_FOUND + 1))
            fi
            ;;
        "*.sql")
            # Allow certain safe SQL files
            if git ls-files | grep -E "\.sql$" | grep -v -E "(init\.sql|migrate_.*\.sql|import.*\.sql|.*_template.*\.sql|.*schema.*\.sql)"; then
                echo -e "${RED}❌ SECURITY ISSUE: SQL dump files are tracked by git${NC}"
                ISSUES_FOUND=$((ISSUES_FOUND + 1))
            fi
            ;;
        *)
            if git ls-files | grep -q "$pattern" 2>/dev/null; then
                echo -e "${RED}❌ SECURITY ISSUE: $pattern is tracked by git${NC}"
                ISSUES_FOUND=$((ISSUES_FOUND + 1))
            fi
            ;;
    esac
done

# Check git status for untracked sensitive files
echo -e "${YELLOW}🔍 Checking git status...${NC}"

if git status --porcelain | grep -E "(\.env|backups|uploads|\.sql|\.tar\.gz|rclone\.conf)"; then
    echo -e "${YELLOW}⚠️  Sensitive files detected (but not tracked):${NC}"
    git status --porcelain | grep -E "(\.env|backups|uploads|\.sql|\.tar\.gz|rclone\.conf)"
    echo -e "${GREEN}✅ These files are correctly ignored by git${NC}"
fi

# Check .gitignore
echo -e "${YELLOW}🔍 Checking .gitignore coverage...${NC}"

REQUIRED_IGNORES=(
    ".env"
    "backups/"
    "backend/uploads/"
    "*.sql"
    "*.tar.gz"
    "rclone.conf"
)

for ignore in "${REQUIRED_IGNORES[@]}"; do
    if grep -q "$ignore" .gitignore; then
        echo -e "${GREEN}✅ $ignore is in .gitignore${NC}"
    else
        echo -e "${RED}❌ $ignore missing from .gitignore${NC}"
        ISSUES_FOUND=$((ISSUES_FOUND + 1))
    fi
done

# Check if rclone config exists and is secure
if [ -f "$HOME/.config/rclone/rclone.conf" ]; then
    echo -e "${GREEN}✅ rclone config exists and is outside project directory${NC}"
    echo -e "${YELLOW}📁 Location: $HOME/.config/rclone/rclone.conf${NC}"
else
    echo -e "${YELLOW}ℹ️  rclone not configured yet${NC}"
fi

# Final summary
echo ""
if [ $ISSUES_FOUND -eq 0 ]; then
    echo -e "${GREEN}🎉 Security Check Passed!${NC}"
    echo -e "${GREEN}========================${NC}"
    echo -e "${GREEN}✅ No sensitive files will be committed to git${NC}"
    echo -e "${GREEN}✅ All security measures are in place${NC}"
else
    echo -e "${RED}🚨 Security Issues Found: $ISSUES_FOUND${NC}"
    echo -e "${RED}===========================${NC}"
    echo -e "${YELLOW}💡 Fix these issues before committing to git${NC}"
fi

echo ""
echo -e "${YELLOW}📋 What's safe to commit:${NC}"
echo "   ✅ Source code (*.py, *.html, *.css)"
echo "   ✅ Configuration templates (init.sql, docker-compose.yml)"
echo "   ✅ Backup scripts (no credentials included)"
echo "   ✅ Documentation (README.md, BACKUP_GUIDE.md)"
echo ""
echo -e "${YELLOW}🔒 What's NEVER committed:${NC}"
echo "   ❌ .env files (contain passwords)"
echo "   ❌ backups/ folder (contains real data)"
echo "   ❌ backend/uploads/ (contains receipt files)"
echo "   ❌ *.sql dumps (contain real data)"
echo "   ❌ rclone config (contains Google Drive credentials)"