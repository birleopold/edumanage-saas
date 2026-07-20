import secrets


UPPERCASE = "ABCDEFGHJKLMNPQRSTUVWXYZ"
LOWERCASE = "abcdefghijkmnopqrstuvwxyz"
DIGITS = "23456789"
SPECIALS = "!@#$%&*+-_"
TEMPORARY_PASSWORD_ALPHABET = UPPERCASE + LOWERCASE + DIGITS + SPECIALS


def generate_temporary_password(length: int = 12) -> str:
    """Generate a strong, printable temporary password.

    Django 5 removed ``UserManager.make_random_password``. This helper keeps
    temporary credential generation independent of that removed manager API
    and guarantees at least one uppercase letter, lowercase letter, digit, and
    special character.
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
