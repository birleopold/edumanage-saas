import secrets

from django.contrib.auth.models import UserManager as DjangoUserManager


UPPERCASE = "ABCDEFGHJKLMNPQRSTUVWXYZ"
LOWERCASE = "abcdefghijkmnopqrstuvwxyz"
DIGITS = "23456789"
SPECIALS = "!@#$%&*+-_"
TEMPORARY_PASSWORD_ALPHABET = UPPERCASE + LOWERCASE + DIGITS + SPECIALS


def generate_temporary_password(length: int = 12) -> str:
    """Generate a strong, printable temporary password.

    The password always contains at least one uppercase letter, lowercase
    letter, digit, and special character. Ambiguous characters are excluded so
    printed credentials are easier for school users to read correctly.
    """

    if length < 8:
        raise ValueError("Temporary passwords must be at least 8 characters long.")

    characters = [
        secrets.choice(UPPERCASE),
        secrets.choice(LOWERCASE),
        secrets.choice(DIGITS),
        secrets.choice(SPECIALS),
    ]
    characters.extend(
        secrets.choice(TEMPORARY_PASSWORD_ALPHABET)
        for _ in range(length - len(characters))
    )
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)


def _legacy_make_random_password(self, length: int = 10, allowed_chars=None) -> str:
    """Django 4-compatible manager method for legacy EduManage call sites."""

    if allowed_chars is not None:
        if length < 1:
            raise ValueError("Password length must be at least 1 character.")
        if not allowed_chars:
            raise ValueError("allowed_chars cannot be empty.")
        return "".join(secrets.choice(allowed_chars) for _ in range(length))
    return generate_temporary_password(length=length)


def install_user_manager_password_compatibility() -> None:
    """Restore the manager API removed by Django 5 for existing workflows.

    EduManage still has account-creation paths that call
    ``User.objects.make_random_password``. Installing the compatibility method
    once during app startup repairs every such path without changing database
    models or weakening password generation.
    """

    if not hasattr(DjangoUserManager, "make_random_password"):
        setattr(DjangoUserManager, "make_random_password", _legacy_make_random_password)
