# CockroachDB Vector Search Demo Commands

## 🔍 Direct SQL Shell Commands

These commands work directly in the CockroachDB SQL shell. Connect with:
```bash
docker exec -it banko-cockroachdb ./cockroach sql --insecure
```

### ✅ Working Vector Search Queries

#### 1. Basic Vector Search (Using Existing Embedding)
```sql
-- Find similar expenses to the first expense in the table
SELECT expense_id, description, expense_amount, merchant, 
       embedding <-> (SELECT embedding FROM expenses LIMIT 1) as similarity_score 
FROM expenses 
ORDER BY embedding <-> (SELECT embedding FROM expenses LIMIT 1) 
LIMIT 5;
```

#### 2. Vector Search with Zero Vector (Demo Purpose)
```sql
-- Search using a zero vector (384 dimensions)
SELECT expense_id, description, expense_amount, merchant,
       embedding <-> '[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]' as similarity_score
FROM expenses 
ORDER BY similarity_score 
LIMIT 10;
```

#### 3. Check Vector Index Usage
```sql
-- Verify the vector index exists
SHOW INDEXES FROM expenses;
```

#### 4. Explain Vector Search Query Plan
```sql
-- Show that vector index is being used
EXPLAIN SELECT expense_id, description, expense_amount, merchant,
        embedding <-> '[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]' AS distance
FROM expenses 
ORDER BY distance 
LIMIT 5;
```

## 🚫 What DOESN'T Work in SQL Shell

### ❌ Parameterized Queries
```sql
-- This FAILS in SQL shell (but works in application code)
SELECT expense_id, description, expense_amount, merchant,
       embedding <-> :search_embedding as similarity_score  -- ❌ :search_embedding is not valid SQL
FROM expenses
ORDER BY embedding <-> :search_embedding
LIMIT 10;
```

### ❌ SQLAlchemy-style Parameters
```sql
-- This FAILS in SQL shell
SELECT * FROM expenses WHERE embedding <-> %(vector)s;  -- ❌ %(vector)s is SQLAlchemy syntax
```

## ✅ How Parameters Work in Application Code

In Python with SQLAlchemy (like our Banko AI app):

```python
# This WORKS in application code
search_query = text("""
    SELECT expense_id, description, expense_amount, merchant,
           embedding <-> :search_embedding as similarity_score
    FROM expenses
    ORDER BY embedding <-> :search_embedding
    LIMIT :limit
""")

with engine.connect() as conn:
    results = conn.execute(search_query, {
        'search_embedding': '[0.1, 0.2, 0.3, ...]',  # 384-dimensional vector
        'limit': 10
    })
```

## 🎯 Key Points

1. **Direct SQL Shell**: Use literal vector values `'[0,0,0,...]'` or subqueries
2. **Application Code**: Use parameters `:search_embedding` for dynamic values
3. **Vector Index**: Confirmed working with `VECTOR INDEX expenses_embedding_idx`
4. **Distance Operator**: `<->` for L2 distance (matches our `vector_l2_ops` index)

## 🔧 Quick Test Commands

```bash
# Connect to database
docker exec -it banko-cockroachdb ./cockroach sql --insecure

# Run a simple vector search
SELECT expense_id, description, merchant, embedding <-> (SELECT embedding FROM expenses LIMIT 1) as score FROM expenses ORDER BY score LIMIT 3;

# Check vector index
SHOW INDEXES FROM expenses;

# Exit
\q
```
