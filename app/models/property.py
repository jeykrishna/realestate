from sqlalchemy import Column, String, Integer, BigInteger, Boolean, Text, ARRAY, Enum as SAEnum, JSON, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class PropertyCategory(str, enum.Enum):
    residential = "residential"
    agriculture = "agriculture"
    commercial = "commercial"


class PropertyStatus(str, enum.Enum):
    active = "active"
    draft = "draft"
    archived = "archived"


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Property(Base):
    __tablename__ = "properties"

    id = Column(String, primary_key=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    city = Column(String, nullable=False, index=True)
    category = Column(SAEnum(PropertyCategory), nullable=False, index=True)
    description = Column(Text, nullable=False)
    location = Column(JSON, nullable=True)
    hero_image = Column(String, nullable=True)
    gallery = Column(ARRAY(String), default=[])
    video_url = Column(String, nullable=True)
    map_embed_url = Column(String, nullable=True)
    rera_number = Column(String, nullable=True)
    amenities = Column(ARRAY(String), default=[])
    price_range = Column(JSON, nullable=True)
    sqft_range = Column(JSON, nullable=True)
    total_plots = Column(Integer, default=0)
    available_plots = Column(Integer, default=0)
    status = Column(SAEnum(PropertyStatus), default=PropertyStatus.draft, index=True)
    approval_status = Column(SAEnum(ApprovalStatus), nullable=False, default=ApprovalStatus.approved, index=True)
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    owner_id = Column(String, nullable=False, index=True)
    views_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    plot_area_sqft = Column(Integer, nullable=True)
    dimensions_label = Column(String, nullable=True)
    boundary_wall = Column(Boolean, nullable=True)
    ownership_type = Column(String, nullable=True)
    overlooking = Column(ARRAY(String), default=[])
    transaction_type = Column(String, nullable=True)
    construction_done = Column(Boolean, nullable=True)
    facing = Column(String, nullable=True)
    gated_community = Column(Boolean, nullable=True)
    corner_plot = Column(Boolean, nullable=True)
    price_per_sqft = Column(Integer, nullable=True)
    starting_price = Column(BigInteger, nullable=True)

    # Relationships
    owner = relationship(
        "User",
        back_populates="properties",
        primaryjoin="Property.owner_id == User.id",
        foreign_keys="[Property.owner_id]",
    )
    plots = relationship(
        "Plot", back_populates="property",
        primaryjoin="Property.id == Plot.property_id",
        foreign_keys="[Plot.property_id]",
        cascade="all, delete-orphan",
    )
    enquiries = relationship(
        "Enquiry", back_populates="property",
        primaryjoin="Property.id == Enquiry.property_id",
        foreign_keys="[Enquiry.property_id]",
        cascade="all, delete-orphan",
    )
    analytics_events = relationship(
        "AnalyticsEvent", back_populates="property",
        primaryjoin="Property.id == AnalyticsEvent.property_id",
        foreign_keys="[AnalyticsEvent.property_id]",
        cascade="all, delete-orphan",
    )
    images = relationship(
        "PropertyImage", back_populates="property",
        primaryjoin="Property.id == PropertyImage.property_id",
        foreign_keys="[PropertyImage.property_id]",
        cascade="all, delete-orphan",
    )
    plot_config = relationship(
        "PlotConfig", back_populates="property",
        primaryjoin="Property.id == PlotConfig.property_id",
        foreign_keys="[PlotConfig.property_id]",
        uselist=False, cascade="all, delete-orphan",
    )


class PropertyImage(Base):
    __tablename__ = "property_images"

    id = Column(String, primary_key=True)
    property_id = Column(String, nullable=False, index=True)
    image_url = Column(String, nullable=False)
    sort_order = Column(Integer, default=0)
    caption = Column(String, nullable=True)

    property = relationship(
        "Property", back_populates="images",
        primaryjoin="PropertyImage.property_id == Property.id",
        foreign_keys="[PropertyImage.property_id]",
    )
