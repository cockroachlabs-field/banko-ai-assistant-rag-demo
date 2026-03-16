"""
Data enrichment module for improving vector search accuracy.

This module enriches expense descriptions with contextual information
to improve vector search accuracy and relevance.
"""

from datetime import datetime


class DataEnricher:
    """Enriches expense data with contextual information for better vector search."""
    
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
        """Create enriched description for vector search indexing."""
        return f"Spent ${amount:.2f} on {category.lower()} at {merchant} using {payment_method}."
    
    def create_searchable_text(
        self, 
        description: str, 
        merchant: str, 
        amount: float, 
        category: str,
        **kwargs
    ) -> str:
        """Create searchable text for vector embedding."""
        payment_method = kwargs.get('payment_method', 'Credit Card')
        return f"Spent ${amount:.2f} on {category.lower()} at {merchant} using {payment_method}."
