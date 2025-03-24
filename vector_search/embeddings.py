import pandas as pd
from sentence_transformers import SentenceTransformer
import numpy as np

def load_data(csv_path):
    return pd.read_csv("expense_data.csv")

def generate_embeddings(descriptions, model_name='all-MiniLM-L6-v2'):
    # Initialize the sentence transformer model
    model = SentenceTransformer(model_name)
    
    # Generate embeddings
    embeddings = model.encode(descriptions, show_progress_bar=True)
    return embeddings

def save_embeddings(df, embeddings, output_path):
    # Convert embeddings to list of lists for easier storage in DataFrame
    embeddings_list = embeddings.tolist()
    
    # Add embeddings as a new column
    df['embedding'] = embeddings_list
    
    # Save the updated DataFrame to CSV
    df.to_csv("expense_data_with_embeddings.csv", index=False)

def main():
    # File paths
    input_csv = 'expense_data.csv'
    
    # Load the data
    print("Loading expense data...")
    df = load_data(input_csv)
    
    # Generate embeddings for descriptions
    print("Generating embeddings...")
    embeddings = generate_embeddings(df['description'].tolist())
    
    # Save DataFrame with embeddings
    print("Saving data with embeddings...")
    save_embeddings(df, embeddings, input_csv)
    
    print(f"Embeddings shape: {embeddings.shape}")
    print("Embeddings saved as 'embedding' column in the CSV file")

if __name__ == "__main__":
    main()
