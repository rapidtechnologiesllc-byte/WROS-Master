from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON
from datetime import datetime
from app.models.base import Base


class GeneticWeightPopulation(Base):
    """Tracks genetic algorithm populations for weight optimization."""
    __tablename__ = "genetic_weight_populations"

    id = Column(Integer, primary_key=True)
    orchestrator_id = Column(String(100), nullable=False, index=True)
    generation_num = Column(Integer, nullable=False)
    population_size = Column(Integer, default=50)
    elite_count = Column(Integer, default=5)
    best_fitness = Column(Float, nullable=True)
    avg_fitness = Column(Float, nullable=True)
    worst_fitness = Column(Float, nullable=True)
    genetic_diversity = Column(Float, nullable=True)  # 0.0 to 1.0
    elite_chromosomes = Column(JSON, nullable=True)  # Top 5 chromosomes
    mutation_rate = Column(Float, default=0.15)
    crossover_rate = Column(Float, default=0.8)
    convergence_status = Column(String(50), default="EVOLVING")  # CONVERGED, STALLED, EVOLVING
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_archived = Column(Boolean, default=False)

    def __repr__(self):
        return f"<GeneticWeightPopulation orchestrator={self.orchestrator_id} gen={self.generation_num} fitness={self.best_fitness:.2f}>"
