import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_babel import gettext, ngettext
from dotenv import load_dotenv
from datetime import datetime, date
import bcrypt
import uuid
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from auth import User, require_auth, require_permission
from forms import LoginForm, ChangePasswordForm, CreateUserForm, EditUserForm, CreateExpenseForm, MarkPaidForm, RejectExpenseForm, DeleteExpenseForm, EditExpenseForm
from i18n import init_babel, _, _l

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder='frontend/templates', static_folder='frontend/static')
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['WTF_CSRF_ENABLED'] = True
app.config['SERVER_NAME'] = None  # Allow any hostname

# File upload configuration
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max file size
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads', 'expenses')
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'pdf'}

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
                SELECT u.id, u.username, u.email, u.full_name, u.is_active, u.language, u.bank_account,
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
                    user_data['language'] or 'en',
                    user_data['bank_account']
                )
    except psycopg2.Error as e:
        print(f"Error loading user: {e}")
    finally:
        conn.close()
    
    return None

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_expense_file(file, expense_id):
    """Save uploaded file and return file info"""
    if file and allowed_file(file.filename):
        # Generate unique filename
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        
        # Ensure upload directory exists
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        
        # Save file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        return {
            'filename': unique_filename,
            'original_filename': file.filename,
            'file_path': file_path,
            'file_size': os.path.getsize(file_path),
            'mime_type': file.mimetype
        }
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
            
            # Get pending expenses for Economy and Admin users
            pending_expenses = []
            if current_user.can_access('expenses', 'full'):
                cur.execute("""
                    SELECT e.id, e.amount, e.description, e.submitted_date, u.full_name, u.username
                    FROM expenses e
                    JOIN users u ON e.user_id = u.id
                    WHERE e.status = 'Pending'
                    ORDER BY e.submitted_date ASC
                    LIMIT 5
                """)
                pending_expenses = cur.fetchall()
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        keg_stats = []
        recent_kegs = []
        pending_expenses = []
    finally:
        conn.close()
    
    return render_template('index.html', keg_stats=keg_stats, recent_kegs=recent_kegs, pending_expenses=pending_expenses)

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
                SELECT u.id, u.username, u.email, u.full_name, u.language, u.is_active, u.created_date, u.last_login, u.bank_account,
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
            # Get user data (updated to include bank_account)
            cur.execute("""
                SELECT u.id, u.username, u.email, u.full_name, u.role_id, u.language, u.is_active, u.bank_account
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
                # Populate form with current values (updated to include bank_account)
                form.username.data = user_data['username']
                form.email.data = user_data['email']
                form.full_name.data = user_data['full_name']
                form.role_id.data = user_data['role_id']
                form.language.data = user_data['language']
                form.is_active.data = user_data['is_active']
                form.bank_account.data = user_data['bank_account']
            
            if form.validate_on_submit():
                # Check if password change is requested (for self-editing)
                password_changed = False
                if is_self_edit and form.new_password.data:
                    # Verify current password first
                    if not form.current_password.data:
                        flash(_('Current password is required to change password'), 'error')
                        return render_template('edit_user.html', form=form, user_data=user_data, is_self_edit=is_self_edit)
                    
                    # Check current password
                    cur.execute("SELECT password_hash FROM users WHERE id = %s", (user_id,))
                    user_password = cur.fetchone()
                    
                    if not (user_password and bcrypt.checkpw(form.current_password.data.encode('utf-8'), 
                                                           user_password['password_hash'].encode('utf-8'))):
                        flash(_('Current password is incorrect'), 'error')
                        return render_template('edit_user.html', form=form, user_data=user_data, is_self_edit=is_self_edit)
                    
                    # Update password
                    new_password_hash = bcrypt.hashpw(form.new_password.data.encode('utf-8'), 
                                                     bcrypt.gensalt()).decode('utf-8')
                    cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_password_hash, user_id))
                    password_changed = True
                
                # Clean bank account input (remove dots and spaces)
                bank_account = None
                if form.bank_account.data:
                    bank_account = ''.join(filter(str.isdigit, form.bank_account.data))
                    if len(bank_account) != 11:
                        flash(_('Bank account must be exactly 11 digits'), 'error')
                        return render_template('edit_user.html', form=form, user_data=user_data, is_self_edit=is_self_edit)
                
                # For self-editing, restrict what can be changed
                if is_self_edit:
                    # Users can only update their own basic info, language, and bank account
                    cur.execute("""
                        UPDATE users 
                        SET email = %s, full_name = %s, language = %s, bank_account = %s
                        WHERE id = %s
                    """, (
                        form.email.data,
                        form.full_name.data,
                        form.language.data,
                        bank_account,
                        user_id
                    ))
                else:
                    # Admin can update everything
                    cur.execute("""
                        UPDATE users 
                        SET username = %s, email = %s, full_name = %s, role_id = %s, language = %s, is_active = %s, bank_account = %s
                        WHERE id = %s
                    """, (
                        form.username.data,
                        form.email.data,
                        form.full_name.data,
                        form.role_id.data,
                        form.language.data,
                        form.is_active.data,
                        bank_account,
                        user_id
                    ))
                conn.commit()
                
                # If updating current user's language, force logout to refresh user object
                if user_id == current_user.id:
                    from flask_login import logout_user
                    logout_user()
                    success_msg = _('Profile updated successfully!')
                    if password_changed:
                        success_msg += ' ' + _('Password changed successfully!')
                    success_msg += ' ' + _('Please log in again to see language change.')
                    flash(success_msg, 'success')
                    return redirect(url_for('login'))
                else:
                    success_msg = _('User {} updated successfully!').format(form.username.data)
                    if password_changed:
                        success_msg += ' ' + _('Password changed successfully!')
                    flash(success_msg, 'success')
                    
                return redirect(url_for('users') if current_user.can_access('users', 'view') else url_for('index'))
                
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
    finally:
        conn.close()
    
    return render_template('edit_user.html', form=form, user_data=user_data, is_self_edit=is_self_edit)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@require_permission('users', 'full')
def delete_user(user_id):
    """Delete user (admin only)"""
    # Prevent admin from deleting themselves
    if user_id == current_user.id:
        flash(_('You cannot delete your own account'), 'error')
        return redirect(url_for('users'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('users'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get user info before deletion
            cur.execute("SELECT username, full_name FROM users WHERE id = %s", (user_id,))
            user_data = cur.fetchone()
            
            if not user_data:
                flash(_('User not found'), 'error')
                return redirect(url_for('users'))
            
            # Delete the user
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
            
            flash(_('User {} ({}) deleted successfully').format(
                user_data['username'], user_data['full_name'] or 'No name'), 'success')
            
    except psycopg2.Error as e:
        flash(f'Error deleting user: {e}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('users'))

@app.route('/reset_password/<int:user_id>', methods=['GET', 'POST'])
@require_permission('users', 'full') 
def reset_password(user_id):
    """Reset user password (admin only)"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('users'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get user info
            cur.execute("SELECT username, full_name, email FROM users WHERE id = %s", (user_id,))
            user_data = cur.fetchone()
            
            if not user_data:
                flash(_('User not found'), 'error')
                return redirect(url_for('users'))
            
            if request.method == 'GET':
                return render_template('reset_password.html', user_data=user_data)
            
            # POST request - process password reset
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            # Validation
            if not new_password:
                flash(_('New password is required'), 'error')
                return render_template('reset_password.html', user_data=user_data)
            
            if len(new_password) < 6:
                flash(_('Password must be at least 6 characters long'), 'error')
                return render_template('reset_password.html', user_data=user_data)
            
            if new_password != confirm_password:
                flash(_('Passwords do not match'), 'error')
                return render_template('reset_password.html', user_data=user_data)
            
            # Hash and update password
            password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))
            conn.commit()
            
            flash(_('Password reset successfully for user {}').format(user_data['username']), 'success')
            return redirect(url_for('users'))
            
    except psycopg2.Error as e:
        flash(f'Error resetting password: {e}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('users'))

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

# ==========================================
# EXPENSE MANAGEMENT ROUTES
# ==========================================

@app.route('/expenses')
@require_permission('expenses', 'view')
def expenses():
    """View all expenses (based on permissions)"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Economy and Admin can see all expenses, Brewers only see their own
            if current_user.can_access('expenses', 'full'):
                # Economy and Admin view
                cur.execute("""
                    SELECT e.id, e.user_id, e.amount, e.description, e.purchase_date, e.submitted_date, 
                           e.status, e.paid_date, e.rejection_reason, e.rejected_date,
                           u.full_name, u.username, u.bank_account,
                           p.full_name as paid_by_name, r.full_name as rejected_by_name,
                           COUNT(ei.id) as receipt_count
                    FROM expenses e
                    JOIN users u ON e.user_id = u.id
                    LEFT JOIN users p ON e.paid_by = p.id
                    LEFT JOIN users r ON e.rejected_by = r.id
                    LEFT JOIN expense_images ei ON e.id = ei.expense_id
                    GROUP BY e.id, e.user_id, u.full_name, u.username, u.bank_account, p.full_name, r.full_name
                    ORDER BY e.submitted_date DESC
                """)
            else:
                # Brewer view - only their own expenses
                cur.execute("""
                    SELECT e.id, e.user_id, e.amount, e.description, e.purchase_date, e.submitted_date, 
                           e.status, e.paid_date, e.rejection_reason, e.rejected_date,
                           u.full_name, u.username, u.bank_account,
                           p.full_name as paid_by_name, r.full_name as rejected_by_name,
                           COUNT(ei.id) as receipt_count
                    FROM expenses e
                    JOIN users u ON e.user_id = u.id
                    LEFT JOIN users p ON e.paid_by = p.id
                    LEFT JOIN users r ON e.rejected_by = r.id
                    LEFT JOIN expense_images ei ON e.id = ei.expense_id
                    WHERE e.user_id = %s
                    GROUP BY e.id, e.user_id, u.full_name, u.username, u.bank_account, p.full_name, r.full_name
                    ORDER BY e.submitted_date DESC
                """, (current_user.id,))
            
            expenses_list = cur.fetchall()
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        expenses_list = []
    finally:
        conn.close()
    
    return render_template('expenses.html', expenses=expenses_list)

@app.route('/expenses/create', methods=['GET', 'POST'])
@require_permission('expenses', 'edit')
def create_expense():
    """Create a new expense"""
    form = CreateExpenseForm()
    
    if form.validate_on_submit():
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('expenses'))
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Insert expense
                cur.execute("""
                    INSERT INTO expenses (user_id, amount, description, purchase_date)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (
                    current_user.id,
                    form.amount.data,
                    form.description.data,
                    form.purchase_date.data
                ))
                
                expense_id = cur.fetchone()['id']
                
                # Handle file uploads
                uploaded_files = []
                if form.receipts.data:
                    for file in form.receipts.data:
                        if file.filename != '':  # Skip empty file inputs
                            file_info = save_expense_file(file, expense_id)
                            if file_info:
                                cur.execute("""
                                    INSERT INTO expense_images (expense_id, filename, original_filename, 
                                                              file_path, file_size, mime_type)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (
                                    expense_id,
                                    file_info['filename'],
                                    file_info['original_filename'],
                                    file_info['file_path'],
                                    file_info['file_size'],
                                    file_info['mime_type']
                                ))
                                uploaded_files.append(file_info['original_filename'])
                
                conn.commit()
                
                if uploaded_files:
                    flash(_('Expense submitted successfully with {} receipt(s): {}').format(
                        len(uploaded_files), ', '.join(uploaded_files)), 'success')
                else:
                    flash(_('Expense submitted successfully'), 'success')
                
                return redirect(url_for('expenses'))
                
        except psycopg2.Error as e:
            flash(f'Database error: {e}', 'error')
        except Exception as e:
            flash(f'File upload error: {e}', 'error')
        finally:
            conn.close()
    
    return render_template('create_expense.html', form=form)

@app.route('/expenses/<int:expense_id>/mark_paid', methods=['POST'])
@require_permission('expenses', 'full')
def mark_expense_paid(expense_id):
    """Mark an expense as paid (Economy and Admin only)"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('expenses'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if expense exists and is pending
            cur.execute("""
                SELECT id, amount, description, user_id, status
                FROM expenses 
                WHERE id = %s
            """, (expense_id,))
            
            expense = cur.fetchone()
            if not expense:
                flash(_('Expense not found'), 'error')
                return redirect(url_for('expenses'))
            
            if expense['status'] != 'Pending':
                flash(_('Expense is not pending'), 'error')
                return redirect(url_for('expenses'))
            
            # Mark as paid
            cur.execute("""
                UPDATE expenses 
                SET status = 'Paid', paid_by = %s, paid_date = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (current_user.id, expense_id))
            
            conn.commit()
            flash(_('Expense marked as paid successfully'), 'success')
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('expenses'))

@app.route('/expenses/<int:expense_id>/reject', methods=['GET', 'POST'])
@require_permission('expenses', 'full')
def reject_expense(expense_id):
    """Reject an expense (Economy and Admin only)"""
    form = RejectExpenseForm()
    
    if form.validate_on_submit():
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('expenses'))
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if expense exists and is pending
                cur.execute("""
                    SELECT e.id, e.amount, e.description, u.full_name, e.status
                    FROM expenses e
                    JOIN users u ON e.user_id = u.id
                    WHERE e.id = %s
                """, (expense_id,))
                
                expense = cur.fetchone()
                if not expense:
                    flash(_('Expense not found'), 'error')
                    return redirect(url_for('expenses'))
                
                if expense['status'] != 'Pending':
                    flash(_('Only pending expenses can be rejected'), 'error')
                    return redirect(url_for('expenses'))
                
                # Reject the expense
                cur.execute("""
                    UPDATE expenses 
                    SET status = 'Rejected', rejected_by = %s, rejected_date = CURRENT_TIMESTAMP, rejection_reason = %s
                    WHERE id = %s
                """, (current_user.id, form.rejection_reason.data, expense_id))
                
                conn.commit()
                flash(_('Expense rejected successfully'), 'success')
                return redirect(url_for('expenses'))
                
        except psycopg2.Error as e:
            flash(f'Database error: {e}', 'error')
        finally:
            conn.close()
    
    # Get expense details for the form
    conn = get_db_connection()
    expense = None
    if conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT e.id, e.amount, e.description, e.purchase_date, u.full_name, u.username
                    FROM expenses e
                    JOIN users u ON e.user_id = u.id
                    WHERE e.id = %s
                """, (expense_id,))
                expense = cur.fetchone()
        except psycopg2.Error:
            pass
        finally:
            conn.close()
    
    if not expense:
        flash(_('Expense not found'), 'error')
        return redirect(url_for('expenses'))
    
    return render_template('reject_expense.html', form=form, expense=expense)

@app.route('/expenses/<int:expense_id>/delete', methods=['POST'])
@require_permission('expenses', 'edit')
def delete_expense(expense_id):
    """Delete an expense (owners can delete their own, admins can delete any)"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('expenses'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if expense exists and get owner info
            cur.execute("""
                SELECT e.id, e.user_id, e.description, e.status, u.full_name
                FROM expenses e
                JOIN users u ON e.user_id = u.id
                WHERE e.id = %s
            """, (expense_id,))
            
            expense = cur.fetchone()
            if not expense:
                flash(_('Expense not found'), 'error')
                return redirect(url_for('expenses'))
            
            # Check permissions: admin/economy can delete any, others can only delete their own
            if not current_user.can_access('expenses', 'full') and expense['user_id'] != current_user.id:
                flash(_('You can only delete your own expenses'), 'error')
                return redirect(url_for('expenses'))
            
            # Prevent deletion of paid expenses (even for admins, to maintain audit trail)
            if expense['status'] == 'Paid':
                flash(_('Paid expenses cannot be deleted to maintain audit trail'), 'error')
                return redirect(url_for('expenses'))
            
            # Delete associated images first (files will be removed by CASCADE)
            cur.execute("""
                SELECT file_path FROM expense_images WHERE expense_id = %s
            """, (expense_id,))
            
            image_paths = cur.fetchall()
            
            # Delete the expense (CASCADE will handle expense_images)
            cur.execute("DELETE FROM expenses WHERE id = %s", (expense_id,))
            
            conn.commit()
            
            # Delete physical files
            for img in image_paths:
                try:
                    if os.path.exists(img['file_path']):
                        os.remove(img['file_path'])
                except Exception as e:
                    print(f"Warning: Could not delete file {img['file_path']}: {e}")
            
            flash(_('Expense deleted successfully'), 'success')
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('expenses'))

@app.route('/debug/permissions')
@require_auth
def debug_permissions():
    """Debug route to check current user permissions"""
    return f"""
    <h1>Debug: User Permissions</h1>
    <p><strong>Username:</strong> {current_user.username}</p>
    <p><strong>Role:</strong> {current_user.role_name}</p>
    <p><strong>Full Permissions:</strong> {current_user.permissions}</p>
    <p><strong>Can access expenses (view):</strong> {current_user.can_access('expenses', 'view')}</p>
    <p><strong>Can access expenses (edit):</strong> {current_user.can_access('expenses', 'edit')}</p>
    <p><strong>Can access expenses (full):</strong> {current_user.can_access('expenses', 'full')}</p>
    <a href="{url_for('expenses')}">Back to Expenses</a>
    """

@app.route('/expenses/<int:expense_id>/edit', methods=['GET', 'POST'])
@require_auth
def edit_expense(expense_id):
    """Edit a rejected expense (owner only)"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('expenses'))
    
    # Check if user can edit this expense
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT e.id, e.user_id, e.amount, e.description, e.purchase_date, e.status, e.rejection_reason
                FROM expenses e
                WHERE e.id = %s
            """, (expense_id,))
            
            expense = cur.fetchone()
            if not expense:
                flash(_('Expense not found'), 'error')
                return redirect(url_for('expenses'))
            
            # Only allow editing if user owns the expense OR has full access (admin/economy) and it's rejected
            if expense['user_id'] != current_user.id and not current_user.can_access('expenses', 'full'):
                flash(_('You can only edit your own expenses'), 'error')
                return redirect(url_for('expenses'))
            
            if expense['status'] != 'Rejected':
                flash(_('Only rejected expenses can be edited'), 'error')
                return redirect(url_for('expenses'))
            
            # Get existing attachments
            cur.execute("""
                SELECT id, filename, original_filename, file_size, mime_type
                FROM expense_images
                WHERE expense_id = %s
                ORDER BY id
            """, (expense_id,))
            
            existing_attachments = cur.fetchall()
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        return redirect(url_for('expenses'))
    finally:
        conn.close()
    
    form = EditExpenseForm()
    
    if form.validate_on_submit():
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('expenses'))
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Handle attachment removals if any
                removed_files = []
                if form.remove_attachments.data:
                    attachment_ids = form.remove_attachments.data.split(',')
                    for attachment_id in attachment_ids:
                        if attachment_id.strip():
                            # Get file info before deletion
                            cur.execute("""
                                SELECT filename, original_filename, file_path
                                FROM expense_images
                                WHERE id = %s AND expense_id = %s
                            """, (attachment_id.strip(), expense_id))
                            
                            file_info = cur.fetchone()
                            if file_info:
                                # Delete file from filesystem
                                import os
                                try:
                                    if os.path.exists(file_info['file_path']):
                                        os.remove(file_info['file_path'])
                                except Exception as e:
                                    print(f"Failed to delete file {file_info['file_path']}: {e}")
                                
                                # Delete from database
                                cur.execute("""
                                    DELETE FROM expense_images
                                    WHERE id = %s AND expense_id = %s
                                """, (attachment_id.strip(), expense_id))
                                
                                removed_files.append(file_info['original_filename'])
                
                # Update expense and reset status to Pending
                cur.execute("""
                    UPDATE expenses 
                    SET amount = %s, description = %s, purchase_date = %s, 
                        status = 'Pending', rejection_reason = NULL, rejected_by = NULL, rejected_date = NULL,
                        submitted_date = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    form.amount.data,
                    form.description.data,
                    form.purchase_date.data,
                    expense_id
                ))
                
                # Handle new file uploads if any
                uploaded_files = []
                if form.receipts.data:
                    for file in form.receipts.data:
                        if file.filename != '':
                            file_info = save_expense_file(file, expense_id)
                            if file_info:
                                cur.execute("""
                                    INSERT INTO expense_images (expense_id, filename, original_filename, 
                                                              file_path, file_size, mime_type)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (
                                    expense_id,
                                    file_info['filename'],
                                    file_info['original_filename'],
                                    file_info['file_path'],
                                    file_info['file_size'],
                                    file_info['mime_type']
                                ))
                                uploaded_files.append(file_info['original_filename'])
                
                conn.commit()
                
                # Build success message
                message_parts = []
                if uploaded_files:
                    message_parts.append(_('Added {} new receipt(s): {}').format(
                        len(uploaded_files), ', '.join(uploaded_files)))
                if removed_files:
                    message_parts.append(_('Removed {} receipt(s): {}').format(
                        len(removed_files), ', '.join(removed_files)))
                
                if message_parts:
                    flash(_('Expense updated and resubmitted successfully. {}').format(
                        '. '.join(message_parts)), 'success')
                else:
                    flash(_('Expense updated and resubmitted successfully'), 'success')
                
                return redirect(url_for('expenses'))
                
        except psycopg2.Error as e:
            flash(f'Database error: {e}', 'error')
        except Exception as e:
            flash(f'File upload error: {e}', 'error')
        finally:
            conn.close()
    
    # Populate form with current values
    if request.method == 'GET':
        form.amount.data = expense['amount']
        form.description.data = expense['description']
        form.purchase_date.data = expense['purchase_date']
    
    return render_template('edit_expense.html', form=form, expense=expense, existing_attachments=existing_attachments)

@app.route('/expenses/<int:expense_id>/receipts')
@require_permission('expenses', 'view')
def expense_receipts(expense_id):
    """Get list of receipts for an expense"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('expenses'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Verify user can access this expense
            if current_user.can_access('expenses', 'full'):
                # Economy and Admin can see all
                cur.execute("""
                    SELECT e.id, e.description, u.full_name, u.username
                    FROM expenses e
                    JOIN users u ON e.user_id = u.id
                    WHERE e.id = %s
                """, (expense_id,))
            else:
                # Brewers can only see their own
                cur.execute("""
                    SELECT e.id, e.description, u.full_name, u.username
                    FROM expenses e
                    JOIN users u ON e.user_id = u.id
                    WHERE e.id = %s AND e.user_id = %s
                """, (expense_id, current_user.id))
            
            expense = cur.fetchone()
            if not expense:
                flash(_('Expense not found'), 'error')
                return redirect(url_for('expenses'))
            
            # Get receipt images
            cur.execute("""
                SELECT id, filename, original_filename, file_size, mime_type, uploaded_date
                FROM expense_images
                WHERE expense_id = %s
                ORDER BY uploaded_date
            """, (expense_id,))
            
            receipts = cur.fetchall()
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        return redirect(url_for('expenses'))
    finally:
        conn.close()
    
    return render_template('expense_receipts.html', expense=expense, receipts=receipts)

@app.route('/expenses/<int:expense_id>/images/<filename>')
@require_permission('expenses', 'view')
def expense_image(expense_id, filename):
    """Serve expense receipt images"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('expenses'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Verify user can access this expense
            if current_user.can_access('expenses', 'full'):
                # Economy and Admin can see all
                cur.execute("""
                    SELECT ei.file_path, ei.original_filename, ei.mime_type
                    FROM expense_images ei
                    JOIN expenses e ON ei.expense_id = e.id
                    WHERE e.id = %s AND ei.filename = %s
                """, (expense_id, filename))
            else:
                # Brewers can only see their own
                cur.execute("""
                    SELECT ei.file_path, ei.original_filename, ei.mime_type
                    FROM expense_images ei
                    JOIN expenses e ON ei.expense_id = e.id
                    WHERE e.id = %s AND ei.filename = %s AND e.user_id = %s
                """, (expense_id, filename, current_user.id))
            
            image_data = cur.fetchone()
            if not image_data:
                flash(_('Image not found'), 'error')
                return redirect(url_for('expenses'))
            
            return send_file(
                image_data['file_path'],
                as_attachment=True,
                download_name=image_data['original_filename'],
                mimetype=image_data['mime_type']
            )
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
    except Exception as e:
        flash(f'File error: {e}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('expenses'))

if __name__ == '__main__':
    debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
