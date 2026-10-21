"""Encryption service for securing sensitive tokens at rest (SEC-004).

Uses cryptography.fernet.Fernet (AES-128-CBC with HMAC-SHA256).
"""

from cryptography.fernet import Fernet, InvalidToken


class EncryptionService:
    """Handles symmetric encryption and decryption for credentials and tokens."""

    def __init__(self, key: str | bytes):
        """Initialize with a 32-byte urlsafe base64-encoded Fernet key.

        Args:
            key: Fernet key string or bytes.

        Raises:
            ValueError: If key is empty or invalid.
        """
        if not key:
            raise ValueError("Encryption key cannot be empty.")

        if isinstance(key, str):
            key_bytes = key.strip().encode("utf-8")
        else:
            key_bytes = key

        try:
            self._fernet = Fernet(key_bytes)
        except Exception as e:
            raise ValueError(f"Invalid Fernet encryption key: {e}") from e

    def encrypt(self, plaintext: str) -> bytes:
        """Encrypt plaintext string into encrypted ciphertext bytes.

        Args:
            plaintext: Sensitive string (e.g. access token).

        Returns:
            bytes: Encrypted ciphertext bytes.
        """
        if not plaintext:
            return b""
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes) -> str:
        """Decrypt ciphertext bytes back into plaintext string.

        Args:
            ciphertext: Encrypted token bytes.

        Returns:
            str: Decrypted plaintext string.

        Raises:
            ValueError: If token decryption fails or token is corrupted.
        """
        if not ciphertext:
            return ""
        try:
            return self._fernet.decrypt(ciphertext).decode("utf-8")
        except InvalidToken as e:
            raise ValueError("Failed to decrypt token: Invalid or corrupted ciphertext.") from e

    @staticmethod
    def generate_key() -> str:
        """Generate a fresh URL-safe base64-encoded 32-byte key."""
        return Fernet.generate_key().decode("utf-8")
