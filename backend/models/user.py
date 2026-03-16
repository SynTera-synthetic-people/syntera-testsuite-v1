"""User model mapped to shared Postgres users table."""
from sqlalchemy import Column, String, DateTime, Boolean, Integer
from database.base import Base
import enum


class UserRole(str, enum.Enum):
    USER = "user"
    SUPER_USER = "super"


class User(Base):
    __tablename__ = "user"

    # Core identity fields (match shared table)
    id = Column(String, primary_key=True)
    full_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)

    # Role / type flags
    user_type = Column(String, nullable=True)
    role = Column(String, nullable=True)  # stores values like "user", "super", etc.
    is_verified = Column(Boolean, default=False)

    # Tokens
    verification_token = Column(String, nullable=True)
    verification_expiry = Column(DateTime(timezone=False), nullable=True)
    reset_token = Column(String, nullable=True)
    reset_token_expiry = Column(DateTime(timezone=False), nullable=True)

    # Activity / trial flags
    is_active = Column(Boolean, default=True)
    is_trial = Column(Boolean, default=True)
    exploration_count = Column(Integer, default=0)
    trial_exploration_limit = Column(Integer, default=1)
    must_change_password = Column(Boolean, default=False)

    # Pricing / org fields
    account_tier = Column(String, nullable=True)
    organization_id = Column(String, nullable=True)

    # Audit fields (match existing table columns)
    created_at = Column(DateTime(timezone=False), nullable=True)
    last_activity_at = Column(DateTime(timezone=False), nullable=True)

    def has_privilege(self, required_role: UserRole) -> bool:
        """Check if user has required privilege level based on textual role."""
        role_value = (self.role or UserRole.USER.value).lower()
        if role_value == UserRole.SUPER_USER.value:
            return True
        return role_value == required_role.value
