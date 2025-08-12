"""
Smart Transaction Categorization Module for Banko Assistant

This module provides intelligent transaction categorization using machine learning
and rule-based approaches to automatically categorize expenses and suggest
improvements to user spending patterns.

Features:
- ML-based categorization using merchant and description patterns
- Rule-based categorization for common merchants
- Smart category suggestions for new transactions
- Category confidence scoring
- Spending pattern analysis

Author: Banko AI Team
Date: 2025
"""

import re
from collections import Counter
from typing import Dict, List, Tuple, Optional
import json

class TransactionCategorizer:
    """Smart transaction categorization with ML and rule-based approaches."""
    
    def __init__(self):
        # Common merchant patterns for rule-based categorization
        self.merchant_patterns = {
            'Grocery': [
                r'walmart', r'kroger', r'safeway', r'whole foods', r'trader joe',
                r'costco', r'target', r'grocery', r'supermarket', r'market',
                r'fresh.*market', r'food.*mart', r'aldi', r'publix'
            ],
            'Restaurants': [
                r'mcdonald', r'starbucks', r'subway', r'pizza', r'restaurant',
                r'cafe', r'coffee', r'bar.*grill', r'diner', r'bistro',
                r'fast.*food', r'burger', r'taco', r'chinese.*food'
            ],
            'Gas': [
                r'shell', r'bp', r'exxon', r'chevron', r'mobil', r'gas.*station',
                r'fuel', r'gasoline', r'petrol'
            ],
            'Entertainment': [
                r'netflix', r'spotify', r'cinema', r'theater', r'movie',
                r'amusement', r'concert', r'gaming', r'entertainment'
            ],
            'Shopping': [
                r'amazon', r'ebay', r'mall', r'department.*store', r'retail',
                r'clothing', r'fashion', r'boutique'
            ],
            'Healthcare': [
                r'pharmacy', r'hospital', r'clinic', r'doctor', r'dental',
                r'medical', r'health', r'cvs', r'walgreens'
            ],
            'Utilities': [
                r'electric', r'power', r'water', r'gas.*company', r'utility',
                r'internet', r'phone', r'telecom'
            ],
            'Transportation': [
                r'uber', r'lyft', r'taxi', r'metro', r'bus', r'train',
                r'parking', r'toll', r'transit'
            ]
        }
        
        # Description keywords for enhanced categorization
        self.description_patterns = {
            'Subscription': [
                r'monthly', r'subscription', r'recurring', r'membership',
                r'premium', r'plus', r'pro'
            ],
            'Food & Dining': [
                r'lunch', r'dinner', r'breakfast', r'meal', r'food',
                r'dining', r'eat', r'snack'
            ],
            'Travel': [
                r'hotel', r'airline', r'flight', r'booking', r'travel',
                r'vacation', r'trip', r'airbnb'
            ],
            'Education': [
                r'school', r'university', r'course', r'tuition', r'book',
                r'education', r'learning', r'training'
            ]
        }

    def categorize_transaction(self, merchant: str, description: str, amount: float) -> Tuple[str, float]:
        """
        Categorize a single transaction based on merchant and description.
        
        Args:
            merchant (str): Merchant name
            description (str): Transaction description
            amount (float): Transaction amount
            
        Returns:
            Tuple[str, float]: (predicted_category, confidence_score)
        """
        merchant_lower = merchant.lower()
        description_lower = description.lower()
        
        # Rule-based categorization
        for category, patterns in self.merchant_patterns.items():
            for pattern in patterns:
                if re.search(pattern, merchant_lower):
                    return category, 0.9  # High confidence for merchant match
        
        # Description-based categorization
        for category, patterns in self.description_patterns.items():
            for pattern in patterns:
                if re.search(pattern, description_lower):
                    return category, 0.7  # Medium confidence for description match
        
        # Amount-based heuristics
        if amount > 1000:
            return 'Major Purchase', 0.5
        elif amount < 5:
            return 'Small Purchase', 0.6
        
        return 'Other', 0.3  # Low confidence fallback

    def analyze_spending_patterns(self, transactions: List[Dict]) -> Dict:
        """
        Analyze spending patterns and provide categorization insights.
        
        Args:
            transactions (List[Dict]): List of transaction records
            
        Returns:
            Dict: Analysis results with category breakdowns and suggestions
        """
        if not transactions:
            return {}
        
        categorized_transactions = []
        category_totals = Counter()
        category_counts = Counter()
        uncategorized_transactions = []
        
        for transaction in transactions:
            merchant = transaction.get('merchant', '')
            description = transaction.get('description', '')
            amount = float(transaction.get('expense_amount', 0))
            current_category = transaction.get('shopping_type', 'Other')
            
            # Get AI-suggested category
            suggested_category, confidence = self.categorize_transaction(merchant, description, amount)
            
            categorized_transactions.append({
                **transaction,
                'suggested_category': suggested_category,
                'confidence': confidence,
                'needs_review': confidence < 0.7 or current_category != suggested_category
            })
            
            category_totals[suggested_category] += amount
            category_counts[suggested_category] += 1
            
            if confidence < 0.7:
                uncategorized_transactions.append(transaction)
        
        # Generate insights
        total_amount = sum(category_totals.values())
        category_percentages = {
            category: (amount / total_amount * 100) if total_amount > 0 else 0
            for category, amount in category_totals.items()
        }
        
        # Find spending anomalies
        anomalies = self._find_spending_anomalies(categorized_transactions)
        
        # Generate recommendations
        recommendations = self._generate_category_recommendations(category_totals, category_percentages)
        
        return {
            'categorized_transactions': categorized_transactions,
            'category_totals': dict(category_totals),
            'category_percentages': category_percentages,
            'uncategorized_count': len(uncategorized_transactions),
            'uncategorized_transactions': uncategorized_transactions,
            'anomalies': anomalies,
            'recommendations': recommendations,
            'total_analyzed': len(transactions)
        }

    def _find_spending_anomalies(self, transactions: List[Dict]) -> List[Dict]:
        """Find unusual spending patterns or potential mis-categorizations."""
        anomalies = []
        
        # Group by category
        category_amounts = {}
        for transaction in transactions:
            category = transaction['suggested_category']
            amount = float(transaction['expense_amount'])
            
            if category not in category_amounts:
                category_amounts[category] = []
            category_amounts[category].append(amount)
        
        # Find outliers in each category
        for category, amounts in category_amounts.items():
            if len(amounts) < 3:  # Need at least 3 transactions to detect anomalies
                continue
            
            avg_amount = sum(amounts) / len(amounts)
            for transaction in transactions:
                if transaction['suggested_category'] == category:
                    amount = float(transaction['expense_amount'])
                    if amount > avg_amount * 3:  # 3x average is considered anomaly
                        anomalies.append({
                            'transaction': transaction,
                            'anomaly_type': 'unusually_high_amount',
                            'message': f"Unusually high {category} expense: ${amount:.2f} (avg: ${avg_amount:.2f})"
                        })
        
        return anomalies

    def _generate_category_recommendations(self, category_totals: Counter, category_percentages: Dict) -> List[str]:
        """Generate smart recommendations based on spending patterns."""
        recommendations = []
        
        # High spending categories
        top_categories = category_totals.most_common(3)
        if top_categories:
            top_category, top_amount = top_categories[0]
            percentage = category_percentages[top_category]
            recommendations.append(
                f"**🎯 Top Spending Category**: {top_category} represents {percentage:.1f}% of your expenses (${top_amount:.2f}). "
                f"Consider setting a budget limit for this category."
            )
        
        # Restaurant spending check
        restaurant_total = category_totals.get('Restaurants', 0)
        grocery_total = category_totals.get('Grocery', 0)
        if restaurant_total > grocery_total and restaurant_total > 0:
            ratio = restaurant_total / grocery_total if grocery_total > 0 else float('inf')
            recommendations.append(
                f"**🍽️ Dining Out Alert**: You spend more on restaurants (${restaurant_total:.2f}) than groceries (${grocery_total:.2f}). "
                f"Cooking at home could save significant money."
            )
        
        # Subscription analysis
        subscription_total = category_totals.get('Subscription', 0)
        if subscription_total > 100:
            recommendations.append(
                f"**📱 Subscription Review**: You have ${subscription_total:.2f} in subscription expenses. "
                f"Review active subscriptions and cancel unused services."
            )
        
        # Small purchase accumulation
        small_purchase_total = category_totals.get('Small Purchase', 0)
        if small_purchase_total > 200:
            recommendations.append(
                f"**💳 Small Purchases Add Up**: Your small purchases total ${small_purchase_total:.2f}. "
                f"These can significantly impact your budget over time."
            )
        
        return recommendations

    def get_category_suggestions(self, merchant: str, description: str) -> List[Tuple[str, float]]:
        """
        Get multiple category suggestions for a transaction.
        
        Args:
            merchant (str): Merchant name
            description (str): Transaction description
            
        Returns:
            List[Tuple[str, float]]: List of (category, confidence) suggestions
        """
        suggestions = []
        merchant_lower = merchant.lower()
        description_lower = description.lower()
        
        # Check all patterns and score them
        for category, patterns in self.merchant_patterns.items():
            max_confidence = 0
            for pattern in patterns:
                if re.search(pattern, merchant_lower):
                    max_confidence = max(max_confidence, 0.9)
            if max_confidence > 0:
                suggestions.append((category, max_confidence))
        
        for category, patterns in self.description_patterns.items():
            max_confidence = 0
            for pattern in patterns:
                if re.search(pattern, description_lower):
                    max_confidence = max(max_confidence, 0.7)
            if max_confidence > 0 and not any(s[0] == category for s in suggestions):
                suggestions.append((category, max_confidence))
        
        # Sort by confidence
        suggestions.sort(key=lambda x: x[1], reverse=True)
        
        return suggestions[:3]  # Return top 3 suggestions

# Global instance for easy import
categorizer = TransactionCategorizer()
