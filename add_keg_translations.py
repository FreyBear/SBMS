import re

# Read the current translation file
with open('translations/no/LC_MESSAGES/messages.po', 'r', encoding='utf-8') as f:
    content = f.read()

# Dictionary of new translations for keg functionality
translations = {
    'Update Date': 'Oppdateringsdato',
    'Date when this update occurred': 'Dato når denne oppdateringen skjedde',
    'Amount Left': 'Mengde Igjen',
    'Liters': 'Liter',
    'Select location...': 'Velg plassering...',
    'Brewery': 'Bryggeri',
    'Cellar': 'Kjeller',
    'Storage': 'Lager',
    'Bar': 'Bar',
    'Cleaning': 'Rengjøring',
    'Arrangement': 'Arrangement',
    'Normal operation': 'Normal drift',
    'Maintenance': 'Vedlikehold',
    'Any additional notes about this update...': 'Eventuelle tilleggsnotater om denne oppdateringen...',
    'Update Keg': 'Oppdater Fat',
    'Cancel': 'Avbryt',
    'Full': 'Fullt',
    'Started': 'Startet',
    'Available/Cleaned': 'Tilgjengelig/Rengjort',
    'Empty': 'Tomt',
    'Date': 'Dato',
    'Event/Occasion': 'Hendelse/Anledning',
    'Edit': 'Rediger',
    'Edit History Entry': 'Rediger Historikkoppføring',
    'Keg': 'Fat',
    'Update Entry': 'Oppdater Oppføring',
    'Delete Entry': 'Slett Oppføring',
    'Filling': 'Fylling',
    'Event': 'Hendelse',
    'Any additional notes about this entry...': 'Eventuelle tilleggsnotater om denne oppføringen...',
}

# Replace empty translations and remove fuzzy markers
for english, norwegian in translations.items():
    # Fix empty translations
    pattern = rf'(msgid "{re.escape(english)}"\nmsgstr ")"'
    replacement = f'msgid "{english}"\nmsgstr "{norwegian}"'
    content = re.sub(pattern, replacement, content)
    
    # Fix fuzzy translations
    pattern = rf'(#, fuzzy\nmsgid "{re.escape(english)}"\nmsgstr ")[^"]*"'
    replacement = f'msgid "{english}"\nmsgstr "{norwegian}"'
    content = re.sub(pattern, replacement, content)

# Write back the file
with open('translations/no/LC_MESSAGES/messages.po', 'w', encoding='utf-8') as f:
    f.write(content)

print("Keg functionality translations added!")
