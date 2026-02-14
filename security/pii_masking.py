"""
AUTO-BROKER PII Protection & Masking
GDPR Article 5(1)(f) - Security of processing
Zero Trust - P0 Critical
"""

import re
import hashlib
import logging
from typing import Dict, Any, Optional, Union, List
from functools import wraps
import json

from cryptography.fernet import Fernet
from sqlalchemy import TypeDecorator, String, Text
from sqlalchemy_utils import EncryptedType
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class PIIMasker:
    """
    PII detection and masking for GDPR compliance.
    
    Masks in:
    - Logs (automatic middleware)
    - API responses (selective)
    - Database (encrypted fields)
    """
    
    # Regex patterns for PII detection
    PATTERNS = {
        "phone_it": {
            "pattern": r"(\+39\s?)?(3\d{1}\s?\d{3}\s?\d{3}\s?\d{3})",
            "mask": r"XXX XXX XXXX",
            "description": "Italian mobile number"
        },
        "phone_intl": {
            "pattern": r"(\+\d{1,3})[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{1,4}[\s\-]?\d{1,9}",
            "mask": lambda m: f"{m.group(1)} *** ****",
            "description": "International phone"
        },
        "email": {
            "pattern": r"([a-zA-Z0-9._%+-]{2})[a-zA-Z0-9._%+-]*@([a-zA-Z0-9.-]{2})[a-zA-Z0-9.-]*\.[a-zA-Z]{2,}",
            "mask": r"\1***@\2***",
            "description": "Email address"
        },
        "piva": {
            "pattern": r"(\d{8})(\d{3})",
            "mask": r"*********\2",
            "description": "Partita IVA (last 3 digits shown)"
        },
        "cf_italian": {
            "pattern": r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]",
            "mask": lambda m: f"XXXXXX{m.group(0)[6:8]}X{m.group(0)[9:11]}X***",
            "description": "Italian Codice Fiscale"
        },
        "iban_it": {
            "pattern": r"IT\d{2}[A-Z]\d{10}[A-Z0-9]{12}",
            "mask": lambda m: f"IT{m.group(0)[2:4]}**************{m.group(0)[-4:]}",
            "description": "Italian IBAN"
        },
        "credit_card": {
            "pattern": r"\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}",
            "mask": "**** **** **** ****",
            "description": "Credit card number"
        },
        "ip_address": {
            "pattern": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
            "mask": lambda m: "***.***.***.***",
            "description": "IP address"
        }
    }
    
    def __init__(self, encryption_key: Optional[bytes] = None):
        """Initialize with optional Fernet encryption key."""
        self.encryption_key = encryption_key
        if encryption_key:
            self.cipher = Fernet(encryption_key)
        else:
            self.cipher = None
    
    def mask_text(self, text: str, mask_email: bool = True, mask_phone: bool = True) -> str:
        """
        Mask PII in text content.
        
        Args:
            text: Input text that may contain PII
            mask_email: Whether to mask email addresses
            mask_phone: Whether to mask phone numbers
        
        Returns:
            Text with PII masked
        """
        if not text:
            return text
        
        masked = text
        
        # Mask phone numbers
        if mask_phone:
            # Italian format: +39 XXX XXX XXXX
            masked = re.sub(
                r"(\+39\s?)(\d{3})\s?(\d{3})\s?(\d{4})",
                r"\1*** *** \4",
                masked
            )
            # Generic international
            masked = re.sub(
                r"(\+\d{1,3})[\s\-]?\(?\d{1,4}\)?[\s\-]?(\d{1,4})[\s\-]?(\d{1,4})",
                lambda m: f"{m.group(1)} *** *** {m.group(4) if len(m.groups()) > 3 else '****'}",
                masked
            )
        
        # Mask emails
        if mask_email:
            masked = re.sub(
                r"([a-zA-Z0-9._%+-]{2})[a-zA-Z0-9._%+-]*@([a-zA-Z0-9.-]{2})[a-zA-Z0-9.-]*(\.[a-zA-Z]{2,})",
                r"\1***@\2***\3",
                masked
            )
        
        # Mask Partita IVA (show last 3 digits only)
        masked = re.sub(
            r"\b(\d{8})(\d{3})\b",
            r"*********\2",
            masked
        )
        
        return masked
    
    def mask_dict(self, data: Dict[str, Any], fields_to_mask: List[str]) -> Dict[str, Any]:
        """
        Mask specific fields in a dictionary.
        
        Args:
            data: Dictionary containing data
            fields_to_mask: List of field names to mask
        
        Returns:
            Dictionary with masked fields
        """
        result = {}
        for key, value in data.items():
            if key in fields_to_mask and isinstance(value, str):
                result[key] = self.mask_text(value)
            elif isinstance(value, dict):
                result[key] = self.mask_dict(value, fields_to_mask)
            elif isinstance(value, list):
                result[key] = [
                    self.mask_dict(item, fields_to_mask) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result
    
    def hash_identifier(self, identifier: str, salt: Optional[str] = None) -> str:
        """
        Hash an identifier for pseudonymization (GDPR).
        
        Args:
            identifier: Value to hash
            salt: Optional salt for additional security
        
        Returns:
            SHA-256 hash of identifier
        """
        data = identifier.encode()
        if salt:
            data = salt.encode() + data
        return hashlib.sha256(data).hexdigest()
    
    def encrypt_field(self, value: str) -> str:
        """
        Encrypt a field value using Fernet (AES-128).
        
        Raises:
            ValueError: If no encryption key configured
        """
        if not self.cipher:
            raise ValueError("Encryption key not configured")
        
        return self.cipher.encrypt(value.encode()).decode()
    
    def decrypt_field(self, encrypted_value: str) -> str:
        """Decrypt a field value."""
        if not self.cipher:
            raise ValueError("Encryption key not configured")
        
        return self.cipher.decrypt(encrypted_value.encode()).decode()


# SQLAlchemy Encrypted Type for Database
class EncryptedString(TypeDecorator):
    """
    SQLAlchemy type for encrypted string storage.
    
    Usage:
        phone = Column(EncryptedString(key=vault_key))
    """
    
    impl = String
    
    def __init__(self, key: bytes, **kwargs):
        super().__init__(**kwargs)
        self.cipher = Fernet(key)
    
    def process_bind_param(self, value, dialect):
        """Encrypt before saving."""
        if value is None:
            return None
        return self.cipher.encrypt(value.encode()).decode()
    
    def process_result_value(self, value, dialect):
        """Decrypt after loading."""
        if value is None:
            return None
        return self.cipher.decrypt(value.encode()).decode()


# FastAPI Middleware for Automatic PII Masking in Logs
class PIIMaskingMiddleware:
    """
    Middleware to automatically mask PII in request/response logging.
    
    Installation:
        app.add_middleware(PIIMaskingMiddleware)
    """
    
    def __init__(self, app, masker: Optional[PIIMasker] = None):
        self.app = app
        self.masker = masker or PIIMasker()
        self.sensitive_fields = {
            "email", "phone", "telefono", "mobile", "cellulare",
            "piva", "vat", "partita_iva", "cf", "codice_fiscale",
            "iban", "cc", "credit_card", "password", "token"
        }
    
    async def __call__(self, scope, receive, send):
        """ASGI middleware entry point."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Wrap receive to mask request body in logs
        async def wrapped_receive():
            message = await receive()
            if message.get("type") == "http.request":
                body = message.get("body", b"")
                if body:
                    try:
                        data = json.loads(body)
                        masked = self._mask_sensitive_data(data)
                        message["body"] = json.dumps(masked).encode()
                    except json.JSONDecodeError:
                        pass
            return message
        
        await self.app(scope, wrapped_receive, send)
    
    def _mask_sensitive_data(self, data: Any) -> Any:
        """Recursively mask sensitive fields."""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if key.lower() in self.sensitive_fields and isinstance(value, str):
                    result[key] = self.masker.mask_text(value)
                elif isinstance(value, (dict, list)):
                    result[key] = self._mask_sensitive_data(value)
                else:
                    result[key] = value
            return result
        elif isinstance(data, list):
            return [self._mask_sensitive_data(item) for item in data]
        return data


# Structured Log Processor
class PIIFilteringLogger:
    """
    Logger wrapper that automatically masks PII before output.
    
    Usage:
        logger = PIIFilteringLogger(logging.getLogger(__name__))
        logger.info("User email: {email}", extra={"email": user.email})
    """
    
    def __init__(self, base_logger: logging.Logger):
        self.logger = base_logger
        self.masker = PIIMasker()
    
    def _mask_extra(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        """Mask PII in extra fields."""
        if not extra:
            return extra
        
        sensitive_keys = {"email", "phone", "telefono", "mobile", "user_id", "ip"}
        masked = {}
        
        for key, value in extra.items():
            if key in sensitive_keys and isinstance(value, str):
                masked[key] = self.masker.mask_text(value)
            else:
                masked[key] = value
        
        return masked
    
    def info(self, msg: str, *args, **kwargs):
        """Log info with PII masking."""
        if "extra" in kwargs:
            kwargs["extra"] = self._mask_extra(kwargs["extra"])
        self.logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        """Log warning with PII masking."""
        if "extra" in kwargs:
            kwargs["extra"] = self._mask_extra(kwargs["extra"])
        self.logger.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        """Log error with PII masking."""
        if "extra" in kwargs:
            kwargs["extra"] = self._mask_extra(kwargs["extra"])
        self.logger.error(msg, *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        """Log debug with PII masking."""
        if "extra" in kwargs:
            kwargs["extra"] = self._mask_extra(kwargs["extra"])
        self.logger.debug(msg, *args, **kwargs)


# Utility functions for GDPR
def anonymize_user_data(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Anonymize user data for GDPR right to erasure.
    
    Replaces PII with irreversible hashes while preserving
    statistical aggregates.
    """
    masker = PIIMasker()
    
    anonymized = {}
    for key, value in user_data.items():
        if key in ["nome", "cognome", "name", "surname"]:
            # Replace name with hash
            anonymized[key] = masker.hash_identifier(str(value), salt="anon")
        elif key in ["email", "phone", "telefono"]:
            # Nullify contact info
            anonymized[key] = None
        elif key in ["indirizzo", "address", "cap"]:
            # Keep only general location (country/region)
            anonymized[key] = "[REDACTED]"
        else:
            anonymized[key] = value
    
    # Mark as anonymized
    anonymized["_anonymized"] = True
    anonymized["_anonymized_at"] = datetime.now().isoformat()
    
    return anonymized


from datetime import datetime
