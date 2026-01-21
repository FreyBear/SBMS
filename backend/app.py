import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_babel import gettext, ngettext
from dotenv import load_dotenv
from datetime import datetime, date
from decimal import Decimal
import bcrypt
import uuid
import math
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from werkzeug.middleware.proxy_fix import ProxyFix
from auth import User, require_auth, require_permission
from forms import LoginForm, ChangePasswordForm, CreateUserForm, EditUserForm, CreateExpenseForm, MarkPaidForm, RejectExpenseForm, DeleteExpenseForm, EditExpenseForm, CreateKitForm, EditKitForm, DeleteKitForm
from i18n import init_babel, _, _l
from beerxml_handler import BeerXMLHandler
from mqtt_handler import MQTTHandler

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder='frontend/templates', static_folder='frontend/static')

# Configure Flask for reverse proxy (Nginx Proxy Manager)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

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

# Custom template filters for translations
@app.template_filter('translate_status')
def translate_status(status):
    """Translate keg status values to current locale"""
    from flask_babel import get_locale
    
    current_locale = str(get_locale())
    
    if current_locale == 'no':
        # Norwegian Bokmål translations
        status_translations = {
            # Keg statuses
            'Empty': 'Tomt',
            'Full': 'Fullt', 
            'Started': 'Påbegynt',
            'Available/Cleaned': 'Vasket',
            'Never': 'Aldri',
            'Unknown': 'Ukjent',
            # Expense statuses
            'Pending': 'Venter',
            'Paid': 'Betalt',
            'Rejected': 'Avvist'
        }
        return status_translations.get(status, status)
    elif current_locale == 'nn':
        # Norwegian Nynorsk translations
        status_translations = {
            # Keg statuses
            'Empty': 'Tomt',
            'Full': 'Fullt', 
            'Started': 'Påbegynt',
            'Available/Cleaned': 'Vaska',
            'Never': 'Aldri',
            'Unknown': 'Ukjent',
            # Expense statuses
            'Pending': 'Ventar',
            'Paid': 'Betalt',
            'Rejected': 'Avvist'
        }
        return status_translations.get(status, status)
    
    # Default to English
    return status

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

# Initialize MQTT Handler (after get_db_connection is defined)
mqtt_handler = MQTTHandler(get_db_connection)

@app.before_request
def force_https():
    """Handle HTTPS redirects when behind reverse proxy"""
    # Check if we're behind a proxy with HTTPS
    if os.getenv('ENABLE_HTTPS', 'false').lower() == 'true':
        # Check if request came through HTTPS proxy
        if request.headers.get('X-Forwarded-Proto') == 'https':
            # Request is already HTTPS, continue normally
            pass
        elif request.headers.get('X-Forwarded-Proto') == 'http':
            # Request came through HTTP, redirect to HTTPS
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)
    
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
                           u.language, u.bank_account,
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
                        user_data['is_active'],
                        user_data['language'] or 'en',
                        user_data['bank_account']
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
            
            # Get bottle batch summary (only non-empty batches)
            cur.execute("""
                SELECT 
                    bb.id,
                    bb.bottle_size_liters,
                    bb.bottles_left,
                    bb.initial_quantity,
                    bb.location,
                    bb.cap_type,
                    b.name as brew_name,
                    b.style as brew_style,
                    COALESCE(b.actual_abv, b.estimated_abv) as abv
                FROM bottle_batch bb
                LEFT JOIN brew b ON bb.brew_id = b.id
                WHERE bb.bottles_left > 0
                ORDER BY bb.bottling_date DESC, bb.id DESC
            """)
            bottle_batches = cur.fetchall()
            
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
            
            # Get pending brew tasks (next 7 days) across all brews
            pending_brew_tasks = []
            if current_user.can_access('brews', 'view'):
                cur.execute("""
                    SELECT bt.*, b.name as brew_name
                    FROM brew_task bt
                    JOIN brew b ON bt.brew_id = b.id
                    WHERE bt.is_completed = FALSE
                      AND bt.scheduled_date <= CURRENT_DATE + INTERVAL '7 days'
                    ORDER BY bt.scheduled_date ASC, bt.created_date ASC
                    LIMIT 20
                """)
                pending_brew_tasks = cur.fetchall()
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        keg_stats = []
        bottle_batches = []
        recent_kegs = []
        pending_expenses = []
        pending_brew_tasks = []
    finally:
        conn.close()
    
    # Import datetime for template usage
    from datetime import date
    today_date = date.today()
    
    return render_template('index.html', 
                         keg_stats=keg_stats,
                         bottle_batches=bottle_batches,
                         recent_kegs=recent_kegs, 
                         pending_expenses=pending_expenses,
                         pending_brew_tasks=pending_brew_tasks,
                         today_date=today_date)

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
                WHERE k.historical = false
                ORDER BY k.keg_number::integer
            """)
            kegs = cur.fetchall()
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        kegs = []
    finally:
        conn.close()
    
    return render_template('kegs.html', kegs=kegs)

@app.route('/keg/add', methods=['GET', 'POST'])
@require_permission('kegs', 'edit')
def add_keg():
    """Add a new keg - Admin only"""
    # Only admins can add kegs
    if current_user.role_name != 'admin':
        flash(_('Only administrators can add kegs'), 'error')
        return redirect(url_for('kegs'))
    
    if request.method == 'GET':
        return render_template('add_keg.html')
    
    # POST request - create new keg
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('kegs'))
    
    try:
        keg_number = request.form.get('keg_number')
        volume_liters = float(request.form.get('volume_liters'))
        location = request.form.get('location', 'Storage')
        notes = request.form.get('notes', '')
        
        # Get weight-related fields
        empty_weight_kg = request.form.get('empty_weight_kg')
        if empty_weight_kg:
            empty_weight_kg = float(empty_weight_kg)
        else:
            empty_weight_kg = None
        
        # keg_size_liters will match volume_liters
        keg_size_liters = volume_liters
        
        with conn.cursor() as cur:
            # Check if keg number already exists (including historical kegs)
            cur.execute("SELECT id, historical FROM keg WHERE keg_number = %s", (keg_number,))
            existing = cur.fetchone()
            
            if existing:
                if existing[1]:  # historical = true
                    flash(_('Keg #%(num)s exists but is marked as historical. Restore it instead of creating a new one.', num=keg_number), 'error')
                else:
                    flash(_('Keg #%(num)s already exists', num=keg_number), 'error')
                return redirect(url_for('kegs'))
            
            # Insert new keg
            cur.execute("""
                INSERT INTO keg 
                (keg_number, volume_liters, keg_size_liters, empty_weight_kg, 
                 status, location, notes, historical, amount_left_liters, last_measured)
                VALUES (%s, %s, %s, %s, 'Available/Cleaned', %s, %s, false, 0, CURRENT_DATE)
                RETURNING id
            """, (keg_number, volume_liters, keg_size_liters, empty_weight_kg, location, notes))
            
            keg_id = cur.fetchone()[0]
            
            # Create initial history entry
            cur.execute("""
                INSERT INTO keg_history 
                (keg_id, recorded_date, status, amount_left_liters, location, arrangement, notes)
                VALUES (%s, CURRENT_DATE, 'Available/Cleaned', 0, %s, 'Keg added to system', %s)
            """, (keg_id, location, notes))
            
            conn.commit()
            flash(_('Keg #%(num)s added successfully', num=keg_number), 'success')
            return redirect(url_for('keg_detail', keg_id=keg_id))
            
    except (psycopg2.Error, ValueError) as e:
        conn.rollback()
        flash(f'Error adding keg: {e}', 'error')
        return redirect(url_for('kegs'))
    finally:
        conn.close()

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
                
                # Get all brews for dropdown
                cur.execute("""
                    SELECT id, name, actual_abv, gluten_free 
                    FROM brew 
                    ORDER BY date_brewed DESC
                """)
                brews = cur.fetchall()
                
        except psycopg2.Error as e:
            flash(f'Database error: {e}', 'error')
            keg = None
            brews = []
        finally:
            conn.close()
        
        if not keg:
            flash('Keg not found', 'error')
            return redirect(url_for('kegs'))
        
        # Pass today's date to template
        today = datetime.now().strftime('%Y-%m-%d')
        return render_template('update_keg.html', keg=keg, brews=brews, today=today)
    
    # POST request - always update main keg AND create history entry
    try:
        with conn.cursor() as cur:
            # Parse the update date
            update_date = datetime.strptime(request.form['update_date'], '%Y-%m-%d').date()
            
            # Get brew_id, abv, and gluten_free from form
            brew_id = request.form.get('brew_id')
            brew_id = int(brew_id) if brew_id and brew_id != '' else None
            
            abv = request.form.get('abv')
            abv = float(abv) if abv and abv != '' else None
            
            gluten_free = request.form.get('gluten_free') == 'on'
            
            # Handle weight-based or manual measurement
            current_weight_kg = request.form.get('current_weight_kg')
            measurement_source = 'manual'
            
            if current_weight_kg and current_weight_kg.strip():
                # Weight was entered - use weight-based calculation
                current_weight_kg = float(current_weight_kg)
                
                # Get empty weight from database
                cur.execute("SELECT empty_weight_kg FROM keg WHERE id = %s", (keg_id,))
                result = cur.fetchone()
                empty_weight = result[0] if result else None
                
                if empty_weight is None:
                    flash('Empty weight not configured for this keg', 'error')
                    conn.close()
                    return redirect(url_for('update_keg', keg_id=keg_id))
                
                # Calculate amount left with floor rounding to 0.1
                raw_liters = current_weight_kg - empty_weight
                amount_left_liters = math.floor(raw_liters * 10) / 10
                amount_left_liters = max(0, amount_left_liters)  # Cannot be negative
                measurement_source = 'weight'
            else:
                # No weight entered - use manual amount_left_liters
                current_weight_kg = None
                amount_left_liters = float(request.form['amount_left_liters']) if request.form['amount_left_liters'] else 0
            
            # Update the main keg record with latest values
            cur.execute("""
                UPDATE keg SET
                    contents = %s,
                    status = %s,
                    amount_left_liters = %s,
                    current_weight_kg = %s,
                    location = %s,
                    brew_id = %s,
                    abv = %s,
                    gluten_free = %s,
                    notes = %s,
                    last_measured = %s
                WHERE id = %s
            """, (
                request.form['contents'],
                request.form['status'],
                amount_left_liters,
                current_weight_kg,
                request.form['location'],
                brew_id,
                abv,
                gluten_free,
                request.form['notes'],
                update_date,
                keg_id
            ))
            
            # Create a history entry for this update
            cur.execute("""
                INSERT INTO keg_history 
                (keg_id, recorded_date, contents, status, amount_left_liters, location, arrangement, notes, measurement_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                keg_id,
                update_date,
                request.form['contents'],
                request.form['status'],
                amount_left_liters,
                request.form['location'],
                request.form.get('arrangement', 'Normal operation'),
                request.form['notes'],
                measurement_source
            ))
            
            conn.commit()
            flash(_('Keg updated successfully and history entry created'), 'success')
    except (psycopg2.Error, ValueError) as e:
        flash(f'Error updating keg: {e}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('keg_detail', keg_id=keg_id))

@app.route('/kegs/bulk_mark_cleaned', methods=['POST'])
@require_permission('kegs', 'edit')
def bulk_mark_cleaned():
    """Mark multiple kegs as cleaned in one operation"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('kegs'))
    
    try:
        # Get form data
        keg_ids_str = request.form.get('keg_ids', '')
        location = request.form.get('location', 'Storage')
        notes = request.form.get('notes', 'Bulk cleaned')
        
        if not keg_ids_str:
            flash('No kegs selected', 'error')
            return redirect(url_for('kegs'))
        
        # Parse keg IDs
        keg_ids = [int(kid.strip()) for kid in keg_ids_str.split(',') if kid.strip()]
        
        if not keg_ids:
            flash('No valid keg IDs provided', 'error')
            return redirect(url_for('kegs'))
        
        update_date = datetime.now().date()
        updated_count = 0
        
        with conn.cursor() as cur:
            for keg_id in keg_ids:
                # Update main keg record to Available/Cleaned status
                cur.execute("""
                    UPDATE keg SET
                        status = 'Available/Cleaned',
                        contents = NULL,
                        amount_left_liters = 0,
                        location = %s,
                        brew_id = NULL,
                        abv = NULL,
                        gluten_free = false,
                        notes = %s,
                        last_measured = %s
                    WHERE id = %s
                """, (location, notes, update_date, keg_id))
                
                # Create history entry
                cur.execute("""
                    INSERT INTO keg_history 
                    (keg_id, recorded_date, contents, status, amount_left_liters, location, arrangement, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    keg_id,
                    update_date,
                    None,  # contents
                    'Available/Cleaned',
                    0,  # amount_left_liters
                    location,
                    'Bulk cleaning',  # arrangement
                    notes
                ))
                
                updated_count += 1
        
        conn.commit()
        flash(_('Successfully marked %(count)d kegs as cleaned', count=updated_count), 'success')
        
    except (psycopg2.Error, ValueError) as e:
        conn.rollback()
        flash(f'Error during bulk cleaning: {e}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('kegs'))

@app.route('/kegs/bulk_mark_empty', methods=['POST'])
@require_permission('kegs', 'edit')
def bulk_mark_empty():
    """Mark multiple kegs as empty in one operation"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('kegs'))
    
    try:
        # Get form data
        keg_ids_str = request.form.get('keg_ids', '')
        location = request.form.get('location', 'Storage')
        notes = request.form.get('notes', 'Bulk emptied')
        
        if not keg_ids_str:
            flash('No kegs selected', 'error')
            return redirect(url_for('kegs'))
        
        # Parse keg IDs
        keg_ids = [int(kid.strip()) for kid in keg_ids_str.split(',') if kid.strip()]
        
        if not keg_ids:
            flash('No valid keg IDs provided', 'error')
            return redirect(url_for('kegs'))
        
        update_date = datetime.now().date()
        updated_count = 0
        
        with conn.cursor() as cur:
            for keg_id in keg_ids:
                # Update main keg record to Empty status
                cur.execute("""
                    UPDATE keg SET
                        status = 'Empty',
                        contents = NULL,
                        amount_left_liters = 0,
                        location = %s,
                        brew_id = NULL,
                        abv = NULL,
                        gluten_free = false,
                        notes = %s,
                        last_measured = %s
                    WHERE id = %s
                """, (location, notes, update_date, keg_id))
                
                # Create history entry
                cur.execute("""
                    INSERT INTO keg_history 
                    (keg_id, recorded_date, contents, status, amount_left_liters, location, arrangement, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    keg_id,
                    update_date,
                    None,  # contents
                    'Empty',
                    0,  # amount_left_liters
                    location,
                    'Bulk emptying',  # arrangement
                    notes
                ))
                
                updated_count += 1
        
        conn.commit()
        flash(_('Successfully marked %(count)d kegs as empty', count=updated_count), 'success')
        
    except (psycopg2.Error, ValueError) as e:
        conn.rollback()
        flash(f'Error during bulk emptying: {e}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('kegs'))

@app.route('/keg/<int:keg_id>/delete', methods=['POST'])
@require_permission('kegs', 'edit')
def delete_keg(keg_id):
    """Soft-delete a keg by marking it as historical - Admin only"""
    # Only admins can delete kegs
    if current_user.role_name != 'admin':
        flash(_('Only administrators can delete kegs'), 'error')
        return redirect(url_for('kegs'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('kegs'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get keg info before marking as historical
            cur.execute("SELECT keg_number, historical FROM keg WHERE id = %s", (keg_id,))
            keg = cur.fetchone()
            
            if not keg:
                flash(_('Keg not found'), 'error')
                return redirect(url_for('kegs'))
            
            if keg['historical']:
                flash(_('Keg is already marked as historical'), 'error')
                return redirect(url_for('kegs'))
            
            # Mark keg as historical (soft delete)
            cur.execute("""
                UPDATE keg 
                SET historical = true,
                    notes = CASE 
                        WHEN notes IS NULL OR notes = '' THEN 'Marked as historical'
                        ELSE notes || ' - Marked as historical'
                    END
                WHERE id = %s
            """, (keg_id,))
            
            # Create history entry
            cur.execute("""
                INSERT INTO keg_history 
                (keg_id, recorded_date, status, amount_left_liters, location, arrangement, notes)
                SELECT id, CURRENT_DATE, status, amount_left_liters, location, 'Keg marked as historical', 'Removed from active inventory'
                FROM keg WHERE id = %s
            """, (keg_id,))
            
            conn.commit()
            flash(_('Keg #%(num)s marked as historical', num=keg['keg_number']), 'success')
            
    except psycopg2.Error as e:
        conn.rollback()
        flash(f'Error marking keg as historical: {e}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('kegs'))

@app.route('/keg/<int:keg_id>/history/<int:history_id>/edit', methods=['GET', 'POST'])
@require_permission('kegs', 'edit')
def edit_keg_history(keg_id, history_id):
    """Edit keg history entry - Admin only"""
    # Only admins can edit/delete history entries
    if current_user.role_name != 'admin':
        flash(_('Only administrators can edit or delete history entries'), 'error')
        return redirect(url_for('keg_detail', keg_id=keg_id))
    
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

# ============================================================================
# BOTTLE BATCH ROUTES
# ============================================================================

@app.route('/bottles')
@require_permission('brews', 'view')
def bottles():
    """View all bottle batches"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT bb.*, 
                       b.name as brew_name,
                       b.style as brew_style,
                       b.actual_abv,
                       b.estimated_abv,
                       b.gluten_free
                FROM bottle_batch bb
                LEFT JOIN brew b ON bb.brew_id = b.id
                ORDER BY bb.bottling_date DESC, bb.id DESC
            """)
            bottle_batches = cur.fetchall()
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        bottle_batches = []
    finally:
        conn.close()
    
    return render_template('bottles.html', bottle_batches=bottle_batches)

@app.route('/bottles/create', methods=['GET', 'POST'])
@require_permission('brews', 'edit')
def create_bottle_batch():
    """Create a new bottle batch"""
    if request.method == 'POST':
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('bottles'))
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO bottle_batch (
                        brew_id, bottle_size_liters, initial_quantity, bottles_left,
                        bottling_date, cap_type, location, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    request.form['brew_id'],
                    request.form['bottle_size_liters'],
                    request.form['initial_quantity'],
                    request.form['initial_quantity'],  # bottles_left = initial_quantity when created
                    request.form['bottling_date'],
                    request.form.get('cap_type'),
                    request.form.get('location'),
                    request.form.get('notes')
                ))
                conn.commit()
                flash('Bottle batch registered successfully!', 'success')
        except psycopg2.Error as e:
            conn.rollback()
            flash(f'Database error: {e}', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('bottles'))
    
    # GET request - show form
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('bottles'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get all brews for the dropdown
            cur.execute("""
                SELECT b.id, b.name, b.style, b.date_brewed,
                       COALESCE(b.actual_abv, b.estimated_abv) as abv
                FROM brew b
                ORDER BY b.date_brewed DESC, b.name
            """)
            brews = cur.fetchall()
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        brews = []
    finally:
        conn.close()
    
    return render_template('create_bottle_batch.html', brews=brews)

@app.route('/bottles/<int:batch_id>')
@require_permission('brews', 'view')
def bottle_batch_detail(batch_id):
    """View bottle batch details"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('bottles'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT bb.*,
                       b.name as brew_name,
                       b.style as brew_style,
                       b.date_brewed,
                       b.actual_abv,
                       b.estimated_abv,
                       b.gluten_free,
                       b.actual_og,
                       b.actual_fg
                FROM bottle_batch bb
                LEFT JOIN brew b ON bb.brew_id = b.id
                WHERE bb.id = %s
            """, (batch_id,))
            batch = cur.fetchone()
            
            if not batch:
                flash('Bottle batch not found', 'error')
                return redirect(url_for('bottles'))
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        return redirect(url_for('bottles'))
    finally:
        conn.close()
    
    return render_template('bottle_batch_detail.html', batch=batch)

@app.route('/bottles/<int:batch_id>/update', methods=['GET', 'POST'])
@require_permission('brews', 'edit')
def update_bottle_batch(batch_id):
    """Update bottle batch information"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('bottles'))
    
    if request.method == 'POST':
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE bottle_batch SET
                        bottles_left = %s,
                        location = %s,
                        notes = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    request.form['bottles_left'],
                    request.form.get('location'),
                    request.form.get('notes'),
                    batch_id
                ))
                conn.commit()
                flash('Bottle batch updated successfully!', 'success')
        except psycopg2.Error as e:
            conn.rollback()
            flash(f'Database error: {e}', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('bottle_batch_detail', batch_id=batch_id))
    
    # GET request - show form
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT bb.*,
                       b.name as brew_name,
                       b.style as brew_style
                FROM bottle_batch bb
                LEFT JOIN brew b ON bb.brew_id = b.id
                WHERE bb.id = %s
            """, (batch_id,))
            batch = cur.fetchone()
            
            if not batch:
                flash('Bottle batch not found', 'error')
                return redirect(url_for('bottles'))
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        return redirect(url_for('bottles'))
    finally:
        conn.close()
    
    return render_template('update_bottle_batch.html', batch=batch)

@app.route('/brews')
@require_permission('brews', 'view')
def brews():
    """View all brews with enhanced information"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT b.*, 
                       r.name as recipe_name, 
                       k.name as kit_name,
                       COALESCE(r.style, k.style) as source_style,
                       COUNT(keg.id) as keg_count,
                       COUNT(bt.id) as task_count,
                       COUNT(CASE WHEN bt.is_completed = true THEN 1 END) as completed_tasks
                FROM brew b
                LEFT JOIN recipe r ON b.recipe_id = r.id
                LEFT JOIN kit k ON b.kit_id = k.id
                LEFT JOIN keg ON b.id = keg.brew_id
                LEFT JOIN brew_task bt ON b.id = bt.brew_id
                GROUP BY b.id, r.name, k.name, r.style, k.style
                ORDER BY b.date_brewed DESC
            """)
            brews = cur.fetchall()
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        brews = []
    finally:
        conn.close()
    
    return render_template('brews.html', brews=brews)

@app.route('/brews/create', methods=['GET', 'POST'])
@require_permission('brews', 'edit')
def create_brew():
    """Create a new brew from recipe or kit"""
    from forms import CreateBrewForm
    
    form = CreateBrewForm()
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Populate recipe and kit choices
            cur.execute("SELECT id, name FROM recipe WHERE is_active = true ORDER BY name")
            recipes = cur.fetchall()
            form.recipe_id.choices = [('', 'Select Recipe')] + [(str(r['id']), r['name']) for r in recipes]
            
            cur.execute("SELECT id, name FROM kit ORDER BY name")
            kits = cur.fetchall()
            form.kit_id.choices = [('', 'Select Kit')] + [(str(k['id']), k['name']) for k in kits]
            
            if form.validate_on_submit():
                # Validate source selection
                if form.source_type.data == 'recipe' and not form.recipe_id.data:
                    flash('Please select a recipe', 'error')
                elif form.source_type.data == 'kit' and not form.kit_id.data:
                    flash('Please select a kit', 'error')
                else:
                    # Calculate actual ABV if both OG and FG are provided
                    actual_abv = None
                    if form.actual_og.data and form.actual_fg.data:
                        actual_abv = round((form.actual_og.data - form.actual_fg.data) * Decimal('131.25'), 1)
                    
                    # Insert brew
                    cur.execute("""
                        INSERT INTO brew (name, date_brewed, recipe_id, kit_id, style, 
                                        estimated_abv, expected_og, expected_fg, batch_size_liters,
                                        actual_og, actual_fg, actual_abv, gluten_free, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        form.name.data,
                        form.date_brewed.data,
                        form.recipe_id.data if form.source_type.data == 'recipe' else None,
                        form.kit_id.data if form.source_type.data == 'kit' else None,
                        form.style.data,
                        form.estimated_abv.data,
                        form.expected_og.data,
                        form.expected_fg.data,
                        form.batch_size_liters.data,
                        form.actual_og.data,
                        form.actual_fg.data,
                        actual_abv,
                        form.gluten_free.data or False,
                        form.notes.data
                    ))
                    
                    brew_id = cur.fetchone()['id']
                    conn.commit()
                    
                    flash('Brew created successfully!', 'success')
                    return redirect(url_for('brew_detail', brew_id=brew_id))
    
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        conn.rollback()
    finally:
        conn.close()
    
    return render_template('create_brew.html', form=form)

@app.route('/brew/<int:brew_id>')
@require_permission('brews', 'view')
def brew_detail(brew_id):
    """View brew details with task schedule"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get brew details
            cur.execute("""
                SELECT b.*, r.name as recipe_name, k.name as kit_name,
                       COALESCE(r.style, k.style, b.style) as display_style
                FROM brew b
                LEFT JOIN recipe r ON b.recipe_id = r.id
                LEFT JOIN kit k ON b.kit_id = k.id
                WHERE b.id = %s
            """, (brew_id,))
            
            brew = cur.fetchone()
            if not brew:
                flash('Brew not found', 'error')
                return redirect(url_for('brews'))
            
            # Get brew task schedule
            cur.execute("""
                SELECT * FROM brew_task 
                WHERE brew_id = %s 
                ORDER BY scheduled_date, created_date
            """, (brew_id,))
            
            brew_tasks = cur.fetchall()
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        return redirect(url_for('brews'))
    finally:
        conn.close()
    
    return render_template('brew_detail.html', brew=brew, brew_tasks=brew_tasks)

@app.route('/brew/<int:brew_id>/edit', methods=['GET', 'POST'])
@require_permission('brews', 'edit')
def edit_brew(brew_id):
    """Edit an existing brew"""
    from forms import EditBrewForm
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get current brew data
            cur.execute("""
                SELECT b.*, r.name as recipe_name, k.name as kit_name
                FROM brew b
                LEFT JOIN recipe r ON b.recipe_id = r.id
                LEFT JOIN kit k ON b.kit_id = k.id
                WHERE b.id = %s
            """, (brew_id,))
            
            brew = cur.fetchone()
            if not brew:
                flash('Brew not found', 'error')
                return redirect(url_for('brews'))
            
            # Initialize form
            form = EditBrewForm()
            
            # On GET request, populate form with current brew data
            if request.method == 'GET':
                form.name.data = brew['name']
                form.date_brewed.data = brew['date_brewed']
                form.style.data = brew['style']
                form.estimated_abv.data = brew['estimated_abv']
                form.expected_og.data = brew['expected_og']
                form.expected_fg.data = brew['expected_fg']
                form.batch_size_liters.data = brew['batch_size_liters']
                form.actual_og.data = brew['actual_og']
                form.actual_fg.data = brew['actual_fg']
                form.gluten_free.data = brew.get('gluten_free', False)
                form.notes.data = brew['notes']
                
                # Set source info (read-only)
                if brew['recipe_name']:
                    form.source_info.data = f"Recipe: {brew['recipe_name']}"
                elif brew['kit_name']:
                    form.source_info.data = f"Kit: {brew['kit_name']}"
                else:
                    form.source_info.data = "Unknown source"
            
            # Get brew task schedule
            cur.execute("""
                SELECT * FROM brew_task 
                WHERE brew_id = %s 
                ORDER BY scheduled_date, created_date
            """, (brew_id,))
            
            brew_tasks = cur.fetchall()
            
            if form.validate_on_submit():
                # Calculate actual ABV if both OG and FG are provided
                actual_abv = None
                if form.actual_og.data and form.actual_fg.data:
                    actual_abv = round((form.actual_og.data - form.actual_fg.data) * Decimal('131.25'), 1)
                
                cur.execute("""
                    UPDATE brew SET 
                        name = %s, date_brewed = %s, style = %s, 
                        estimated_abv = %s, expected_og = %s, expected_fg = %s, 
                        batch_size_liters = %s, actual_og = %s, actual_fg = %s, 
                        actual_abv = %s, gluten_free = %s, notes = %s
                    WHERE id = %s
                """, (
                    form.name.data,
                    form.date_brewed.data,
                    form.style.data,
                    form.estimated_abv.data,
                    form.expected_og.data,
                    form.expected_fg.data,
                    form.batch_size_liters.data,
                    form.actual_og.data,
                    form.actual_fg.data,
                    actual_abv,
                    form.gluten_free.data or False,
                    form.notes.data,
                    brew_id
                ))
                
                conn.commit()
                flash('Brew updated successfully!', 'success')
                return redirect(url_for('brew_detail', brew_id=brew_id))
    
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        conn.rollback()
    finally:
        conn.close()
    
    return render_template('edit_brew.html', form=form, brew=brew, brew_tasks=brew_tasks)

@app.route('/brew/<int:brew_id>/delete', methods=['POST'])
@require_permission('brews', 'delete')
def delete_brew(brew_id):
    """Delete a brew (admin only)"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('brews'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # First check if brew exists and get its name
            cur.execute("SELECT name FROM brew WHERE id = %s", (brew_id,))
            brew = cur.fetchone()
            
            if not brew:
                flash('Brew not found', 'error')
                return redirect(url_for('brews'))
            
            # Delete the brew (brew task records will be cascade deleted)
            cur.execute("DELETE FROM brew WHERE id = %s", (brew_id,))
            conn.commit()
            
            flash(f'Brew "{brew["name"]}" has been deleted successfully', 'success')
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        conn.rollback()
    finally:
        conn.close()
    
    return redirect(url_for('brews'))

# ========================================
# Brew Task Management Routes
# ========================================

@app.route('/brew/<int:brew_id>/task/add', methods=['GET', 'POST'])
@require_permission('brews', 'edit')
def add_brew_task(brew_id):
    """Add a brew task to a brew"""
    from forms import AddBrewTaskForm
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    # Verify brew exists
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, name FROM brew WHERE id = %s", (brew_id,))
            brew = cur.fetchone()
            
            if not brew:
                flash('Brew not found', 'error')
                return redirect(url_for('brews'))
            
            form = AddBrewTaskForm()
            
            if form.validate_on_submit():
                cur.execute("""
                    INSERT INTO brew_task (brew_id, scheduled_date, action, notes)
                    VALUES (%s, %s, %s, %s)
                """, (
                    brew_id,
                    form.scheduled_date.data,
                    form.action.data,
                    form.notes.data
                ))
                
                conn.commit()
                flash('Brew task added successfully!', 'success')
                return redirect(url_for('brew_detail', brew_id=brew_id))
    
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        conn.rollback()
    finally:
        conn.close()
    
    return render_template('add_brew_task.html', form=form, brew=brew)

@app.route('/brew-task/<int:task_id>/edit', methods=['GET', 'POST'])
@require_permission('brews', 'edit')
def edit_brew_task(task_id):
    """Edit or mark brew task as completed"""
    from forms import EditBrewTaskForm
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT bt.*, b.name as brew_name 
                FROM brew_task bt
                JOIN brew b ON bt.brew_id = b.id
                WHERE bt.id = %s
            """, (task_id,))
            
            brew_task = cur.fetchone()
            if not brew_task:
                flash('Brew task not found', 'error')
                return redirect(url_for('brews'))
            
            # Initialize form
            form = EditBrewTaskForm()
            
            # On GET request, populate form with current brew task data
            if request.method == 'GET':
                form.scheduled_date.data = brew_task['scheduled_date']
                form.completed_date.data = brew_task['completed_date']
                form.action.data = brew_task['action']
                form.is_completed.data = brew_task['is_completed']
                form.notes.data = brew_task['notes']
            
            if form.validate_on_submit():
                # Handle completed date based on is_completed checkbox
                if form.is_completed.data:
                    # If marking as completed, set completed date if not already set
                    completed_date = form.completed_date.data
                    if not completed_date:
                        completed_date = datetime.now().date()
                else:
                    # If unchecking completed, clear the completed date
                    completed_date = None
                
                cur.execute("""
                    UPDATE brew_task SET 
                        scheduled_date = %s, completed_date = %s, action = %s,
                        is_completed = %s, notes = %s, updated_date = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    form.scheduled_date.data,
                    completed_date,
                    form.action.data,
                    form.is_completed.data,
                    form.notes.data,
                    task_id
                ))
                
                conn.commit()
                flash('Brew task updated successfully!', 'success')
                return redirect(url_for('brew_detail', brew_id=brew_task['brew_id']))
    
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        conn.rollback()
    finally:
        conn.close()
    
    return render_template('edit_brew_task.html', form=form, brew_task=brew_task)

@app.route('/brew-task/<int:task_id>/delete', methods=['POST'])
@require_permission('brews', 'edit')
def delete_brew_task(task_id):
    """Delete a brew task"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('brews'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get brew_id before deleting
            cur.execute("SELECT brew_id FROM brew_task WHERE id = %s", (task_id,))
            result = cur.fetchone()
            
            if not result:
                flash('Brew task not found', 'error')
                return redirect(url_for('brews'))
            
            brew_id = result['brew_id']
            
            # Delete the task
            cur.execute("DELETE FROM brew_task WHERE id = %s", (task_id,))
            conn.commit()
            
            flash('Brew task deleted successfully!', 'success')
            return redirect(url_for('brew_detail', brew_id=brew_id))
    
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        conn.rollback()
        return redirect(url_for('brews'))
    finally:
        conn.close()

@app.route('/api/recipe/<int:recipe_id>')
@require_permission('brews', 'view')
def api_recipe_data(recipe_id):
    """API endpoint to get recipe data for brew creation"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection error'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT name, style, target_abv, target_og, target_fg, batch_size_liters
                FROM recipe WHERE id = %s
            """, (recipe_id,))
            
            recipe = cur.fetchone()
            if recipe:
                return jsonify(dict(recipe))
            else:
                return jsonify({'error': 'Recipe not found'}), 404
    
    except psycopg2.Error as e:
        return jsonify({'error': 'Database error'}), 500
    finally:
        conn.close()

@app.route('/api/kit/<int:kit_id>')
@require_permission('brews', 'view')
def api_kit_data(kit_id):
    """API endpoint to get kit data for brew creation"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Database connection error'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT name, style, estimated_abv, volume_liters
                FROM kit WHERE id = %s
            """, (kit_id,))
            
            kit = cur.fetchone()
            if kit:
                return jsonify(dict(kit))
            else:
                return jsonify({'error': 'Kit not found'}), 404
    
    except psycopg2.Error as e:
        return jsonify({'error': 'Database error'}), 500
    finally:
        conn.close()

# ========================================
# Brew Task Management API Endpoints
# ========================================

@app.route('/api/brew-task/add', methods=['POST'])
@require_permission('brews', 'edit')
def api_add_brew_task():
    """API endpoint to add a new brew task"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        data = request.get_json()
        brew_id = data.get('brew_id')
        
        # Verify brew exists
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id FROM brew WHERE id = %s", (brew_id,))
            if not cur.fetchone():
                return jsonify({'success': False, 'message': 'Brew not found'}), 404
            
            # Insert new brew task
            cur.execute("""
                INSERT INTO brew_task 
                (brew_id, scheduled_date, action, notes)
                VALUES (%s, %s, %s, %s)
            """, (
                brew_id,
                data.get('scheduled_date'),
                data.get('action'),
                data.get('notes')
            ))
            
            conn.commit()
            return jsonify({'success': True, 'message': 'Brew task added successfully'})
            
    except psycopg2.Error as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error adding brew task: {e}'}), 500
    finally:
        conn.close()

@app.route('/api/brew-task/<int:task_id>/edit', methods=['PUT'])
@require_permission('brews', 'edit')
def api_edit_brew_task(task_id):
    """API endpoint to edit a brew task"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        data = request.get_json()
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Verify brew task exists
            cur.execute("SELECT id FROM brew_task WHERE id = %s", (task_id,))
            if not cur.fetchone():
                return jsonify({'success': False, 'message': 'Brew task not found'}), 404
            
            # Update brew task
            cur.execute("""
                UPDATE brew_task 
                SET scheduled_date = %s, action = %s, notes = %s, 
                    updated_date = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (
                data.get('scheduled_date'),
                data.get('action'),
                data.get('notes'),
                task_id
            ))
            
            conn.commit()
            return jsonify({'success': True, 'message': 'Brew task updated successfully'})
            
    except psycopg2.Error as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error updating brew task: {e}'}), 500
    finally:
        conn.close()

@app.route('/api/brew-task/<int:task_id>/delete', methods=['DELETE'])
@require_permission('brews', 'edit')
def api_delete_brew_task(task_id):
    """API endpoint to delete a brew task"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Verify and delete brew task
            cur.execute("DELETE FROM brew_task WHERE id = %s RETURNING id", (task_id,))
            if cur.fetchone():
                conn.commit()
                return jsonify({'success': True, 'message': 'Brew task deleted successfully'})
            else:
                return jsonify({'success': False, 'message': 'Brew task not found'}), 404
            
    except psycopg2.Error as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error deleting brew task: {e}'}), 500
    finally:
        conn.close()

@app.route('/api/brew-task/<int:task_id>/complete', methods=['POST'])
@require_permission('brews', 'edit')
def api_complete_brew_task(task_id):
    """API endpoint to mark a brew task as completed with date validation"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        data = request.get_json()
        completed_date = data.get('completed_date', str(datetime.now().date()))
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get scheduled date for comparison
            cur.execute("""
                SELECT scheduled_date FROM brew_task WHERE id = %s
            """, (task_id,))
            
            result = cur.fetchone()
            if not result:
                return jsonify({'success': False, 'message': 'Brew task not found'}), 404
            
            scheduled_date = result['scheduled_date']
            completed_date_obj = datetime.strptime(completed_date, '%Y-%m-%d').date()
            
            # Check for date mismatch warning
            warning = None
            if scheduled_date != completed_date_obj:
                warning = f'Task was scheduled for {scheduled_date.strftime("%Y-%m-%d")} but marked completed on {completed_date}'
            
            # Update brew task to completed
            cur.execute("""
                UPDATE brew_task 
                SET is_completed = TRUE, completed_date = %s, updated_date = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (completed_date, task_id))
            
            conn.commit()
            
            response = {'success': True, 'message': 'Brew task marked as completed'}
            if warning:
                response['warning'] = warning
            
            return jsonify(response)
            
    except (psycopg2.Error, ValueError) as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error completing brew task: {e}'}), 500
    finally:
        conn.close()

@app.route('/api/brew-task/<int:task_id>/uncomplete', methods=['POST'])
@require_permission('brews', 'edit')
def api_uncomplete_brew_task(task_id):
    """API endpoint to undo completion of a brew task"""
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'message': 'Database connection error'}), 500
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Update brew task to not completed
            cur.execute("""
                UPDATE brew_task 
                SET is_completed = FALSE, completed_date = NULL, updated_date = CURRENT_TIMESTAMP
                WHERE id = %s RETURNING id
            """, (task_id,))
            
            if cur.fetchone():
                conn.commit()
                return jsonify({'success': True, 'message': 'Brew task completion undone'})
            else:
                return jsonify({'success': False, 'message': 'Brew task not found'}), 404
            
    except psycopg2.Error as e:
        conn.rollback()
        return jsonify({'success': False, 'message': f'Error uncompleting brew task: {e}'}), 500
    finally:
        conn.close()

@app.route('/recipes')
@require_permission('recipes', 'view')
def recipes():
    """View all recipes with versioning support"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get latest version of each recipe (only the highest version number per recipe name)
            cur.execute("""
                SELECT r.*, COUNT(b.id) as brew_count,
                       CASE WHEN r.target_abv IS NOT NULL THEN r.target_abv ELSE 0 END as target_abv,
                       CASE WHEN r.ibu IS NOT NULL THEN r.ibu ELSE 0 END as ibu,
                       CASE WHEN r.batch_size_liters IS NOT NULL THEN r.batch_size_liters ELSE 0 END as batch_size_liters,
                       (SELECT COUNT(*) FROM recipe r2 WHERE r2.name = r.name) as version_count
                FROM recipe r
                LEFT JOIN brew b ON r.id = b.recipe_id
                WHERE r.id IN (
                    SELECT DISTINCT ON (name) id
                    FROM recipe
                    WHERE is_active = true
                    ORDER BY name, version DESC
                )
                GROUP BY r.id
                ORDER BY r.name, r.version DESC
            """)
            recipes = cur.fetchall()
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        recipes = []
    finally:
        conn.close()
    
    return render_template('recipes.html', recipes=recipes)

@app.route('/recipe/<int:recipe_id>')
@require_permission('recipes', 'view')
def recipe_detail(recipe_id):
    """View detailed recipe with all ingredients and versions"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get recipe details
            cur.execute("""
                SELECT r.*, u.username as created_by_name
                FROM recipe r
                LEFT JOIN users u ON r.created_by = u.id
                WHERE r.id = %s
            """, (recipe_id,))
            recipe = cur.fetchone()
            
            if not recipe:
                flash('Recipe not found', 'error')
                return redirect(url_for('recipes'))
            
            # Get malts
            cur.execute("""
                SELECT * FROM recipe_malts 
                WHERE recipe_id = %s 
                ORDER BY sort_order, id
            """, (recipe_id,))
            malts = cur.fetchall()
            
            # Get hops
            cur.execute("""
                SELECT * FROM recipe_hops 
                WHERE recipe_id = %s 
                ORDER BY time_minutes DESC, sort_order, id
            """, (recipe_id,))
            hops = cur.fetchall()
            
            # Get yeast
            cur.execute("""
                SELECT * FROM recipe_yeast 
                WHERE recipe_id = %s 
                ORDER BY sort_order, id
            """, (recipe_id,))
            yeast = cur.fetchall()
            
            # Get adjuncts
            cur.execute("""
                SELECT * FROM recipe_adjuncts 
                WHERE recipe_id = %s 
                ORDER BY sort_order, id
            """, (recipe_id,))
            adjuncts = cur.fetchall()
            
            # Get recipe versions - find all recipes with same name
            cur.execute("""
                SELECT id, version, last_modified, notes, is_active,
                       CASE WHEN id = %s THEN true ELSE false END as is_current
                FROM recipe 
                WHERE name = (SELECT name FROM recipe WHERE id = %s)
                ORDER BY version DESC
            """, (recipe_id, recipe_id))
            versions = cur.fetchall()
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        return redirect(url_for('recipes'))
    finally:
        conn.close()
    
    return render_template('recipe_detail.html', 
                         recipe=recipe, malts=malts, hops=hops, 
                         yeast=yeast, adjuncts=adjuncts, versions=versions)

@app.route('/recipe/<int:recipe_id>/shopping-cart')
@require_permission('recipes', 'view')
def recipe_shopping_cart(recipe_id):
    """Generate shopping cart/ingredient list for a recipe"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('recipes'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get recipe details
            cur.execute("""
                SELECT r.*, u.username as created_by_name
                FROM recipe r
                LEFT JOIN users u ON r.created_by = u.id
                WHERE r.id = %s
            """, (recipe_id,))
            recipe = cur.fetchone()
            
            if not recipe:
                flash('Recipe not found', 'error')
                return redirect(url_for('recipes'))
            
            # Get all ingredients for shopping list (aggregated by name)
            # Malts - sum by malt name
            cur.execute("""
                SELECT malt_name as name, 
                       SUM(amount_kg) as amount_kg, 
                       STRING_AGG(DISTINCT malt_type, ', ') as malt_type,
                       AVG(lovibond) as lovibond
                FROM recipe_malts 
                WHERE recipe_id = %s 
                GROUP BY malt_name
                ORDER BY SUM(amount_kg) DESC
            """, (recipe_id,))
            malts = cur.fetchall()
            
            # Hops - sum by hop name (remove boil time from display)
            cur.execute("""
                SELECT hop_name as variety, 
                       SUM(amount_grams) as amount_g, 
                       AVG(alpha_acid) as alpha_acid,
                       STRING_AGG(DISTINCT hop_type, ', ') as hop_type
                FROM recipe_hops 
                WHERE recipe_id = %s 
                GROUP BY hop_name
                ORDER BY SUM(amount_grams) DESC
            """, (recipe_id,))
            hops = cur.fetchall()
            
            # Yeast - aggregate by name
            cur.execute("""
                SELECT yeast_name as strain, 
                       STRING_AGG(DISTINCT yeast_type, ', ') as yeast_type, 
                       STRING_AGG(DISTINCT amount, ', ') as amount, 
                       STRING_AGG(DISTINCT temperature_range, ', ') as temperature_range
                FROM recipe_yeast 
                WHERE recipe_id = %s
                GROUP BY yeast_name
                ORDER BY yeast_name
            """, (recipe_id,))
            yeast = cur.fetchall()
            
            # Adjuncts - aggregate by name
            cur.execute("""
                SELECT ingredient_name as name, 
                       STRING_AGG(DISTINCT amount, ', ') as amount, 
                       STRING_AGG(DISTINCT ingredient_type, ', ') as adjunct_type, 
                       STRING_AGG(DISTINCT time_added, ', ') as addition_time
                FROM recipe_adjuncts 
                WHERE recipe_id = %s 
                GROUP BY ingredient_name
                ORDER BY ingredient_name
            """, (recipe_id,))
            adjuncts = cur.fetchall()
    
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        return redirect(url_for('recipes'))
    finally:
        conn.close()
    
    return render_template('recipe_shopping_cart.html', 
                         recipe=recipe, malts=malts, hops=hops, 
                         yeast=yeast, adjuncts=adjuncts)

@app.route('/recipe/<int:recipe_id>/edit', methods=['GET', 'POST'])
@require_permission('recipes', 'edit')
def edit_recipe(recipe_id):
    """Edit recipe - creates new version"""
    if request.method == 'POST':
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('recipe_detail', recipe_id=recipe_id))
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get current recipe
                cur.execute("SELECT * FROM recipe WHERE id = %s", (recipe_id,))
                current_recipe = cur.fetchone()
                
                if not current_recipe:
                    flash('Recipe not found', 'error')
                    return redirect(url_for('recipes'))
                
                # Get the action type from the form
                action = request.form.get('action', 'new_version')
                
                if action == 'update':
                    # Update current recipe in place
                    cur.execute("""
                        UPDATE recipe SET 
                        name = %s, style = %s, description = %s, batch_size_liters = %s, boil_time_minutes = %s,
                        target_abv = %s, target_og = %s, target_fg = %s, ibu = %s, efficiency_percent = %s,
                        mash_schedule = %s, brewing_instructions = %s, last_modified = %s
                        WHERE id = %s
                    """, (
                        request.form.get('name', current_recipe['name']),
                        request.form.get('style', current_recipe['style']),
                        request.form.get('description', current_recipe.get('description', '')),
                        float(request.form.get('batch_size_liters', 0)) if request.form.get('batch_size_liters') else None,
                        int(request.form.get('boil_time_minutes', 0)) if request.form.get('boil_time_minutes') else None,
                        float(request.form.get('target_abv', 0)) if request.form.get('target_abv') else None,
                        float(request.form.get('target_og', 0)) if request.form.get('target_og') else None,
                        float(request.form.get('target_fg', 0)) if request.form.get('target_fg') else None,
                        float(request.form.get('ibu', 0)) if request.form.get('ibu') else None,
                        float(request.form.get('efficiency_percent', 0)) if request.form.get('efficiency_percent') else None,
                        request.form.get('mash_schedule', current_recipe.get('mash_schedule', '')),
                        request.form.get('brewing_instructions', current_recipe.get('brewing_instructions', '')),
                        datetime.now(),
                        recipe_id
                    ))
                    
                    # Update ingredients for current recipe
                    # Clear existing ingredients
                    cur.execute("DELETE FROM recipe_malts WHERE recipe_id = %s", (recipe_id,))
                    cur.execute("DELETE FROM recipe_hops WHERE recipe_id = %s", (recipe_id,))
                    cur.execute("DELETE FROM recipe_yeast WHERE recipe_id = %s", (recipe_id,))
                    
                    updated_recipe_id = recipe_id
                    flash(f'Recipe updated successfully (version {current_recipe["version"]})', 'success')
                    
                else:
                    # Create new version
                    new_version = float(current_recipe['version']) + 0.1
                    
                    cur.execute("""
                        INSERT INTO recipe (name, style, description, batch_size_liters, boil_time_minutes,
                                          target_abv, target_og, target_fg, ibu, efficiency_percent,
                                          mash_schedule, brewing_instructions, notes, version, is_active,
                                          parent_recipe_id, created_by, last_modified)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        request.form.get('name', current_recipe['name']),
                        request.form.get('style', current_recipe['style']),
                        request.form.get('description', current_recipe.get('description', '')),
                        float(request.form.get('batch_size_liters', 0)) if request.form.get('batch_size_liters') else None,
                        int(request.form.get('boil_time_minutes', 0)) if request.form.get('boil_time_minutes') else None,
                        float(request.form.get('target_abv', 0)) if request.form.get('target_abv') else None,
                        float(request.form.get('target_og', 0)) if request.form.get('target_og') else None,
                        float(request.form.get('target_fg', 0)) if request.form.get('target_fg') else None,
                        float(request.form.get('ibu', 0)) if request.form.get('ibu') else None,
                        float(request.form.get('efficiency_percent', 0)) if request.form.get('efficiency_percent') else None,
                        request.form.get('mash_schedule', current_recipe.get('mash_schedule', '')),
                        request.form.get('brewing_instructions', current_recipe.get('brewing_instructions', '')),
                        request.form.get('notes', ''),
                        new_version,
                        True,
                        current_recipe.get('parent_recipe_id') or current_recipe['id'],
                        current_user.id,
                        datetime.now()
                    ))
                    
                    updated_recipe_id = cur.fetchone()['id']
                    
                    # Copy ingredients from old version to new version first
                    # Copy malts
                    cur.execute("""
                        INSERT INTO recipe_malts (recipe_id, malt_name, amount_kg, malt_type, lovibond, percentage, notes, sort_order)
                        SELECT %s, malt_name, amount_kg, malt_type, lovibond, percentage, notes, sort_order
                        FROM recipe_malts WHERE recipe_id = %s
                    """, (updated_recipe_id, recipe_id))
                    
                    # Copy hops
                    cur.execute("""
                        INSERT INTO recipe_hops (recipe_id, hop_name, amount_grams, alpha_acid, time_minutes, hop_type, hop_form, notes, sort_order)
                        SELECT %s, hop_name, amount_grams, alpha_acid, time_minutes, hop_type, hop_form, notes, sort_order
                        FROM recipe_hops WHERE recipe_id = %s
                    """, (updated_recipe_id, recipe_id))
                    
                    # Copy yeast
                    cur.execute("""
                        INSERT INTO recipe_yeast (recipe_id, yeast_name, yeast_type, manufacturer, product_code, amount, attenuation, temperature_range, notes, sort_order)
                        SELECT %s, yeast_name, yeast_type, manufacturer, product_code, amount, attenuation, temperature_range, notes, sort_order
                        FROM recipe_yeast WHERE recipe_id = %s
                    """, (updated_recipe_id, recipe_id))
                    
                    # Copy adjuncts
                    cur.execute("""
                        INSERT INTO recipe_adjuncts (recipe_id, ingredient_name, amount, ingredient_type, time_added, notes, sort_order)
                        SELECT %s, ingredient_name, amount, ingredient_type, time_added, notes, sort_order
                        FROM recipe_adjuncts WHERE recipe_id = %s
                    """, (updated_recipe_id, recipe_id))
                    
                    # Clear existing ingredients for new version (we copied them above, now we replace with form data)
                    cur.execute("DELETE FROM recipe_malts WHERE recipe_id = %s", (updated_recipe_id,))
                    cur.execute("DELETE FROM recipe_hops WHERE recipe_id = %s", (updated_recipe_id,))
                    cur.execute("DELETE FROM recipe_yeast WHERE recipe_id = %s", (updated_recipe_id,))
                    
                    # Mark old versions as inactive and set new version as the only active one
                    cur.execute("UPDATE recipe SET is_active = false WHERE name = %s", (current_recipe['name'],))
                    cur.execute("UPDATE recipe SET is_active = true WHERE id = %s", (updated_recipe_id,))
                    
                    flash(f'New recipe version {new_version} created successfully', 'success')
                
                # Process malts
                malt_names = request.form.getlist('malt_name[]')
                malt_amounts = request.form.getlist('malt_amount[]')
                malt_types = request.form.getlist('malt_type[]')
                malt_lovibonds = request.form.getlist('malt_lovibond[]')
                
                for i, name in enumerate(malt_names):
                    if name.strip():  # Only add non-empty entries
                        cur.execute("""
                            INSERT INTO recipe_malts (recipe_id, malt_name, amount_kg, malt_type, lovibond, sort_order)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            updated_recipe_id, name.strip(),
                            float(malt_amounts[i]) if malt_amounts[i] else None,
                            malt_types[i].strip() if malt_types[i] else None,
                            float(malt_lovibonds[i]) if malt_lovibonds[i] else None,
                            i + 1
                        ))
                
                # Process hops
                hop_names = request.form.getlist('hop_name[]')
                hop_amounts = request.form.getlist('hop_amount[]')
                hop_alphas = request.form.getlist('hop_alpha[]')
                hop_times = request.form.getlist('hop_time[]')
                hop_types = request.form.getlist('hop_type[]')
                
                for i, name in enumerate(hop_names):
                    if name.strip():  # Only add non-empty entries
                        cur.execute("""
                            INSERT INTO recipe_hops (recipe_id, hop_name, amount_grams, alpha_acid, time_minutes, hop_type, sort_order)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            updated_recipe_id, name.strip(),
                            float(hop_amounts[i]) if hop_amounts[i] else None,
                            float(hop_alphas[i]) if hop_alphas[i] else None,
                            int(hop_times[i]) if hop_times[i] else None,
                            hop_types[i].strip() if hop_types[i] else None,
                            i + 1
                        ))
                
                # Process yeast
                yeast_names = request.form.getlist('yeast_name[]')
                yeast_types = request.form.getlist('yeast_type[]')
                yeast_amounts = request.form.getlist('yeast_amount[]')
                yeast_temps = request.form.getlist('yeast_temp[]')
                
                for i, name in enumerate(yeast_names):
                    if name.strip():  # Only add non-empty entries
                        cur.execute("""
                            INSERT INTO recipe_yeast (recipe_id, yeast_name, yeast_type, amount, temperature_range, sort_order)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            updated_recipe_id, name.strip(),
                            yeast_types[i].strip() if yeast_types[i] else None,
                            yeast_amounts[i].strip() if yeast_amounts[i] else None,
                            yeast_temps[i].strip() if yeast_temps[i] else None,
                            i + 1
                        ))
                
                conn.commit()
                return redirect(url_for('recipe_detail', recipe_id=updated_recipe_id))
                
        except psycopg2.Error as e:
            conn.rollback()
            flash(f'Database error: {e}', 'error')
        finally:
            conn.close()
    
    # GET request - show edit form
    return redirect(url_for('recipe_detail', recipe_id=recipe_id))

@app.route('/recipe/<int:recipe_id>/update-version', methods=['POST'])
def update_version_number(recipe_id):
    """Admin: Update recipe version number"""
    if not current_user.is_authenticated or current_user.role_name != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('recipe_detail', recipe_id=recipe_id))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('recipe_detail', recipe_id=recipe_id))
    
    try:
        new_version = float(request.form.get('new_version', 0))
        if new_version <= 0:
            flash('Version number must be positive', 'error')
            return redirect(url_for('recipe_detail', recipe_id=recipe_id))
        
        with conn.cursor() as cur:
            # Check if version already exists for this recipe family
            cur.execute("""
                SELECT id FROM recipe 
                WHERE name = (SELECT name FROM recipe WHERE id = %s) 
                AND version = %s AND id != %s
            """, (recipe_id, new_version, recipe_id))
            
            if cur.fetchone():
                flash(f'Version {new_version} already exists for this recipe', 'error')
                return redirect(url_for('recipe_detail', recipe_id=recipe_id))
            
            # Update version number
            cur.execute("UPDATE recipe SET version = %s WHERE id = %s", (new_version, recipe_id))
            conn.commit()
            flash(f'Version number updated to {new_version}', 'success')
            
    except (ValueError, psycopg2.Error) as e:
        conn.rollback()
        flash(f'Error updating version: {e}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('recipe_detail', recipe_id=recipe_id))

@app.route('/recipe/<int:recipe_id>/delete-version', methods=['POST'])
def delete_recipe_version(recipe_id):
    """Admin: Delete a specific recipe version"""
    if not current_user.is_authenticated or current_user.role_name != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('recipes'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('recipes'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get recipe info before deletion
            cur.execute("SELECT name, version, is_active FROM recipe WHERE id = %s", (recipe_id,))
            recipe = cur.fetchone()
            
            if not recipe:
                flash('Recipe not found', 'error')
                return redirect(url_for('recipes'))
            
            # Check if this is the only version
            cur.execute("SELECT COUNT(*) as count FROM recipe WHERE name = %s", (recipe['name'],))
            version_count_result = cur.fetchone()
            version_count = version_count_result['count']
            
            if version_count <= 1:
                flash('Cannot delete the only version of a recipe. Use "Delete Recipe" instead.', 'error')
                return redirect(url_for('recipe_detail', recipe_id=recipe_id))
            
            was_active = recipe['is_active']
            
            # Delete ingredients first (foreign key constraints)
            cur.execute("DELETE FROM recipe_malts WHERE recipe_id = %s", (recipe_id,))
            cur.execute("DELETE FROM recipe_hops WHERE recipe_id = %s", (recipe_id,))
            cur.execute("DELETE FROM recipe_yeast WHERE recipe_id = %s", (recipe_id,))
            cur.execute("DELETE FROM recipe_adjuncts WHERE recipe_id = %s", (recipe_id,))
            
            # Delete the recipe version
            cur.execute("DELETE FROM recipe WHERE id = %s", (recipe_id,))
            
            # If we deleted the active version, make the highest version number the new active one
            if was_active:
                cur.execute("""
                    SELECT id FROM recipe 
                    WHERE name = %s 
                    ORDER BY version DESC 
                    LIMIT 1
                """, (recipe['name'],))
                highest_version = cur.fetchone()
                
                if highest_version:
                    cur.execute("UPDATE recipe SET is_active = true WHERE id = %s", (highest_version['id'],))
            
            conn.commit()
            flash(f'Version {recipe["version"]} of "{recipe["name"]}" deleted successfully', 'success')
            
            # Redirect to the current active version
            cur.execute("SELECT id FROM recipe WHERE name = %s AND is_active = true", (recipe['name'],))
            active_recipe = cur.fetchone()
            if active_recipe:
                return redirect(url_for('recipe_detail', recipe_id=active_recipe['id']))
            else:
                # Fallback to highest version if no active version (shouldn't happen)
                cur.execute("SELECT id FROM recipe WHERE name = %s ORDER BY version DESC LIMIT 1", (recipe['name'],))
                remaining_recipe = cur.fetchone()
                if remaining_recipe:
                    return redirect(url_for('recipe_detail', recipe_id=remaining_recipe['id']))
                else:
                    return redirect(url_for('recipes'))
                
    except psycopg2.Error as e:
        conn.rollback()
        flash(f'Error deleting version: {e}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('recipes'))

@app.route('/recipe/<int:recipe_id>/set-active', methods=['POST'])
def set_active_version(recipe_id):
    """Admin: Set a specific recipe version as active"""
    if not current_user.is_authenticated or current_user.role_name != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('recipes'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('recipes'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get recipe info
            cur.execute("SELECT name, version FROM recipe WHERE id = %s", (recipe_id,))
            recipe = cur.fetchone()
            
            if not recipe:
                flash('Recipe not found', 'error')
                return redirect(url_for('recipes'))
            
            # Set all versions of this recipe as inactive
            cur.execute("UPDATE recipe SET is_active = false WHERE name = %s", (recipe['name'],))
            
            # Set the selected version as active
            cur.execute("UPDATE recipe SET is_active = true WHERE id = %s", (recipe_id,))
            
            conn.commit()
            flash(f'Version {recipe["version"]} of "{recipe["name"]}" is now the active version', 'success')
            
            return redirect(url_for('recipe_detail', recipe_id=recipe_id))
                
    except psycopg2.Error as e:
        conn.rollback()
        flash(f'Error setting active version: {e}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('recipes'))

@app.route('/recipe/delete-entire/<recipe_name>', methods=['POST'])
def delete_entire_recipe(recipe_name):
    """Admin: Delete all versions of a recipe"""
    if not current_user.is_authenticated or current_user.role_name != 'admin':
        flash('Admin access required', 'error')
        return redirect(url_for('recipes'))
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('recipes'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get all recipe IDs for this recipe name
            cur.execute("SELECT id FROM recipe WHERE name = %s", (recipe_name,))
            recipe_ids = [row['id'] for row in cur.fetchall()]
            
            if not recipe_ids:
                flash('Recipe not found', 'error')
                return redirect(url_for('recipes'))
            
            # Check if any version is used in brews
            placeholders = ','.join(['%s'] * len(recipe_ids))
            cur.execute(f"""
                SELECT COUNT(*) as brew_count, 
                       STRING_AGG(DISTINCT b.name, ', ') as brew_names
                FROM brew b 
                WHERE b.recipe_id IN ({placeholders})
            """, tuple(recipe_ids))
            
            result = cur.fetchone()
            if result and result['brew_count'] > 0:
                flash(
                    f'Cannot delete "{recipe_name}". This recipe is used in {result["brew_count"]} brew(s): {result["brew_names"]}. '
                    f'Please delete or update the brews first.',
                    'error'
                )
                return redirect(url_for('recipes'))
            
            # Delete all ingredients for all versions (CASCADE should handle this, but being explicit)
            for recipe_id in recipe_ids:
                cur.execute("DELETE FROM recipe_malts WHERE recipe_id = %s", (recipe_id,))
                cur.execute("DELETE FROM recipe_hops WHERE recipe_id = %s", (recipe_id,))
                cur.execute("DELETE FROM recipe_yeast WHERE recipe_id = %s", (recipe_id,))
                cur.execute("DELETE FROM recipe_adjuncts WHERE recipe_id = %s", (recipe_id,))
            
            # Delete all recipe versions
            cur.execute("DELETE FROM recipe WHERE name = %s", (recipe_name,))
            
            conn.commit()
            flash(f'All versions of "{recipe_name}" deleted successfully', 'success')
            
    except psycopg2.Error as e:
        conn.rollback()
        flash(f'Error deleting recipe: {e}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('recipes'))

@app.route('/recipe/create', methods=['GET', 'POST'])
@require_permission('recipes', 'edit')
def create_recipe():
    """Create new recipe"""
    if request.method == 'POST':
        conn = get_db_connection()
        if not conn:
            flash('Database connection error', 'error')
            return redirect(url_for('recipes'))
        
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Create new recipe
                cur.execute("""
                    INSERT INTO recipe (name, style, description, batch_size_liters, boil_time_minutes,
                                      target_abv, target_og, target_fg, ibu, efficiency_percent,
                                      mash_schedule, brewing_instructions, notes, version, is_active,
                                      created_by, last_modified)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    request.form.get('name', ''),
                    request.form.get('style', ''),
                    request.form.get('description', ''),
                    float(request.form.get('batch_size_liters', 0)) if request.form.get('batch_size_liters') else None,
                    int(request.form.get('boil_time_minutes', 0)) if request.form.get('boil_time_minutes') else None,
                    float(request.form.get('target_abv', 0)) if request.form.get('target_abv') else None,
                    float(request.form.get('target_og', 0)) if request.form.get('target_og') else None,
                    float(request.form.get('target_fg', 0)) if request.form.get('target_fg') else None,
                    float(request.form.get('ibu', 0)) if request.form.get('ibu') else None,
                    float(request.form.get('efficiency_percent', 0)) if request.form.get('efficiency_percent') else None,
                    request.form.get('mash_schedule', ''),
                    request.form.get('brewing_instructions', ''),
                    request.form.get('notes', ''),
                    1.0,
                    True,
                    current_user.id,
                    datetime.now()
                ))
                
                new_recipe_id = cur.fetchone()['id']
                
                # Process malts
                malt_names = request.form.getlist('malt_name[]')
                malt_amounts = request.form.getlist('malt_amount[]')
                malt_types = request.form.getlist('malt_type[]')
                malt_lovibonds = request.form.getlist('malt_lovibond[]')
                
                for i, name in enumerate(malt_names):
                    if name.strip():  # Only add non-empty entries
                        cur.execute("""
                            INSERT INTO recipe_malts (recipe_id, malt_name, amount_kg, malt_type, lovibond, sort_order)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            new_recipe_id, name.strip(),
                            float(malt_amounts[i]) if i < len(malt_amounts) and malt_amounts[i] else None,
                            malt_types[i].strip() if i < len(malt_types) and malt_types[i] else None,
                            float(malt_lovibonds[i]) if i < len(malt_lovibonds) and malt_lovibonds[i] else None,
                            i + 1
                        ))
                
                # Process hops
                hop_names = request.form.getlist('hop_name[]')
                hop_amounts = request.form.getlist('hop_amount[]')
                hop_times = request.form.getlist('hop_time[]')
                hop_forms = request.form.getlist('hop_form[]')
                hop_alphas = request.form.getlist('hop_alpha[]')
                
                for i, name in enumerate(hop_names):
                    if name.strip():  # Only add non-empty entries
                        cur.execute("""
                            INSERT INTO recipe_hops (recipe_id, hop_name, amount_grams, time_minutes, hop_form, alpha_acid, sort_order)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            new_recipe_id, name.strip(),
                            float(hop_amounts[i]) if i < len(hop_amounts) and hop_amounts[i] else None,
                            int(hop_times[i]) if i < len(hop_times) and hop_times[i] else None,
                            hop_forms[i].strip() if i < len(hop_forms) and hop_forms[i] else None,
                            float(hop_alphas[i]) if i < len(hop_alphas) and hop_alphas[i] else None,
                            i + 1
                        ))
                
                # Process yeast
                yeast_strains = request.form.getlist('yeast_strain[]')
                yeast_types = request.form.getlist('yeast_type[]')
                yeast_amounts = request.form.getlist('yeast_amount[]')
                yeast_temp_lows = request.form.getlist('yeast_temp_low[]')
                yeast_temp_highs = request.form.getlist('yeast_temp_high[]')
                
                for i, strain in enumerate(yeast_strains):
                    if strain.strip():  # Only add non-empty entries
                        # Combine temperature range if both are provided
                        temp_range = None
                        if i < len(yeast_temp_lows) and yeast_temp_lows[i] and i < len(yeast_temp_highs) and yeast_temp_highs[i]:
                            temp_range = f"{yeast_temp_lows[i]}-{yeast_temp_highs[i]}°C"
                        elif i < len(yeast_temp_lows) and yeast_temp_lows[i]:
                            temp_range = f"{yeast_temp_lows[i]}°C"
                        elif i < len(yeast_temp_highs) and yeast_temp_highs[i]:
                            temp_range = f"{yeast_temp_highs[i]}°C"
                            
                        # Format amount as string with unit
                        amount_str = None
                        if i < len(yeast_amounts) and yeast_amounts[i]:
                            amount_str = f"{yeast_amounts[i]}g"
                        
                        cur.execute("""
                            INSERT INTO recipe_yeast (recipe_id, yeast_name, yeast_type, amount, temperature_range, sort_order)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (
                            new_recipe_id, strain.strip(),
                            yeast_types[i].strip() if i < len(yeast_types) and yeast_types[i] else None,
                            amount_str,
                            temp_range,
                            i + 1
                        ))
                
                conn.commit()
                
                flash('Recipe created successfully with ingredients', 'success')
                return redirect(url_for('recipe_detail', recipe_id=new_recipe_id))
                
        except psycopg2.Error as e:
            conn.rollback()
            flash(f'Database error: {e}', 'error')
        finally:
            conn.close()
    
    return render_template('create_recipe.html')


@app.route('/recipe/import', methods=['GET', 'POST'])
@login_required
def import_recipe():
    """Import recipe from BeerXML file (available to brewer, economy, and admin)"""
    # Check if user has appropriate role
    if current_user.role_name not in ['admin', 'brewer', 'economy']:
        flash(_('You do not have permission to import recipes.'), 'error')
        return redirect(url_for('recipes'))
    
    if request.method == 'POST':
        # Check if file was uploaded
        if 'beerxml_file' not in request.files:
            flash(_('No file selected'), 'error')
            return redirect(request.url)
        
        file = request.files['beerxml_file']
        
        if file.filename == '':
            flash(_('No file selected'), 'error')
            return redirect(request.url)
        
        if not file.filename.lower().endswith('.xml'):
            flash(_('File must be a BeerXML (.xml) file'), 'error')
            return redirect(request.url)
        
        try:
            # Read XML content
            xml_content = file.read().decode('utf-8')
            
            # Import using BeerXMLHandler
            conn = get_db_connection()
            if not conn:
                flash(_('Database connection error'), 'error')
                return redirect(url_for('recipes'))
            
            try:
                handler = BeerXMLHandler(conn)
                result = handler.import_from_xml(xml_content, user_id=current_user.id)
                
                if result['success']:
                    recipe_names = ', '.join([r['name'] for r in result['recipes']])
                    flash(ngettext(
                        'Successfully imported %(count)d recipe: %(names)s',
                        'Successfully imported %(count)d recipes: %(names)s',
                        result['count'],
                        count=result['count'],
                        names=recipe_names
                    ), 'success')
                    
                    # Redirect to first imported recipe if only one
                    if result['count'] == 1:
                        return redirect(url_for('recipe_detail', recipe_id=result['recipes'][0]['id']))
                    else:
                        return redirect(url_for('recipes'))
                else:
                    flash(_('Import failed: %(error)s', error=result.get('error', 'Unknown error')), 'error')
                    return redirect(request.url)
                    
            finally:
                conn.close()
                
        except UnicodeDecodeError:
            flash(_('Invalid file encoding. File must be UTF-8 encoded XML.'), 'error')
            return redirect(request.url)
        except Exception as e:
            flash(_('Error importing recipe: %(error)s', error=str(e)), 'error')
            return redirect(request.url)
    
    return render_template('import_recipe.html')


@app.route('/recipe/<int:recipe_id>/export')
@login_required
def export_recipe(recipe_id):
    """Export single recipe to BeerXML format (available to all users)"""
    conn = get_db_connection()
    if not conn:
        flash(_('Database connection error'), 'error')
        return redirect(url_for('recipes'))
    
    try:
        # Verify recipe exists
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT name FROM recipe WHERE id = %s", (recipe_id,))
            recipe = cur.fetchone()
            
            if not recipe:
                flash(_('Recipe not found'), 'error')
                return redirect(url_for('recipes'))
        
        # Export using BeerXMLHandler
        handler = BeerXMLHandler(conn)
        xml_content = handler.export_to_xml(recipe_id)
        
        if xml_content:
            # Create safe filename
            safe_name = secure_filename(recipe['name'])
            filename = f"{safe_name}.xml"
            
            # Send file
            from io import BytesIO
            xml_bytes = BytesIO(xml_content.encode('utf-8'))
            
            return send_file(
                xml_bytes,
                mimetype='application/xml',
                as_attachment=True,
                download_name=filename
            )
        else:
            flash(_('Error exporting recipe'), 'error')
            return redirect(url_for('recipe_detail', recipe_id=recipe_id))
            
    finally:
        conn.close()


@app.route('/recipes/export', methods=['POST'])
@login_required
def export_multiple_recipes():
    """Export multiple recipes to single BeerXML file (available to all users)"""
    # Get selected recipe IDs from form
    recipe_ids = request.form.getlist('recipe_ids[]')
    
    if not recipe_ids:
        flash(_('No recipes selected for export'), 'error')
        return redirect(url_for('recipes'))
    
    try:
        recipe_ids = [int(rid) for rid in recipe_ids]
    except ValueError:
        flash(_('Invalid recipe selection'), 'error')
        return redirect(url_for('recipes'))
    
    conn = get_db_connection()
    if not conn:
        flash(_('Database connection error'), 'error')
        return redirect(url_for('recipes'))
    
    try:
        # Export using BeerXMLHandler
        handler = BeerXMLHandler(conn)
        xml_content = handler.export_multiple_recipes(recipe_ids)
        
        if xml_content:
            # Create filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"recipes_export_{timestamp}.xml"
            
            # Send file
            from io import BytesIO
            xml_bytes = BytesIO(xml_content.encode('utf-8'))
            
            return send_file(
                xml_bytes,
                mimetype='application/xml',
                as_attachment=True,
                download_name=filename
            )
        else:
            flash(_('Error exporting recipes'), 'error')
            return redirect(url_for('recipes'))
            
    finally:
        conn.close()


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
# KIT MANAGEMENT ROUTES
# ==========================================

@app.route('/kits')
@require_permission('kits', 'view')
def kits():
    """View all kits"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT k.*, COUNT(b.id) as brew_count
                FROM kit k
                LEFT JOIN brew b ON k.id = b.kit_id
                GROUP BY k.id
                ORDER BY k.name
            """)
            kits = cur.fetchall()
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        kits = []
    finally:
        conn.close()
    
    return render_template('kits.html', kits=kits)

@app.route('/kit/<int:kit_id>')
@require_permission('kits', 'view')
def kit_detail(kit_id):
    """View detailed kit information"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return render_template('error.html')
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get kit details
            cur.execute("SELECT * FROM kit WHERE id = %s", (kit_id,))
            kit = cur.fetchone()
            
            if not kit:
                flash('Kit not found', 'error')
                return redirect(url_for('kits'))
            
            # Get brews made with this kit
            cur.execute("""
                SELECT b.*
                FROM brew b
                WHERE b.kit_id = %s
                ORDER BY b.date_brewed DESC
            """, (kit_id,))
            brews = cur.fetchall()
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        return redirect(url_for('kits'))
    finally:
        conn.close()
    
    return render_template('kit_detail.html', kit=kit, brews=brews)

def save_kit_file(file, kit_id, file_type):
    """Save uploaded kit file (image or PDF) and return file info"""
    if file and allowed_kit_file(file.filename, file_type):
        # Generate unique filename with descriptive prefix
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        prefix = f"kit_{kit_id}_{file_type}_" if kit_id else f"kit_new_{file_type}_"
        unique_filename = f"{prefix}{uuid.uuid4().hex}.{file_extension}"
        
        # Ensure kits upload directory exists
        kit_upload_dir = os.path.join(os.path.dirname(__file__), 'uploads', 'kits')
        os.makedirs(kit_upload_dir, exist_ok=True)
        
        # Save file
        file_path = os.path.join(kit_upload_dir, unique_filename)
        file.save(file_path)
        
        return {
            'filename': unique_filename,
            'original_filename': file.filename,
            'file_path': file_path,
            'file_size': os.path.getsize(file_path),
            'mime_type': file.mimetype
        }
    return None

def allowed_kit_file(filename, file_type):
    """Check if file type is allowed for kits"""
    if not filename:
        return False
    
    file_extension = filename.rsplit('.', 1)[1].lower()
    
    if file_type == 'image':
        return file_extension in ['png', 'jpg', 'jpeg']
    elif file_type == 'pdf':
        return file_extension == 'pdf'
    
    return False

@app.route('/kits/create', methods=['GET', 'POST'])
@require_permission('kits', 'edit')
def create_kit():
    """Create a new kit"""
    form = CreateKitForm()
    
    if form.validate_on_submit():
        try:
            conn = get_db_connection()
            if not conn:
                flash('Database connection error', 'error')
                return render_template('create_kit.html', form=form)
            
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Insert kit
                    cur.execute("""
                        INSERT INTO kit (name, kit_type, manufacturer, style, estimated_abv, 
                                       volume_liters, cost, supplier, additional_ingredients_needed,
                                       description, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (form.name.data, form.kit_type.data, form.manufacturer.data, 
                          form.style.data, form.estimated_abv.data, form.volume_liters.data,
                          form.cost.data, form.supplier.data, form.additional_ingredients_needed.data, 
                          form.description.data, form.notes.data))
                    
                    kit_id = cur.fetchone()['id']
                    
                    # Handle file uploads
                    label_filename = None
                    pdf_filename = None
                    
                    # Handle label image upload
                    if form.label_image.data:
                        file_info = save_kit_file(form.label_image.data, kit_id, 'image')
                        if file_info:
                            label_filename = file_info['filename']
                    
                    # Handle instruction PDF upload
                    if form.instruction_pdf.data:
                        file_info = save_kit_file(form.instruction_pdf.data, kit_id, 'pdf')
                        if file_info:
                            pdf_filename = file_info['filename']
                    
                    # Update kit with file names
                    if label_filename or pdf_filename:
                        cur.execute("""
                            UPDATE kit 
                            SET label_image_filename = COALESCE(%s, label_image_filename),
                                instruction_pdf_filename = COALESCE(%s, instruction_pdf_filename)
                            WHERE id = %s
                        """, (label_filename, pdf_filename, kit_id))
                    
                    conn.commit()
                    flash(f'Kit "{form.name.data}" created successfully', 'success')
                    return redirect(url_for('kit_detail', kit_id=kit_id))
                    
            except psycopg2.Error as e:
                conn.rollback()
                flash(f'Database error: {e}', 'error')
            finally:
                conn.close()
                
        except Exception as e:
            flash(f'Error creating kit: {e}', 'error')
    
    return render_template('create_kit.html', form=form)

@app.route('/kit/<int:kit_id>/edit', methods=['GET', 'POST'])
@require_permission('kits', 'edit')
def edit_kit(kit_id):
    """Edit an existing kit"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('kits'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get kit details
            cur.execute("SELECT * FROM kit WHERE id = %s", (kit_id,))
            kit = cur.fetchone()
            
            if not kit:
                flash('Kit not found', 'error')
                return redirect(url_for('kits'))
            
            # Create form and populate with existing data
            form = EditKitForm()
            
            if form.validate_on_submit():
                
                try:
                    # Update kit basic info
                    cur.execute("""
                        UPDATE kit 
                        SET name = %s, kit_type = %s, manufacturer = %s, style = %s, 
                            estimated_abv = %s, volume_liters = %s, cost = %s, supplier = %s,
                            additional_ingredients_needed = %s, description = %s, notes = %s,
                            updated_date = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (form.name.data, form.kit_type.data, form.manufacturer.data, form.style.data, 
                          form.estimated_abv.data, form.volume_liters.data, form.cost.data, form.supplier.data,
                          form.additional_ingredients_needed.data, form.description.data, 
                          form.notes.data, kit_id))
                    
                    # Handle file uploads
                    files_updated = []
                    
                    # Handle label image upload
                    if form.label_image.data:
                        file_info = save_kit_file(form.label_image.data, kit_id, 'image')
                        if file_info:
                            cur.execute("""
                                UPDATE kit SET label_image_filename = %s WHERE id = %s
                            """, (file_info['filename'], kit_id))
                            files_updated.append('label image')
                    
                    # Handle instruction PDF upload
                    if form.instruction_pdf.data:
                        file_info = save_kit_file(form.instruction_pdf.data, kit_id, 'pdf')
                        if file_info:
                            cur.execute("""
                                UPDATE kit SET instruction_pdf_filename = %s WHERE id = %s
                            """, (file_info['filename'], kit_id))
                            files_updated.append('instruction PDF')
                    
                    conn.commit()
                    
                    success_msg = f'Kit "{form.name.data}" updated successfully'
                    if files_updated:
                        success_msg += f' (new files: {", ".join(files_updated)})'
                    
                    flash(success_msg, 'success')
                    return redirect(url_for('kit_detail', kit_id=kit_id))
                    
                except psycopg2.Error as e:
                    conn.rollback()
                    flash(f'Database error: {e}', 'error')
            else:
                # Populate form with existing data for GET request
                form.name.data = kit['name']
                form.kit_type.data = kit['kit_type']
                form.manufacturer.data = kit['manufacturer']
                form.style.data = kit['style']
                form.estimated_abv.data = kit['estimated_abv']
                form.volume_liters.data = kit['volume_liters']
                form.cost.data = kit['cost']
                form.supplier.data = kit['supplier']
                form.additional_ingredients_needed.data = kit['additional_ingredients_needed']
                form.description.data = kit['description']
                form.notes.data = kit['notes']
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        return redirect(url_for('kits'))
    finally:
        conn.close()
    
    return render_template('edit_kit.html', kit=kit, form=form)

@app.route('/kit/<int:kit_id>/delete', methods=['POST'])
@require_permission('kits', 'full')  # Only admins can delete
def delete_kit(kit_id):
    """Delete a kit (admin only)"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('kits'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Check if kit exists and get file names
            cur.execute("SELECT name, label_image_filename, instruction_pdf_filename FROM kit WHERE id = %s", (kit_id,))
            kit = cur.fetchone()
            
            if not kit:
                flash('Kit not found', 'error')
                return redirect(url_for('kits'))
            
            # Check if kit is used in any brews
            cur.execute("SELECT COUNT(*) as count FROM brew WHERE kit_id = %s", (kit_id,))
            brew_count = cur.fetchone()['count']
            
            if brew_count > 0:
                flash(f'Cannot delete kit "{kit["name"]}" - it is used in {brew_count} brew(s)', 'error')
                return redirect(url_for('kit_detail', kit_id=kit_id))
            
            # Delete the kit
            cur.execute("DELETE FROM kit WHERE id = %s", (kit_id,))
            
            # Delete associated files
            kit_upload_dir = os.path.join(os.path.dirname(__file__), 'uploads', 'kits')
            
            if kit['label_image_filename']:
                try:
                    os.remove(os.path.join(kit_upload_dir, kit['label_image_filename']))
                except OSError:
                    pass  # File might not exist
            
            if kit['instruction_pdf_filename']:
                try:
                    os.remove(os.path.join(kit_upload_dir, kit['instruction_pdf_filename']))
                except OSError:
                    pass  # File might not exist
            
            conn.commit()
            flash(f'Kit "{kit["name"]}" deleted successfully', 'success')
            
    except psycopg2.Error as e:
        conn.rollback()
        flash(f'Database error: {e}', 'error')
        return redirect(url_for('kit_detail', kit_id=kit_id))
    finally:
        conn.close()
    
    return redirect(url_for('kits'))

@app.route('/kit/<int:kit_id>/image/<filename>')
def kit_image(kit_id, filename):
    """Serve kit label images"""
    kit_upload_dir = os.path.join(os.path.dirname(__file__), 'uploads', 'kits')
    return send_from_directory(kit_upload_dir, filename)

@app.route('/kit/<int:kit_id>/pdf/<filename>')
def kit_pdf(kit_id, filename):
    """Serve kit instruction PDFs"""
    kit_upload_dir = os.path.join(os.path.dirname(__file__), 'uploads', 'kits')
    return send_from_directory(kit_upload_dir, filename)

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
                    ORDER BY 
                        CASE 
                            WHEN e.status = 'Pending' THEN 1
                            WHEN e.status = 'Rejected' THEN 2
                            WHEN e.status = 'Paid' THEN 3
                        END,
                        e.submitted_date DESC
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
                    ORDER BY 
                        CASE 
                            WHEN e.status = 'Pending' THEN 1
                            WHEN e.status = 'Rejected' THEN 2
                            WHEN e.status = 'Paid' THEN 3
                        END,
                        e.submitted_date DESC
                """, (current_user.id,))
            
            expenses_list = cur.fetchall()
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        expenses_list = []
    finally:
        conn.close()
    
    return render_template('expenses.html', expenses=expenses_list)

@app.route('/expenses/export', methods=['GET'])
@require_permission('expenses', 'view')
def export_expenses():
    """Export expenses to CSV with optional date range"""
    from io import BytesIO
    import csv
    from datetime import datetime
    
    # Get date range parameters
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('expenses'))
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Build query based on permissions and filters
            where_clauses = []
            params = []
            
            if not current_user.can_access('expenses', 'full'):
                # Brewers only see their own expenses
                where_clauses.append("e.user_id = %s")
                params.append(current_user.id)
            
            if start_date:
                where_clauses.append("e.purchase_date >= %s")
                params.append(start_date)
            
            if end_date:
                where_clauses.append("e.purchase_date <= %s")
                params.append(end_date)
            
            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)
            
            query = f"""
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
                {where_sql}
                GROUP BY e.id, e.user_id, u.full_name, u.username, u.bank_account, p.full_name, r.full_name
                ORDER BY e.purchase_date DESC
            """
            
            cur.execute(query, params)
            expenses_list = cur.fetchall()
            
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        return redirect(url_for('expenses'))
    finally:
        conn.close()
    
    # Create CSV in memory (using BytesIO for Flask send_file)
    output = BytesIO()
    # CSV writer needs text mode, so we'll write to string first
    import io
    text_stream = io.StringIO()
    # Use semicolon delimiter for Excel compatibility (especially Norwegian/European Excel)
    writer = csv.writer(text_stream, delimiter=';')
    
    # Write header
    if current_user.can_access('expenses', 'full'):
        writer.writerow([
            'Submitted Date', 'User', 'Bank Account', 'Amount (NOK)', 
            'Description', 'Purchase Date', 'Status', 'Paid Date', 
            'Paid By', 'Rejection Reason', 'Receipts'
        ])
    else:
        writer.writerow([
            'Submitted Date', 'Amount (NOK)', 'Description', 
            'Purchase Date', 'Status', 'Paid Date', 'Receipts'
        ])
    
    # Write data
    total_amount = 0
    for expense in expenses_list:
        total_amount += float(expense['amount'])
        
        # Format dates
        submitted = expense['submitted_date'].strftime('%Y-%m-%d %H:%M') if expense['submitted_date'] else ''
        purchase = expense['purchase_date'].strftime('%Y-%m-%d') if expense['purchase_date'] else ''
        paid = expense['paid_date'].strftime('%Y-%m-%d') if expense['paid_date'] else ''
        
        # Format bank account
        bank_account = ''
        if expense.get('bank_account'):
            ba = expense['bank_account']
            bank_account = f"{ba[:4]}.{ba[4:6]}.{ba[6:]}"
        
        if current_user.can_access('expenses', 'full'):
            writer.writerow([
                submitted,
                expense['full_name'] or expense['username'],
                bank_account,
                f"{expense['amount']:.2f}",
                expense['description'],
                purchase,
                expense['status'],
                paid,
                expense['paid_by_name'] or '',
                expense['rejection_reason'] or '',
                expense['receipt_count']
            ])
        else:
            writer.writerow([
                submitted,
                f"{expense['amount']:.2f}",
                expense['description'],
                purchase,
                expense['status'],
                paid,
                expense['receipt_count']
            ])
    
    # Add total row
    if expenses_list:
        if current_user.can_access('expenses', 'full'):
            writer.writerow(['', '', 'TOTAL:', f"{total_amount:.2f}", '', '', '', '', '', '', ''])
        else:
            writer.writerow(['', f"{total_amount:.2f}", '', '', '', '', ''])
    
    # Convert string to bytes for send_file
    output.write(text_stream.getvalue().encode('utf-8'))
    output.seek(0)
    
    # Generate filename with date range
    filename = 'expenses'
    if start_date and end_date:
        filename += f'_{start_date}_to_{end_date}'
    elif start_date:
        filename += f'_from_{start_date}'
    elif end_date:
        filename += f'_until_{end_date}'
    filename += '.csv'
    
    response = send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename
    )
    
    return response

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
            
            # Only prevent deletion of paid expenses for non-admin users
            if expense['status'] == 'Paid' and not current_user.can_access('expenses', 'full'):
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

# ============================================================================
# SETTINGS ROUTES
# ============================================================================

@app.route('/settings', methods=['GET', 'POST'])
@require_permission('users', 'full')  # Admin only
def settings():
    """System settings page with MQTT configuration"""
    conn = get_db_connection()
    if not conn:
        flash('Database connection error', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        try:
            with conn.cursor() as cur:
                # Get or create mqtt_config record
                cur.execute("SELECT id FROM mqtt_config LIMIT 1")
                config_id = cur.fetchone()
                
                # Prepare form data
                enabled = request.form.get('enabled') == 'on'
                broker_host = request.form['broker_host']
                broker_port = int(request.form['broker_port'])
                username = request.form.get('username', '')
                password = request.form.get('password', '')
                use_tls = request.form.get('use_tls') == 'on'
                topic_prefix = request.form['topic_prefix']
                
                if config_id:
                    # Update existing config
                    # Only update password if a new one was provided
                    if password:
                        cur.execute("""
                            UPDATE mqtt_config SET
                                broker_host = %s,
                                broker_port = %s,
                                username = %s,
                                password = %s,
                                use_tls = %s,
                                topic_prefix = %s,
                                enabled = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (broker_host, broker_port, username, password, use_tls, 
                              topic_prefix, enabled, config_id[0]))
                    else:
                        cur.execute("""
                            UPDATE mqtt_config SET
                                broker_host = %s,
                                broker_port = %s,
                                username = %s,
                                use_tls = %s,
                                topic_prefix = %s,
                                enabled = %s,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (broker_host, broker_port, username, use_tls, 
                              topic_prefix, enabled, config_id[0]))
                else:
                    # Insert new config
                    cur.execute("""
                        INSERT INTO mqtt_config 
                        (broker_host, broker_port, username, password, use_tls, topic_prefix, enabled)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (broker_host, broker_port, username, password, use_tls, 
                          topic_prefix, enabled))
                
                conn.commit()
                flash(_('Settings saved successfully'), 'success')
                
                # Restart MQTT with new config
                new_config = {
                    'broker_host': broker_host,
                    'broker_port': broker_port,
                    'username': username if username else None,
                    'password': password if password else None,
                    'use_tls': use_tls,
                    'topic_prefix': topic_prefix,
                    'enabled': enabled
                }
                mqtt_handler.update_config(new_config)
                
        except (psycopg2.Error, ValueError) as e:
            flash(f'Error saving settings: {e}', 'error')
        finally:
            conn.close()
        
        return redirect(url_for('settings'))
    
    # GET request - load settings
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM mqtt_config LIMIT 1")
            config = cur.fetchone()
            
            if not config:
                # Create default config
                config = {
                    'broker_host': '',
                    'broker_port': 1883,
                    'username': '',
                    'password': '',
                    'use_tls': False,
                    'topic_prefix': 'brewery',
                    'enabled': False
                }
    except psycopg2.Error as e:
        flash(f'Database error: {e}', 'error')
        config = {}
    finally:
        conn.close()
    
    # Check MQTT connection status
    mqtt_connected = mqtt_handler.is_connected()
    
    return render_template('settings.html', config=config, mqtt_connected=mqtt_connected)


@app.route('/settings/mqtt/test', methods=['POST'])
@require_permission('users', 'full')  # Admin only
def test_mqtt_connection():
    """Test MQTT connection without saving"""
    broker_host = request.form.get('broker_host')
    broker_port = int(request.form.get('broker_port', 1883))
    username = request.form.get('username', '') or None
    password = request.form.get('password', '') or None
    use_tls = request.form.get('use_tls') == 'on'
    
    if not broker_host:
        return jsonify({
            'success': False,
            'message': _('Broker host is required')
        })
    
    try:
        # Use the MQTT handler's test function
        success, message = MQTTHandler.test_connection(
            broker_host, broker_port, username, password, use_tls, timeout=10
        )
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Connection test error: {str(e)}'
        })


# ============================================================================
# MQTT API ENDPOINTS
# ============================================================================

@app.route('/api/mqtt/weight/<keg_number>')
@login_required
def get_mqtt_weight(keg_number):
    """Get latest MQTT weight (single sensor for any keg)"""
    # Check if MQTT is enabled
    if not mqtt_handler.config.get('enabled', False):
        return jsonify({
            'success': False,
            'message': 'MQTT is disabled',
            'connected': False
        })
    
    weight_data = mqtt_handler.get_latest_weight()
    
    if weight_data:
        return jsonify({
            'success': True,
            'weight_kg': weight_data['weight_kg'],
            'timestamp': weight_data['timestamp'],
            'connected': mqtt_handler.is_connected()
        })
    else:
        return jsonify({
            'success': False,
            'message': 'No weight data available',
            'connected': mqtt_handler.is_connected()
        })


@app.route('/api/mqtt/status')
@login_required
def get_mqtt_status():
    """Get MQTT connection status and latest weight"""
    # If MQTT is disabled, return disconnected
    if not mqtt_handler.config.get('enabled', False):
        return jsonify({
            'connected': False,
            'weight': None
        })
    
    return jsonify({
        'connected': mqtt_handler.is_connected(),
        'weight': mqtt_handler.get_latest_weight()
    })


# ============================================================================
# APPLICATION STARTUP
# ============================================================================

def start_mqtt_if_enabled():
    """Load MQTT config from database and start client if enabled"""
    try:
        conn = get_db_connection()
        if not conn:
            print("⚠️  Could not connect to database for MQTT config")
            return
        
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM mqtt_config LIMIT 1")
            config = cur.fetchone()
        
        conn.close()
        
        if config and config.get('enabled'):
            print("🚀 Starting MQTT client...")
            mqtt_handler.update_config(dict(config))
            if mqtt_handler.start():
                print("✓ MQTT client started successfully")
            else:
                print("✗ Failed to start MQTT client")
        else:
            print("ℹ️  MQTT is disabled or not configured")
    
    except Exception as e:
        print(f"⚠️  Error starting MQTT: {e}")


def stop_mqtt():
    """Stop MQTT client gracefully"""
    try:
        if mqtt_handler:
            mqtt_handler.stop()
            print("✓ MQTT client stopped")
    except Exception as e:
        print(f"⚠️  Error stopping MQTT: {e}")


# MQTT will be started by Gunicorn post_fork hook in the first worker
# See gunicorn.conf.py for the hook configuration


if __name__ == '__main__':
    # This is only used for development/testing
    # In production, use: gunicorn --config gunicorn.conf.py app:app
    debug_mode = os.getenv('DEBUG', 'false').lower() == 'true'
    port = int(os.getenv('WEB_PORT', 5000))
    
    print("⚠️  WARNING: Running Flask development server")
    print("💡 For production, use: gunicorn --config gunicorn.conf.py app:app")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
