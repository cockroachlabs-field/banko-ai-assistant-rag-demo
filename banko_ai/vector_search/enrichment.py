"""
Data enrichment module for improving vector search accuracy.

This module enriches expense descriptions with merchant context and other relevant
information to improve vector search accuracy and relevance.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import re


class DataEnricher:
    """Enriches expense data with contextual information for better vector search."""
    
    def __init__(self):
        """Initialize the data enricher."""
        self.merchant_categories = {
            "grocery": ["Whole Foods Market", "Trader Joe's", "Kroger", "Safeway", "Publix", "Walmart", "Target"],
            "retail": ["Amazon", "Best Buy", "Apple Store", "Home Depot", "Costco", "Target", "Walmart"],
            "dining": ["Starbucks", "McDonald's", "Chipotle", "Subway", "Pizza Hut", "Domino's"],
            "transportation": ["Shell Gas Station", "Exxon", "Uber", "Lyft", "Metro", "Parking"],
            "healthcare": ["CVS Pharmacy", "Walgreens", "Rite Aid", "Hospital", "Clinic"],
            "entertainment": ["Netflix", "Spotify", "Movie Theater", "Concert", "Gaming"],
            "utilities": ["Electric Company", "Internet Provider", "Phone Company", "Water Company"]
        }
        
        self.amount_ranges = {
            "low": (0, 25),
            "medium": (25, 100),
            "high": (100, 500),
            "very_high": (500, float('inf'))
        }
    
    def enrich_expense_description(
        self, 
        description: str, 
        merchant: str, 
        amount: float, 
        category: str,
        payment_method: str,
        date: datetime,
        **kwargs
    ) -> str:
        """
        Create a simple description that matches the original CSV format.
        
        Args:
            description: Original expense description
            merchant: Merchant name
            amount: Expense amount
            category: Expense category
            payment_method: Payment method used
            date: Expense date
            **kwargs: Additional metadata
            
        Returns:
            Simple description string matching original CSV format
        """
        # Create the exact same format as the original CSV
        enriched_description = f"Spent ${amount:.2f} on {category.lower()} at {merchant} using {payment_method}."
        
        return enriched_description
    
    def _get_merchant_context(self, merchant: str, amount: float) -> Optional[str]:
        """Get merchant-specific context."""
        merchant_lower = merchant.lower()
        
        # Gas stations
        if any(gas in merchant_lower for gas in ["shell", "exxon", "chevron", "bp", "gas"]):
            return f"fuel purchase at {merchant}"
        
        # Grocery stores
        if any(grocery in merchant_lower for grocery in ["whole foods", "trader joe", "kroger", "safeway"]):
            return f"grocery shopping at {merchant}"
        
        # Online retailers
        if merchant_lower == "amazon":
            return f"online purchase from {merchant}"
        
        # Coffee shops
        if any(coffee in merchant_lower for coffee in ["starbucks", "dunkin", "peet", "coffee"]):
            return f"coffee and food at {merchant}"
        
        # Fast food
        if any(fast in merchant_lower for fast in ["mcdonald", "burger", "pizza", "chipotle", "subway"]):
            return f"fast food at {merchant}"
        
        # Pharmacies
        if any(pharmacy in merchant_lower for pharmacy in ["cvs", "walgreens", "rite aid", "pharmacy"]):
            return f"pharmacy visit at {merchant}"
        
        # Home improvement
        if any(home in merchant_lower for home in ["home depot", "lowes", "ace hardware"]):
            return f"home improvement at {merchant}"
        
        return None
    
    def _get_amount_context(self, amount: float) -> Optional[str]:
        """Get amount-based context."""
        if amount < 10:
            return "small purchase"
        elif amount < 50:
            return "moderate expense"
        elif amount < 200:
            return "significant purchase"
        elif amount < 500:
            return "major expense"
        else:
            return "large transaction"
    
    def _get_category_context(self, category: str, merchant: str) -> Optional[str]:
        """Get category-specific context."""
        category_lower = category.lower()
        
        if category_lower == "groceries":
            return "food and household items"
        elif category_lower == "transportation":
            return "travel and commuting"
        elif category_lower == "dining":
            return "restaurant and food service"
        elif category_lower == "entertainment":
            return "leisure and recreation"
        elif category_lower == "healthcare":
            return "medical and wellness"
        elif category_lower == "shopping":
            return "retail and consumer goods"
        elif category_lower == "utilities":
            return "essential services"
        
        return None
    
    def _get_payment_context(self, payment_method: str) -> Optional[str]:
        """Get payment method context."""
        payment_lower = payment_method.lower()
        
        if "credit" in payment_lower:
            return "paid with credit card"
        elif "debit" in payment_lower:
            return "paid with debit card"
        elif "cash" in payment_lower:
            return "paid with cash"
        elif "mobile" in payment_lower:
            return "paid with mobile payment"
        elif "bank" in payment_lower:
            return "paid via bank transfer"
        
        return None
    
    def _get_temporal_context(self, date: datetime) -> Optional[str]:
        """Get temporal context based on date."""
        from datetime import date as date_type
        # Convert both to datetime for consistent comparison
        if isinstance(date, date_type):
            date = datetime.combine(date, datetime.min.time())
        now = datetime.now()
        days_ago = (now - date).days
        
        if days_ago == 0:
            return "today"
        elif days_ago == 1:
            return "yesterday"
        elif days_ago <= 7:
            return "this week"
        elif days_ago <= 30:
            return "this month"
        elif days_ago <= 90:
            return "recently"
        else:
            return "in the past"
    
    def _get_merchant_category(self, merchant: str) -> Optional[str]:
        """Get merchant category for additional context."""
        merchant_lower = merchant.lower()
        
        for category, merchants in self.merchant_categories.items():
            if any(m in merchant_lower for m in merchants):
                return category
        
        return None
    
    def _clean_description(self, description: str) -> str:
        """Clean and format the enriched description."""
        # Remove extra spaces
        description = re.sub(r'\s+', ' ', description)
        
        # Remove duplicate words
        words = description.split()
        seen = set()
        unique_words = []
        for word in words:
            if word.lower() not in seen:
                unique_words.append(word)
                seen.add(word.lower())
        
        return ' '.join(unique_words).strip()
    
    def create_searchable_text(
        self, 
        description: str, 
        merchant: str, 
        amount: float, 
        category: str,
        **kwargs
    ) -> str:
        """
        Create a simple searchable text that matches the original CSV format.
        
        This creates the exact same format as the original CSV: 
        "Spent $X.XX on [category] at [merchant] using [payment_method]."
        """
        # Extract required parameters from kwargs
        payment_method = kwargs.get('payment_method', 'Credit Card')
        
        # Create the exact same format as the original CSV
        searchable_text = f"Spent ${amount:.2f} on {category.lower()} at {merchant} using {payment_method}."
        
        return searchable_text
