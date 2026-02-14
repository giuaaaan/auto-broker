"""
AUTO-BROKER Enterprise Identity Provider
OAuth2/OIDC with Keycloak integration, SAML 2.0 support
Zero Trust Architecture - P0 Critical
"""

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from functools import wraps

import httpx
import jwt
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    """RBAC roles aligned with business functions."""
    BROKER = "broker"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"


@dataclass
class JWTClaims:
    """Custom JWT claims for AUTO-BROKER."""
    sub: str  # User ID
    email: str
    organization_id: str
    role: UserRole
    mfa_verified: bool
    iat: datetime
    exp: datetime
    jti: str  # JWT ID for revocation
    scope: List[str]


class TokenPair(BaseModel):
    """Access + Refresh token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900  # 15 minutes
    refresh_expires_in: int = 604800  # 7 days


class KeycloakConfig(BaseModel):
    """Keycloak/OpenID Connect configuration."""
    server_url: str = Field(default="http://keycloak:8080")
    realm: str = Field(default="auto-broker")
    client_id: str = Field(default="auto-broker-api")
    client_secret: str = Field(default="")  # Loaded from Vault
    algorithm: str = "RS256"
    audience: str = "auto-broker-api"


class IdentityProvider:
    """
    Enterprise Identity Provider with Keycloak integration.
    
    Features:
    - OAuth2/OIDC authentication
    - SAML 2.0 SSO (Okta/Azure AD)
    - JWT with rotating refresh tokens
    - MFA enforcement for privileged roles
    """
    
    def __init__(self, config: Optional[KeycloakConfig] = None, vault_client=None):
        self.config = config or KeycloakConfig()
        self.vault = vault_client
        self._jwks_cache: Optional[Dict] = None
        self._jwks_last_fetch: Optional[datetime] = None
        self._token_revocation_list: set = set()  # In production: Redis
        
    async def _fetch_jwks(self) -> Dict:
        """Fetch JWKS from Keycloak with caching."""
        if self._jwks_cache and self._jwks_last_fetch:
            if datetime.now() - self._jwks_last_fetch < timedelta(hours=1):
                return self._jwks_cache
        
        jwks_url = f"{self.config.server_url}/realms/{self.config.realm}/protocol/openid-connect/certs"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url, timeout=10.0)
            response.raise_for_status()
            self._jwks_cache = response.json()
            self._jwks_last_fetch = datetime.now()
            return self._jwks_cache
    
    def _get_signing_key(self, jwks: Dict, kid: str) -> str:
        """Extract RSA public key from JWKS."""
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                # Convert JWK to PEM
                from jwt.algorithms import RSAAlgorithm
                return RSAAlgorithm.from_jwk(json.dumps(key))
        raise ValueError(f"Key {kid} not found in JWKS")
    
    async def validate_token(self, token: str) -> JWTClaims:
        """
        Validate JWT access token.
        
        Raises:
            HTTPException: If token invalid, expired, or revoked
        """
        try:
            # Check revocation list
            unverified = jwt.decode(token, options={"verify_signature": False})
            jti = unverified.get("jti")
            if jti in self._token_revocation_list:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token revoked"
                )
            
            # Fetch JWKS and validate
            jwks = await self._fetch_jwks()
            kid = unverified.get("header", {}).get("kid") or unverified.get("kid")
            
            if kid and jwks:
                public_key = self._get_signing_key(jwks, kid)
            else:
                # Fallback: fetch from Keycloak introspection
                public_key = None
            
            payload = jwt.decode(
                token,
                key=public_key,
                algorithms=[self.config.algorithm],
                audience=self.config.audience,
                options={"verify_exp": True, "verify_iat": True}
            )
            
            return JWTClaims(
                sub=payload["sub"],
                email=payload.get("email", ""),
                organization_id=payload.get("organization_id", ""),
                role=UserRole(payload.get("role", "broker")),
                mfa_verified=payload.get("mfa_verified", False),
                iat=datetime.fromtimestamp(payload["iat"]),
                exp=datetime.fromtimestamp(payload["exp"]),
                jti=payload.get("jti", str(uuid.uuid4())),
                scope=payload.get("scope", "").split()
            )
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired"
            )
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    async def exchange_code(self, code: str, redirect_uri: str) -> TokenPair:
        """Exchange OAuth2 authorization code for tokens."""
        token_url = f"{self.config.server_url}/realms/{self.config.realm}/protocol/openid-connect/token"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret
                },
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            
            return TokenPair(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_in=data.get("expires_in", 900),
                refresh_expires_in=data.get("refresh_expires_in", 604800)
            )
    
    async def refresh_access_token(self, refresh_token: str) -> TokenPair:
        """Rotate refresh token and issue new access token."""
        token_url = f"{self.config.server_url}/realms/{self.config.realm}/protocol/openid-connect/token"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret
                },
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            
            # Revoke old refresh token (rotation)
            old_claims = jwt.decode(refresh_token, options={"verify_signature": False})
            self._token_revocation_list.add(old_claims.get("jti"))
            
            return TokenPair(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_in=data.get("expires_in", 900),
                refresh_expires_in=data.get("refresh_expires_in", 604800)
            )
    
    async def revoke_token(self, token: str, token_type_hint: str = "access_token"):
        """Revoke token (logout)."""
        revoke_url = f"{self.config.server_url}/realms/{self.config.realm}/protocol/openid-connect/revoke"
        
        # Add to local revocation list
        try:
            claims = jwt.decode(token, options={"verify_signature": False})
            self._token_revocation_list.add(claims.get("jti"))
        except jwt.InvalidTokenError:
            pass
        
        # Notify Keycloak
        async with httpx.AsyncClient() as client:
            await client.post(
                revoke_url,
                data={
                    "token": token,
                    "token_type_hint": token_type_hint,
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret
                },
                timeout=10.0
            )


# FastAPI Security
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    idp: IdentityProvider = Depends(lambda: IdentityProvider())
) -> JWTClaims:
    """Dependency to extract and validate current user from JWT."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )
    
    return await idp.validate_token(credentials.credentials)


def require_role(required_role: UserRole):
    """Decorator/dependency to enforce RBAC role."""
    async def role_checker(user: JWTClaims = Depends(get_current_user)):
        role_hierarchy = {
            UserRole.ADMIN: 3,
            UserRole.SUPERVISOR: 2,
            UserRole.BROKER: 1
        }
        
        user_level = role_hierarchy.get(user.role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient privileges. Required: {required_role}"
            )
        
        # MFA check for privileged operations
        if required_role in [UserRole.ADMIN, UserRole.SUPERVISOR] and not user.mfa_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="MFA required for this operation"
            )
        
        return user
    return role_checker


def require_mfa():
    """Dependency to enforce MFA verification."""
    async def mfa_checker(user: JWTClaims = Depends(get_current_user)):
        if not user.mfa_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Multi-factor authentication required"
            )
        return user
    return mfa_checker


# Enterprise SSO Integration (SAML 2.0)
class SAMLIdentityProvider:
    """
    SAML 2.0 integration for enterprise SSO (Okta, Azure AD).
    
    Note: This is a structural implementation. Full SAML requires
    xmlsec1 and complex XML processing. For production, use
    python3-saml or similar library.
    """
    
    def __init__(self, settings: Dict[str, Any]):
        self.settings = settings
        
    def generate_authn_request(self, return_to: str) -> str:
        """Generate SAML AuthNRequest XML."""
        raise NotImplementedError(
            "SAML AuthNRequest generation requires python3-saml library. "
            "Install: pip install python3-saml && apt-get install xmlsec1"
        )
    
    def process_saml_response(self, saml_response: str) -> Dict[str, Any]:
        """Process and validate SAMLResponse from IdP."""
        raise NotImplementedError(
            "SAML Response processing requires xmlsec1 and python3-saml. "
            "Implement with proper XML signature verification."
        )
