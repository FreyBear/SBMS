# SBMS
Small Brewery Management System. Management of brewing, fermentation and kegs.
# Small Brewery Management System (SBMS)

A simple, stable, and easy-to-use management system for small breweries. SBMS is designed to run reliably on an Ubuntu Linux home server (latest LTS) and leverages well-known database and web technologies, all containerized with Docker Compose for hassle-free deployment.

## Features

- **Recipe Management**: Store and organize your brewing recipes.
- **Brew Logs**: Record and review logs from each brewing session.
- **Keg Tracking**: Monitor the status and location of your kegs.

## Technology Stack

**Backend**: Python Flask or Node.js Express (widely supported, easy to extend)  
**Database**: PostgreSQL (robust, scalable, and supports future extensions)  
**Frontend**: React, Vue, or plain HTML/CSS (modular and maintainable)  
**Containerization**: Docker Compose (isolated, reproducible environments)  
**Backup System**: Automated database and file backups (e.g., scheduled with cron, stored offsite or in cloud)  
**Security**:  
  - HTTPS (SSL/TLS) for web access  
  - Strong authentication and authorization  
  - Regular updates and vulnerability scanning  
**Dynamic DNS**: DuckDNS integration for automatic IP updates  

## Getting Started

1. **Clone the repository**
   ```bash
   git clone https://github.com/FreyBear/SBMS.git
   cd SBMS
   ```

2. **Configure environment variables**
   - Edit `.env` files as needed for database and web settings.

3. **Start the system with Docker Compose**
   ```bash
   docker compose up -d
   ```

4. **Access the web interface**
   - Open your browser and go to `http://localhost:YOUR_PORT`

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

4. **Do not share your `.env` file!**
   - Never commit `.env` to GitHub or share it publicly.

### More Resources
- [12 Factor App: Store config in the environment](https://12factor.net/config)
- [DuckDNS Setup Guide](https://www.duckdns.org/install.jsp)
- [PostgreSQL Environment Variables](https://www.postgresql.org/docs/current/libpq-envars.html)

If you have questions about any setting, check the comments in `.env.example` or ask for help!

## Data Migration

Future updates will integrate legacy keg data into the new system.

## Extensibility

The system is designed to allow new features and modules to be added without changing the core database structure.
PostgreSQL enables easy schema migrations and supports advanced data types.

## Backup & Recovery

Automated backups ensure you can restore to a working state without data loss.
Backup scripts and instructions will be included for both database and application data.

## Security

The server runs behind NAT with port forwarding.
HTTPS is enforced for all web traffic.
User authentication and access control are required for all sensitive operations.
Regular security updates and monitoring.

## Dynamic DNS (DuckDNS)

DuckDNS is used to keep your domain updated with your changing IP address.
Setup instructions for DuckDNS will be provided.

## Goals

- **Stability**: Use proven technologies for reliable operation.
- **Simplicity**: Easy to deploy, use, and maintain.
- **Extensibility**: Designed to grow with your brewery’s needs.

## License

MIT License

## Example PostgreSQL Schema for Keg Management

Below is an example SQL schema for tracking kegs, brews, and recipes. This structure is designed for extensibility and traceability.

```sql
-- Table for brew batches
CREATE TABLE brew (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    date_brewed DATE NOT NULL,
    recipe_id INTEGER REFERENCES recipe(id),
    notes TEXT
);

-- Table for kegs
CREATE TABLE keg (
    id SERIAL PRIMARY KEY,
    keg_number TEXT NOT NULL,
    volume_liters NUMERIC,
    condition TEXT, -- e.g., 'God', 'Defekt'
    location TEXT,
    status TEXT, -- e.g., 'Full', 'Tom', 'Rengjort'
    last_cleaned DATE,
    notes TEXT,
    brew_id INTEGER REFERENCES brew(id),
    contents TEXT, -- e.g., 'IPA', 'Vann'
    date_filled DATE
);

-- Table for recipes (optional, for future extensibility)
CREATE TABLE recipe (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    style TEXT,
    notes TEXT
);
```

- Each keg references a brew via `brew_id`.
- Each brew can reference a recipe via `recipe_id`.
- This schema allows you to track the contents, condition, and status of all kegs, and trace each keg back to its brew and recipe.
