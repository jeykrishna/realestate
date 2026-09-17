from sqlalchemy import Column, String, Text, Enum as SAEnum, DateTime, func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class EnquiryStatus(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    closed = "closed"


class Enquiry(Base):
    __tablename__ = "enquiries"

    id = Column(String, primary_key=True)
    property_id = Column(String, nullable=False, index=True)
    plot_id = Column(String, nullable=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    phone = Column(String(10), nullable=False)
    city = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    status = Column(SAEnum(EnquiryStatus), default=EnquiryStatus.new, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    property = relationship(
        "Property", back_populates="enquiries",
        primaryjoin="Enquiry.property_id == Property.id",
        foreign_keys="[Enquiry.property_id]",
    )
    plot = relationship(
        "Plot", back_populates="enquiries",
        primaryjoin="Enquiry.plot_id == Plot.id",
        foreign_keys="[Enquiry.plot_id]",
    )
