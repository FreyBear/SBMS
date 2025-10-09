"""
SBMS Forms for authentication and user management
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, MultipleFileField, FileAllowed
from wtforms import StringField, PasswordField, SelectField, BooleanField, SubmitField, TextAreaField, DecimalField, DateField, HiddenField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, Regexp, NumberRange

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
    language = SelectField('Language', choices=[('en', 'English'), ('no', 'Norsk')], default='en')
    is_active = BooleanField('Active', default=True)
    submit = SubmitField('Create User')

class EditUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    role_id = SelectField('Role', coerce=int, validators=[DataRequired()])
    language = SelectField('Language', choices=[('en', 'English'), ('no', 'Norsk')], default='en')
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
    submit = SubmitField('Submit Expense')

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