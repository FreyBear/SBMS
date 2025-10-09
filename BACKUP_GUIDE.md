# SBMS Backup & Recovery Guide

## 📋 Overview

SBMS includes comprehensive backup solutions that protect both your database and uploaded files (receipts). This guide covers all backup methods and recovery procedures.

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
- **Requires**: rclone installed and configured for Google Drive
- **What it does**: Creates local backup + uploads to Google Drive
- **Use case**: Off-site backup, automatic cloud storage
- **Setup**: 
  ```bash
  # Install rclone
  curl https://rclone.org/install.sh | sudo bash
  
  # Configure Google Drive
  rclone config
  # Choose: New remote -> Google Drive -> Follow prompts
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

### Full System Restore
```bash
# 1. Stop current system
docker-compose down

# 2. Remove old database
docker volume rm sbms_postgres_data

# 3. Restore from backup
./restore_sbms.sh ./backups/sbms_backup_YYYYMMDD_HHMMSS.tar.gz

# 4. System will automatically restart
# 5. Verify at http://localhost:8080
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