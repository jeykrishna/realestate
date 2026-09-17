from sqlalchemy import Column, String, ARRAY, Enum as SAEnum
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    owner = "owner"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String(10), nullable=False)
    role = Column(SAEnum(UserRole), nullable=False, default=UserRole.owner)
    property_ids = Column(ARRAY(String), default=[])

    # Relationships
    properties = relationship(
        "Property",
        back_populates="owner",
        primaryjoin="User.id == foreign(Property.owner_id)",
    )
