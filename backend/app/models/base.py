from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData

# Create declarative base with app_schema as the default schema for all tables
Base = declarative_base(metadata=MetaData(schema="app_schema"))
