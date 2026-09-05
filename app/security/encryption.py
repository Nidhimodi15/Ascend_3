"""
Encryption Module — AES-256-GCM Authenticated Payload Encryption.

Provides standard AES-256-GCM encryption and decryption for simulated store data payloads.
Key loaded via environment variable KILLPOINT_ENCRYPTION_KEY.
"""
import os
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class PayloadEncryptor:
    """AES-256-GCM Payload Encryptor & Decryptor."""

    def __init__(self):
        raw_key = os.getenv("KILLPOINT_ENCRYPTION_KEY", "CHANGE_ME")
        if not raw_key or raw_key == "CHANGE_ME":
            raw_key = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        
        # Derive fixed 32-byte key via SHA-256
        self.key_bytes = hashlib.sha256(raw_key.encode("utf-8")).digest()
        self.aesgcm = AESGCM(self.key_bytes)
        self.algorithm = "AES-256-GCM"

    def encrypt(self, text: str) -> str:
        """Encrypt plain text to authenticated ciphertext representation."""
        if not text or text.startswith("enc:"):
            return text
        nonce = os.urandom(12)
        ciphertext = self.aesgcm.encrypt(nonce, text.encode("utf-8"), None)
        return f"enc:{nonce.hex()}:{ciphertext.hex()}"

    def decrypt(self, text: str) -> str:
        """Decrypt cipher payload back to plain text."""
        if not text or not text.startswith("enc:"):
            return text
        try:
            parts = text.split(":", 2)
            if len(parts) != 3:
                return text
            nonce = bytes.fromhex(parts[1])
            ciphertext = bytes.fromhex(parts[2])
            decrypted_bytes = self.aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted_bytes.decode("utf-8")
        except Exception:
            return text


encryptor = PayloadEncryptor()
