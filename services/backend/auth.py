"""
JWT Authentication utilities for RS256 token generation and validation

Reason: Implements secure JWT authentication using RSA key pairs (RS256 algorithm)
This provides better security than HS256 as the private key is never shared
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend
import os

# Reason: Password hashing context for secure password storage
# Use pbkdf2_sha256 to avoid relying on native bcrypt bindings inside container.
# pbkdf2_sha256 is slower than bcrypt but avoids platform-specific native deps
# making local dev and CI builds more robust.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# Reason: JWT configuration
ALGORITHM = "RS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Reason: RSA key pair paths
PRIVATE_KEY_PATH = "keys/private_key.pem"
PUBLIC_KEY_PATH = "keys/public_key.pem"


def generate_rsa_keys():
    """
    Generate RSA key pair for JWT signing
    
    Reason: Creates private/public key pair on first run
    Private key signs tokens, public key verifies them
    """
    os.makedirs("keys", exist_ok=True)
    
    # Reason: Generate 2048-bit RSA key pair
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    # Reason: Save private key in PEM format
    with open(PRIVATE_KEY_PATH, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
        )
    
    # Reason: Save public key in PEM format
    public_key = private_key.public_key()
    with open(PUBLIC_KEY_PATH, "wb") as f:
        f.write(
            public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        )
    
    print("RSA key pair generated successfully")


def load_private_key() -> str:
    """
    Load private key for signing tokens
    
    Reason: Reads the private key from file for JWT signing
    """
    if not os.path.exists(PRIVATE_KEY_PATH):
        generate_rsa_keys()
    
    with open(PRIVATE_KEY_PATH, "r") as f:
        return f.read()


def load_public_key() -> str:
    """
    Load public key for verifying tokens
    
    Reason: Reads the public key from file for JWT verification
    """
    if not os.path.exists(PUBLIC_KEY_PATH):
        generate_rsa_keys()
    
    with open(PUBLIC_KEY_PATH, "r") as f:
        return f.read()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash
    
    Reason: Securely compares plain password with bcrypt hash
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash password using bcrypt
    
    Reason: Creates secure password hash for storage
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token
    
    Reason: Generates short-lived access token for API authentication
    """
    to_encode = data.copy()
    
    # Reason: Set expiration time (default 15 minutes)
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    
    # Reason: Sign token with private key using RS256
    private_key = load_private_key()
    encoded_jwt = jwt.encode(to_encode, private_key, algorithm=ALGORITHM)
    
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    Create JWT refresh token
    
    Reason: Generates long-lived refresh token for obtaining new access tokens
    """
    to_encode = data.copy()
    
    # Reason: Set expiration time (7 days)
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    
    # Reason: Sign token with private key using RS256
    private_key = load_private_key()
    encoded_jwt = jwt.encode(to_encode, private_key, algorithm=ALGORITHM)
    
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    """
    Verify and decode JWT token
    
    Reason: Validates token signature and expiration, returns payload if valid
    """
    try:
        # Reason: Verify token with public key
        public_key = load_public_key()
        payload = jwt.decode(token, public_key, algorithms=[ALGORITHM])
        
        # Reason: Verify token type matches expected type
        if payload.get("type") != token_type:
            return None
        
        return payload
    except JWTError:
        return None
