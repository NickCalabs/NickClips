from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, RadioField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional
from models import User, ReferralCode

class ThemePreferenceForm(FlaskForm):
    theme = RadioField(
        'Theme Preference',
        choices=[
            ('light', 'Light Theme'), 
            ('dark', 'Dark Theme'),
            ('auto', 'Auto (System Default)')
        ],
        default='light'
    )
    submit = SubmitField('Save Appearance Settings')

class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField(
        'Confirm New Password', validators=[DataRequired(), EqualTo('new_password')]
    )
    submit = SubmitField('Change Password')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    password2 = PasswordField(
        'Confirm Password', validators=[DataRequired(), EqualTo('password')]
    )
    invite_code = StringField('Invite Code', validators=[DataRequired()])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Username already in use. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Email already registered. Please use a different email or sign in.')

    def validate_invite_code(self, invite_code):
        """Validate referral code against database"""
        code = ReferralCode.query.filter_by(code=invite_code.data.upper().strip()).first()
        if not code:
            raise ValidationError('Invalid invite code.')
        if code.used_by_id is not None:
            raise ValidationError('This invite code has already been used.')


class AdminCreateUserForm(FlaskForm):
    """Form for admin to create users directly without referral code"""
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    is_admin = BooleanField('Admin', default=False)
    submit = SubmitField('Create User')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Username already in use.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user is not None:
            raise ValidationError('Email already registered.')


class AdminResetPasswordForm(FlaskForm):
    """Form for admin to reset a user's password"""
    new_password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    submit = SubmitField('Reset Password')