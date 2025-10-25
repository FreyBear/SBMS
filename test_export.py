#!/usr/bin/env python3
"""Test BeerXML export functionality"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app import app, get_db_connection
from beerxml_handler import BeerXMLHandler

def test_export(recipe_id):
    """Test exporting a recipe"""
    with app.app_context():
        conn = get_db_connection()
        if not conn:
            print("Could not connect to database")
            return
        
        try:
            handler = BeerXMLHandler(conn)
            xml_output = handler.export_to_xml(recipe_id)
            
            if xml_output:
                # Write to file
                output_file = f'recipe_{recipe_id}_exported.xml'
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(xml_output)
                print(f"✅ Export successful!")
                print(f"📄 File written to: {output_file}")
                print(f"\n📊 Preview (first 500 chars):")
                print(xml_output[:500])
                return True
            else:
                print("❌ Export failed - no XML output generated")
                return False
                
        finally:
            conn.close()

if __name__ == '__main__':
    recipe_id = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    print(f"🧪 Testing export of recipe ID {recipe_id}...")
    test_export(recipe_id)
