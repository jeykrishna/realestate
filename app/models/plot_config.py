from sqlalchemy import Column, String, Integer, JSON
from sqlalchemy.orm import relationship
from app.database import Base


class PlotConfig(Base):
    __tablename__ = "plot_configs"

    id = Column(String, primary_key=True)
    property_id = Column(String, unique=True, nullable=False, index=True)
    layout_type = Column(String, default="grid")
    rows = Column(Integer, nullable=True)
    cols = Column(Integer, nullable=True)
    roads = Column(JSON, default=[])
    labels = Column(JSON, default={})
    image_url = Column(String, nullable=True)
    img_width = Column(Integer, nullable=True)
    img_height = Column(Integer, nullable=True)

    property = relationship(
        "Property", back_populates="plot_config",
        primaryjoin="PlotConfig.property_id == Property.id",
        foreign_keys="[PlotConfig.property_id]",
    )
