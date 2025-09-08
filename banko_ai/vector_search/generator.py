"""
Enhanced expense data generator with data enrichment.

This module generates realistic expense data with enriched descriptions
for improved vector search accuracy.
"""

import os
import uuid
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from .enrichment import DataEnricher


class EnhancedExpenseGenerator:
    """Enhanced expense generator with data enrichment for better vector search."""
    
    def __init__(self, database_url: Optional[str] = None):
        """Initialize the enhanced expense generator."""
        self.database_url = database_url or os.getenv('DATABASE_URL', "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable")
        self._engine = None
        self.enricher = DataEnricher()
        self._embedding_model = None
        self._merchants = None
        self._categories = None
        self._payment_methods = None
        self._user_ids = None
    
    @property
    def engine(self):
        """Get SQLAlchemy engine (lazy import)."""
        if self._engine is None:
            from sqlalchemy import create_engine
            self._engine = create_engine(self.database_url)
        return self._engine
    
    @property
    def embedding_model(self):
        """Get embedding model (lazy import)."""
        if self._embedding_model is None:
            from sentence_transformers import SentenceTransformer
            self._embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        return self._embedding_model
    
    @property
    def merchants(self):
        """Get merchants data (lazy load)."""
        if self._merchants is None:
            self._init_merchants_and_categories()
        return self._merchants
    
    @property
    def categories(self):
        """Get categories data (lazy load)."""
        if self._categories is None:
            self._init_merchants_and_categories()
        return self._categories
    
    @property
    def payment_methods(self):
        """Get payment methods (lazy load)."""
        if self._payment_methods is None:
            self._init_merchants_and_categories()
        return self._payment_methods
    
    @property
    def user_ids(self):
        """Get user IDs (lazy load)."""
        if self._user_ids is None:
            self._init_merchants_and_categories()
        return self._user_ids
    
    def _init_merchants_and_categories(self):
        """Initialize merchants and categories data - matches original CSV exactly."""
        # Use the exact merchants from the original CSV
        self._merchants = [
            "Starbucks", "Local Market", "McDonald's", "IKEA", "Amazon", "Whole Foods",
            "Italian Bistro", "Uber", "Lyft", "Spotify", "Delta Airlines", "Costco",
            "Home Depot", "Shell Gas Station", "Lowe's", "Tesla Supercharger", "Planet Fitness",
            "Apple Store", "Walmart", "Target", "Netflix", "Best Buy", "CVS Pharmacy",
            "Walgreens", "Rite Aid", "Chipotle", "Subway", "Pizza Hut", "Domino's",
            "Exxon", "Chevron", "BP", "Dunkin' Donuts", "Peet's Coffee", "Ace Hardware",
            "Movie Theater", "Concert Venue", "Gaming Store", "Electric Company",
            "Internet Provider", "Phone Company", "Water Company"
        ]
        
        # Use the exact categories from the original CSV with appropriate merchants
        self._categories = {
            "Groceries": {
                "items": ["Fresh produce", "Dairy products", "Meat and poultry", "Pantry staples", "Organic foods", "Beverages", "Snacks"],
                "merchants": ["Whole Foods", "Local Market", "Costco", "Walmart", "Target"],
                "amount_range": (10, 150)
            },
            "Home Improvement": {
                "items": ["Tools", "Hardware", "Paint", "Lumber", "Electrical supplies", "Plumbing supplies", "Garden supplies"],
                "merchants": ["Home Depot", "Lowe's", "Ace Hardware", "IKEA"],
                "amount_range": (20, 500)
            },
            "Electronics": {
                "items": ["Smartphone", "Laptop", "Tablet", "Headphones", "Camera", "Gaming console", "Smart home device"],
                "merchants": ["Apple Store", "Best Buy", "Amazon", "Target", "Walmart"],
                "amount_range": (50, 1000)
            },
            "Subscription": {
                "items": ["Streaming service", "Software subscription", "Gym membership", "News subscription", "Cloud storage", "Music service"],
                "merchants": ["Netflix", "Spotify", "Planet Fitness", "Electric Company", "Internet Provider"],
                "amount_range": (10, 50)
            },
            "Shopping": {
                "items": ["Clothing", "Shoes", "Accessories", "Home decor", "Books", "Toys", "Beauty products"],
                "merchants": ["Amazon", "Target", "Walmart", "IKEA", "Best Buy"],
                "amount_range": (15, 200)
            },
            "Restaurant": {
                "items": ["Dinner", "Lunch", "Breakfast", "Takeout", "Delivery", "Catering", "Fine dining"],
                "merchants": ["McDonald's", "Italian Bistro", "Chipotle", "Subway", "Pizza Hut", "Domino's"],
                "amount_range": (15, 100)
            },
            "Transport": {
                "items": ["Uber ride", "Lyft ride", "Taxi", "Bus fare", "Train ticket", "Flight", "Car rental"],
                "merchants": ["Uber", "Lyft", "Delta Airlines"],
                "amount_range": (5, 500)
            },
            "Fuel": {
                "items": ["Gas fill-up", "Electric charging", "Diesel fuel", "Premium gas", "Regular gas"],
                "merchants": ["Shell Gas Station", "Tesla Supercharger", "Exxon", "Chevron", "BP"],
                "amount_range": (20, 100)
            },
            "Travel": {
                "items": ["Flight", "Hotel", "Car rental", "Travel insurance", "Airport parking", "Baggage fee"],
                "merchants": ["Delta Airlines", "Hilton Hotels"],
                "amount_range": (100, 2000)
            },
            "Coffee": {
                "items": ["Coffee", "Espresso", "Latte", "Cappuccino", "Pastry", "Sandwich", "Breakfast"],
                "merchants": ["Starbucks", "Local Market", "Whole Foods", "Costco"],
                "amount_range": (3, 25)
            }
        }
        
        # Use the exact payment methods from the original CSV
        self._payment_methods = [
            "Debit Card", "PayPal", "Apple Pay", "Bank Transfer", "Credit Card"
        ]
        self._user_ids = [str(uuid.uuid4()) for _ in range(100)]  # Generate 100 user IDs
    
    def generate_expense(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate a single enriched expense record that matches the original CSV format."""
        # Select category and get associated data
        category = random.choice(list(self.categories.keys()))
        category_data = self.categories[category]
        
        # Select merchant from category-specific merchants
        merchant = random.choice(category_data["merchants"])
        
        # Generate amount within category range
        amount = round(random.uniform(*category_data["amount_range"]), 2)
        
        # Select item from category items
        item = random.choice(category_data["items"])
        
        # Generate basic description
        basic_description = f"Bought {item.lower()}"
        
        # Generate date (last 90 days)
        days_ago = random.randint(0, 90)
        expense_date = (datetime.now() - timedelta(days=days_ago)).date()
        
        # Generate additional metadata
        payment_method = random.choice(self.payment_methods)
        recurring = random.choice([True, False]) if category in ["Subscription", "Coffee"] else False
        tags = [category.lower(), merchant.lower().replace(" ", "_")]
        
        # Create the exact same description format as the original CSV
        enriched_description = f"Spent ${amount:.2f} on {category.lower()} at {merchant} using {payment_method}."
        
        # Create searchable text for embedding (same as description for simplicity)
        searchable_text = enriched_description
        
        # Generate embedding
        embedding = self.embedding_model.encode([searchable_text])[0].tolist()
        
        return {
            "expense_id": str(uuid.uuid4()),
            "user_id": user_id or random.choice(self.user_ids),
            "expense_date": expense_date,
            "expense_amount": amount,
            "shopping_type": category,
            "description": enriched_description,
            "merchant": merchant,
            "payment_method": payment_method,
            "recurring": recurring,
            "tags": tags,
            "embedding": embedding,
            "searchable_text": searchable_text  # Store for debugging
        }
    
    def generate_expenses(self, count: int, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Generate multiple enriched expense records."""
        expenses = []
        
        for _ in range(count):
            expense = self.generate_expense(user_id)
            expenses.append(expense)
        
        return expenses
    
    def save_expenses_to_database(self, expenses: List[Dict[str, Any]]) -> int:
        """Save expenses to the database with retry logic for CockroachDB."""
        import pandas as pd
        import time
        import random
        from sqlalchemy.exc import OperationalError
        
        # Prepare data for insertion
        data_to_insert = []
        for expense in expenses:
            data_to_insert.append({
                'expense_id': expense['expense_id'],
                'user_id': expense['user_id'],
                'expense_date': expense['expense_date'],
                'expense_amount': expense['expense_amount'],
                'shopping_type': expense['shopping_type'],
                'description': expense['description'],
                'merchant': expense['merchant'],
                'payment_method': expense['payment_method'],
                'recurring': expense['recurring'],
                'tags': expense['tags'],
                'embedding': expense['embedding']
            })
        
        # Insert in smaller batches to reduce transaction conflicts
        batch_size = 50  # Reduced from 100 to minimize conflicts
        total_inserted = 0
        total_batches = (len(data_to_insert) + batch_size - 1) // batch_size
        
        print(f"📊 Inserting {len(data_to_insert)} records in {total_batches} batches of {batch_size}")
        
        for i in range(0, len(data_to_insert), batch_size):
            batch = data_to_insert[i:i + batch_size]
            
            # Retry logic for CockroachDB transaction conflicts
            max_retries = 5
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    with self.engine.begin() as conn:
                        # Use pandas to insert the batch
                        df = pd.DataFrame(batch)
                        df.to_sql('expenses', conn, if_exists='append', index=False, method='multi')
                        # Transaction is automatically committed when exiting the context
                        
                    # Only increment counter after successful transaction
                    total_inserted += len(batch)
                    batch_num = i//batch_size + 1
                    print(f"✅ Batch {batch_num}/{total_batches}: {len(batch)} records inserted (Total: {total_inserted})")
                    break  # Success, exit retry loop
                        
                except OperationalError as e:
                    # Check if it's a CockroachDB serialization failure (SQL state 40001)
                    if "40001" in str(e) or "SerializationFailure" in str(e) or "restart transaction" in str(e).lower():
                        retry_count += 1
                        if retry_count < max_retries:
                            # Exponential backoff with jitter
                            base_delay = 0.1 * (2 ** retry_count)
                            jitter = random.uniform(0, 0.1)
                            delay = base_delay + jitter
                            print(f"Transaction conflict detected, retrying in {delay:.2f}s (attempt {retry_count}/{max_retries})")
                            time.sleep(delay)
                            continue
                        else:
                            print(f"Max retries exceeded for batch {i//batch_size + 1}: {e}")
                            return total_inserted
                    else:
                        # Non-retryable error
                        print(f"Non-retryable database error: {e}")
                        return total_inserted
                        
                except Exception as e:
                    print(f"Unexpected error saving batch {i//batch_size + 1}: {e}")
                    return total_inserted
        
        return total_inserted
    
    def clear_expenses(self) -> bool:
        """Clear all expenses from the database with retry logic."""
        import time
        import random
        from sqlalchemy import text
        from sqlalchemy.exc import OperationalError
        
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                with self.engine.begin() as conn:
                    conn.execute(text("DELETE FROM expenses"))
                    # Transaction is automatically committed when exiting the context
                    return True
                    
            except OperationalError as e:
                # Check if it's a CockroachDB serialization failure (SQL state 40001)
                if "40001" in str(e) or "SerializationFailure" in str(e) or "restart transaction" in str(e).lower():
                    retry_count += 1
                    if retry_count < max_retries:
                        # Exponential backoff with jitter
                        base_delay = 0.1 * (2 ** retry_count)
                        jitter = random.uniform(0, 0.1)
                        delay = base_delay + jitter
                        print(f"Transaction conflict detected while clearing, retrying in {delay:.2f}s (attempt {retry_count}/{max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        print(f"Max retries exceeded while clearing expenses: {e}")
                        return False
                else:
                    # Non-retryable error
                    print(f"Non-retryable database error while clearing: {e}")
                    return False
                    
            except Exception as e:
                print(f"Unexpected error clearing expenses: {e}")
                return False
        
        return False
    
    def get_expense_count(self) -> int:
        """Get the current number of expenses in the database."""
        try:
            # Ensure tables exist first
            self._ensure_tables_exist()
            
            from sqlalchemy import text
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM expenses"))
                return result.scalar()
        except Exception as e:
            print(f"Error getting expense count: {e}")
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                print("💡 Make sure CockroachDB is running:")
                print("   cockroach start --insecure")
                print("   Or set DATABASE_URL to your database connection string")
            return 0
    
    def _ensure_tables_exist(self):
        """Ensure database tables exist."""
        try:
            from ..utils.database import DatabaseManager
            db_manager = DatabaseManager(self.database_url)
            db_manager.create_tables()
        except Exception as e:
            print(f"Error creating tables: {e}")
            # Continue anyway - tables might already exist
    
    def generate_and_save(
        self, 
        count: int, 
        user_id: Optional[str] = None, 
        clear_existing: bool = False
    ) -> int:
        """Generate and save expenses to the database."""
        if clear_existing:
            self.clear_expenses()
        
        expenses = self.generate_expenses(count, user_id)
        return self.save_expenses_to_database(expenses)
    
    def create_user_specific_indexes(self) -> bool:
        """Create user-specific vector indexes for CockroachDB."""
        try:
            with self.engine.connect() as conn:
                # Create user-specific vector index
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_expenses_user_embedding 
                    ON expenses (user_id, embedding) 
                    USING ivfflat (embedding vector_cosine_ops) 
                    WITH (lists = 100)
                """))
                
                # Create regional index if supported
                try:
                    conn.execute(text("""
                        CREATE INDEX IF NOT EXISTS idx_expenses_user_embedding_regional 
                        ON expenses (user_id, embedding) 
                        LOCALITY REGIONAL BY ROW AS region
                    """))
                except Exception:
                    # Regional indexing might not be supported in all deployments
                    pass
                
                conn.commit()
                return True
        except Exception as e:
            print(f"Error creating user-specific indexes: {e}")
            return False
