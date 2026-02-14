"""
AUTO-BROKER HashiCorp Vault Integration
Dynamic secrets, automatic rotation, zero hardcoded credentials
Zero Trust - P0 Critical
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from functools import wraps

import hvac
from hvac.exceptions import VaultError
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


@dataclass
class DatabaseCredentials:
    """Dynamic database credentials from Vault."""
    username: str
    password: str
    host: str
    port: int
    database: str
    lease_id: str
    lease_duration: int
    renewable: bool


@dataclass
class APIKeySecret:
    """API key with metadata."""
    key: str
    name: str
    rotation_date: Optional[datetime]
    expires_at: Optional[datetime]


class VaultClient:
    """
    Enterprise HashiCorp Vault client for AUTO-BROKER.
    
    Features:
    - Dynamic database credentials with automatic rotation
    - API key retrieval from secure paths
    - JWT signing key management with rotation
    - PKI certificate issuance
    """
    
    def __init__(
        self,
        vault_url: str = "http://vault:8200",
        role_id: Optional[str] = None,
        secret_id: Optional[str] = None,
        token: Optional[str] = None,
        namespace: Optional[str] = None
    ):
        """
        Initialize Vault client.
        
        Auth methods:
        1. AppRole (role_id + secret_id) - Production
        2. Token - Development/testing
        3. Kubernetes - K8s deployments
        """
        self.vault_url = vault_url
        self.namespace = namespace
        
        # Initialize client
        self.client = hvac.Client(url=vault_url, namespace=namespace)
        
        # Authenticate
        if token:
            self.client.token = token
        elif role_id and secret_id:
            self._auth_approle(role_id, secret_id)
        else:
            raise ValueError("Must provide token or role_id+secret_id for Vault auth")
        
        # Verify connection
        if not self.client.is_authenticated():
            raise VaultError("Vault authentication failed")
        
        logger.info("Vault client initialized", extra={"vault_url": vault_url})
        
        # Cache for credentials
        self._db_credentials: Optional[DatabaseCredentials] = None
        self._db_creds_expiry: Optional[datetime] = None
        self._jwt_keys: Dict[str, Any] = {}
        self._api_keys: Dict[str, APIKeySecret] = {}
    
    def _auth_approle(self, role_id: str, secret_id: str):
        """Authenticate using AppRole."""
        response = self.client.auth.approle.login(
            role_id=role_id,
            secret_id=secret_id
        )
        self.client.token = response["auth"]["client_token"]
        logger.info("Vault authenticated via AppRole")
    
    # ==================== Dynamic Database Credentials ====================
    
    async def get_database_credentials(
        self,
        mount_point: str = "database",
        role: str = "auto-broker-app",
        ttl: str = "1h"
    ) -> DatabaseCredentials:
        """
        Get dynamic PostgreSQL credentials from Vault.
        
        Args:
            mount_point: Vault database secrets engine mount
            role: Database role to assume
            ttl: Credential lifetime
        
        Returns:
            DatabaseCredentials with username/password
        """
        # Return cached if valid
        if self._db_credentials and self._db_creds_expiry:
            if datetime.now() < self._db_creds_expiry - timedelta(minutes=5):
                return self._db_credentials
        
        try:
            # Generate credentials
            response = self.client.secrets.database.generate_credentials(
                name=role,
                mount_point=mount_point
            )
            
            data = response["data"]
            lease = response["lease_duration"]
            
            creds = DatabaseCredentials(
                username=data["username"],
                password=data["password"],
                host="postgres",  # From Vault config
                port=5432,
                database="broker_db",
                lease_id=response["lease_id"],
                lease_duration=lease,
                renewable=response.get("renewable", True)
            )
            
            # Cache
            self._db_credentials = creds
            self._db_creds_expiry = datetime.now() + timedelta(seconds=lease)
            
            logger.info(
                "Database credentials generated",
                extra={
                    "username": creds.username,
                    "lease_duration": lease,
                    "masked": True
                }
            )
            
            return creds
            
        except VaultError as e:
            logger.error(f"Failed to get database credentials: {e}")
            raise
    
    async def renew_database_credentials(self):
        """Renew lease for current database credentials."""
        if not self._db_credentials:
            raise ValueError("No credentials to renew")
        
        try:
            self.client.sys.renew_lease(
                lease_id=self._db_credentials.lease_id,
                increment=3600  # 1 hour
            )
            
            # Update expiry
            self._db_creds_expiry = datetime.now() + timedelta(hours=1)
            
            logger.info("Database credentials renewed")
            
        except VaultError as e:
            logger.error(f"Failed to renew credentials: {e}")
            # Will fetch new credentials on next get_database_credentials call
            self._db_credentials = None
    
    async def revoke_database_credentials(self):
        """Revoke current database credentials immediately."""
        if self._db_credentials:
            try:
                self.client.sys.revoke_lease(
                    lease_id=self._db_credentials.lease_id
                )
                logger.info("Database credentials revoked")
            except VaultError as e:
                logger.error(f"Failed to revoke credentials: {e}")
            finally:
                self._db_credentials = None
                self._db_creds_expiry = None
    
    # ==================== API Keys Management ====================
    
    def get_api_key(self, service: str, environment: str = "production") -> APIKeySecret:
        """
        Get API key from Vault KV store.
        
        Args:
            service: Service name (e.g., 'hume', 'dat', 'dhl')
            environment: Environment (production, staging, dev)
        
        Returns:
            APIKeySecret with key and metadata
        """
        cache_key = f"{service}:{environment}"
        
        # Check cache
        if cache_key in self._api_keys:
            key_secret = self._api_keys[cache_key]
            if not key_secret.expires_at or datetime.now() < key_secret.expires_at:
                return key_secret
        
        # Fetch from Vault
        path = f"secret/auto-broker/{environment}/{service}"
        
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point="secret"
            )
            
            data = response["data"]["data"]
            metadata = response["data"]["metadata"]
            
            key_secret = APIKeySecret(
                key=data["api_key"],
                name=service,
                rotation_date=datetime.fromisoformat(data.get("rotation_date")) if data.get("rotation_date") else None,
                expires_at=datetime.fromisoformat(data.get("expires_at")) if data.get("expires_at") else None
            )
            
            # Cache
            self._api_keys[cache_key] = key_secret
            
            logger.info(f"API key retrieved for {service}")
            
            return key_secret
            
        except VaultError as e:
            logger.error(f"Failed to get API key for {service}: {e}")
            raise
    
    def rotate_api_key(self, service: str, new_key: str, environment: str = "production"):
        """
        Rotate API key in Vault.
        
        Args:
            service: Service name
            new_key: New API key value
            environment: Environment
        """
        path = f"secret/auto-broker/{environment}/{service}"
        
        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                path=path,
                secret={
                    "api_key": new_key,
                    "rotation_date": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(days=90)).isoformat()
                },
                mount_point="secret"
            )
            
            # Invalidate cache
            cache_key = f"{service}:{environment}"
            if cache_key in self._api_keys:
                del self._api_keys[cache_key]
            
            logger.info(f"API key rotated for {service}")
            
        except VaultError as e:
            logger.error(f"Failed to rotate API key: {e}")
            raise
    
    # ==================== JWT Key Management ====================
    
    def get_jwt_signing_key(self, key_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get JWT signing key from Vault Transit engine.
        
        Supports key rotation with multiple active keys.
        
        Args:
            key_id: Specific key ID, or None for latest
        
        Returns:
            Dict with key material and metadata
        """
        mount_point = "transit"
        key_name = "jwt-signing"
        
        try:
            if key_id:
                # Get specific key version
                response = self.client.secrets.transit.read_key(
                    name=key_name,
                    mount_point=mount_point
                )
                
                keys = response["data"]["keys"]
                if key_id not in keys:
                    raise ValueError(f"Key {key_id} not found")
                
                return {
                    "key_id": key_id,
                    "public_key": keys[key_id]["public_key"],
                    "creation_time": keys[key_id]["creation_time"]
                }
            else:
                # Get latest key
                response = self.client.secrets.transit.read_key(
                    name=key_name,
                    mount_point=mount_point
                )
                
                latest_version = response["data"]["latest_version"]
                keys = response["data"]["keys"]
                
                return {
                    "key_id": str(latest_version),
                    "public_key": keys[str(latest_version)]["public_key"],
                    "creation_time": keys[str(latest_version)]["creation_time"],
                    "min_decryption_version": response["data"]["min_decryption_version"]
                }
                
        except VaultError as e:
            logger.error(f"Failed to get JWT key: {e}")
            raise
    
    def rotate_jwt_key(self) -> str:
        """
        Rotate JWT signing key.
        
        Returns:
            New key ID
        
        Note: Old keys remain valid for verification until
        min_decryption_version is updated.
        """
        try:
            response = self.client.secrets.transit.rotate_key(
                name="jwt-signing",
                mount_point="transit"
            )
            
            new_version = response["data"]["latest_version"]
            logger.info(f"JWT signing key rotated to version {new_version}")
            
            return str(new_version)
            
        except VaultError as e:
            logger.error(f"Failed to rotate JWT key: {e}")
            raise
    
    def sign_jwt(self, payload: Dict[str, Any], key_version: Optional[str] = None) -> str:
        """
        Sign JWT using Vault Transit (asymmetric signing).
        
        Args:
            payload: JWT claims
            key_version: Key version to use, or None for latest
        
        Returns:
            Signed JWT string
        """
        try:
            # For Transit engine, we'd use sign operation
            # This requires the data to be pre-hashed
            import hashlib
            import json
            
            data = json.dumps(payload, sort_keys=True).encode()
            digest = hashlib.sha256(data).hexdigest()
            
            response = self.client.secrets.transit.sign_data(
                name="jwt-signing",
                hash_input=digest,
                key_version=key_version,
                mount_point="transit"
            )
            
            signature = response["data"]["signature"]
            
            # Construct JWT (simplified - real impl uses proper JWT library)
            header = {"alg": "RS256", "kid": key_version or "latest"}
            jwt_parts = [
                self._base64_url_encode(header),
                self._base64_url_encode(payload),
                signature
            ]
            
            return ".".join(jwt_parts)
            
        except VaultError as e:
            logger.error(f"Failed to sign JWT: {e}")
            raise
    
    def _base64_url_encode(self, data: Any) -> str:
        """Base64URL encode data."""
        import base64
        import json
        
        if isinstance(data, dict):
            data = json.dumps(data).encode()
        elif isinstance(data, str):
            data = data.encode()
        
        return base64.urlsafe_b64encode(data).decode().rstrip("=")
    
    # ==================== PKI Certificates ====================
    
    def issue_service_certificate(
        self,
        service_name: str,
        ttl: str = "720h",  # 30 days
        alt_names: Optional[list] = None
    ) -> Dict[str, str]:
        """
        Issue mTLS certificate for service.
        
        Args:
            service_name: Name of service
            ttl: Certificate lifetime
            alt_names: Subject Alternative Names
        
        Returns:
            Dict with certificate, private_key, ca_chain
        """
        try:
            response = self.client.secrets.pki.issue_certificate(
                name="auto-broker-services",
                common_name=f"{service_name}.auto-broker.svc.cluster.local",
                alt_names=alt_names or [],
                ttl=ttl,
                mount_point="pki"
            )
            
            data = response["data"]
            
            return {
                "certificate": data["certificate"],
                "private_key": data["private_key"],
                "ca_chain": "\n".join(data["ca_chain"]),
                "serial_number": data["serial_number"],
                "expiration": data["expiration"]
            }
            
        except VaultError as e:
            logger.error(f"Failed to issue certificate: {e}")
            raise


# Decorator for automatic credential rotation
def with_vault_credentials(vault_client: VaultClient, resource_type: str = "database"):
    """Decorator to inject Vault credentials into function."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if resource_type == "database":
                creds = await vault_client.get_database_credentials()
                kwargs["db_credentials"] = creds
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Singleton instance management
_vault_instance: Optional[VaultClient] = None


def get_vault_client(
    vault_url: Optional[str] = None,
    role_id: Optional[str] = None,
    secret_id: Optional[str] = None
) -> VaultClient:
    """Get or create singleton Vault client."""
    global _vault_instance
    
    if _vault_instance is None:
        import os
        _vault_instance = VaultClient(
            vault_url=vault_url or os.getenv("VAULT_ADDR", "http://vault:8200"),
            role_id=role_id or os.getenv("VAULT_ROLE_ID"),
            secret_id=secret_id or os.getenv("VAULT_SECRET_ID"),
            token=os.getenv("VAULT_TOKEN")  # Dev only
        )
    
    return _vault_instance
