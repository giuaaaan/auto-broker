"""
AUTO-BROKER: Authentication Router
JWT-based authentication for Mission Control Center.
"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Configuration
SECRET_KEY = "auto-broker-secret-key-change-in-production-2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Security
security = HTTPBearer()


# Mock users database - In production, use database
USERS = {
    "admin@autobroker.com": {
        "id": "user-001",
        "email": "admin@autobroker.com",
        "name": "Admin User",
        "role": "admin",
        "password": "admin"  # In production: hashed
    },
    "operator@autobroker.com": {
        "id": "user-002",
        "email": "operator@autobroker.com",
        "name": "Operator User",
        "role": "operator",
        "password": "operator"
    }
}


# ==========================================
# SCHEMAS
# ==========================================

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str


# ==========================================
# JWT FUNCTIONS
# ==========================================

def create_access_token(data: dict) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(credentials: HTTPAuthorizationCredentials) -> dict:
    """Verify JWT token."""
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Dependency to get current authenticated user."""
    payload = verify_token(credentials)
    email = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    
    user = USERS.get(email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"]
    }


# ==========================================
# ENDPOINTS
# ==========================================

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user and return JWT token."""
    user = USERS.get(request.email)
    
    if not user or user["password"] != request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create token
    access_token = create_access_token({
        "sub": user["email"],
        "user_id": user["id"],
        "role": user["role"]
    })
    
    return LoginResponse(
        access_token=access_token,
        user={
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"]
        }
    )


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout user (invalidate token on client side)."""
    # In a more complex setup, you might add the token to a blacklist
    return {"success": True, "message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info."""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        name=current_user["name"],
        role=current_user["role"]
    )


@router.post("/refresh")
async def refresh_token(current_user: dict = Depends(get_current_user)):
    """Refresh access token."""
    new_token = create_access_token({
        "sub": current_user["email"],
        "user_id": current_user["id"],
        "role": current_user["role"]
    })
    
    return {
        "access_token": new_token,
        "token_type": "bearer"
    }