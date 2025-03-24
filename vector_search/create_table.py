# create_table.py
from sqlalchemy import text,create_engine
import os

# Set your CockroachDB connection string here
DATABASE_URL = os.getenv('DATABASE_URL', "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable")

# Initialize the database engine
engine = create_engine(DATABASE_URL)


def create_expenses_table():
    create_table_query = text("""
        CREATE TABLE expenses (
            expense_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            expense_date DATE NOT NULL,
            expense_amount DECIMAL(10,2) NOT NULL,
            shopping_type STRING NOT NULL,
            description STRING,
            merchant STRING,
            payment_method STRING NOT NULL,
            recurring BOOL DEFAULT FALSE,
            tags STRING[],
            embedding vector(384),
            VECTOR INDEX (embedding)
        );
    """)
    with engine.connect() as conn:
        conn.execute(create_table_query)
        conn.commit()

if __name__ == "__main__":
    create_expenses_table()
    print("Table 'expenses' created successfully.")
