# SBMS Backup & Recovery Guide

## 🎯 Quick Summary

### Backup Your System
```bash
./backup_sbms.sh  # Creates ./backups/sbms_backup_YYYYMMDD_HHMMSS.tar.gz
```

### Restore Your System (After Crash)
```bash
./restore_sbms.sh ./backups/sbms_backup_YYYYMMDD_HHMMSS.tar.gz
# Automatically handles:
# ✅ Stops current system
# ✅ Removes old database 
# ✅ Clears schema conflicts
# ✅ Restores all data
# ✅ Restores files
# ✅ Starts system
```

### Test Your Restore (Optional)
```bash
./test_restore.sh ./backups/sbms_backup_YYYYMMDD_HHMMSS.tar.gz
# Verifies restore works correctly
```

---

## 🚀 Quick Start

### Manual Backup (Recommended)
```bash
# Create a complete backup
./backup_sbms.sh

# Backup includes:
# ✅ PostgreSQL database with all users, expenses, kegs, etc.
# ✅ All uploaded receipt files
# ✅ Configuration files
# ✅ Compressed .tar.gz archive
```

### Restore from Backup
```bash
# Restore from backup file
./restore_sbms.sh ./backups/sbms_backup_YYYYMMDD_HHMMSS.tar.gz

# ⚠️ WARNING: This replaces ALL current data!
```

## 💾 Backup Methods

### 1. Local Backup (`backup_sbms.sh`)
- **What it backs up**: Database, receipts, configuration
- **Output**: Compressed .tar.gz file in `./backups/` folder
- **Use case**: Manual backups, local testing, quick snapshots

### 2. Google Drive Backup (`backup_to_gdrive.sh`)
- **Requires**: rclone installed and configured for Google Drive (`gdrive` remote)
- **What it does**:
  1. Creates a fresh local backup (`backup_sbms.sh`)
  2. Uploads backup(s) to `gdrive:SBMS_Backups/`
  3. Applies **GFS (Grandfather-Father-Son)** rotation on Google Drive:
     - **Daily (Son)**: Keeps the last **7 daily** backups
     - **Weekly (Father)**: Keeps the last **4 weekly** backups (Sundays)
     - **Monthly (Grandfather)**: Keeps the last **12 monthly** backups (1st of month)
  4. Cleans up local backups older than **7 days**
- **Use case**: Off-site backup, automatic cloud storage with standard lifecycle management
- **Setup**:
  ```bash
  # Interactive setup helper
  ./setup_gdrive.sh
  ```

### 3. Automated Backups (`setup_auto_backup.sh`)
- **What it does**: Sets up cron jobs for scheduled backups
- **Options**: Daily, weekly, twice daily, or custom schedule
- **Features**: Automatic cleanup of old backups
- **Log file**: `backup.log` tracks all automated backups

## 📁 What Gets Backed Up

### Database Content
- ✅ All user accounts and roles
- ✅ All expenses and approval history
- ✅ All keg data and history
- ✅ All brew and recipe information
- ✅ System configuration and permissions

### Files
- ✅ All expense receipt images (JPG, PNG, PDF)
- ✅ docker-compose.yml configuration
- ✅ .env configuration (if present)

### Metadata
- ✅ Backup timestamp and information
- ✅ Restore instructions
- ✅ File integrity information

## 🔧 Recovery Procedures

### Full System Restore (Recommended)
```bash
# Simple one-command restore
./restore_sbms.sh ./backups/sbms_backup_YYYYMMDD_HHMMSS.tar.gz

# The script automatically:
# 1. Stops current system
# 2. Removes old database volume  
# 3. Starts fresh database
# 4. Clears any conflicting schema
# 5. Restores your backup data
# 6. Restores receipt files
# 7. Starts complete system
```

### Manual Recovery (If script fails)
```bash
# 1. Stop system completely
docker-compose down
docker volume rm sbms_postgres_data

# 2. Extract backup manually
tar -xzf sbms_backup_YYYYMMDD_HHMMSS.tar.gz

# 3. Start database only
docker-compose up -d db
sleep 15

# 4. Clear existing schema to avoid conflicts
docker exec -i sbms_db psql -U sbms_user sbms -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# 5. Restore database
docker exec -i sbms_db psql -U sbms_user sbms < sbms_backup_YYYYMMDD_HHMMSS/database.sql

# 6. Restore files
cp -r sbms_backup_YYYYMMDD_HHMMSS/uploads/* ./backend/uploads/

# 7. Start complete system
docker-compose up -d
```

### Database-Only Restore
```bash
# Extract database from backup
tar -xzf sbms_backup_YYYYMMDD_HHMMSS.tar.gz
cd sbms_backup_YYYYMMDD_HHMMSS

# Restore database only
docker exec -i sbms_db psql -U sbms_user sbms < database.sql
```

### Files-Only Restore
```bash
# Extract and restore receipts only
tar -xzf sbms_backup_YYYYMMDD_HHMMSS.tar.gz
cp -r sbms_backup_YYYYMMDD_HHMMSS/uploads/* ./backend/uploads/
```

## 📅 Backup Strategies

### For Production Systems
- **Frequency**: Daily automated backups
- **Storage**: Local + Google Drive
- **Retention**: Keep 30 days local, 1 year cloud
- **Testing**: Monthly restore tests

### For Development/Testing
- **Frequency**: Weekly or before major changes
- **Storage**: Local only
- **Retention**: Keep 7 days
- **Testing**: Before each development cycle

### For Small Operations
- **Frequency**: Weekly automated
- **Storage**: Google Drive
- **Retention**: Keep 90 days
- **Testing**: Quarterly

## 🛡️ Security Considerations

### Backup Security
- 🔒 Database dumps contain sensitive information
- 🔒 Receipt files may contain personal/financial data
- 🔒 .env files contain passwords and secrets
- 💡 **Store backups securely and limit access**

### Google Drive Security
- 🔒 Use dedicated Google account for backups
- 🔒 Enable 2FA on backup Google account
- 🔒 Limit rclone access permissions
- 🔒 Regularly rotate Google API credentials

## 🔍 Monitoring & Verification

### Backup Verification
```bash
# Check recent backups
ls -la ./backups/

# Verify backup contents
tar -tzf sbms_backup_YYYYMMDD_HHMMSS.tar.gz

# Check backup log
tail -f backup.log
```

### Health Checks
```bash
# Test database connection
docker exec sbms_db psql -U sbms_user sbms -c "SELECT COUNT(*) FROM users;"

# Check file system
ls -la ./backend/uploads/expenses/

# Verify system status
docker-compose ps
```

## 📞 Troubleshooting

### Common Issues

**Backup fails with permission error**
```bash
# Fix permissions
sudo chown -R $USER:$USER ./backend/uploads/
chmod -R 755 ./backend/uploads/
```

**Google Drive upload fails**
```bash
# Reconfigure rclone
rclone config reconnect gdrive:
```

**Restore fails - database exists**
```bash
# Force remove database volume
docker-compose down
docker volume rm sbms_postgres_data --force

# If database schema conflicts persist:
docker exec -i sbms_db psql -U sbms_user sbms -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

**Partial restore (missing data)**
```bash
# This usually means the database schema conflicted during restore
# Use the manual recovery process above, which includes schema clearing
./restore_sbms.sh will now handle this automatically
```

**Password changed - can't connect to database**
```bash
# If .env has been updated with new database password:
# 1. The restore process will recreate the database with new password
# 2. Your data will be restored completely
# 3. User passwords in the app remain unchanged (they use bcrypt hashing)
```

**Large backup files**
```bash
# Check what's taking space
tar -tzf backup.tar.gz | grep -E '\.(jpg|png|pdf)$' | wc -l
du -sh ./backend/uploads/
```

## 📚 Advanced Usage

### Custom Backup Scripts
```bash
# Backup only database
docker exec sbms_db pg_dump -U sbms_user sbms > custom_db_backup.sql

# Backup only specific date range (manual SQL)
docker exec -i sbms_db psql -U sbms_user sbms << EOF
COPY (SELECT * FROM expenses WHERE submitted_date >= '2025-01-01') TO STDOUT WITH CSV HEADER;
EOF > expenses_2025.csv
```

### Automated Monitoring
```bash
# Add to cron for backup monitoring
0 3 * * * cd /path/to/SBMS && find ./backups -name "*.tar.gz" -mtime -1 | wc -l | awk '{if($1==0) print "SBMS backup failed yesterday"}' | mail -s "SBMS Backup Alert" admin@yourdomain.com
```

## 🆘 Emergency Procedures

### Complete System Loss
1. **Install Docker** on new system
2. **Clone SBMS** from GitHub
3. **Download latest backup** from Google Drive
4. **Run restore script**: `./restore_sbms.sh backup_file.tar.gz`
5. **Verify all systems** operational
6. **Update configurations** as needed

### Partial Data Loss
1. **Stop system**: `docker-compose down`
2. **Identify what's lost** (database vs files)
3. **Extract specific data** from backup
4. **Restore only needed components**
5. **Restart and verify**: `docker-compose up -d`

---

**💡 Remember**: Regular backups are only useful if you also regularly test your restore procedures!