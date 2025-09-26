import re

# Read the current translation file
with open('translations/no/LC_MESSAGES/messages.po', 'r', encoding='utf-8') as f:
    content = f.read()

# Dictionary of translations
translations = {
    'Date Brewed': 'Bryggingsdato',
    'Style': 'Stil',
    'Brewery Dashboard': 'Bryggeri Dashboard', 
    'Keg Status Summary': 'Fat Status Sammendrag',
    'kegs': 'fat',
    'View All Kegs': 'Se Alle Fat',
    'Recipe Management': 'Oppskrift Administrasjon',
    'Recipe Name': 'Oppskrift Navn',
    'Created': 'Opprettet',
    'User Management': 'Bruker Administrasjon',
    'Create User': 'Opprett Bruker',
    'Username': 'Brukernavn',
    'Full Name': 'Fullt Navn',
    'Email': 'E-post',
    'Role': 'Rolle',
    'Language': 'Språk',
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

print("Translations updated!")
