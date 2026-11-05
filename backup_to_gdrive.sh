#!/bin/bash

# SBMS Google Drive Backup Script with GFS (Grandfather-Father-Son) Retention
# Requires rclone to be installed and configured for Google Drive

# Ensure we always run from the SBMS project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Configuration
GDRIVE_REMOTE="gdrive"          # rclone remote name
GDRIVE_FOLDER="SBMS_Backups"    # Folder in Google Drive
LOCAL_BACKUP_DIR="./backups"

# Retention Policy (Grandfather-Father-Son)
LOCAL_KEEP_DAYS=7               # Keep local backups for the last 7 days
GFS_DAILY_KEEP=7                # Keep last 7 daily backups on Google Drive
GFS_WEEKLY_KEEP=4               # Keep last 4 weekly backups (Sundays) on Google Drive
GFS_MONTHLY_KEEP=12             # Keep last 12 monthly backups (1st of month) on Google Drive

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔄 Starting SBMS Google Drive backup ($(date '+%Y-%m-%d %H:%M:%S'))...${NC}"

# Check if rclone is installed
if ! command -v rclone &> /dev/null; then
    echo -e "${RED}❌ rclone is not installed${NC}"
    echo -e "${YELLOW}💡 Install rclone: sudo apt install rclone${NC}"
    echo -e "${YELLOW}💡 Configure Google Drive: ./setup_gdrive.sh${NC}"
    exit 1
fi

# Check if rclone remote exists
if ! rclone listremotes | grep -q "^${GDRIVE_REMOTE}:$"; then
    echo -e "${RED}❌ rclone remote '${GDRIVE_REMOTE}' not found${NC}"
    echo -e "${YELLOW}💡 Configure remote with: ./setup_gdrive.sh${NC}"
    exit 1
fi

# 1. Create local backup first
echo -e "${YELLOW}📦 Creating local backup first...${NC}"
./backup_sbms.sh

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Local backup failed${NC}"
    exit 1
fi

# Get the latest backup file
LATEST_BACKUP=$(ls -t "${LOCAL_BACKUP_DIR}"/sbms_backup_*.tar.gz 2>/dev/null | head -n1)

if [ -z "$LATEST_BACKUP" ]; then
    echo -e "${RED}❌ No backup file found${NC}"
    exit 1
fi

# Ensure remote folder exists
rclone mkdir "${GDRIVE_REMOTE}:${GDRIVE_FOLDER}" 2>/dev/null

# 2. Upload latest backup to Google Drive
echo -e "${YELLOW}☁️  Uploading $(basename "$LATEST_BACKUP") to Google Drive (${GDRIVE_REMOTE}:${GDRIVE_FOLDER})...${NC}"
if [ -t 1 ]; then
    RCLONE_FLAGS="--progress"
else
    RCLONE_FLAGS="--stats-one-line --stats=30s"
fi

rclone copy "$LATEST_BACKUP" "${GDRIVE_REMOTE}:${GDRIVE_FOLDER}/" $RCLONE_FLAGS

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ Upload to Google Drive failed! Skipping cleanup to prevent data loss.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Backup uploaded to Google Drive successfully${NC}"

# 3. Apply GFS (Grandfather-Father-Son) retention on Google Drive
echo -e "${YELLOW}🧹 Applying GFS retention policy on Google Drive (${GFS_DAILY_KEEP} daily, ${GFS_WEEKLY_KEEP} weekly, ${GFS_MONTHLY_KEEP} monthly)...${NC}"

REMOTE_FILES=$(rclone lsf "${GDRIVE_REMOTE}:${GDRIVE_FOLDER}/" --include "sbms_backup_*.tar.gz" 2>/dev/null)

if [ -n "$REMOTE_FILES" ]; then
    GFS_PLAN=$(REMOTE_FILES="$REMOTE_FILES" \
        GFS_DAILY="$GFS_DAILY_KEEP" \
        GFS_WEEKLY="$GFS_WEEKLY_KEEP" \
        GFS_MONTHLY="$GFS_MONTHLY_KEEP" \
        python3 - << 'PYEOF'
import os
import re
from datetime import datetime, timedelta

files = [f.strip() for f in os.environ.get("REMOTE_FILES", "").splitlines() if f.strip()]
daily_keep = int(os.environ.get("GFS_DAILY", "7"))
weekly_keep = int(os.environ.get("GFS_WEEKLY", "4"))
monthly_keep = int(os.environ.get("GFS_MONTHLY", "12"))

pattern = re.compile(r"^sbms_backup_(\d{8})_(\d{6})\.tar\.gz$")
parsed = []
for fname in files:
    m = pattern.match(fname)
    if m:
        dt = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        parsed.append((dt, fname))

if not parsed:
    raise SystemExit(0)

# Sort newest first
parsed.sort(key=lambda x: x[0], reverse=True)

# Group by date (YYYY-MM-DD), keeping the newest backup of each day as representative
by_date = {}
for dt, fname in parsed:
    d = dt.date()
    if d not in by_date:
        by_date[d] = (dt, fname)

keep_reasons = {}  # fname -> list of reasons

def mark_keep(fname, reason):
    keep_reasons.setdefault(fname, [])
    if reason not in keep_reasons[fname]:
        keep_reasons[fname].append(reason)

# Always keep the absolute newest backup
mark_keep(parsed[0][1], "Latest")

today = datetime.now().date()

# 1. Daily: Keep backups from the last N calendar days (plus up to N most recent backup dates)
daily_cutoff = today - timedelta(days=daily_keep - 1)
sorted_dates = sorted(by_date.keys(), reverse=True)
for idx, d in enumerate(sorted_dates):
    if d >= daily_cutoff or idx < daily_keep:
        mark_keep(by_date[d][1], "Daily")

# 2. Weekly (Father): Keep 1 backup per ISO week for the last W weeks
# Prefer Sunday (weekday == 6); if no Sunday backup exists in that week, keep the earliest backup of that week
by_week = {}
for d, (dt, fname) in by_date.items():
    iso_year, iso_week, _ = d.isocalendar()
    wk_key = (iso_year, iso_week)
    by_week.setdefault(wk_key, []).append((d, dt, fname))

sorted_weeks = sorted(by_week.keys(), reverse=True)[:weekly_keep]
for wk_key in sorted_weeks:
    candidates = by_week[wk_key]
    sundays = [c for c in candidates if c[0].weekday() == 6]
    if sundays:
        chosen = max(sundays, key=lambda c: c[1])
        mark_keep(chosen[2], f"Weekly-Sun({wk_key[0]}-W{wk_key[1]:02d})")
    else:
        chosen = min(candidates, key=lambda c: c[1])
        mark_keep(chosen[2], f"Weekly({wk_key[0]}-W{wk_key[1]:02d})")

# 3. Monthly (Grandfather): Keep 1 backup per calendar month for the last M months
# Prefer the 1st of the month (day == 1); if not present, keep the earliest backup of that month
by_month = {}
for d, (dt, fname) in by_date.items():
    m_key = (d.year, d.month)
    by_month.setdefault(m_key, []).append((d, dt, fname))

sorted_months = sorted(by_month.keys(), reverse=True)[:monthly_keep]
for m_key in sorted_months:
    candidates = by_month[m_key]
    first_of_month = [c for c in candidates if c[0].day == 1]
    if first_of_month:
        chosen = max(first_of_month, key=lambda c: c[1])
        mark_keep(chosen[2], f"Monthly-1st({m_key[0]}-{m_key[1]:02d})")
    else:
        chosen = min(candidates, key=lambda c: c[1])
        mark_keep(chosen[2], f"Monthly({m_key[0]}-{m_key[1]:02d})")

for dt, fname in parsed:
    if fname in keep_reasons:
        print(f"KEEP|{fname}|{','.join(keep_reasons[fname])}")
    else:
        print(f"DELETE|{fname}|expired")
PYEOF
    )

    while IFS='|' read -r action fname reason; do
        [ -z "$action" ] && continue
        if [ "$action" = "KEEP" ]; then
            echo -e "   ${GREEN}✓ Keep:${NC}   $fname [${BLUE}${reason}${NC}]"
        elif [ "$action" = "DELETE" ]; then
            echo -e "   ${YELLOW}🗑️  Delete:${NC} $fname (expired by GFS policy)"
            rclone deletefile "${GDRIVE_REMOTE}:${GDRIVE_FOLDER}/${fname}"
        fi
    done <<< "$GFS_PLAN"
fi

# 4. Clean up old local backups (keep last LOCAL_KEEP_DAYS days, minimum 7 newest daily files)
echo -e "${YELLOW}🧹 Cleaning up local backups (keeping last ${LOCAL_KEEP_DAYS} days)...${NC}"
LOCAL_FILES=$(ls -1 "${LOCAL_BACKUP_DIR}"/sbms_backup_*.tar.gz 2>/dev/null | xargs -n1 basename 2>/dev/null)

if [ -n "$LOCAL_FILES" ]; then
    LOCAL_PLAN=$(LOCAL_FILES="$LOCAL_FILES" LOCAL_KEEP_DAYS="$LOCAL_KEEP_DAYS" python3 - << 'PYEOF'
import os
import re
from datetime import datetime, timedelta

files = [f.strip() for f in os.environ.get("LOCAL_FILES", "").splitlines() if f.strip()]
keep_days = int(os.environ.get("LOCAL_KEEP_DAYS", "7"))

pattern = re.compile(r"^sbms_backup_(\d{8})_(\d{6})\.tar\.gz$")
parsed = []
for fname in files:
    m = pattern.match(fname)
    if m:
        dt = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        parsed.append((dt, fname))

parsed.sort(key=lambda x: x[0], reverse=True)

by_date = {}
for dt, fname in parsed:
    d = dt.date()
    if d not in by_date:
        by_date[d] = fname

keep_set = set()
if parsed:
    keep_set.add(parsed[0][1])

cutoff = datetime.now().date() - timedelta(days=keep_days - 1)
sorted_dates = sorted(by_date.keys(), reverse=True)
for idx, d in enumerate(sorted_dates):
    # Keep all backups from the last keep_days calendar days (and at least 3 newest dates as safety net)
    if d >= cutoff or idx < 3:
        keep_set.add(by_date[d])

for dt, fname in parsed:
    if fname in keep_set:
        print(f"KEEP|{fname}")
    else:
        print(f"DELETE|{fname}")
PYEOF
    )

    while IFS='|' read -r action fname; do
        [ -z "$action" ] && continue
        if [ "$action" = "DELETE" ]; then
            echo -e "   ${YELLOW}🗑️  Removing old local backup:${NC} $fname"
            rm -f "${LOCAL_BACKUP_DIR}/${fname}"
        fi
    done <<< "$LOCAL_PLAN"
fi

echo -e "${GREEN}"
echo "🎉 Google Drive Backup & GFS Rotation Complete!"
echo "==============================================="
echo "☁️  Location: ${GDRIVE_REMOTE}:${GDRIVE_FOLDER}/"
echo "📦 Latest:   $(basename "$LATEST_BACKUP")"
echo "📏 Size:     $(ls -lh "$LATEST_BACKUP" | awk '{print $5}')"
echo ""
echo "💡 To restore from Google Drive:"
echo "   1. Download: rclone copy \"${GDRIVE_REMOTE}:${GDRIVE_FOLDER}/$(basename "$LATEST_BACKUP")\" ./backups/"
echo "   2. Restore:  ./restore_sbms.sh ./backups/$(basename "$LATEST_BACKUP")"
echo -e "${NC}"
