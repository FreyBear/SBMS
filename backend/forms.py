"""
SBMS Forms for authentication and user management
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, MultipleFileField, FileAllowed
from wtforms import StringField, PasswordField, SelectField, BooleanField, SubmitField, TextAreaField, DecimalField, DateField, HiddenField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, Regexp, NumberRange
from flask_babel import lazy_gettext as _l

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(), 
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(),
        EqualTo('new_password', message='Passwords must match')
    ])
    submit = SubmitField('Change Password')

class CreateUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    role_id = SelectField('Role', coerce=int, validators=[DataRequired()])
    language = SelectField('Language', choices=[('en', 'English'), ('no', 'Norsk (Bokmål)'), ('nn', 'Norsk (Nynorsk)')], default='en')
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Create User')

class EditUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    role_id = SelectField('Role', coerce=int, validators=[DataRequired()])
    language = SelectField('Language', choices=[('en', 'English'), ('no', 'Norsk (Bokmål)'), ('nn', 'Norsk (Nynorsk)')], default='en')
    is_active = BooleanField('Active')
    bank_account = StringField('Bank Account', validators=[
        Optional(),
        Length(min=11, max=11, message='Bank account must be exactly 11 digits'),
        Regexp(r'^\d{11}$', message='Bank account must contain only digits')
    ])
    # Password change fields (optional for self-editing)
    current_password = PasswordField('Current Password', validators=[Optional()])
    new_password = PasswordField('New Password', validators=[
        Optional(), 
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        Optional(),
        EqualTo('new_password', message='Passwords must match')
    ])
    submit = SubmitField('Update User')

class CreateExpenseForm(FlaskForm):
    amount = DecimalField(_l('Amount (NOK)'), validators=[
        DataRequired(),
        NumberRange(min=0.01, message='Amount must be greater than 0')
    ], places=2)
    description = TextAreaField(_l('Description'), validators=[
        DataRequired(),
        Length(min=10, max=500, message='Description must be between 10 and 500 characters')
    ])
    purchase_date = DateField(_l('Purchase Date'), validators=[DataRequired()])
    receipts = MultipleFileField(_l('Receipt Images'), validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Only JPG, PNG, and PDF files are allowed')
    ])
    submit = SubmitField(_l('Submit Expense'))

class MarkPaidForm(FlaskForm):
    submit = SubmitField('Mark as Paid')

class RejectExpenseForm(FlaskForm):
    rejection_reason = TextAreaField('Rejection Reason', validators=[
        DataRequired(),
        Length(min=10, max=500, message='Rejection reason must be between 10 and 500 characters')
    ])
    submit = SubmitField('Reject Expense')

class DeleteExpenseForm(FlaskForm):
    submit = SubmitField('Delete Expense')

class EditExpenseForm(FlaskForm):
    amount = DecimalField('Amount (NOK)', validators=[
        DataRequired(),
        NumberRange(min=0.01, message='Amount must be greater than 0')
    ], places=2)
    description = TextAreaField('Description', validators=[
        DataRequired(),
        Length(min=10, max=500, message='Description must be between 10 and 500 characters')
    ])
    purchase_date = DateField('Purchase Date', validators=[DataRequired()])
    receipts = MultipleFileField('Receipt Images', validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'pdf'], 'Only JPG, PNG, and PDF files are allowed')
    ])
    remove_attachments = HiddenField('Remove Attachments')
    submit = SubmitField('Update Expense')

class CreateKitForm(FlaskForm):
    name = StringField(_l('Kit Name'), validators=[
        DataRequired(),
        Length(max=255, message='Kit name cannot exceed 255 characters')
    ])
    kit_type = SelectField(_l('Kit Type'), validators=[DataRequired()], choices=[
        ('Fresh Wort', _l('Fresh Wort')),
        ('Cider', _l('Cider')),
        ('Red Wine', _l('Red Wine')),
        ('White Wine', _l('White Wine')),
        ('Rose Wine', _l('Rose Wine')),
        ('Sparkling Wine', _l('Sparkling Wine')),
        ('Mead', _l('Mead'))
    ])
    manufacturer = StringField(_l('Manufacturer'), validators=[Optional(), Length(max=255)])
    style = StringField(_l('Style'), validators=[Optional(), Length(max=255)])
    estimated_abv = DecimalField(_l('Estimated ABV (%)'), validators=[Optional(), NumberRange(min=0, max=100)], places=2)
    volume_liters = DecimalField(_l('Volume (L)'), validators=[Optional(), NumberRange(min=0.1)], places=2)
    cost = DecimalField(_l('Cost'), validators=[Optional(), NumberRange(min=0)], places=2)
    supplier = StringField(_l('Supplier'), validators=[Optional(), Length(max=255)])
    additional_ingredients_needed = TextAreaField(_l('Additional Ingredients Needed'), validators=[Optional(), Length(max=1000)])
    description = TextAreaField(_l('Description'), validators=[Optional(), Length(max=1000)])
    notes = TextAreaField(_l('Notes'), validators=[Optional(), Length(max=1000)])
    label_image = FileField(_l('Label Image'), validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png'], 'Only JPG and PNG files are allowed for images')
    ])
    instruction_pdf = FileField(_l('Instruction PDF'), validators=[
        Optional(),
        FileAllowed(['pdf'], 'Only PDF files are allowed')
    ])
    submit = SubmitField(_l('Create Kit'))

class EditKitForm(FlaskForm):
    name = StringField(_l('Kit Name'), validators=[
        DataRequired(),
        Length(max=255, message='Kit name cannot exceed 255 characters')
    ])
    kit_type = SelectField(_l('Kit Type'), validators=[DataRequired()], choices=[
        ('Fresh Wort', _l('Fresh Wort')),
        ('Cider', _l('Cider')),
        ('Red Wine', _l('Red Wine')),
        ('White Wine', _l('White Wine')),
        ('Rose Wine', _l('Rose Wine')),
        ('Sparkling Wine', _l('Sparkling Wine')),
        ('Mead', _l('Mead'))
    ])
    manufacturer = StringField(_l('Manufacturer'), validators=[Optional(), Length(max=255)])
    style = StringField(_l('Style'), validators=[Optional(), Length(max=255)])
    estimated_abv = DecimalField(_l('Estimated ABV (%)'), validators=[Optional(), NumberRange(min=0, max=100)], places=2)
    volume_liters = DecimalField(_l('Volume (L)'), validators=[Optional(), NumberRange(min=0.1)], places=2)
    cost = DecimalField(_l('Cost'), validators=[Optional(), NumberRange(min=0)], places=2)
    supplier = StringField(_l('Supplier'), validators=[Optional(), Length(max=255)])
    additional_ingredients_needed = TextAreaField(_l('Additional Ingredients Needed'), validators=[Optional(), Length(max=1000)])
    description = TextAreaField(_l('Description'), validators=[Optional(), Length(max=1000)])
    notes = TextAreaField(_l('Notes'), validators=[Optional(), Length(max=1000)])
    label_image = FileField(_l('Label Image'), validators=[
        Optional(),
        FileAllowed(['jpg', 'jpeg', 'png'], 'Only JPG and PNG files are allowed for images')
    ])
    instruction_pdf = FileField(_l('Instruction PDF'), validators=[
        Optional(),
        FileAllowed(['pdf'], 'Only PDF files are allowed')
    ])
    submit = SubmitField(_l('Update Kit'))

class DeleteKitForm(FlaskForm):
    submit = SubmitField('Delete Kit')

class CreateBrewForm(FlaskForm):
    name = StringField(_l('Brew Name'), validators=[DataRequired(), Length(max=200)])
    date_brewed = DateField(_l('Date Brewed'), validators=[DataRequired()])
    
    # Source selection - either recipe OR kit
    source_type = SelectField(_l('Brew Source'), 
                             choices=[('recipe', _l('Recipe')), ('kit', _l('Kit'))], 
                             validators=[DataRequired()])
    recipe_id = SelectField(_l('Select Recipe'), coerce=lambda x: int(x) if x and x != '0' else None, validators=[Optional()])
    kit_id = SelectField(_l('Select Kit'), coerce=lambda x: int(x) if x and x != '0' else None, validators=[Optional()])
    
    # Auto-populated but editable fields
    style = StringField(_l('Style'), validators=[Optional(), Length(max=100)])
    estimated_abv = DecimalField(_l('Estimated ABV (%)'), validators=[Optional(), NumberRange(min=0, max=20)], places=1)
    expected_og = DecimalField(_l('Expected OG'), validators=[Optional(), NumberRange(min=1.000, max=1.200)], places=4)
    expected_fg = DecimalField(_l('Expected FG'), validators=[Optional(), NumberRange(min=0.990, max=1.050)], places=4)
    batch_size_liters = DecimalField(_l('Batch Size (L)'), validators=[Optional(), NumberRange(min=0, max=1000)], places=2)
    
    # Actual measurements
    actual_og = DecimalField(_l('Actual OG'), validators=[Optional(), NumberRange(min=1.000, max=1.200)], places=4)
    actual_fg = DecimalField(_l('Actual FG'), validators=[Optional(), NumberRange(min=0.990, max=1.050)], places=4)
    
    # Gluten-free indicator
    gluten_free = BooleanField(_l('Gluten Free'))
    
    notes = TextAreaField(_l('Notes'), validators=[Optional()])
    submit = SubmitField(_l('Create Brew'))

class EditBrewForm(FlaskForm):
    name = StringField(_l('Brew Name'), validators=[DataRequired(), Length(max=200)])
    date_brewed = DateField(_l('Date Brewed'), validators=[DataRequired()])
    
    # Show current source but don't allow changing
    source_info = StringField(_l('Brew Source'), render_kw={'readonly': True})
    
    # Editable fields
    style = StringField(_l('Style'), validators=[Optional(), Length(max=100)])
    estimated_abv = DecimalField(_l('Estimated ABV (%)'), validators=[Optional(), NumberRange(min=0, max=20)], places=1)
    expected_og = DecimalField(_l('Expected OG'), validators=[Optional(), NumberRange(min=1.000, max=1.200)], places=4)
    expected_fg = DecimalField(_l('Expected FG'), validators=[Optional(), NumberRange(min=0.990, max=1.050)], places=4)
    batch_size_liters = DecimalField(_l('Batch Size (L)'), validators=[Optional(), NumberRange(min=0, max=1000)], places=2)
    
    # Actual measurements
    actual_og = DecimalField(_l('Actual OG'), validators=[Optional(), NumberRange(min=1.000, max=1.200)], places=4)
    actual_fg = DecimalField(_l('Actual FG'), validators=[Optional(), NumberRange(min=0.990, max=1.050)], places=4)
    
    # Gluten-free indicator
    gluten_free = BooleanField(_l('Gluten Free'))
    
    notes = TextAreaField(_l('Notes'), validators=[Optional()])
    submit = SubmitField(_l('Update Brew'))

class AddBrewTaskForm(FlaskForm):
    scheduled_date = DateField(_l('Scheduled Date'), validators=[DataRequired()])
    action = StringField(_l('Action/Task'), validators=[DataRequired(), Length(max=500)], 
                        render_kw={"placeholder": _l("e.g., Add Cascade hops 50g, Cold crash to 2°C, Transfer to keg #5")})
    notes = TextAreaField(_l('Notes'), validators=[Optional()], 
                         render_kw={"placeholder": _l("Optional additional details or instructions")})
    submit = SubmitField(_l('Add Brew Task'))

class EditBrewTaskForm(FlaskForm):
    scheduled_date = DateField(_l('Scheduled Date'), validators=[DataRequired()])
    completed_date = DateField(_l('Completed Date'), validators=[Optional()])
    action = StringField(_l('Action/Task'), validators=[DataRequired(), Length(max=500)])
    is_completed = BooleanField(_l('Mark as Completed'))
    notes = TextAreaField(_l('Notes'), validators=[Optional()])
    submit = SubmitField(_l('Update Brew Task'))

# Legacy forms kept for backwards compatibility (can be removed if not needed elsewhere)
class AddDryHopForm(FlaskForm):
    scheduled_date = DateField(_l('Scheduled Date'), validators=[DataRequired()])
    ingredient = StringField(_l('Hop Variety/Ingredient'), validators=[DataRequired(), Length(max=200)])
    amount_grams = DecimalField(_l('Amount (grams)'), validators=[DataRequired(), NumberRange(min=0.1, max=10000)], places=2)
    hop_variety = StringField(_l('Hop Variety'), validators=[Optional(), Length(max=100)])
    notes = TextAreaField(_l('Notes'), validators=[Optional()])
    submit = SubmitField(_l('Add Dry Hop Schedule'))

class EditDryHopForm(FlaskForm):
    scheduled_date = DateField(_l('Scheduled Date'), validators=[DataRequired()])
    completed_date = DateField(_l('Completed Date'), validators=[Optional()])
    ingredient = StringField(_l('Hop Variety/Ingredient'), validators=[DataRequired(), Length(max=200)])
    amount_grams = DecimalField(_l('Amount (grams)'), validators=[DataRequired(), NumberRange(min=0.1, max=10000)], places=2)
    hop_variety = StringField(_l('Hop Variety'), validators=[Optional(), Length(max=100)])
    is_completed = BooleanField(_l('Mark as Completed'))
    notes = TextAreaField(_l('Notes'), validators=[Optional()])
    submit = SubmitField(_l('Update Dry Hop'))