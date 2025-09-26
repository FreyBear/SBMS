#!/usr/bin/env python3
"""
SBMS Keg Data Import Script
Imports keg data from CSV file into PostgreSQL database
"""

import csv
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Database configuration
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'database': os.getenv('POSTGRES_DB', 'sbms'),
    'user': os.getenv('POSTGRES_USER', 'sbms_user'),
    'password': os.getenv('POSTGRES_PASSWORD', 'change_this_password_123'),
    'port': os.getenv('POSTGRES_PORT', '5432')
}

def import_kegs_from_csv(csv_file='keg_import_template.csv'):
    """Import keg data from CSV file"""
    
    # Connect to database
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print(f"Connected to database: {DB_CONFIG['database']}")
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        return False
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Read CSV file
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                imported_count = 0
                
                for row in reader:
                    # Skip comment lines
                    if row['keg_number'].startswith('#'):
                        continue
                    
                    # Check if keg already exists
                    cur.execute("SELECT id FROM keg WHERE keg_number = %s", (row['keg_number'],))
                    if cur.fetchone():
                        print(f"Keg {row['keg_number']} already exists, skipping...")
                        continue
                    
                    # Insert keg data
                    cur.execute("""
                        INSERT INTO keg (
                            keg_number, volume_liters, contents, status, 
                            amount_left_liters, location, notes, last_measured
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        row['keg_number'],
                        float(row['volume_liters']) if row['volume_liters'] else 19,
                        row['contents'] if row['contents'] else None,
                        row['status'] if row['status'] else 'Available/Cleaned',
                        float(row['amount_left_liters']) if row['amount_left_liters'] else 0,
                        row['location'] if row['location'] else None,
                        row['notes'] if row['notes'] else None,
                        row['last_measured'] if row['last_measured'] else None
                    ))
                    
                    imported_count += 1
                    print(f"Imported keg {row['keg_number']}")
                
                conn.commit()
                print(f"\nSuccessfully imported {imported_count} kegs!")
                
    except FileNotFoundError:
        print(f"CSV file {csv_file} not found!")
        return False
    except (psycopg2.Error, ValueError) as e:
        print(f"Import error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
    
    return True

if __name__ == "__main__":
    import sys
    
    # Load environment variables if .env file exists
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("python-dotenv not available, using default environment")
    
    csv_file = sys.argv[1] if len(sys.argv) > 1 else 'keg_import_template.csv'
    
    print(f"SBMS Keg Import Script")
    print(f"Importing from: {csv_file}")
    print("=" * 40)
    
    success = import_kegs_from_csv(csv_file)
    
    if success:
        print("\nImport completed successfully!")
    else:
        print("\nImport failed!")
        sys.exit(1)