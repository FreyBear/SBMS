import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_babel import gettext, ngettext
from dotenv import load_dotenv
from datetime import datetime
import bcrypt
from auth import User, require_auth, require_permission
from forms import LoginForm, ChangePasswordForm, CreateUserForm, EditUserForm
from i18n import init_babel, _, _l

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder='frontend/templates', static_folder='frontend/static')
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['WTF_CSRF_ENABLED'] = True
app.config['SERVER_NAME'] = None  # Allow any hostname

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = _l('Please log in to access this page.')
login_manager.login_message_category = 'info'

# Initialize Babel for i18n
babel = init_babel(app)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'database': os.getenv('POSTGRES_DB', 'sbms'),
    'user': os.getenv('POSTGRES_USER', 'postgres'),
    'password': os.getenv('POSTGRES_PASSWORD', ''),
    'port': os.getenv('POSTGRES_PORT', '5432')
}

def get_db_connection():
    """Get database connection with error handling"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        return None

@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT u.id, u.username, u.email, u.full_name, u.is_active, u.language,
                       r.name as role_name, r.permissions
                FROM users u
                JOIN user_role r ON u.role_id = r.id
                WHERE u.id = %s AND u.is_active = true
            """, (user_id,))
            user_data = cur.fetchone()
            
            if user_data:
                return User(
                    user_data['id'],
                    user_data['username'], 
                    user_data['email'],
                    user_data['full_name'],
                    user_data['role_name'],
                    user_data['permissions'],
                    user_data['is_active'],
                    user_data['language'] or 'en'
                )
    except psycopg2.Error as e:
        print(f"Error loading user: {e}")
    finally:
        conn.close()
    
    return None

# Template context processor for Babel
@app.context_processor
def inject_conf_vars():
    """Make Babel functions available in templates"""
    from flask_babel import get_locale, gettext as babel_gettext
    return dict(
        LANGUAGES=app.config['LANGUAGES'],
        get_locale=get_locale,
        _=babel_gettext
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return render_template('login.html', form=form)
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT u.id, u.username, u.email, u.password_hash, u.full_name, u.is_active,
                           r.name as role_name, r.permissions
                    FROM users u
                    JOIN user_role r ON u.role_id = r.id
                    WHERE u.username = %s AND u.is_active = true
                """, (form.username.data,))
                user_data = cur.fetchone()
                
                if user_data and bcrypt.checkpw(form.password.data.encode('utf-8'), user_data['password_hash'].encode('utf-8')):
                    user = User(
                        user_data['id'],
                        user_data['username'],
                        user_data['email'],
                        user_data['full_name'],
                        user_data['role_name'],
                        user_data['permissions'],
                        user_data['is_active']
                    )
                    login_user(user, remember=form.remember_me.data)
                    
                    # Update last login
                    cur.execute("UPDATE users SET last_login = %s WHERE id = %s", 
                              (datetime.now(), user_data['id']))
                    conn.commit()
                    
                    next_page = request.args.get('next')
                    flash(_('Welcome back, %(name)s!', name=user.full_name), 'success')
                    return redirect(next_page) if next_page else redirect(url_for('index'))
                else:
                    flash(_('Invalid username or password'), 'error')
        except psycopg2.Error as e:
            flash(_('Database error: %(error)s', error=str(e)), 'error')
        finally:
            conn.close()
    
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """User logout"""
    logout_user()
    flash(_('You have been logged out successfully.'), 'info')
    return redirect(url_for('login'))

@app.route('/debug_locale')
@login_required
def debug_locale():
    """Debug route to check locale detection"""
    from flask_babel import get_locale
    
    # Simple HTML debug page
    debug_info = {
        'current_locale': str(get_locale()),
        'session_language': session.get('language', 'Not set'),
        'user_language': getattr(current_user, 'language', 'Not set'),
        'config_languages': app.config.get('LANGUAGES', {}),
        'change_password_translated': _('Change Password'),
        'logout_translated': _('Logout')
    }
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Debug Locale</title></head>
    <body>
        <h1>Locale Debug Information</h1>
        <ul>
            <li><strong>Current Locale:</strong> {debug_info['current_locale']}</li>
            <li><strong>Session Language:</strong> {debug_info['session_language']}</li>
            <li><strong>User Language:</strong> {debug_info['user_language']}</li>
            <li><strong>Config Languages:</strong> {debug_info['config_languages']}</li>
            <li><strong>Change Password Translated:</strong> "{debug_info['change_password_translated']}"</li>
            <li><strong>Logout Translated:</strong> "{debug_info['logout_translated']}"</li>
        </ul>
        <p><a href="/">Back to Dashboard</a></p>
    </body>
    </html>
    """
    return html

@app.route('/')
@require_auth
def index():
    """Main dashboard"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get keg summary statistics
            cur.execute("""
                SELECT 
                    status,
                    COUNT(*) as count,
                    SUM(amount_left_liters) as total_liters
                FROM keg 
                GROUP BY status
                ORDER BY status
            """)
            keg_stats = cur.fetchall()
            
            # Get recent kegs
            cur.execute("""
                SELECT id, keg_number, contents, status, amount_left_liters, location, last_measured
                FROM keg 
                ORDER BY last_measured DESC, id DESC 
                LIMIT 10
            """)
            recent_kegs = cur.fetchall()
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        keg_stats = []
        recent_kegs = []
    finally:
        conn.close()
    
    return render_template('index.html', keg_stats=keg_stats, recent_kegs=recent_kegs)

@app.route('/kegs')
@require_permission('kegs', 'view')
def kegs():
    """View all kegs"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT k.*, b.name as brew_name, r.name as recipe_name
                FROM keg k
                LEFT JOIN brew b ON k.brew_id = b.id
                LEFT JOIN recipe r ON b.recipe_id = r.id
                ORDER BY k.keg_number
            """)
            kegs = cur.fetchall()
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        kegs = []
    finally:
        conn.close()
    
    return render_template('kegs.html', kegs=kegs)

@app.route('/keg/<int:keg_id>')
@require_permission('kegs', 'view')
def keg_detail(keg_id):
    """View individual keg details"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    keg_history = []  # Initialize to avoid undefined variable
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT k.*, b.name as brew_name, b.date_brewed, r.name as recipe_name, r.style
                FROM keg k
                LEFT JOIN brew b ON k.brew_id = b.id
                LEFT JOIN recipe r ON b.recipe_id = r.id
                WHERE k.id = %s
            """, (keg_id,))
            keg = cur.fetchone()
            
            if keg:  # Only get history if keg exists
                # Get keg history if available
                cur.execute("""
                    SELECT * FROM keg_history 
                    WHERE keg_id = %s 
                    ORDER BY recorded_date DESC, created_timestamp DESC
                """, (keg_id,))
                keg_history = cur.fetchall()
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        keg = None
        keg_history = []
    finally:
        conn.close()
    
    if not keg:
        flash('Keg not found', 'error')
        return redirect(url_for('kegs'))
    
    return render_template('keg_detail.html', keg=keg, keg_history=keg_history)

@app.route('/keg/<int:keg_id>/update', methods=['GET', 'POST'])
@require_permission('kegs', 'edit')
def update_keg(keg_id):
    """Update keg information and create history entry"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('kegs'))
    
    if request.method == 'GET':
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM keg WHERE id = %s", (keg_id,))
                keg = cur.fetchone()
        except psycopg2.Error as e:
            flash(f'Database error: {e}', 'error')
            keg = None
        finally:
            conn.close()
        
        if not keg:
            flash('Keg not found', 'error')
            return redirect(url_for('kegs'))
        
        # Pass today's date to template
        today = datetime.now().strftime('%Y-%m-%d')
        return render_template('update_keg.html', keg=keg, today=today)
    
    # POST request - update keg and create history entry
    try:
        with conn.cursor() as cur:
            # Parse the update date
            update_date = datetime.strptime(request.form['update_date'], '%Y-%m-%d').date()
            
            # Update the main keg record
            cur.execute("""
                UPDATE keg SET
                    contents = %s,
                    status = %s,
                    amount_left_liters = %s,
                    location = %s,
                    notes = %s,
                    last_measured = %s
                WHERE id = %s
            """, (
                request.form['contents'],
                request.form['status'],
                float(request.form['amount_left_liters']) if request.form['amount_left_liters'] else 0,
                request.form['location'],
                request.form['notes'],
                update_date,
                keg_id
            ))
            
            # Create a history entry for this update
            cur.execute("""
                INSERT INTO keg_history 
                (keg_id, recorded_date, contents, status, amount_left_liters, location, arrangement, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                keg_id,
                update_date,
                request.form['contents'],
                request.form['status'],
                float(request.form['amount_left_liters']) if request.form['amount_left_liters'] else 0,
                request.form['location'],
                request.form.get('arrangement', 'Normal operation'),
                request.form['notes']
            ))
            
            conn.commit()
            flash(_('Keg updated successfully and history entry created'), 'success')
    except (psycopg2.Error, ValueError) as e:
        flash(f'Error updating keg: {e}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('keg_detail', keg_id=keg_id))

@app.route('/keg/<int:keg_id>/history/<int:history_id>/edit', methods=['GET', 'POST'])
@require_permission('kegs', 'edit')
def edit_keg_history(keg_id, history_id):
    """Edit keg history entry"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('keg_detail', keg_id=keg_id))
    
    if request.method == 'GET':
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get keg info
                cur.execute("SELECT * FROM keg WHERE id = %s", (keg_id,))
                keg = cur.fetchone()
                
                # Get history entry
                cur.execute("SELECT * FROM keg_history WHERE id = %s AND keg_id = %s", (history_id, keg_id))
                history_entry = cur.fetchone()
                
        except psycopg2.Error as e:
            flash(f'Database error: {e}', 'error')
            return redirect(url_for('keg_detail', keg_id=keg_id))
        finally:
            conn.close()
        
        if not keg or not history_entry:
            flash('Keg or history entry not found', 'error')
            return redirect(url_for('keg_detail', keg_id=keg_id))
        
        return render_template('edit_keg_history.html', keg=keg, history_entry=history_entry)
    
    # POST request - update or delete history entry
    if 'delete' in request.form:
        # Delete the history entry
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM keg_history WHERE id = %s AND keg_id = %s", (history_id, keg_id))
                conn.commit()
                flash(_('History entry deleted successfully'), 'success')
        except psycopg2.Error as e:
            flash(f'Error deleting history entry: {e}', 'error')
        finally:
            conn.close()
    else:
        # Update the history entry
        try:
            with conn.cursor() as cur:
                recorded_date = datetime.strptime(request.form['recorded_date'], '%Y-%m-%d').date()
                
                cur.execute("""
                    UPDATE keg_history SET
                        recorded_date = %s,
                        contents = %s,
                        status = %s,
                        amount_left_liters = %s,
                        location = %s,
                        arrangement = %s,
                        notes = %s
                    WHERE id = %s AND keg_id = %s
                """, (
                    recorded_date,
                    request.form['contents'],
                    request.form['status'],
                    float(request.form['amount_left_liters']) if request.form['amount_left_liters'] else 0,
                    request.form['location'],
                    request.form['arrangement'],
                    request.form['notes'],
                    history_id,
                    keg_id
                ))
                
                # Also update the keg's last_measured if this is the most recent entry
                cur.execute("""
                    SELECT MAX(recorded_date) as max_date FROM keg_history WHERE keg_id = %s
                """, (keg_id,))
                max_date_result = cur.fetchone()
                
                if max_date_result[0] == recorded_date:
                    # This is the most recent entry, update the keg record
                    cur.execute("""
                        UPDATE keg SET
                            contents = %s,
                            status = %s,
                            amount_left_liters = %s,
                            location = %s,
                            notes = %s,
                            last_measured = %s
                        WHERE id = %s
                    """, (
                        request.form['contents'],
                        request.form['status'],
                        float(request.form['amount_left_liters']) if request.form['amount_left_liters'] else 0,
                        request.form['location'],
                        request.form['notes'],
                        recorded_date,
                        keg_id
                    ))
                
                conn.commit()
                flash(_('History entry updated successfully'), 'success')
        except (psycopg2.Error, ValueError) as e:
            flash(f'Error updating history entry: {e}', 'error')
        finally:
            conn.close()
    
    return redirect(url_for('keg_detail', keg_id=keg_id))

@app.route('/brews')
@require_permission('brews', 'view')
def brews():
    """View all brews"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT b.*, r.name as recipe_name, r.style,
                       COUNT(k.id) as keg_count
                FROM brew b
                LEFT JOIN recipe r ON b.recipe_id = r.id
                LEFT JOIN keg k ON b.id = k.brew_id
                GROUP BY b.id, r.name, r.style
                ORDER BY b.date_brewed DESC
            """)
            brews = cur.fetchall()
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        brews = []
    finally:
        conn.close()
    
    return render_template('brews.html', brews=brews)

@app.route('/recipes')
@require_permission('recipes', 'view')
def recipes():
    """View all recipes"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT r.*, COUNT(b.id) as brew_count
                FROM recipe r
                LEFT JOIN brew b ON r.id = b.recipe_id
                GROUP BY r.id
                ORDER BY r.name
            """)
            recipes = cur.fetchall()
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        recipes = []
    finally:
        conn.close()
    
    return render_template('recipes.html', recipes=recipes)

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error="Page not found"), 404

@app.route('/users')
@require_permission('users', 'view')
def users():
    """View all users (admin only)"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT u.id, u.username, u.email, u.full_name, u.language, u.is_active, u.created_date, u.last_login,
                       r.name as role_name
                FROM users u
                JOIN user_role r ON u.role_id = r.id
                ORDER BY u.created_date DESC
            """)
            users_list = cur.fetchall()
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        users_list = []
    finally:
        conn.close()
    
    return render_template('users.html', users=users_list)

@app.route('/create_user', methods=['GET', 'POST'])
@require_permission('users', 'full')
def create_user():
    """Create new user (admin only)"""
    form = CreateUserForm()
    
    # Populate role choices
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id, name, description FROM user_role ORDER BY name")
                roles = cur.fetchall()
                form.role_id.choices = [(role['id'], f"{role['name']} - {role['description']}") for role in roles]
        except psycopg2.Error as e:
            flash(f'Error loading roles: {e}', 'error')
            return redirect(url_for('users'))
        finally:
            conn.close()
    
    if form.validate_on_submit():
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return render_template('create_user.html', form=form)
        
        try:
            with conn.cursor() as cur:
                # Check if username exists
                cur.execute("SELECT id FROM users WHERE username = %s", (form.username.data,))
                if cur.fetchone():
                    flash('Username already exists', 'error')
                    return render_template('create_user.html', form=form)
                
                # Hash password
                password_hash = bcrypt.hashpw(form.password.data.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                
                # Create user
                cur.execute("""
                    INSERT INTO users (username, email, password_hash, full_name, role_id, language, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    form.username.data,
                    form.email.data,
                    password_hash,
                    form.full_name.data,
                    form.role_id.data,
                    form.language.data,
                    form.is_active.data
                ))
                conn.commit()
                flash(f'User {form.username.data} created successfully!', 'success')
                return redirect(url_for('users'))
                
        except psycopg2.Error as e:
            flash(f'Error creating user: {e}', 'error')
        finally:
            conn.close()
    
    return render_template('create_user.html', form=form)

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change user password"""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return render_template('change_password.html', form=form)
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Verify current password
                cur.execute("SELECT password_hash FROM users WHERE id = %s", (current_user.id,))
                user_data = cur.fetchone()
                
                if user_data and bcrypt.checkpw(form.current_password.data.encode('utf-8'), 
                                                user_data['password_hash'].encode('utf-8')):
                    # Update password
                    new_password_hash = bcrypt.hashpw(form.new_password.data.encode('utf-8'), 
                                                     bcrypt.gensalt()).decode('utf-8')
                    cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", 
                              (new_password_hash, current_user.id))
                    conn.commit()
                    flash('Password changed successfully!', 'success')
                    return redirect(url_for('index'))
                else:
                    flash('Current password is incorrect', 'error')
                    
        except psycopg2.Error as e:
            flash(f'Error changing password: {e}', 'error')
        finally:
            conn.close()
    
    return render_template('change_password.html', form=form)

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@require_auth
def edit_user(user_id):
    """Edit user (admin only) or allow users to edit themselves"""
    # Allow users to edit themselves OR require admin permission for editing others
    if user_id != current_user.id and not current_user.can_access('users', 'full'):
        flash(_('You can only edit your own profile'), 'error')
        return redirect(url_for('users') if current_user.can_access('users', 'view') else url_for('index'))
    
    # Determine if this is self-editing
    is_self_edit = (user_id == current_user.id)
    
    form = EditUserForm()
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('users'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get user data
            cur.execute("""
                SELECT u.id, u.username, u.email, u.full_name, u.role_id, u.language, u.is_active
                FROM users u WHERE u.id = %s
            """, (user_id,))
            user_data = cur.fetchone()
            
            if not user_data:
                flash('User not found', 'error')
                return redirect(url_for('users'))
            
            # Get roles for dropdown
            cur.execute("SELECT id, name, description FROM user_role ORDER BY name")
            roles = cur.fetchall()
            form.role_id.choices = [(role['id'], f"{role['name']} - {role['description']}") for role in roles]
            
            if request.method == 'GET':
                # Populate form with current values
                form.username.data = user_data['username']
                form.email.data = user_data['email']
                form.full_name.data = user_data['full_name']
                form.role_id.data = user_data['role_id']
                form.language.data = user_data['language']
                form.is_active.data = user_data['is_active']
            
            if form.validate_on_submit():
                # For self-editing, restrict what can be changed
                if is_self_edit:
                    # Users can only update their own basic info and language
                    cur.execute("""
                        UPDATE users 
                        SET email = %s, full_name = %s, language = %s
                        WHERE id = %s
                    """, (
                        form.email.data,
                        form.full_name.data,
                        form.language.data,
                        user_id
                    ))
                else:
                    # Admin can update everything
                    cur.execute("""
                        UPDATE users 
                        SET username = %s, email = %s, full_name = %s, role_id = %s, language = %s, is_active = %s
                        WHERE id = %s
                    """, (
                        form.username.data,
                        form.email.data,
                        form.full_name.data,
                        form.role_id.data,
                        form.language.data,
                        form.is_active.data,
                        user_id
                    ))
                conn.commit()
                
                # If updating current user's language, force logout to refresh user object
                if user_id == current_user.id:
                    from flask_login import logout_user
                    logout_user()
                    flash(_('Profile updated successfully! Please log in again to see language change.'), 'success')
                    return redirect(url_for('login'))
                else:
                    flash(_('User {} updated successfully!').format(form.username.data), 'success')
                    
                return redirect(url_for('users') if current_user.can_access('users', 'view') else url_for('index'))
                
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
    finally:
        conn.close()
    
    return render_template('edit_user.html', form=form, user_data=user_data, is_self_edit=is_self_edit)

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error="Page not found"), 404

@app.errorhandler(500)
def server_error(error):
    return render_template('error.html', error="Internal server error"), 500

@app.route('/debug/translation')
@require_auth
def debug_translation():
    """Debug route to test translations"""
    import os
    from flask_babel import get_locale, gettext
    from i18n import _
    
    current_locale = str(get_locale())
    user_lang = current_user.language if hasattr(current_user, 'language') else 'None'
    
    # Check if translation files exist
    mo_file_path = f"translations/{current_locale}/LC_MESSAGES/messages.mo"
    mo_exists = os.path.exists(mo_file_path)
    
    # Test translations with both methods
    translations = {
        'Dashboard': _('Dashboard'),
        'Kegs': _('Kegs'), 
        'Brews': _('Brews'),
        'Recipes': _('Recipes'),
        'Users': _('Users'),
        'Change Password': _('Change Password'),
        'Logout': _('Logout')
    }
    
    # Also test with direct gettext
    direct_translations = {
        'Dashboard': gettext('Dashboard'),
        'Kegs': gettext('Kegs'), 
        'Brews': gettext('Brews'),
        'Recipes': gettext('Recipes'),
        'Users': gettext('Users'),
        'Change Password': gettext('Change Password'),
        'Logout': gettext('Logout')
    }
    
    debug_info = f"""
    <h2>Translation Debug Info</h2>
    <p><strong>Current Locale:</strong> {current_locale}</p>
    <p><strong>User Language:</strong> {user_lang}</p>
    <p><strong>User Full Name:</strong> {current_user.full_name}</p>
    <p><strong>MO File Exists:</strong> {mo_exists} ({mo_file_path})</p>
    
    <h3>Translations via _():</h3>
    <ul>
    """
    
    for key, value in translations.items():
        debug_info += f"<li><strong>{key}:</strong> {value}</li>"
    
    debug_info += """
    </ul>
    
    <h3>Translations via gettext():</h3>
    <ul>
    """
    
    for key, value in direct_translations.items():
        debug_info += f"<li><strong>{key}:</strong> {value}</li>"
    
    debug_info += """
    </ul>
    <a href="/">Back to Dashboard</a>
    """
    
    return debug_info

if __name__ == '__main__':
    debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
