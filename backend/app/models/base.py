from sqlalchemy.orm import declarative_base

# Create declarative base with app_schema as the default schema for all tables
Base = declarative_base(metadata=None)

# Override the metadata to use app_schema by default
from sqlalchemy import MetaData
Base.metadata = MetaData(schema="app_schema")
