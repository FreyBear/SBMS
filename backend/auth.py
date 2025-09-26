"""
SBMS User Authentication and Authorization
"""
import json
from functools import wraps
from flask import session, redirect, url_for, flash, request
from flask_login import UserMixin, current_user

class User(UserMixin):
    def __init__(self, id, username, email, full_name, role_name, permissions, is_active=True, language='en'):
        self.id = id
        self.username = username
        self.email = email
        self.full_name = full_name
        self.role_name = role_name
        self.permissions = json.loads(permissions) if isinstance(permissions, str) else permissions
        self._is_active = is_active
        self.language = language
    
    @property
    def is_active(self):
        """Flask-Login property for user active status"""
        return self._is_active
    
    def can_access(self, resource, action="view"):
        """Check if user can perform action on resource"""
        if not self._is_active:
            return False
        
        if self.role_name == 'admin':
            return True
            
        resource_perm = self.permissions.get(resource, "none")
        
        if resource_perm == "full":
            return True
        elif resource_perm == "edit" and action in ["view", "edit", "update"]:
            return True
        elif resource_perm == "view" and action == "view":
            return True
        
        return False
    
    def get_id(self):
        return str(self.id)

def require_auth(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def require_permission(resource, action="view"):
    """Decorator to require specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'error')
                return redirect(url_for('login', next=request.url))
            
            if not current_user.can_access(resource, action):
                flash(f'You do not have permission to {action} {resource}.', 'error')
                return redirect(url_for('index'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator