"""Passwords.

We never store a password. We store a salted hash: a scrambled value that
can be checked against a password but cannot be turned back into one.
"""
import hashlib
import hmac
import secrets


def new_salt():
    """A random value, different for every user, mixed into their hash."""
    return secrets.token_hex(16)


def hash_password(password, salt):
    """Scramble a password with its salt. Same inputs always give the same result."""
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), 200_000
    )
    return digest.hex()


def password_matches(password, salt, expected_hash):
    """True if this password produces the stored hash."""
    return hmac.compare_digest(hash_password(password, salt), expected_hash)
