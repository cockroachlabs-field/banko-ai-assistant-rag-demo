"""
Intent classifier for Banko AI.

Uses embedding similarity to determine whether a user query is related to
personal finance / expense tracking. Non-financial queries are intercepted
before the RAG pipeline so we skip the vector search and LLM call entirely.
"""

import numpy as np
from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None

FINANCIAL_ANCHORS = [
    "expense report spending budget",
    "transaction payment purchase receipt",
    "credit card debit charge bill",
    "grocery shopping restaurant dining coffee food",
    "monthly cost salary income savings",
    "financial summary category breakdown",
    "subscription recurring payment",
    "refund reimbursement overdraft",
    "rent mortgage utility electricity",
    "travel hotel flight uber lyft taxi",
    "duplicate fraud suspicious charge",
    "how much did I spend on",
    "amazon walmart target costco starbucks",
]

# Queries that are clearly non-financial get high similarity to these anchors,
# so we check against them and reject if the query is closer to this set.
NON_FINANCIAL_ANCHORS = [
    "weather forecast temperature rain",
    "joke funny humor laugh",
    "recipe cook bake ingredients",
    "sports game score team",
    "politics president election government",
    "movie film actor director",
    "song music lyrics album",
    "translate language dictionary words",
    "science physics chemistry biology",
    "history war ancient civilization",
]

REDIRECT_MESSAGE = (
    "I'm Banko, your personal finance assistant. "
    "I can help with expense tracking, spending analysis, budgets, "
    "receipt processing, and fraud detection. "
    "What would you like to know about your finances?"
)

SIMILARITY_THRESHOLD = 0.20


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


_financial_embeddings: np.ndarray | None = None
_non_financial_embeddings: np.ndarray | None = None


def _get_financial_embeddings() -> np.ndarray:
    global _financial_embeddings
    if _financial_embeddings is None:
        model = _get_model()
        _financial_embeddings = model.encode(FINANCIAL_ANCHORS, normalize_embeddings=True)
    return _financial_embeddings


def _get_non_financial_embeddings() -> np.ndarray:
    global _non_financial_embeddings
    if _non_financial_embeddings is None:
        model = _get_model()
        _non_financial_embeddings = model.encode(NON_FINANCIAL_ANCHORS, normalize_embeddings=True)
    return _non_financial_embeddings


def is_financial_query(query: str) -> bool:
    """Return True if the query is related to personal finance.

    Uses a two-sided check: the query must be closer to financial anchors
    than to non-financial anchors, OR exceed the similarity threshold
    against financial anchors.
    """
    model = _get_model()
    query_embedding = model.encode([query], normalize_embeddings=True)[0]

    fin_sims = np.dot(_get_financial_embeddings(), query_embedding)
    non_fin_sims = np.dot(_get_non_financial_embeddings(), query_embedding)

    max_fin = float(np.max(fin_sims))
    max_non_fin = float(np.max(non_fin_sims))

    # Financial if closer to financial anchors or above threshold
    if max_fin >= SIMILARITY_THRESHOLD and max_fin > max_non_fin:
        return True
    return False
