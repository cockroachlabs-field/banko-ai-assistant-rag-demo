# insert_data.py
import json
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from sqlalchemy import text, create_engine
import pandas as pd


# Database connection settings
DB_URI = "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable"

# Create SQLAlchemy engine
engine = create_engine(DB_URI)


def numpy_vector_to_pg_vector(vector):
    return json.dumps(vector.flatten().tolist())

def read_csv_data(file_path):
    df = pd.read_csv('/Users/david/Documents/Demos/ML-AI-Banking-App/vector_search/expense_data.csv')
    return df.to_dict('records')

def insert_content(data_content, batch_size=50):
    model = SentenceTransformer('all-MiniLM-L6-v2')
    insert_query = text("""
        INSERT INTO expenses (
            expense_id, user_id, expense_date, expense_amount, shopping_type,
            description, merchant, payment_method, recurring, tags,
            embedding
        ) VALUES (
            :expense_id, :user_id, :expense_date, :expense_amount, :shopping_type,
            :description, :merchant, :payment_method, :recurring, :tags,
            :embedding
        )
    """)
    
    for i in range(0, len(data_content), batch_size):
        batch = data_content[i:i + batch_size]
        batch_parameters = []
        for content in tqdm(batch):
            # Create embedding from description and merchant
            content_text = f"{content['description']}"
            embedding = model.encode(content_text)
            
            # Convert string representation of tags list to actual list
            tags = eval(content['tags']) if isinstance(content['tags'], str) else content['tags']
            
            batch_parameters.append({
                "expense_id": content["expense_id"],
                "user_id": content["user_id"],
                "expense_date": content["expense_date"],
                "expense_amount": content["expense_amount"],
                "shopping_type": content["shopping_type"],
                "description": content["description"],
                "merchant": content["merchant"],
                "payment_method": content["payment_method"],
                "recurring": content["recurring"],
                "tags": tags,
                "embedding": numpy_vector_to_pg_vector(embedding)
            })
        
        with engine.connect() as conn:
            conn.execute(insert_query, batch_parameters)
            conn.commit()

if __name__ == "__main__":
    data = read_csv_data('expense_data.csv')
    insert_content(data)
    print("Data inserted successfully.")
