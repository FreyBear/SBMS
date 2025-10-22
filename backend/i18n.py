"""
Internationalization (i18n) configuration for SBMS
"""

from flask_babel import Babel, get_locale, ngettext, gettext, lazy_gettext
from flask import request, session, current_app

class Config:
    """i18n configuration"""
    LANGUAGES = {
        'en': 'English',
        'no': 'Norsk (Bokmål)',
        'nn': 'Norsk (Nynorsk)'
    }
    BABEL_DEFAULT_LOCALE = 'en'
    BABEL_DEFAULT_TIMEZONE = 'Europe/Oslo'

def init_babel(app):
    """Initialize Babel with Flask app"""
    babel = Babel(app)
    
    # Configure Babel
    app.config['LANGUAGES'] = Config.LANGUAGES
    app.config['BABEL_DEFAULT_LOCALE'] = Config.BABEL_DEFAULT_LOCALE
    app.config['BABEL_DEFAULT_TIMEZONE'] = Config.BABEL_DEFAULT_TIMEZONE
    
    def get_locale():
        """Select locale for the request"""
        # Use user's language preference from database (if logged in)
        from flask_login import current_user
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            if hasattr(current_user, 'language') and current_user.language and current_user.language in current_app.config['LANGUAGES']:
                return current_user.language
        
        # Default fallback
        return current_app.config['BABEL_DEFAULT_LOCALE']
    
    babel.init_app(app, locale_selector=get_locale)
    return babel

# Translation helper functions
_ = gettext
_l = lazy_gettext