import secrets
import hashlib
from typing import Tuple


def generate_api_key_pair() -> Tuple[str, str, str]:
    """
    Generate an API key pair: (raw_key, key_hash, prefix).
    - raw_key: Shown once to user upon creation, never stored.
    - prefix: Stored for display/identification (e.g. 'sec_abc12345').
    - key_hash: SHA-256 hash stored in DB for fast indexed lookup.
    """
    random_part = secrets.token_urlsafe(32)
    raw_key = f"sec_{random_part}"
    prefix = raw_key[:12]
    key_hash = hash_api_key(raw_key)
    return raw_key, key_hash, prefix


def hash_api_key(raw_key: str) -> str:
    """Compute SHA-256 hash of raw API key for storage and matching."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
