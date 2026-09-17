from sqlalchemy import Column, String, Integer, BigInteger, Text, Enum as SAEnum, JSON, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class PlotStatus(str, enum.Enum):
    available = "available"
    booked = "booked"
    reserved = "reserved"


class Plot(Base):
    __tablename__ = "plots"

    id = Column(String, primary_key=True)
    property_id = Column(String, nullable=False, index=True)
    plot_number = Column(String, nullable=False)
    sqft = Column(Integer, nullable=False)
    dimensions = Column(JSON, nullable=True)
    facing = Column(String, nullable=True)
    road_width = Column(Integer, nullable=True)
    price = Column(BigInteger, nullable=True)
    polygon = Column(Text, nullable=True)
    status = Column(SAEnum(PlotStatus), default=PlotStatus.available, index=True)
    grid_row = Column(Integer, default=0)
    grid_col = Column(Integer, default=0)
    col_span = Column(Integer, default=1)
    row_span = Column(Integer, default=1)
    notes = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    property = relationship(
        "Property", back_populates="plots",
        primaryjoin="Plot.property_id == Property.id",
        foreign_keys="[Plot.property_id]",
    )
    enquiries = relationship(
        "Enquiry", back_populates="plot",
        primaryjoin="Plot.id == Enquiry.plot_id",
        foreign_keys="[Enquiry.plot_id]",
    )
    analytics_events = relationship(
        "AnalyticsEvent", back_populates="plot",
        primaryjoin="Plot.id == AnalyticsEvent.plot_id",
        foreign_keys="[AnalyticsEvent.plot_id]",
    )
