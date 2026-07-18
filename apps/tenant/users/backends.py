from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

class EmailOrUsernameModelBackend(ModelBackend):
    """Authenticate by username, or by email only when the email identifies one user."""
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)
        if not username or not password:
            return None
        user_model = get_user_model()
        normalized = str(username).strip()
        user = user_model.objects.filter(username__iexact=normalized).first()
        if user is None:
            email_matches = user_model.objects.filter(email__iexact=normalized).order_by("pk")
            if email_matches.count() != 1:
                return None
            user = email_matches.first()
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
