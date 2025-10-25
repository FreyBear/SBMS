"""
BeerXML Import/Export Handler
Handles importing and exporting recipes in BeerXML 1.0 format
Compatible with BeerSmith, Brewfather, and other brewing software
"""

import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
from decimal import Decimal
from datetime import date, datetime
import psycopg2
from psycopg2.extras import RealDictCursor


class BeerXMLHandler:
    """Handles BeerXML import and export operations"""
    
    def __init__(self, db_connection):
        """Initialize with database connection"""
        self.conn = db_connection
    
    # Field mapping from BeerXML (PascalCase) to PostgreSQL (snake_case)
    RECIPE_FIELD_MAP = {
        'NAME': 'name',
        'VERSION': 'version',
        'TYPE': None,  # All recipes are All Grain, skip this
        'BREWER': 'brewer',
        'BATCH_SIZE': 'batch_size_liters',
        'BOIL_SIZE': 'boil_size_liters',
        'BOIL_TIME': 'boil_time_minutes',
        'EFFICIENCY': 'efficiency_percent',
        'OG': 'target_og',
        'FG': 'target_fg',
        'ABV': 'target_abv',
        'IBU': 'ibu',
        'EST_OG': 'target_og',
        'EST_FG': 'target_fg',
        'EST_ABV': 'target_abv',
        'EST_COLOR': 'color_srm',
        'IBU_METHOD': None,  # Not stored separately
        'EST_IBU': 'ibu',
        'STYLE_NAME': 'style',
        'STYLE_CATEGORY': None,
        'STYLE_GUIDE': None,
        'NOTES': 'notes',
        'TASTE_NOTES': 'taste_notes',
        'TASTE_RATING': 'taste_rating',
        'OG_MEASURED': 'og_measured',
        'FG_MEASURED': 'fg_measured',
        'FERMENTATION_STAGES': 'fermentation_stages',
        'PRIMARY_AGE': 'primary_age_days',
        'PRIMARY_TEMP': 'primary_temp',
        'SECONDARY_AGE': 'secondary_age_days',
        'SECONDARY_TEMP': 'secondary_temp',
        'TERTIARY_AGE': 'tertiary_age_days',
        'TERTIARY_TEMP': 'tertiary_temp',
        'AGE': 'age_days',
        'AGE_TEMP': 'age_temp',
        'CARBONATION': 'carbonation',
        'CARBONATION_USED': 'carbonation_used',
        'PRIMING_SUGAR_NAME': 'priming_sugar_name',
        'PRIMING_SUGAR_EQUIV': 'priming_sugar_equiv',
        'KEG_PRIMING_FACTOR': 'keg_priming_factor',
        'FORCED_CARBONATION': 'forced_carbonation',
        'CARBONATION_TEMP': 'carbonation_temp',
    }
    
    FERMENTABLE_FIELD_MAP = {
        'NAME': 'malt_name',
        'VERSION': 'version',
        'TYPE': 'malt_type',
        'AMOUNT': 'amount_kg',
        'YIELD': 'yield_percent',
        'COLOR': 'lovibond',
        'ADD_AFTER_BOIL': None,
        'ORIGIN': 'origin',
        'SUPPLIER': 'supplier',
        'NOTES': 'notes',
        'COARSE_FINE_DIFF': 'coarse_fine_diff',
        'MOISTURE': 'moisture',
        'DIASTATIC_POWER': 'diastatic_power',
        'PROTEIN': 'protein',
        'MAX_IN_BATCH': 'max_in_batch',
        'RECOMMEND_MASH': 'recommend_mash',
        'IBU_GAL_PER_LB': 'ibu_gal_per_lb',
        'DISPLAY_AMOUNT': 'display_amount',
        'POTENTIAL': 'potential',
        'INVENTORY': 'inventory',
    }
    
    HOP_FIELD_MAP = {
        'NAME': 'hop_name',
        'VERSION': 'version',
        'ALPHA': 'alpha_acid',
        'AMOUNT': 'amount_grams',
        'USE': 'use_type',
        'TIME': 'time_minutes',
        'NOTES': 'notes',
        'TYPE': 'hop_type',
        'FORM': 'hop_form',
        'BETA': 'beta_acid',
        'HSI': 'hsi',
        'ORIGIN': 'origin',
        'SUBSTITUTES': 'substitutes',
        'HUMULENE': 'humulene',
        'CARYOPHYLLENE': 'caryophyllene',
        'COHUMULONE': 'cohumulone',
        'MYRCENE': 'myrcene',
        'DISPLAY_AMOUNT': 'display_amount',
        'INVENTORY': 'inventory',
        'DISPLAY_TIME': 'display_time',
    }
    
    YEAST_FIELD_MAP = {
        'NAME': 'yeast_name',
        'VERSION': 'version',
        'TYPE': 'yeast_type',
        'FORM': 'yeast_form',
        'AMOUNT': 'amount',
        'AMOUNT_IS_WEIGHT': None,
        'LABORATORY': 'laboratory',
        'PRODUCT_ID': 'product_code',
        'MIN_TEMPERATURE': 'min_temperature',
        'MAX_TEMPERATURE': 'max_temperature',
        'FLOCCULATION': 'flocculation',
        'ATTENUATION': 'attenuation',
        'NOTES': 'notes',
        'BEST_FOR': 'best_for',
        'TIMES_CULTURED': 'times_cultured',
        'MAX_REUSE': 'max_reuse',
        'ADD_TO_SECONDARY': 'add_to_secondary',
        'DISPLAY_AMOUNT': 'display_amount',
        'DISP_MIN_TEMP': 'disp_min_temp',
        'DISP_MAX_TEMP': 'disp_max_temp',
        'INVENTORY': 'inventory',
        'CULTURE_DATE': 'culture_date',
    }
    
    def _get_element_text(self, parent: ET.Element, tag: str, default: Any = None) -> Any:
        """Safely get text from XML element"""
        elem = parent.find(tag)
        if elem is not None and elem.text:
            return elem.text.strip()
        return default
    
    def _convert_to_celsius(self, fahrenheit: float) -> float:
        """Convert Fahrenheit to Celsius"""
        return round((fahrenheit - 32) * 5/9, 1)
    
    def _convert_gallons_to_liters(self, gallons: float) -> float:
        """Convert US gallons to liters"""
        return round(gallons * 3.78541, 2)
    
    def _convert_pounds_to_kg(self, pounds: float) -> float:
        """Convert pounds to kilograms"""
        return round(pounds * 0.453592, 3)
    
    def _convert_ounces_to_grams(self, ounces: float) -> float:
        """Convert ounces to grams"""
        return round(ounces * 28.3495, 2)
    
    def _parse_recipe_element(self, recipe_elem: ET.Element) -> Dict:
        """Parse a RECIPE element from BeerXML"""
        recipe_data = {}
        
        # Parse basic recipe fields
        for xml_field, db_field in self.RECIPE_FIELD_MAP.items():
            if db_field is None:
                continue
            
            value = self._get_element_text(recipe_elem, xml_field)
            if value is not None:
                # Handle temperature conversions (BeerXML uses Celsius by default, but check)
                if 'temp' in db_field.lower() and db_field != 'carbonation_temp':
                    try:
                        recipe_data[db_field] = float(value)
                    except (ValueError, TypeError):
                        pass
                
                # Handle volume conversions (BeerXML typically uses liters)
                elif db_field in ['batch_size_liters', 'boil_size_liters']:
                    try:
                        recipe_data[db_field] = float(value)
                    except (ValueError, TypeError):
                        pass
                
                # Handle boolean fields
                elif db_field == 'forced_carbonation':
                    recipe_data[db_field] = value.upper() in ['TRUE', '1', 'YES']
                
                # Handle numeric fields
                elif db_field in ['target_og', 'target_fg', 'og_measured', 'fg_measured']:
                    try:
                        recipe_data[db_field] = float(value)
                    except (ValueError, TypeError):
                        pass
                
                else:
                    recipe_data[db_field] = value
        
        # Parse STYLE element if present
        style_elem = recipe_elem.find('STYLE')
        if style_elem is not None:
            style_name = self._get_element_text(style_elem, 'NAME')
            if style_name:
                recipe_data['style'] = style_name
            
            # Get color from style if not in recipe
            if 'color_srm' not in recipe_data:
                color = self._get_element_text(style_elem, 'COLOR_MIN')
                if color:
                    try:
                        recipe_data['color_srm'] = float(color)
                        recipe_data['color_ebc'] = round(float(color) * 2.65, 1)
                    except (ValueError, TypeError):
                        pass
        
        return recipe_data
    
    def _parse_fermentables(self, recipe_elem: ET.Element) -> List[Dict]:
        """Parse FERMENTABLES from BeerXML"""
        fermentables = []
        fermentables_elem = recipe_elem.find('FERMENTABLES')
        
        if fermentables_elem is not None:
            for ferm_elem in fermentables_elem.findall('FERMENTABLE'):
                ferm_data = {}
                
                for xml_field, db_field in self.FERMENTABLE_FIELD_MAP.items():
                    if db_field is None:
                        continue
                    
                    value = self._get_element_text(ferm_elem, xml_field)
                    if value is not None:
                        # Handle amount conversion (BeerXML uses kg)
                        if db_field == 'amount_kg':
                            try:
                                ferm_data[db_field] = float(value)
                            except (ValueError, TypeError):
                                pass
                        
                        # Handle color (convert to Lovibond if needed)
                        elif db_field == 'lovibond':
                            try:
                                color_value = float(value)
                                ferm_data[db_field] = color_value
                                ferm_data['color_ebc'] = round(color_value * 2.65, 2)
                            except (ValueError, TypeError):
                                pass
                        
                        # Handle boolean
                        elif db_field == 'recommend_mash':
                            ferm_data[db_field] = value.upper() in ['TRUE', '1', 'YES']
                        
                        # Numeric fields
                        elif db_field in ['yield_percent', 'coarse_fine_diff', 'moisture', 
                                         'diastatic_power', 'protein', 'max_in_batch', 
                                         'ibu_gal_per_lb', 'potential']:
                            try:
                                ferm_data[db_field] = float(value)
                            except (ValueError, TypeError):
                                pass
                        
                        else:
                            ferm_data[db_field] = value
                
                if ferm_data:
                    fermentables.append(ferm_data)
        
        return fermentables
    
    def _parse_hops(self, recipe_elem: ET.Element) -> List[Dict]:
        """Parse HOPS from BeerXML"""
        hops = []
        hops_elem = recipe_elem.find('HOPS')
        
        if hops_elem is not None:
            for hop_elem in hops_elem.findall('HOP'):
                hop_data = {}
                
                for xml_field, db_field in self.HOP_FIELD_MAP.items():
                    if db_field is None:
                        continue
                    
                    value = self._get_element_text(hop_elem, xml_field)
                    if value is not None:
                        # Handle amount conversion (BeerXML uses kg, we want grams)
                        if db_field == 'amount_grams':
                            try:
                                hop_data[db_field] = float(value) * 1000  # kg to grams
                            except (ValueError, TypeError):
                                pass
                        
                        # Numeric fields
                        elif db_field in ['alpha_acid', 'beta_acid', 'time_minutes', 'hsi',
                                         'humulene', 'caryophyllene', 'cohumulone', 'myrcene']:
                            try:
                                hop_data[db_field] = float(value)
                            except (ValueError, TypeError):
                                pass
                        
                        else:
                            hop_data[db_field] = value
                
                if hop_data:
                    hops.append(hop_data)
        
        return hops
    
    def _parse_yeasts(self, recipe_elem: ET.Element) -> List[Dict]:
        """Parse YEASTS from BeerXML"""
        yeasts = []
        yeasts_elem = recipe_elem.find('YEASTS')
        
        if yeasts_elem is not None:
            for yeast_elem in yeasts_elem.findall('YEAST'):
                yeast_data = {}
                
                for xml_field, db_field in self.YEAST_FIELD_MAP.items():
                    if db_field is None:
                        continue
                    
                    value = self._get_element_text(yeast_elem, xml_field)
                    if value is not None:
                        # Handle boolean
                        if db_field == 'add_to_secondary':
                            yeast_data[db_field] = value.upper() in ['TRUE', '1', 'YES']
                        
                        # Handle date
                        elif db_field == 'culture_date':
                            try:
                                yeast_data[db_field] = datetime.strptime(value, '%Y-%m-%d').date()
                            except (ValueError, TypeError):
                                pass
                        
                        # Numeric fields
                        elif db_field in ['min_temperature', 'max_temperature', 'attenuation',
                                         'alcohol_tolerance', 'times_cultured', 'max_reuse']:
                            try:
                                yeast_data[db_field] = float(value)
                            except (ValueError, TypeError):
                                pass
                        
                        else:
                            yeast_data[db_field] = value
                
                if yeast_data:
                    yeasts.append(yeast_data)
        
        return yeasts
    
    def _parse_miscs(self, recipe_elem: ET.Element) -> List[Dict]:
        """Parse MISCS (adjuncts) from BeerXML"""
        adjuncts = []
        miscs_elem = recipe_elem.find('MISCS')
        
        if miscs_elem is not None:
            for misc_elem in miscs_elem.findall('MISC'):
                adjunct_data = {
                    'ingredient_name': self._get_element_text(misc_elem, 'NAME', ''),
                    'ingredient_type': self._get_element_text(misc_elem, 'TYPE', ''),
                    'time_added': self._get_element_text(misc_elem, 'USE', ''),
                    'amount': self._get_element_text(misc_elem, 'AMOUNT', ''),
                    'notes': self._get_element_text(misc_elem, 'NOTES', ''),
                }
                
                if adjunct_data['ingredient_name']:
                    adjuncts.append(adjunct_data)
        
        return adjuncts
    
    def import_from_xml(self, xml_content: str, user_id: Optional[int] = None) -> Dict:
        """
        Import recipe from BeerXML format
        
        Args:
            xml_content: BeerXML content as string
            user_id: ID of user creating the recipe
            
        Returns:
            Dict with recipe_id and success status
        """
        try:
            root = ET.fromstring(xml_content)
            
            # Find RECIPE elements (can be multiple recipes in one file)
            recipes_imported = []
            
            for recipe_elem in root.findall('.//RECIPE'):
                # Parse recipe data
                recipe_data = self._parse_recipe_element(recipe_elem)
                
                if user_id:
                    recipe_data['created_by'] = user_id
                
                # Insert recipe
                with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Build INSERT query dynamically
                    fields = list(recipe_data.keys())
                    placeholders = [f'%({field})s' for field in fields]
                    
                    query = f"""
                        INSERT INTO recipe ({', '.join(fields)})
                        VALUES ({', '.join(placeholders)})
                        RETURNING id
                    """
                    
                    cur.execute(query, recipe_data)
                    recipe_id = cur.fetchone()['id']
                    
                    # Parse and insert fermentables
                    fermentables = self._parse_fermentables(recipe_elem)
                    for i, ferm in enumerate(fermentables):
                        ferm['recipe_id'] = recipe_id
                        ferm['sort_order'] = i
                        
                        ferm_fields = list(ferm.keys())
                        ferm_placeholders = [f'%({field})s' for field in ferm_fields]
                        
                        query = f"""
                            INSERT INTO recipe_malts ({', '.join(ferm_fields)})
                            VALUES ({', '.join(ferm_placeholders)})
                        """
                        cur.execute(query, ferm)
                    
                    # Parse and insert hops
                    hops = self._parse_hops(recipe_elem)
                    for i, hop in enumerate(hops):
                        hop['recipe_id'] = recipe_id
                        hop['sort_order'] = i
                        
                        hop_fields = list(hop.keys())
                        hop_placeholders = [f'%({field})s' for field in hop_fields]
                        
                        query = f"""
                            INSERT INTO recipe_hops ({', '.join(hop_fields)})
                            VALUES ({', '.join(hop_placeholders)})
                        """
                        cur.execute(query, hop)
                    
                    # Parse and insert yeasts
                    yeasts = self._parse_yeasts(recipe_elem)
                    for i, yeast in enumerate(yeasts):
                        yeast['recipe_id'] = recipe_id
                        yeast['sort_order'] = i
                        
                        yeast_fields = list(yeast.keys())
                        yeast_placeholders = [f'%({field})s' for field in yeast_fields]
                        
                        query = f"""
                            INSERT INTO recipe_yeast ({', '.join(yeast_fields)})
                            VALUES ({', '.join(yeast_placeholders)})
                        """
                        cur.execute(query, yeast)
                    
                    # Parse and insert adjuncts/miscs
                    adjuncts = self._parse_miscs(recipe_elem)
                    for i, adjunct in enumerate(adjuncts):
                        adjunct['recipe_id'] = recipe_id
                        adjunct['sort_order'] = i
                        
                        adjunct_fields = list(adjunct.keys())
                        adjunct_placeholders = [f'%({field})s' for field in adjunct_fields]
                        
                        query = f"""
                            INSERT INTO recipe_adjuncts ({', '.join(adjunct_fields)})
                            VALUES ({', '.join(adjunct_placeholders)})
                        """
                        cur.execute(query, adjunct)
                    
                    self.conn.commit()
                    recipes_imported.append({
                        'id': recipe_id,
                        'name': recipe_data.get('name', 'Unknown')
                    })
            
            return {
                'success': True,
                'recipes': recipes_imported,
                'count': len(recipes_imported)
            }
            
        except ET.ParseError as e:
            return {
                'success': False,
                'error': f'XML parsing error: {str(e)}'
            }
        except Exception as e:
            self.conn.rollback()
            return {
                'success': False,
                'error': f'Import error: {str(e)}'
            }
    
    def export_to_xml(self, recipe_id: int) -> Optional[str]:
        """
        Export recipe to BeerXML 1.0 format
        
        Args:
            recipe_id: ID of recipe to export
            
        Returns:
            BeerXML string or None if recipe not found
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Fetch recipe
                cur.execute("SELECT * FROM recipe WHERE id = %s", (recipe_id,))
                recipe = cur.fetchone()
                
                if not recipe:
                    return None
                
                # Create root element
                root = ET.Element('RECIPES')
                recipe_elem = ET.SubElement(root, 'RECIPE')
                
                # Reverse field mapping (snake_case to PascalCase)
                reverse_recipe_map = {v: k for k, v in self.RECIPE_FIELD_MAP.items() if v is not None}
                
                # Add recipe fields
                for db_field, xml_field in reverse_recipe_map.items():
                    value = recipe.get(db_field)
                    if value is not None:
                        elem = ET.SubElement(recipe_elem, xml_field)
                        elem.text = str(value)
                
                # Add TYPE field (always All Grain)
                type_elem = ET.SubElement(recipe_elem, 'TYPE')
                type_elem.text = 'All Grain'
                
                # Fetch and add fermentables
                cur.execute("""
                    SELECT * FROM recipe_malts 
                    WHERE recipe_id = %s 
                    ORDER BY sort_order
                """, (recipe_id,))
                malts = cur.fetchall()
                
                if malts:
                    fermentables_elem = ET.SubElement(recipe_elem, 'FERMENTABLES')
                    reverse_ferm_map = {v: k for k, v in self.FERMENTABLE_FIELD_MAP.items() if v is not None}
                    
                    for malt in malts:
                        ferm_elem = ET.SubElement(fermentables_elem, 'FERMENTABLE')
                        
                        for db_field, xml_field in reverse_ferm_map.items():
                            value = malt.get(db_field)
                            if value is not None:
                                elem = ET.SubElement(ferm_elem, xml_field)
                                # Special handling for amount (keep in kg)
                                if db_field == 'amount_kg':
                                    elem.text = str(float(value))
                                else:
                                    elem.text = str(value)
                        
                        # Add ADD_AFTER_BOIL (default to FALSE)
                        add_after_elem = ET.SubElement(ferm_elem, 'ADD_AFTER_BOIL')
                        add_after_elem.text = 'FALSE'
                
                # Fetch and add hops
                cur.execute("""
                    SELECT * FROM recipe_hops 
                    WHERE recipe_id = %s 
                    ORDER BY sort_order
                """, (recipe_id,))
                hops = cur.fetchall()
                
                if hops:
                    hops_elem = ET.SubElement(recipe_elem, 'HOPS')
                    reverse_hop_map = {v: k for k, v in self.HOP_FIELD_MAP.items() if v is not None}
                    
                    for hop in hops:
                        hop_elem = ET.SubElement(hops_elem, 'HOP')
                        
                        for db_field, xml_field in reverse_hop_map.items():
                            value = hop.get(db_field)
                            if value is not None:
                                elem = ET.SubElement(hop_elem, xml_field)
                                # Convert grams to kg for BeerXML
                                if db_field == 'amount_grams':
                                    elem.text = str(float(value) / 1000)
                                else:
                                    elem.text = str(value)
                
                # Fetch and add yeasts
                cur.execute("""
                    SELECT * FROM recipe_yeast 
                    WHERE recipe_id = %s 
                    ORDER BY sort_order
                """, (recipe_id,))
                yeasts = cur.fetchall()
                
                if yeasts:
                    yeasts_elem = ET.SubElement(recipe_elem, 'YEASTS')
                    reverse_yeast_map = {v: k for k, v in self.YEAST_FIELD_MAP.items() if v is not None}
                    
                    for yeast in yeasts:
                        yeast_elem = ET.SubElement(yeasts_elem, 'YEAST')
                        
                        for db_field, xml_field in reverse_yeast_map.items():
                            value = yeast.get(db_field)
                            if value is not None:
                                elem = ET.SubElement(yeast_elem, xml_field)
                                # Handle date formatting
                                if db_field == 'culture_date' and isinstance(value, date):
                                    elem.text = value.strftime('%Y-%m-%d')
                                # Handle boolean
                                elif db_field == 'add_to_secondary':
                                    elem.text = 'TRUE' if value else 'FALSE'
                                else:
                                    elem.text = str(value)
                        
                        # Add AMOUNT_IS_WEIGHT (default to FALSE for liquid yeast)
                        amount_is_weight_elem = ET.SubElement(yeast_elem, 'AMOUNT_IS_WEIGHT')
                        amount_is_weight_elem.text = 'FALSE'
                
                # Fetch and add adjuncts (MISCS)
                cur.execute("""
                    SELECT * FROM recipe_adjuncts 
                    WHERE recipe_id = %s 
                    ORDER BY sort_order
                """, (recipe_id,))
                adjuncts = cur.fetchall()
                
                if adjuncts:
                    miscs_elem = ET.SubElement(recipe_elem, 'MISCS')
                    
                    for adjunct in adjuncts:
                        misc_elem = ET.SubElement(miscs_elem, 'MISC')
                        
                        name_elem = ET.SubElement(misc_elem, 'NAME')
                        name_elem.text = adjunct.get('ingredient_name', '')
                        
                        type_elem = ET.SubElement(misc_elem, 'TYPE')
                        type_elem.text = adjunct.get('ingredient_type', 'Other')
                        
                        use_elem = ET.SubElement(misc_elem, 'USE')
                        use_elem.text = adjunct.get('time_added', 'Boil')
                        
                        if adjunct.get('amount'):
                            amount_elem = ET.SubElement(misc_elem, 'AMOUNT')
                            amount_elem.text = adjunct['amount']
                        
                        if adjunct.get('notes'):
                            notes_elem = ET.SubElement(misc_elem, 'NOTES')
                            notes_elem.text = adjunct['notes']
                        
                        version_elem = ET.SubElement(misc_elem, 'VERSION')
                        version_elem.text = '1'
                
                # Generate XML string with proper formatting
                ET.indent(root, space='  ')
                xml_str = ET.tostring(root, encoding='unicode', xml_declaration=True)
                
                return xml_str
                
        except Exception as e:
            print(f"Export error: {str(e)}")
            return None
    
    def export_multiple_recipes(self, recipe_ids: List[int]) -> Optional[str]:
        """
        Export multiple recipes to a single BeerXML file
        
        Args:
            recipe_ids: List of recipe IDs to export
            
        Returns:
            BeerXML string with multiple recipes or None on error
        """
        try:
            root = ET.Element('RECIPES')
            
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                for recipe_id in recipe_ids:
                    # Get individual recipe XML
                    single_xml = self.export_to_xml(recipe_id)
                    if single_xml:
                        # Parse the single recipe XML and append RECIPE element
                        single_root = ET.fromstring(single_xml)
                        recipe_elem = single_root.find('RECIPE')
                        if recipe_elem is not None:
                            root.append(recipe_elem)
            
            if len(root) > 0:
                ET.indent(root, space='  ')
                xml_str = ET.tostring(root, encoding='unicode', xml_declaration=True)
                return xml_str
            
            return None
            
        except Exception as e:
            print(f"Export multiple error: {str(e)}")
            return None
