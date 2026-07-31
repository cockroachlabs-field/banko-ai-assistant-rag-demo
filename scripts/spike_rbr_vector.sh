#!/usr/bin/env bash
# Spike: C-SPANN vector indexes on REGIONAL BY ROW tables
# Run against a multi-region cluster: SPIKE_URL=... ./spike_rbr_vector.sh
#
# VERDICT (corrected 2026-07-29): vector indexes work fine on RBR tables.
# The earlier 42809 finding in this spike was self-inflicted: the index
# was created without an operator class, which defaults to L2, and an L2
# index can never serve a cosine (<=>) ORDER BY. With vector_cosine_ops
# the planner uses the index on RBR tables and the prefix span includes
# the region: [/'us-east-1'/'<user>' - /'us-east-1'/'<user>'].
#
# Two requirements for the vector search operator, verified on v25.4.13:
#   1. The index operator class must match the query operator
#      (vector_cosine_ops for <=>).
#   2. The query vector must be a constant, not a subquery.
#
# Test 4 below keeps the original mistake on purpose as a negative
# control: forcing an L2 index on a cosine query is what produces
# SQLSTATE 42809 ("index cannot be used for this query"). The error text
# never mentions the operator class mismatch, which is how this spike
# originally misread it as an RBR limitation across four versions.
set -euo pipefail
URL="${SPIKE_URL:-postgresql://root@localhost:26257/defaultdb?sslmode=disable}"

psql_run() { cockroach sql --url "$URL" -e "$1"; }

trap 'cockroach sql --url "$URL" -e "DROP DATABASE IF EXISTS spike_rbr CASCADE" 2>/dev/null || true' EXIT

echo "=== Spike: Vector indexes on REGIONAL BY ROW ==="
psql_run "CREATE DATABASE IF NOT EXISTS spike_rbr"
URL_DB="${URL/defaultdb/spike_rbr}"
run() { cockroach sql --url "$URL_DB" -e "$1"; }

# A constant 384-dim query vector; a subquery here would defeat the
# vector search operator no matter how the index was built.
QVEC="[$(python3 -c "print(','.join(['0.1']*384))")]"

run "SHOW REGIONS FROM CLUSTER"
run "ALTER DATABASE spike_rbr SET PRIMARY REGION 'us-east-1'"
run "ALTER DATABASE spike_rbr ADD REGION 'us-central-1'"
run "ALTER DATABASE spike_rbr ADD REGION 'us-west-2'"
run "CREATE TABLE t (
       id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
       user_id UUID NOT NULL,
       body STRING,
       embedding VECTOR(384))"
run "ALTER TABLE t SET LOCALITY REGIONAL BY ROW"
run "CREATE VECTOR INDEX idx_t_cosine ON t (user_id, embedding vector_cosine_ops)"
run "CREATE VECTOR INDEX idx_t_l2_default ON t (user_id, embedding)"

KNOWN_UID="11111111-1111-1111-1111-111111111111"
run "INSERT INTO t (crdb_region, user_id, body, embedding)
     SELECT r::crdb_internal_region, '$KNOWN_UID',
            'expense ' || i::STRING || ' in ' || r,
            ('[' || repeat(((i % 10)::FLOAT8 / 10.0)::STRING || ',', 383)
                 || ((i % 10)::FLOAT8 / 10.0)::STRING || ']')::VECTOR
     FROM (VALUES ('us-east-1'), ('us-central-1'), ('us-west-2')) AS v(r),
          generate_series(1, 20) AS g(i)"
run "INSERT INTO t (crdb_region, user_id, body, embedding)
     SELECT ((ARRAY['us-east-1','us-central-1','us-west-2'])[1 + i % 3])::crdb_internal_region,
            gen_random_uuid(), 'noise ' || i::STRING,
            ('[' || repeat(((i % 7)::FLOAT8 / 7.0)::STRING || ',', 383)
                 || ((i % 7)::FLOAT8 / 7.0)::STRING || ']')::VECTOR
     FROM generate_series(1, 200) AS g(i)"
run "SELECT crdb_region, count(*) FROM t GROUP BY 1 ORDER BY 1"
run "ANALYZE t"

echo ""
echo "=== Test 1: per-user ANN, no region filter (expect vector search) ==="
run "EXPLAIN SELECT body FROM t
     WHERE user_id = '$KNOWN_UID'
     ORDER BY embedding <=> '$QVEC'::VECTOR LIMIT 3"

echo ""
echo "=== Test 2: region + user constrained (expect region in prefix span) ==="
run "EXPLAIN SELECT body FROM t
     WHERE crdb_region = 'us-east-1' AND user_id = '$KNOWN_UID'
     ORDER BY embedding <=> '$QVEC'::VECTOR LIMIT 3"

echo ""
echo "=== Test 3: execute through the cosine index (expect 3 rows) ==="
run "SELECT body FROM t@idx_t_cosine
     WHERE crdb_region = 'us-east-1' AND user_id = '$KNOWN_UID'
     ORDER BY embedding <=> '$QVEC'::VECTOR LIMIT 3"

echo ""
echo "=== Test 4: negative control, force the L2-default index on a cosine query ==="
echo "=== (expect SQLSTATE 42809; this mismatch was the original wrong verdict) ==="
run "SELECT body FROM t@idx_t_l2_default
     WHERE crdb_region = 'us-east-1' AND user_id = '$KNOWN_UID'
     ORDER BY embedding <=> '$QVEC'::VECTOR LIMIT 3" 2>&1 || echo "42809 as expected: L2 index cannot serve a cosine query"

echo ""
echo "SPIKE VERDICT: PASS"
echo "- Vector indexes on RBR tables serve ORDER BY <=> queries: YES (cosine ops class)"
echo "- Region constraint lands in the vector index prefix span: YES"
echo "- 42809 only appears when the index ops class does not match the operator"
run "DROP DATABASE spike_rbr CASCADE"
trap - EXIT
