import re

# Read the current translation file
with open('translations/no/LC_MESSAGES/messages.po', 'r', encoding='utf-8') as f:
    content = f.read()

# Dictionary of new translations for filter functionality
translations = {
    'Filter by Status': 'Filtrer etter Status',
    'Toggle All': 'Veksle Alle',
    'Show Only Available + Empty': 'Vis Bare Tilgjengelige + Tomme',
}

# Replace empty translations
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

print("Filter translations added!")
