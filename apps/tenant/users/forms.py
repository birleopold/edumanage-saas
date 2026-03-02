"""
User authentication and profile forms.
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
)
from django.core.exceptions import ValidationError

User = get_user_model()


class CustomLoginForm(AuthenticationForm):
    """Enhanced login form with better styling and validation."""
    
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Username',
            'autocomplete': 'username',
            'autofocus': True,
        }),
        label='Username',
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Password',
            'autocomplete': 'current-password',
        }),
        label='Password',
    )
    
    remember_me = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        label='Remember me',
    )


class CustomPasswordResetForm(PasswordResetForm):
    """Enhanced password reset form."""
    
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your email address',
            'autocomplete': 'email',
        }),
        label='Email address',
        help_text='Enter the email address associated with your account.',
    )


class CustomPasswordResetConfirmForm(SetPasswordForm):
    """Enhanced password reset confirmation form."""
    
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'New password',
            'autocomplete': 'new-password',
        }),
        label='New password',
        help_text='Password must be at least 8 characters long.',
    )
    
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirm new password',
            'autocomplete': 'new-password',
        }),
        label='Confirm password',
    )


class CustomPasswordChangeForm(PasswordChangeForm):
    """Enhanced password change form."""
    
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Current password',
            'autocomplete': 'current-password',
        }),
        label='Current password',
    )
    
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'New password',
            'autocomplete': 'new-password',
        }),
        label='New password',
        help_text='Password must be at least 8 characters long.',
    )
    
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirm new password',
            'autocomplete': 'new-password',
        }),
        label='Confirm new password',
    )


class UserProfileForm(forms.ModelForm):
    """User profile editing form."""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'First name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Last name',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'Email address',
            }),
        }
        help_texts = {
            'email': 'We\'ll use this email for important notifications.',
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check if email is already used by another user
            qs = User.objects.filter(email=email).exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError('This email address is already in use.')
        return email
