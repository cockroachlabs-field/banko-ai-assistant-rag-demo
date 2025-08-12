#!/usr/bin/env python3
"""
Dynamic Expense Data Generator
Simulates real-world expense generation with on-the-fly embedding creation.
This is more realistic than pre-populated embeddings.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import uuid
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text
import os
import json
from typing import List, Dict

# Database connection
DB_URI = os.getenv('DATABASE_URL', "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable")
engine = create_engine(DB_URI)

# Initialize embedding model (in real-world, this would be a service)
model = SentenceTransformer('all-MiniLM-L6-v2')

class DynamicExpenseGenerator:
    """
    Simulates a real-world expense tracking system where:
    1. Users add expenses via mobile app/web interface
    2. Embeddings are generated on-the-fly when data is inserted
    3. No pre-computed embeddings in storage
    """
    
    def __init__(self):
        self.merchants = [
            "Whole Foods Market", "Target", "Amazon", "Starbucks", "Shell Gas Station",
            "McDonald's", "Home Depot", "CVS Pharmacy", "Uber", "Netflix",
            "Local Market", "Best Buy", "Costco", "Chipotle", "Subway",
            "Walgreens", "Apple Store", "Trader Joe's", "Kroger", "Walmart"
        ]
        
        self.categories = {
            "Groceries": ["Fresh produce", "Dairy products", "Meat and poultry", "Pantry staples", "Organic foods"],
            "Transportation": ["Gas fill-up", "Uber ride", "Metro card reload", "Parking fee", "Car maintenance"],
            "Dining": ["Coffee and pastry", "Lunch meeting", "Dinner date", "Fast food", "Food delivery"],
            "Entertainment": ["Movie tickets", "Streaming service", "Concert tickets", "Gaming", "Books"],
            "Healthcare": ["Prescription medication", "Doctor visit", "Dental cleaning", "Vitamins", "Health insurance"],
            "Shopping": ["Clothing", "Electronics", "Home goods", "Personal care", "Gifts"],
            "Utilities": ["Electric bill", "Internet service", "Phone bill", "Water bill", "Trash service"]
        }
        
        self.payment_methods = ["Credit Card", "Debit Card", "Cash", "Mobile Payment", "Bank Transfer"]
    
    def generate_realistic_description(self, category: str, merchant: str, amount: float) -> str:
        """Generate realistic expense descriptions"""
        category_items = self.categories.get(category, ["Purchase"])
        item = random.choice(category_items)
        
        templates = [
            f"Bought {item.lower()} at {merchant} for ${amount:.2f}",
            f"Spent ${amount:.2f} on {item.lower()} using payment method",
            f"${amount:.2f} purchase: {item} from {merchant}",
            f"Transaction at {merchant}: {item.lower()} (${amount:.2f})",
            f"Paid ${amount:.2f} for {item.lower()} at {merchant}"
        ]
        
        return random.choice(templates)
    
    def generate_expense_batch(self, count: int = 10) -> List[Dict]:
        """Generate a batch of realistic expenses"""
        expenses = []
        
        for _ in range(count):
            category = random.choice(list(self.categories.keys()))
            merchant = random.choice(self.merchants)
            amount = round(random.uniform(5.99, 299.99), 2)
            
            # Generate realistic date (last 90 days)
            days_ago = random.randint(0, 90)
            expense_date = (datetime.now() - timedelta(days=days_ago)).date()
            
            description = self.generate_realistic_description(category, merchant, amount)
            
            expense = {
                "expense_id": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),  # In reality, this would be the logged-in user
                "expense_date": expense_date,
                "expense_amount": amount,
                "shopping_type": category,
                "description": description,
                "merchant": merchant,
                "payment_method": random.choice(self.payment_methods),
                "recurring": random.choice([True, False]) if category in ["Utilities", "Entertainment"] else False,
                "tags": [category.lower(), merchant.lower().replace(" ", "_")]
            }
            
            expenses.append(expense)
        
        return expenses
    
    def add_expense_with_embedding(self, expense_data: Dict) -> bool:
        """
        Add a single expense with dynamic embedding generation.
        This simulates real-world expense addition via API/app.
        """
        try:
            # Generate embedding on-the-fly (real-world scenario)
            content_text = f"{expense_data['description']} {expense_data['merchant']} {expense_data['shopping_type']}"
            embedding = model.encode(content_text)
            
            insert_query = text("""
                INSERT INTO expenses (
                    expense_id, user_id, expense_date, expense_amount, shopping_type,
                    description, merchant, payment_method, recurring, tags, embedding
                ) VALUES (
                    :expense_id, :user_id, :expense_date, :expense_amount, :shopping_type,
                    :description, :merchant, :payment_method, :recurring, :tags, :embedding
                )
            """)
            
            with engine.connect() as conn:
                conn.execute(insert_query, {
                    **expense_data,
                    "embedding": json.dumps(embedding.tolist())
                })
                conn.commit()
                
            print(f"✅ Added expense: {expense_data['description'][:50]}...")
            return True
            
        except Exception as e:
            print(f"❌ Error adding expense: {e}")
            return False
    
    def simulate_real_time_expenses(self, count: int = 5):
        """Simulate adding expenses in real-time (like a mobile app)"""
        print(f"🔄 Simulating {count} real-time expense additions...")
        
        expenses = self.generate_expense_batch(count)
        
        for i, expense in enumerate(expenses, 1):
            print(f"📱 User adding expense {i}/{count}...")
            success = self.add_expense_with_embedding(expense)
            
            if success:
                # Simulate some processing time
                import time
                time.sleep(0.5)
        
        print(f"✅ Simulation complete! Added {count} expenses with dynamic embeddings")
    
    def search_expenses_dynamically(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search expenses using dynamic embedding generation.
        This is how search would work in a real app.
        """
        print(f"🔍 Searching for: '{query}'")
        
        # Generate query embedding on-the-fly
        query_embedding = model.encode(query)
        
        search_query = text("""
            SELECT 
                expense_id, description, expense_amount, merchant, shopping_type, payment_method,
                embedding <-> :search_embedding as similarity_score
            FROM expenses 
            ORDER BY embedding <-> :search_embedding
            LIMIT :limit
        """)
        
        try:
            with engine.connect() as conn:
                results = conn.execute(search_query, {
                    'search_embedding': json.dumps(query_embedding.tolist()),
                    'limit': limit
                })
                
                expenses = []
                for row in results:
                    expense = dict(row._mapping)
                    expenses.append(expense)
                    print(f"  📄 {expense['description'][:60]}... (Score: {expense['similarity_score']:.3f})")
                
                return expenses
                
        except Exception as e:
            print(f"❌ Search error: {e}")
            return []

def main():
    """Demo the dynamic expense system"""
    generator = DynamicExpenseGenerator()
    
    print("🏦 DYNAMIC EXPENSE SYSTEM DEMO")
    print("=" * 50)
    
    # 1. Simulate real-time expense additions
    generator.simulate_real_time_expenses(count=3)
    
    print("\n" + "=" * 50)
    
    # 2. Demonstrate dynamic search
    queries = [
        "coffee and food purchases",
        "gas station transactions", 
        "grocery shopping"
    ]
    
    for query in queries:
        print(f"\n🔍 SEARCH: {query}")
        print("-" * 30)
        results = generator.search_expenses_dynamically(query, limit=3)
        print()

if __name__ == "__main__":
    main()
