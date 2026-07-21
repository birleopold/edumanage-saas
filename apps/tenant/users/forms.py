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
from django.core.exceptions import ObjectDoesNotExist, ValidationError

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
        }),
        label='Confirm new password',
    )


class UserProfileForm(forms.ModelForm):
    """User account form that respects authoritative role-profile identity data."""

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.student_profile = None
        if not self.instance or not self.instance.pk:
            return

        try:
            self.student_profile = self.instance.student_profile
        except (ObjectDoesNotExist, AttributeError):
            return

        # The student record is the source of truth for identity. This also
        # repairs older accounts that were created with blank User names.
        self.student_profile.sync_user_identity()
        self.instance.first_name = self.student_profile.first_name
        self.instance.last_name = self.student_profile.last_name
        self.instance.email = self.student_profile.email or self.instance.email
        self.initial['first_name'] = self.student_profile.first_name
        self.initial['last_name'] = self.student_profile.last_name
        self.initial['email'] = self.instance.email

        for field_name in ('first_name', 'last_name'):
            self.fields[field_name].disabled = True
            self.fields[field_name].help_text = (
                'This name comes from the official student record. '
                'Ask the school administrator to correct it.'
            )

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if email:
            qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError('This email address is already in use.')
        return email

    def save(self, commit=True):
        if self.student_profile is not None:
            self.instance.first_name = self.student_profile.first_name
            self.instance.last_name = self.student_profile.last_name

        user = super().save(commit=commit)
        if commit and self.student_profile is not None:
            new_email = user.email or ''
            if self.student_profile.email != new_email:
                type(self.student_profile).objects.filter(pk=self.student_profile.pk).update(
                    email=new_email
                )
                self.student_profile.email = new_email
        return user
