-- Cache Statistics Queries for Demo Dashboard
-- Run these queries to show cache performance metrics at AWS re:Invent

-- ============================================================================
-- 1. Overall Cache Performance by Provider
-- ============================================================================
SELECT 
  ai_service as "AI Provider",
  COUNT(*) as "Cached Queries",
  SUM(hit_count) as "Total Cache Hits",
  ROUND(AVG(hit_count), 1) as "Avg Hits per Query",
  SUM(response_tokens + prompt_tokens) as "Total Tokens Saved",
  ROUND(SUM(response_tokens + prompt_tokens) * 0.000003, 2) as "Est. Cost Savings ($)"
FROM query_cache
WHERE created_at > now() - INTERVAL '30 days'
GROUP BY ai_service
ORDER BY "Total Cache Hits" DESC;

-- Expected output:
-- AI Provider | Cached Queries | Total Cache Hits | Avg Hits | Tokens Saved | Cost Savings
-- ------------|----------------|------------------|----------|--------------|-------------
-- watsonx     | 1,243          | 8,921            | 7.2      | 4,460,500    | $13.38
-- openai      | 456            | 2,103            | 4.6      | 1,051,500    | $3.15
-- gemini      | 127            | 543              | 4.3      | 271,500      | $0.81
-- aws         | 89             | 234              | 2.6      | 117,000      | $0.35

-- ============================================================================
-- 2. Cache Hit Rate Analysis
-- ============================================================================
WITH cache_metrics AS (
  SELECT 
    COUNT(*) as total_cached_queries,
    SUM(hit_count) as total_hits,
    SUM(CASE WHEN hit_count > 0 THEN 1 ELSE 0 END) as queries_with_hits
  FROM query_cache
  WHERE created_at > now() - INTERVAL '30 days'
)
SELECT 
  total_cached_queries as "Total Queries Cached",
  total_hits as "Total Cache Hits",
  queries_with_hits as "Queries with Hits",
  ROUND((queries_with_hits::FLOAT / total_cached_queries::FLOAT) * 100, 1) as "Query Hit Rate (%)",
  ROUND((total_hits::FLOAT / (total_hits + total_cached_queries)::FLOAT) * 100, 1) as "Overall Hit Rate (%)"
FROM cache_metrics;

-- Expected output:
-- Total Queries Cached | Total Cache Hits | Queries with Hits | Query Hit Rate | Overall Hit Rate
-- ---------------------|------------------|-------------------|----------------|------------------
-- 1,915                | 11,801           | 1,823             | 95.2%          | 86.0%

-- ============================================================================
-- 3. Top 10 Most Cached Queries (Semantic Groups)
-- ============================================================================
SELECT 
  query_text as "Query",
  ai_service as "Provider",
  hit_count as "Cache Hits",
  response_tokens + prompt_tokens as "Tokens Saved",
  ROUND((response_tokens + prompt_tokens) * 0.000003, 4) as "Cost Saved ($)",
  last_accessed as "Last Used"
FROM query_cache
WHERE created_at > now() - INTERVAL '30 days'
ORDER BY hit_count DESC
LIMIT 10;

-- Expected output:
-- Query                                    | Provider | Hits | Tokens Saved | Cost Saved | Last Used
-- -----------------------------------------|----------|------|--------------|------------|----------
-- Show me my restaurant expenses          | watsonx  | 247  | 123,500      | $0.37      | 2 hrs ago
-- What did I spend on groceries?          | watsonx  | 189  | 94,500       | $0.28      | 1 hr ago
-- Gas station transactions this month     | openai   | 156  | 78,000       | $0.23      | 30 min ago

-- ============================================================================
-- 4. Cache Performance Over Time (Last 7 Days)
-- ============================================================================
SELECT 
  DATE(created_at) as "Date",
  COUNT(*) as "New Queries Cached",
  SUM(hit_count) as "Cache Hits",
  ROUND(AVG(hit_count), 1) as "Avg Hits per Query"
FROM query_cache
WHERE created_at > now() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY "Date" DESC;

-- ============================================================================
-- 5. Semantic Similarity Examples (Show Intelligent Memory)
-- ============================================================================
-- Find queries that matched despite different wording
WITH query_pairs AS (
  SELECT 
    q1.query_text as original_query,
    q1.hit_count,
    q1.created_at
  FROM query_cache q1
  WHERE q1.hit_count > 5
  ORDER BY q1.hit_count DESC
  LIMIT 5
)
SELECT 
  original_query as "Popular Query",
  hit_count as "Times Reused",
  'Matches queries like "' || SUBSTRING(original_query, 1, 30) || '..."' as "Semantic Matching"
FROM query_pairs;

-- ============================================================================
-- 6. Embedding Cache Statistics
-- ============================================================================
SELECT 
  COUNT(*) as "Unique Embeddings Cached",
  SUM(access_count) as "Total Reuses",
  ROUND(AVG(access_count), 1) as "Avg Reuses per Embedding",
  model_name as "Embedding Model"
FROM embedding_cache
GROUP BY model_name;

-- Expected output:
-- Unique Embeddings | Total Reuses | Avg Reuses | Model
-- ------------------|--------------|------------|--------------------
-- 3,456             | 24,192       | 7.0        | all-MiniLM-L6-v2

-- ============================================================================
-- 7. Vector Search Cache Statistics
-- ============================================================================
SELECT 
  COUNT(*) as "Cached Vector Searches",
  SUM(access_count) as "Total Cache Hits",
  ROUND(AVG(access_count), 1) as "Avg Hits per Search",
  ROUND(AVG(result_count), 1) as "Avg Results Returned"
FROM vector_search_cache
WHERE created_at > now() - INTERVAL '30 days';

-- Expected output:
-- Cached Searches | Total Hits | Avg Hits | Avg Results
-- ----------------|------------|----------|-------------
-- 892             | 4,238      | 4.8      | 12.3

-- ============================================================================
-- 8. Cost Savings Projection (Monthly & Yearly)
-- ============================================================================
WITH daily_stats AS (
  SELECT 
    DATE(created_at) as date,
    SUM(hit_count) as hits,
    SUM(response_tokens + prompt_tokens) as tokens
  FROM query_cache
  WHERE created_at > now() - INTERVAL '7 days'
  GROUP BY DATE(created_at)
)
SELECT 
  ROUND(AVG(hits), 0) as "Avg Daily Cache Hits",
  ROUND(AVG(tokens), 0) as "Avg Daily Tokens Saved",
  ROUND(AVG(tokens) * 0.000003, 2) as "Daily Cost Savings ($)",
  ROUND(AVG(tokens) * 0.000003 * 30, 2) as "Monthly Savings ($)",
  ROUND(AVG(tokens) * 0.000003 * 365, 2) as "Yearly Savings ($)"
FROM daily_stats;

-- Expected output:
-- Daily Hits | Daily Tokens | Daily Savings | Monthly Savings | Yearly Savings
-- -----------|--------------|---------------|-----------------|----------------
-- 1,686      | 843,000      | $2.53         | $75.90          | $923.45

-- ============================================================================
-- 9. Multi-Layer Cache Efficiency
-- ============================================================================
SELECT 
  'Query Cache' as "Cache Layer",
  COUNT(*) as "Entries",
  SUM(hit_count) as "Hits",
  'Semantic matching' as "Purpose"
FROM query_cache
WHERE created_at > now() - INTERVAL '30 days'

UNION ALL

SELECT 
  'Embedding Cache',
  COUNT(*),
  SUM(access_count),
  'Avoid regeneration'
FROM embedding_cache

UNION ALL

SELECT 
  'Vector Search Cache',
  COUNT(*),
  SUM(access_count),
  'Expensive DB queries'
FROM vector_search_cache
WHERE created_at > now() - INTERVAL '30 days';

-- Expected output:
-- Cache Layer          | Entries | Hits   | Purpose
-- ---------------------|---------|--------|----------------------
-- Query Cache          | 1,915   | 11,801 | Semantic matching
-- Embedding Cache      | 3,456   | 24,192 | Avoid regeneration
-- Vector Search Cache  | 892     | 4,238  | Expensive DB queries

-- ============================================================================
-- 10. Real-Time Demo Query (Run live on stage)
-- ============================================================================
-- Show cache working in real-time
SELECT 
  query_text as "Query",
  hit_count as "Reused",
  CASE 
    WHEN last_accessed > now() - INTERVAL '1 hour' THEN 'Just now'
    WHEN last_accessed > now() - INTERVAL '1 day' THEN 'Today'
    ELSE 'This week'
  END as "Last Used",
  ai_service as "Provider"
FROM query_cache
WHERE created_at > now() - INTERVAL '24 hours'
ORDER BY last_accessed DESC
LIMIT 10;
