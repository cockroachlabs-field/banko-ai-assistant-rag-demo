from sqlalchemy import create_engine, Column, String, Float, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pgvector.sqlalchemy import Vector
import pandas as pd
import numpy as np
import json

# Database connection settings
DB_URI = "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"

# Create SQLAlchemy engine
engine = create_engine(DB_URI)

# Create declarative base
Base = declarative_base()

class Expense(Base):
    __tablename__ = 'expenses'

    # Define columns - adjust types based on your CSV structure
    id = Column(String, primary_key=True)
    description = Column(String)
    amount = Column(Float)
    category = Column(String)
    embedding = Column(Vector(384))  # Store embedding as array of floats

def create_tables():
    Base.metadata.create_all(engine)

def load_data_to_db():
    # Read the CSV file
    df = pd.read_csv('expense_data_with_embeddings.csv')
    
    # Convert embedding column to PostgreSQL vector format
    if 'embedding' in df.columns:
        df['embedding'] = df['embedding'].apply(lambda x: numpy_vector_to_pg_vector(np.array(eval(x))) if isinstance(x, str) else numpy_vector_to_pg_vector(np.array(x)))
    
    # Convert DataFrame to SQL
    df.to_sql(
        'expenses',
        engine,
        if_exists='replace',
        index=False,
        method='multi'
    )
    print("Data successfully loaded to CockroachDB!")

def numpy_vector_to_pg_vector(vector: np.array) -> str:
    """Convert a numpy array to a PostgreSQL vector string format."""
    return json.dumps(vector.flatten().tolist())

def main():
    print("Creating tables...")
    create_tables()
    
    print("Loading data from CSV to CockroachDB...")
    load_data_to_db()

if __name__ == "__main__":
    main()
