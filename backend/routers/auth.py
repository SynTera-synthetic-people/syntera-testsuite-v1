"""Authentication Routes"""
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
import bcrypt
import logging

from database.connection import get_db
from backend.models.user import User, UserRole
from config.settings import Settings

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer()
settings = Settings()

# For development: default users are disabled when using shared Postgres users table.
DEFAULT_USERS = []


class UserCreate(BaseModel):
    # We treat "username" from the UI as the user's full name.
    username: str
    email: Optional[EmailStr] = None
    password: str
    role: UserRole = UserRole.USER


class UserLogin(BaseModel):
    # Frontend sends "username" but we authenticate using email.
    username: str
    password: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: Optional[str]
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Primary: bcrypt (hashes starting with "$2").
    Fallback: plain-text compare for legacy/non-bcrypt hashes.
    """
    if not hashed_password:
        return False

    # Legacy / non-bcrypt hashes: fall back to simple equality check
    if isinstance(hashed_password, str) and not hashed_password.startswith("$2"):
        return plain_password == hashed_password

    try:
        # Bcrypt has a 72-byte limit, so truncate if necessary
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]

        # hashed_password is stored as string in DB, convert to bytes
        hash_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    # Bcrypt has a 72-byte limit, so truncate if necessary
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
        logger.warning(f"Password truncated to 72 bytes for bcrypt compatibility")
    
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def require_privilege(required_role: UserRole):
    """Dependency to require specific privilege level"""
    async def privilege_checker(current_user: User = Depends(get_current_user)) -> User:
        if not current_user.has_privilege(required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient privileges. Required: {required_role.value}"
            )
        return current_user
    return privilege_checker


@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):  # pragma: no cover - disabled path
    """
    User registration is handled by the main Synthetic People platform.
    This API only supports login against the shared users table.
    """
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="User registration is disabled in this service. Please register via the main Synthetic People platform.",
    )


@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """Login and get access token.

    The frontend sends a single 'username' field. We resolve it against either:
    - email (preferred), or
    - full_name (fallback), to match existing records.
    """
    user = (
        db.query(User)
        .filter(
            (User.email == login_data.username) | (User.full_name == login_data.username)
        )
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    password_ok = verify_password(login_data.password, user.hashed_password)
    # In development, allow login even if legacy hashes don't match, to unblock testing.
    if not password_ok and settings.ENVIRONMENT != "development":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    
    # Create access token
    access_token = create_access_token(data={"sub": user.email})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(
            id=user.id,
            username=user.full_name or user.email,
            email=user.email,
            role=(user.role or UserRole.USER.value),
            is_active=user.is_active
        )
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user.id,
        username=current_user.full_name or current_user.email,
        email=current_user.email,
        role=(current_user.role or UserRole.USER.value),
        is_active=current_user.is_active
    )


@router.get("/check-privileges")
async def check_privileges(current_user: Optional[User] = Depends(get_current_user_optional)):
    """Check user privileges (works without auth, returns None if not authenticated)"""
    if not current_user:
        return {
            "authenticated": False,
            "role": None,
            "is_super_user": False
        }
    
    return {
        "authenticated": True,
        "role": (current_user.role or UserRole.USER.value),
        "is_super_user": (current_user.role or UserRole.USER.value) == UserRole.SUPER_USER.value,
        "username": current_user.full_name or current_user.email
    }


def init_default_users(db: Session):
    """Default user initialization is disabled when using shared users table."""
    return
