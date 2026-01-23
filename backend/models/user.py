"""User Models"""
from sqlalchemy import Column, String, DateTime, Boolean, Enum as SQLEnum
from sqlalchemy.sql import func
from database.base import Base
import uuid
import enum

class UserRole(str, enum.Enum):
    USER = "user"
    SUPER_USER = "super"

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def has_privilege(self, required_role: UserRole) -> bool:
        """Check if user has required privilege level"""
        if self.role == UserRole.SUPER_USER:
            return True  # Super users have all privileges
        return self.role == required_role
