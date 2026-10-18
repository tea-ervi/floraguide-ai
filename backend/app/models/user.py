from sqlalchemy import Column, Integer, String, Date, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(TIMESTAMP, nullable=False)

    plants = relationship("UserPlant", back_populates="user")

class UserPlant(Base):
    __tablename__ = "user_plants"
    id = Column(Integer, primary_key=True, index=True)
    custom_name = Column(String)
    planted_at = Column(Date)
    last_watered_at = Column(TIMESTAMP)
    watering_interval_days = Column(Integer)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plant_id = Column(Integer, ForeignKey("plant_species.id"), nullable=False)

    user = relationship("User", back_populates="plants")
    species = relationship("PlantSpecies", back_populates="user_plants")