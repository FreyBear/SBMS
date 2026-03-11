# SBMS
Small Brewery Management System. Management of brewing, fermentation and kegs.
# Small Brewery Management System (SBMS)

A simple, stable, and easy-to-use management system for small breweries. SBMS is designed to run reliably on an Ubuntu Linux home server (latest LTS) and leverages well-known database and web technologies, all containerized with Docker Compose for hassle-free deployment.

## Features

### 🍺 **Brewery Operations**
- **Recipe Management**: Store and organize your brewing recipes with styles and detailed notes
  - **BeerXML Import**: Import recipes from any BeerXML-compatible brewing software (BeerSmith, Brewer's Friend, etc.)
- **Kit Management**: Comprehensive brewing kit tracking system including:
  - Support for multiple kit types (Fresh Wort, Cider, Red Wine, White Wine, Rose Wine, Sparkling Wine, Mead)
  - Kit information management (manufacturer, style, ABV, volume, cost)
  - Supplier and ingredient tracking
  - Label image and instruction PDF uploads
  - Kit-based brewing for easy batch creation
- **Brew Tracking**: Record and review logs from each brewing session with batch tracking from recipes OR kits
  - **Gluten-free Tracking**: Mark and filter gluten-free brews for dietary requirements
  - **ABV Tracking**: Track estimated and actual alcohol by volume for quality control
  - **Brew Details**: Style, batch size, original/final gravity measurements
- **Keg Management**: Comprehensive keg tracking system including:
  - Keg status monitoring (Full, Started, Available/Cleaned, Empty)
  - Location tracking for easy inventory management
  - Condition monitoring (Good, Defective)
  - Volume and content tracking
  - **Brew Linking**: Connect kegs to source brews with automatic ABV and gluten-free info
  - **Searchable Brew Selection**: Modal interface for easy brew selection with filtering
  - **MQTT Weight Integration**: Automatic keg weight monitoring via MQTT broker
    - Real-time weight updates from sensors (e.g., PLAATO Keg)
    - Automatic calculation of remaining beer volume
    - Live status monitoring in Settings page
  - Cleaning schedules and maintenance logs
  - Keg history with detailed tracking of usage patterns
  - **Batch Update**: Update weight, liters, location, and notes across multiple kegs simultaneously
  - **Batch MQTT Refresh**: Fetch live sensor weights for multiple kegs in a single operation

### 💰 **Expense Management**
- **Expense Submission**: Easy expense reporting with receipt upload (JPG, PNG, PDF)
- **Multi-file Receipts**: Attach multiple receipt images per expense
- **Approval Workflow**: Three-stage approval process (Pending → Approved/Rejected)
- **Role-based Access**: Different capabilities based on user roles
- **Reimbursement Integration**: Bank account management for easy reimbursements
- **Audit Trail**: Complete tracking of who approved/rejected expenses and when
- **Edit & Resubmit**: Rejected expenses can be edited and resubmitted
- **Expense Categories**: Classify expenses into categories (Raw Materials, Equipment, Packaging, Cleaning, Transport, Events, Other) with color-coded chips
- **CSV Export**: Export filtered expense lists to CSV with full Nordic character support (UTF-8 BOM)
- **Responsive Design**: Mobile-friendly expense table with combined smart columns

### � **Google Calendar Integration**
- **Automatic Sync**: Brew tasks are automatically synced to Google Calendar when created, updated, or completed
- **Service Account Auth**: Uses Google Service Account for server-side authentication (no OAuth flow required)
- **Color-coded Events**: Active tasks appear in yellow (Banana), completed tasks in grey (Graphite)
- **Easy Toggle**: Enable/disable via `GOOGLE_CALENDAR_ENABLED` environment variable — no code changes needed
- **Supported Operations**: Create, update, complete, uncomplete, and delete calendar events matching brew task lifecycle

### �👥 **User Management**
- **Role-based Security**: Five user roles with different permission levels:
  - **Admin**: Full system access and management
  - **Economy**: Financial management and expense approval
  - **Brewer**: Brewery operations and expense submission
  - **Operator**: Keg operations and limited access
  - **Viewer**: Read-only access to all systems
- **User Profiles**: Customizable user profiles with bank account information
- **Password Management**: Secure password changes and user account management

### 🌐 **Internationalization**
- **Multi-language Support**: English, Norwegian (Norsk), and Nynorsk language options
- **Localized Interface**: All text elements translated for international use
- **User Language Preferences**: Individual language settings per user

### 📊 **Dashboard & Reporting**
- **System Overview**: Real-time dashboard with key metrics
- **Keg Status Summary**: Quick overview of all keg statuses and locations
- **Pending Expense Alerts**: Economy users see pending expense requests
- **Recent Activity**: Track recent keg updates and brewing activity

## Technology Stack

**Backend**: Python Flask with Gunicorn production WSGI server  
**Database**: PostgreSQL with full ACID compliance and advanced data types  
**Frontend**: Server-side rendered HTML templates with Jinja2 and modern CSS  
**IoT Integration**: MQTT client (Paho) for real-time sensor data from weight sensors  
**File Management**: Secure file upload and storage for expense receipts  
**Internationalization**: Flask-Babel for multi-language support  
**Authentication**: Flask-Login with role-based access control  
**Containerization**: Docker Compose for isolated, reproducible environments  
**Production Server**: Gunicorn for multi-threaded, production-ready deployment  
**Reverse Proxy Support**: Configured for Nginx Proxy Manager and HTTPS  
**Google Calendar API**: Server-side sync via google-auth and googleapiclient  

**Core Dependencies**:
  - Flask 2.3.3 (web framework)
  - Gunicorn 21.2.0 (production WSGI server)
  - Flask-Login (authentication)
  - Flask-Babel (internationalization)
  - psycopg2-binary 2.9.7 (PostgreSQL adapter)
  - paho-mqtt 1.6.1 (MQTT client for IoT sensors)
  - python-dotenv 1.0.0 (environment management)
  - bcrypt (password hashing)
  - WTForms (form handling and validation)
  - google-auth / google-api-python-client (Google Calendar sync)

**Security Features**:  
  - Production-ready Gunicorn WSGI server
  - Reverse proxy support (Nginx Proxy Manager, HTTPS)
  - Secure password hashing with bcrypt
  - Role-based permission system
  - CSRF protection on all forms
  - Secure file upload validation
  - SQL injection prevention through parameterized queries  
  - Environment-based configuration management

## Getting Started

### Quick Start (Ubuntu/Debian)

1. **Clone the repository**
   ```bash
   git clone https://github.com/FreyBear/SBMS.git
   cd SBMS
   ```

2. **Run the setup script**
   ```bash
   ./start-sbms.sh
   ```
   
   This script will:
   - Install Docker if not present
   - Create your `.env` file from the template
   - Start the SBMS system with Docker Compose

3. **Access the web interface**
   - Open your browser and go to `http://localhost:8080`
   - **Default login**: username `admin`, password `admin123`
   - **⚠️ Important**: Change the default password immediately after first login!
   - **For production**: Configure your domain in `.env` and set `ENABLE_HTTPS=true`

4. **Create additional users**
   - Log in as admin and go to User Management
   - Create users with appropriate roles for your brewery team

## Production Deployment

SBMS is production-ready out of the box with Gunicorn WSGI server and reverse proxy support.

### **For Public Access (Recommended)**

1. **Configure your domain in `.env`**:
   ```bash
   # Add your domain to allowed hosts
   ALLOWED_HOSTS=localhost,127.0.0.1,yourdomain.com
   ENABLE_HTTPS=true
   ```

2. **Set up reverse proxy** (Nginx Proxy Manager example):
   - **Domain**: `yourdomain.com`
   - **Forward to**: `your-server-ip:8080`
   - **SSL Certificate**: Enable SSL (Let's Encrypt)
   - **Advanced Config**:
     ```nginx
     proxy_set_header Host $host;
     proxy_set_header X-Real-IP $remote_addr;
     proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
     proxy_set_header X-Forwarded-Proto $scheme;
     proxy_set_header X-Forwarded-Host $host;
     proxy_redirect off;
     ```

3. **Restart SBMS**:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

### **Production Features**
- ✅ **Gunicorn WSGI Server**: Multi-worker production server
- ✅ **HTTPS Support**: Automatic HTTPS redirect when behind proxy
- ✅ **Security Headers**: Proper handling of X-Forwarded-* headers
- ✅ **Multi-user Support**: Concurrent user handling
- ✅ **Auto-restart**: Worker processes automatically restart to prevent memory leaks

### **Performance**
- **Workers**: Automatically calculated based on CPU cores (typically 9+ workers)
- **Concurrent Users**: Handles multiple simultaneous users
- **Memory Management**: Workers restart after 1000 requests
- **Request Timeout**: 30-second timeout for stability

## What's Included

When you clone and start SBMS, you get a **complete brewery management system** with:

✅ **Ready-to-use Database**: Complete schema with sample recipes and brew data  
✅ **Default Admin Account**: Immediate access with `admin`/`admin123`  
✅ **All User Roles**: Pre-configured permission system for 5 user types  
✅ **Expense Management**: Full workflow from submission to reimbursement  
✅ **MQTT Integration**: Real-time weight monitoring from IoT sensors (PLAATO Keg, etc.)  
✅ **Multi-language Support**: English and Norwegian interfaces  
✅ **Google Calendar Sync**: Optional brew task sync to Google Calendar (Service Account)  
✅ **BeerXML Import**: Import recipes from BeerSmith, Brewer's Friend, and other tools  
✅ **File Upload System**: Secure receipt storage for expense management  
✅ **Sample Data**: Example recipes, brews, and keg configurations  
✅ **Production Ready**: Containerized with PostgreSQL, Flask, and Gunicorn  
✅ **Reverse Proxy Support**: Pre-configured for Nginx Proxy Manager and HTTPS  
✅ **Backup System**: Complete backup and restore functionality with cloud storage  

**No additional setup required** - just clone, run, and start managing your brewery!

### Manual Setup

If you prefer manual setup or are not on Ubuntu/Debian:

1. **Install Docker and Docker Compose**
   - Follow the official Docker installation guide for your OS

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your preferred settings
   ```

3. **Start the system**
   ```bash
   docker compose up -d
   ```

4. **Access the web interface**
   - Open your browser and go to `http://localhost:8080`
   - **Default login**: username `admin`, password `admin123`
   - **⚠️ Important**: Change the default password immediately after first login!

## Management Commands

```bash
# View logs
docker compose logs -f

# Stop the system
docker compose down

# Rebuild and restart (for updates)
docker compose up -d --build

# View production server status
docker logs sbms_web

# Access database directly
docker exec -it sbms_db psql -U sbms_user -d sbms

# Run security check
./security_check.sh

# Create backup
./backup_sbms.sh

# Create backup
./backup_sbms.sh
```

## Configuration & Environment Variables

To configure the system, copy `.env.example` to `.env` and fill in your own values:

```bash
cp .env.example .env
```

**Important:** Never commit your `.env` file to GitHub. It is already listed in `.gitignore` for your safety.

The `.env.example` file contains all necessary configuration keys, including database, web server, security, DuckDNS, and backup settings.

## Editing Your .env File

The `.env` file contains sensitive configuration for your SBMS system. Here’s how to edit it safely:

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```
2. **Open `.env` in your editor:**
   You can use VS Code, nano, vim, or any text editor.
   ```bash
   nano .env
   ```
3. **Fill in your values:**
   - Database credentials: Choose strong passwords. [Password generator](https://passwordsgenerator.net/)
   - Secret keys: Use a secure random string. [Random key generator](https://randomkeygen.com/)
   - DuckDNS: Get your token and domain from [DuckDNS](https://www.duckdns.org/)
   - Backup path: Make sure the path exists and is writable.
   - HTTPS: For production, set `ENABLE_HTTPS=true` and follow [Let's Encrypt](https://letsencrypt.org/) for free SSL certificates.

4. **Configure Google Calendar** (optional):
   - Create a Google Cloud project and enable the Google Calendar API
   - Create a Service Account and download the JSON key
   - Share your Google Calendar with the Service Account email
   - Base64-encode the JSON key: `base64 -w 0 service_account.json`
   - Set `GOOGLE_CALENDAR_ENABLED=true`, `GOOGLE_CALENDAR_ID`, and `GOOGLE_SERVICE_ACCOUNT_JSON_B64` in `.env`

5. **Do not share your `.env` file!**
   - Never commit `.env` to GitHub or share it publicly.

### More Resources
- [12 Factor App: Store config in the environment](https://12factor.net/config)
- [DuckDNS Setup Guide](https://www.duckdns.org/install.jsp)
- [PostgreSQL Environment Variables](https://www.postgresql.org/docs/current/libpq-envars.html)

If you have questions about any setting, check the comments in `.env.example` or ask for help!

## Project Structure

```
SBMS/
├── docker-compose.yml          # Container orchestration
├── .env                       # Your configuration (not in git)
├── .env.example              # Configuration template
├── database/
│   └── init.sql              # Database schema and initial data
├── backend/
│   ├── app.py               # Main Flask application
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile          # Backend container config
├── frontend/
│   ├── templates/           # HTML templates
│   │   ├── base.html
│   │   ├── index.html      # Dashboard
│   │   ├── kegs.html       # Keg management
│   │   └── ...
│   └── static/
```
SBMS/
├── docker-compose.yml          # Container orchestration
├── .env                       # Your configuration (not in git)
├── .env.example              # Configuration template
├── start-sbms.sh             # Quick setup script
├── database/
│   ├── init.sql              # Complete database schema with expense management
│   ├── add_expenses_permissions.sql  # Legacy migration (now included in init.sql)
│   └── migrate_language.sql  # Language preference migration
├── backend/
│   ├── app.py               # Main Flask application with all routes
│   ├── auth.py              # Authentication and authorization
│   ├── forms.py             # WTForms for all user inputs
│   ├── i18n.py              # Internationalization setup
│   ├── gcal_handler.py      # Google Calendar integration (Service Account)
│   ├── beerxml_handler.py   # BeerXML recipe import handler
│   ├── mqtt_handler.py      # MQTT broker connection and weight handling
│   ├── requirements.txt     # Python dependencies (includes Gunicorn)
│   ├── gunicorn.conf.py     # Production server configuration
│   ├── Dockerfile           # Backend container config (production-ready)
│   └── uploads/             # File storage for expense receipts
├── frontend/
│   ├── templates/           # Jinja2 HTML templates
│   │   ├── base.html        # Base template with navigation
│   │   ├── index.html       # Dashboard with expense alerts
│   │   ├── expenses.html    # Expense management interface
│   │   ├── create_expense.html  # Expense submission form
│   │   ├── edit_expense.html    # Expense editing form
│   │   ├── kegs.html        # Keg management
│   │   ├── recipes.html     # Recipe management
│   │   ├── create_kit.html  # Kit creation form
│   │   ├── edit_kit.html    # Kit editing form
│   │   ├── kit_detail.html  # Kit information display
│   │   ├── users.html       # User management
│   │   ├── login.html       # Authentication
│   │   └── ...              # Additional templates
│   └── static/
│       └── css/
│           └── style.css    # Application styles with expense UI
├── translations/            # Multi-language support
│   ├── en/LC_MESSAGES/      # English translations
│   ├── no/LC_MESSAGES/      # Norwegian (Bokmål) translations  
│   └── nn/LC_MESSAGES/      # Norwegian (Nynorsk) translations
├── backup_sbms.sh          # Complete backup script
├── restore_sbms.sh         # One-click restore script
├── setup_auto_backup.sh    # Automated backup setup
├── security_check.sh       # Security validation tool
└── test_restore.sh         # Backup restore testing
```

## Kit Management System

SBMS includes a comprehensive **Brewing Kit Management** system designed for breweries that use commercial brewing kits alongside traditional recipes:

### 🎛️ **Kit Types Supported**
- **Fresh Wort Kits**: Ready-to-ferment wort concentrates
- **Cider Kits**: Apple and fruit cider concentrates  
- **Wine Kits**: Red Wine, White Wine, Rose Wine varieties
- **Sparkling Wine Kits**: Champagne and sparkling wine kits
- **Mead Kits**: Honey wine and mead concentrates

### 📋 **Kit Information Management**
- **Supplier Details**: Track suppliers, manufacturers, and costs
- **Technical Specifications**: ABV targets, volumes, styles, and ingredients
- **Documentation**: Upload label images and instruction PDFs
- **Inventory Tracking**: Monitor kit availability and usage
- **Brew Integration**: Create brews directly from kits with full traceability

### 🔗 **Kit-to-Brew Workflow**
1. **Add Kit**: Input kit details with supplier and technical information
2. **Upload Files**: Attach label images and instruction PDFs
3. **Create Brew**: Use kit as the base for new brewing batches
4. **Track Progress**: Monitor kit usage through brew history
5. **Manage Inventory**: Track which kits are available vs. used

**Perfect for breweries that:**
- Use commercial brewing kits alongside traditional recipes
- Need to track supplier relationships and costs
- Want visual documentation (labels, instructions) stored with kit data
- Require full traceability from kit purchase to finished product

## System Capabilities

### **Complete Brewery Management**
- **Dashboard**: Real-time overview with keg status, pending expenses, and recent activity
- **Keg Operations**: Full lifecycle management from filling to cleaning
- **Keg History**: Detailed tracking of all keg usage and movements
- **Brew Management**: Batch tracking with recipe OR kit integration
- **Recipe Organization**: Centralized recipe storage with style categorization
- **Kit Management**: Complete brewing kit lifecycle from purchase to brewing with file uploads

### **Professional Expense Management**
- **Expense Workflow**: Complete submission-to-payment process
- **Receipt Management**: Multi-file upload with secure storage
- **Approval System**: Role-based approval with rejection/resubmission capability
- **Financial Integration**: Bank account management for reimbursements
- **Audit Compliance**: Complete expense tracking with timestamps and approvers

### **Enterprise User Management**
- **Role-based Security**: Five distinct user roles with granular permissions
- **Multi-language Support**: English and Norwegian interface options
- **User Profiles**: Comprehensive user management with banking information
- **Authentication**: Secure login with password management

## User Roles & Permissions

SBMS includes a sophisticated role-based access control system with five user types:

### 👨‍💼 **Admin**
- **Full system access** including all features and settings
- **User management**: Create, edit, and deactivate users
- **Complete expense control**: Approve, reject, and delete any expense
- **System configuration**: Access to all administrative functions
- **Use case**: Brewery owner, IT administrator

### 💰 **Economy**
- **Financial management focus** with expense approval authority
- **Expense oversight**: View, approve, reject all expense requests
- **User viewing**: Can see all users and their bank account information
- **Limited brewery operations**: View-only access to kegs, brews, recipes
- **Use case**: Accountant, financial manager, brewery CFO

### 🍺 **Brewer**
- **Full brewery operations** including recipe, kit, and brew management
- **Keg management**: Update keg status, location, and content
- **Recipe control**: Create, edit, and organize brewing recipes
- **Kit management**: Add, edit, and organize brewing kits with file uploads
- **Expense submission**: Submit expenses with receipts, edit rejected expenses
- **User viewing**: Can see basic user information
- **Use case**: Head brewer, brewing staff, production manager

### 🔧 **Operator**
- **Keg operations specialist** with limited system access
- **Keg updates**: Change status, location, and basic keg information
- **View-only access**: Can view brews, recipes, kits, and expenses
- **No user management**: Cannot see or modify user accounts
- **Use case**: Warehouse staff, keg handling personnel, part-time staff

### 👀 **Viewer**
- **Read-only access** to all information systems
- **No modifications**: Cannot change any data in the system
- **Full visibility**: Can view kegs, brews, recipes, kits, and expenses
- **No user access**: Cannot see user management sections
- **Use case**: Investors, consultants, quality control, reporting staff

### Permission Matrix

| Feature | Admin | Economy | Brewer | Operator | Viewer |
|---------|--------|---------|--------|----------|---------|
| **Kegs** | Full | View | Edit | Edit | View |
| **Brews** | Full | View | Full | View | View |
| **Recipes** | Full | View | Full | View | View |
| **Kits** | Full | View | Edit | View | View |
| **Expenses** | Full | Full | Edit Own | View | View |
| **Users** | Full | View | View | None | None |
| **System** | Full | None | None | None | None |

## Data Migration

The system includes sample data for recipes, brews, and kegs. The database will be initialized with basic data structure when first started, and you can add your own kits and recipes through the web interface.

## Extensibility

The system is designed to allow new features and modules to be added without changing the core database structure.
PostgreSQL enables easy schema migrations and supports advanced data types.

## Backup & Recovery

Automated backups ensure you can restore to a working state without data loss.
Complete backup system with local and cloud storage options available.

### **Security & Production**

- ✅ **Production WSGI Server**: Gunicorn with multi-worker support
- ✅ **Reverse Proxy Ready**: Nginx Proxy Manager, Traefik, or Apache support
- ✅ **HTTPS Support**: Automatic HTTPS handling behind SSL terminating proxy
- ✅ **Environment Security**: Sensitive data protected in `.env` files
- ✅ **Role-based Access**: Five-tier permission system
- ✅ **Security Validation**: Built-in security check script

## Dynamic DNS (DuckDNS)

DuckDNS is used to keep your domain updated with your changing IP address.
Setup instructions for DuckDNS will be provided.

## Goals

- **Stability**: Use proven technologies for reliable operation.
- **Simplicity**: Easy to deploy, use, and maintain.
- **Extensibility**: Designed to grow with your brewery’s needs.

## License

MIT License

## Complete Database Schema

The SBMS system uses a comprehensive PostgreSQL schema that supports all brewery operations and expense management:

### Core Tables
- **`users`**: User accounts with roles, language preferences, and bank account information
- **`user_role`**: Role definitions with JSON-based permission system
- **`recipe`**: Brewing recipes with styles and detailed notes
- **`kit`**: Brewing kit management with file uploads and supplier tracking
- **`brew`**: Batch tracking with recipe OR kit links, brewing dates, ABV measurements, and gluten-free status
- **`keg`**: Complete keg lifecycle management with status, location tracking, brew linking, ABV, and gluten-free info
- **`keg_history`**: Historical tracking of all keg changes and movements

### Expense Management Tables
- **`expenses`**: Complete expense tracking with approval workflow
- **`expense_images`**: Receipt file management with secure storage

### Key Features
- **Referential Integrity**: Full foreign key constraints ensure data consistency
- **Audit Trail**: Timestamp tracking on all critical operations
- **File Management**: Secure receipt storage with CASCADE delete protection
- **Internationalization**: Multi-language support built into user preferences
- **Permission System**: JSON-based role permissions for flexible access control

The complete schema is available in `database/init.sql` and includes sample data for immediate testing and development.

---

## Summary

SBMS provides a **complete, production-ready brewery management solution** that combines traditional brewery operations (kegs, brews, recipes, kits) with modern business features (expense management, user roles, internationalization). 

**Perfect for:**
- Small to medium breweries seeking operational efficiency
- Businesses needing expense tracking and approval workflows  
- Multi-user environments requiring role-based access control
- Organizations wanting a simple, maintainable system without vendor lock-in
- Production deployments requiring HTTPS and reverse proxy support

**Built with stability and simplicity in mind** - using proven technologies (PostgreSQL, Flask, Gunicorn) and straightforward architecture for long-term reliability and easy maintenance.

### **Key Advantages**
- 🚀 **Production Ready**: Gunicorn WSGI server with multi-worker support
- 🔒 **Security First**: Role-based access, HTTPS support, secure file handling
- 🌐 **Internet Ready**: Reverse proxy support for public deployment
- 💾 **Data Protection**: Comprehensive backup and restore system
- 🌍 **Multi-language**: English and Norwegian interface support
- 📊 **Complete System**: All brewery operations in one integrated platform

## 💾 Backup & Recovery

SBMS includes comprehensive backup solutions to protect your brewery data:

### **Quick Backup**
```bash
# Create complete backup (database + files)
./backup_sbms.sh

# Output: ./backups/sbms_backup_YYYYMMDD_HHMMSS.tar.gz
```

### **Backup Features**
- ✅ **Complete System Backup**: Database, receipts, configuration
- ✅ **Google Drive Integration**: Automatic cloud storage with `rclone`
- ✅ **Automated Scheduling**: Cron-based daily/weekly backups
- ✅ **One-Click Restore**: Simple restore from any backup file
- ✅ **Security**: Encrypted, compressed archives

### **Setup Automated Backups**
```bash
# Configure automated daily backups
./setup_auto_backup.sh

# Options: Daily, weekly, or custom schedule
# Includes Google Drive sync and log monitoring

# Test backup and restore process
./test_restore.sh ./backups/backup_file.tar.gz
```

📖 **Complete documentation**: See [BACKUP_GUIDE.md](BACKUP_GUIDE.md) for detailed backup strategies, troubleshooting, and recovery procedures.
