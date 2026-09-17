from sqlalchemy import Column, String, BigInteger, Enum as SAEnum, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class EventType(str, enum.Enum):
    view = "view"
    phone_click = "phone_click"
    whatsapp_click = "whatsapp_click"
    enquiry_submit = "enquiry_submit"


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    property_id = Column(String, nullable=False, index=True)
    plot_id = Column(String, nullable=True, index=True)
    event_type = Column(SAEnum(EventType), nullable=False, index=True)
    session_id = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    property = relationship(
        "Property", back_populates="analytics_events",
        primaryjoin="AnalyticsEvent.property_id == Property.id",
        foreign_keys="[AnalyticsEvent.property_id]",
    )
    plot = relationship(
        "Plot", back_populates="analytics_events",
        primaryjoin="AnalyticsEvent.plot_id == Plot.id",
        foreign_keys="[AnalyticsEvent.plot_id]",
    )
