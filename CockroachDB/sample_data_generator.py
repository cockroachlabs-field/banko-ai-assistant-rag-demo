import pandas as pd
import random
import uuid
from datetime import datetime, timedelta

# Sample data for merchants and categories
merchants = [
    ("Local Market", "Groceries"), ("Whole Foods", "Groceries"), ("Costco", "Groceries"),
    ("Italian Bistro", "Restaurant"), ("McDonald's", "Restaurant"), ("Starbucks", "Coffee"),
    ("Best Buy", "Electronics"), ("Amazon", "Electronics"), ("Apple Store", "Electronics"),
    ("Planet Fitness", "Subscription"), ("Netflix", "Subscription"), ("Spotify", "Subscription"),
    ("Delta Airlines", "Travel"), ("Hilton Hotels", "Travel"), ("Uber", "Transport"),
    ("Shell Gas Station", "Fuel"), ("Tesla Supercharger", "Fuel"), ("Lyft", "Transport"),
    ("Nike Store", "Shopping"), ("Walmart", "Shopping"), ("Target", "Shopping"),
    ("Home Depot", "Home Improvement"), ("Lowe's", "Home Improvement"), ("IKEA", "Home Improvement")
]

# Payment methods
payment_methods = ["Credit Card", "Debit Card", "PayPal", "Apple Pay", "Bank Transfer"]

# Generate 100 sample expense rows
expense_data = []
start_date = datetime(2025, 1, 1)

for _ in range(3000):
    expense_id = str(uuid.uuid4())
    user_id = "24e64c01-6f77-4f4d-a0ab-2532cdfefc22"  # Single user for this example
    expense_date = (start_date + timedelta(days=random.randint(0, 60))).strftime("%Y-%m-%d")
    expense_amount = round(random.uniform(10, 500), 2)
    merchant, shopping_type = random.choice(merchants)
    payment_method = random.choice(payment_methods)
    recurring = random.choice([True, False])
    
    description = f"Spent ${expense_amount:.2f} on {shopping_type.lower()} at {merchant} using {payment_method}."
    
    tags = [shopping_type]
    if recurring:
        tags.append("Recurring")
    
    expense_data.append([
        expense_id, user_id, expense_date, expense_amount, shopping_type, description, merchant,
        payment_method, recurring, tags
    ])

# Create DataFrame
columns = [
    "expense_id", "user_id", "expense_date", "expense_amount", "shopping_type", "description",
    "merchant", "payment_method", "recurring", "tags"
]
df_expenses = pd.DataFrame(expense_data, columns=columns)

# Display the DataFrame
print(df_expenses.head())

# Save to CSV
df_expenses.to_csv('expense_data.csv', index=False)
print("Data saved to expense_data.csv")
