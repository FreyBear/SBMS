"""
SBMS Forms for authentication and user management
"""
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, BooleanField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional

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
    submit = SubmitField('Update User')