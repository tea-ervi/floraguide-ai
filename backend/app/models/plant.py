from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.models.base import Base

class PlantCategory(Base):
    __tablename__ = "plant_categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    image_url = Column(Text, nullable=False)

    species = relationship("PlantSpecies", back_populates="category")
    parts = relationship("PlantPart", back_populates="category")

class PlantSpecies(Base):
    __tablename__ = "plant_species"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    scientific_name = Column(String)
    description = Column(Text)
    optimal_lux = Column(Integer)
    optimal_humidity = Column(Integer)
    soil_composition = Column(Text)
    growth_duration_days = Column(Integer)
    embedding = Column(Vector(384))
    category_id = Column(Integer, ForeignKey("plant_categories.id"), nullable=False)

    category = relationship("PlantCategory", back_populates="species")
    user_plants = relationship("UserPlant", back_populates="species")

class PlantPart(Base):
    __tablename__ = "plant_parts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False)
    category_id = Column(Integer, ForeignKey("plant_categories.id"), nullable=False)

    category = relationship("PlantCategory", back_populates="parts")
    issues = relationship("VisualIssue", back_populates="part")

class VisualIssue(Base):
    __tablename__ = "visual_issues"
    id = Column(Integer, primary_key=True, index=True)
    symptom_title = Column(String, nullable=False)
    cause = Column(Text, nullable=False)
    solution = Column(Text, nullable=False)
    embedding = Column(Vector(384))
    plant_part_id = Column(Integer, ForeignKey("plant_parts.id"), nullable=False)

    part = relationship("PlantPart", back_populates="issues")