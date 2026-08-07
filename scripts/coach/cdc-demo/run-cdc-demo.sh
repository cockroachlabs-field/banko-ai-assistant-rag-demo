#!/usr/bin/env bash
# Real-CDC Coach demo: CockroachDB changefeed -> Debezium -> Kafka -> Coach.
#
# Brings up Kafka + Kafka Connect, registers the Debezium CockroachDB source
# on the spending_signals table, and prints how to run the app against it.
# CockroachDB itself is whatever the app already uses; point at it with the
# env vars below.
#
#   CRDB_HOST             default host.docker.internal (local host node)
#   CRDB_PORT             default 26257
#   CRDB_USER             default root
#   CRDB_DB               default defaultdb
#   CHANGEFEED_KAFKA_URI  default kafka://localhost:29092 (URI the CRDB
#                         process itself pushes the changefeed to; use
#                         kafka://kafka:9092 if CRDB runs in this compose
#                         network)
#
# Connector plugin resolution order:
#   1. ./connect-plugins already populated
#   2. copy from ~/idea_workspace/debezium-cockroachdb-examples (local dev)
#   3. download from Maven Central
set -euo pipefail
cd "$(dirname "$0")"

echo "== 0/5 cockroachdb"
# The connector must watch the SAME database the app uses, so this script
# never creates its own CockroachDB. It does make sure one is running:
# a stopped repo container gets started, and if nothing is listening at
# all, the repo compose brings one up (data lives on a named volume).
if [ -n "${CRDB_HOST:-}" ]; then
    echo "   using CRDB_HOST=${CRDB_HOST} from the environment"
elif docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^banko-cockroachdb$'; then
    echo "   banko-cockroachdb already running"
elif (echo > /dev/tcp/localhost/26257) 2>/dev/null; then
    echo "   using the CockroachDB already listening on localhost:26257"
    echo "   (make sure this is the cluster your app points at)"
elif docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q '^banko-cockroachdb$'; then
    docker start banko-cockroachdb >/dev/null
    echo "   started existing banko-cockroachdb container"
else
    (cd "$(git -C . rev-parse --show-toplevel 2>/dev/null || echo ../../..)" \
        && docker compose up -d cockroachdb)
    echo "   brought up the repo compose cockroachdb"
fi

# When CockroachDB runs in docker (the repo compose container or any other
# stack, like the 5-node chaos cluster), the changefeed sink URI must be
# reachable FROM THE CRDB NODES, so it has to be the in-network kafka:9092;
# kafka://localhost:29092 would make each node dial itself. Every CRDB
# container also gets joined to the cdc network in step 2.
CRDB_CONTAINERS="$(docker ps --format '{{.Names}} {{.Image}}' 2>/dev/null \
    | awk '$2 ~ /cockroachdb\/cockroach/ {print $1}')"
if echo "$CRDB_CONTAINERS" | grep -q '^banko-cockroachdb$'; then
    CRDB_DEFAULT_HOST="banko-cockroachdb"
    KAFKA_URI_DEFAULT="kafka://kafka:9092"
elif [ -n "$CRDB_CONTAINERS" ]; then
    # Foreign cluster (chaos demo etc.): JDBC goes through the host's
    # published 26257 (haproxy on the chaos stack), the sink stays
    # in-network.
    CRDB_DEFAULT_HOST="host.docker.internal"
    KAFKA_URI_DEFAULT="kafka://kafka:9092"
else
    CRDB_DEFAULT_HOST="host.docker.internal"
    KAFKA_URI_DEFAULT="kafka://localhost:29092"
fi
CRDB_HOST="${CRDB_HOST:-$CRDB_DEFAULT_HOST}"
CRDB_PORT="${CRDB_PORT:-26257}"
CRDB_USER="${CRDB_USER:-root}"
CRDB_DB="${CRDB_DB:-defaultdb}"
CHANGEFEED_KAFKA_URI="${CHANGEFEED_KAFKA_URI:-$KAFKA_URI_DEFAULT}"
CONNECTOR_VERSION="${CONNECTOR_VERSION:-3.6.0.Final}"
# gvproxy keeps forwards for other stacks (a 5-node cluster's admin UIs
# occupy 8080-8084, for example). If the port is held by anything that is
# not our own connect container, hop to the next free one.
CONNECT_PORT="${CONNECT_PORT:-8084}"
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^banko-cdc-connect$'; then
    # Reuse whatever port the running container already publishes;
    # recreating it on the default collides with whoever took 8084.
    EXISTING_PORT="$(docker port banko-cdc-connect 8083/tcp 2>/dev/null \
        | head -1 | awk -F: '{print $NF}')"
    [ -n "$EXISTING_PORT" ] && CONNECT_PORT="$EXISTING_PORT"
else
    while (echo > /dev/tcp/localhost/${CONNECT_PORT}) 2>/dev/null; do
        echo "   port ${CONNECT_PORT} is taken; trying $((CONNECT_PORT+1))"
        CONNECT_PORT=$((CONNECT_PORT+1))
    done
fi
export CONNECT_PORT
EXAMPLES_REPO="${EXAMPLES_REPO:-$HOME/idea_workspace/debezium-cockroachdb-examples}"

echo "== 1/5 connector plugin"
if ls connect-plugins/debezium-connector-cockroachdb/*.jar >/dev/null 2>&1; then
    echo "   already present"
elif ls "$EXAMPLES_REPO"/crdb-to-crdb/connect-plugins/debezium-connector-cockroachdb/*.jar >/dev/null 2>&1; then
    mkdir -p connect-plugins
    cp -R "$EXAMPLES_REPO/crdb-to-crdb/connect-plugins/debezium-connector-cockroachdb" connect-plugins/
    echo "   copied from $EXAMPLES_REPO"
else
    ZIP="debezium-connector-cockroachdb-${CONNECTOR_VERSION}-plugin.zip"
    URL="https://repo1.maven.org/maven2/io/debezium/debezium-connector-cockroachdb/${CONNECTOR_VERSION}/${ZIP}"
    mkdir -p connect-plugins
    curl -fsSL -o "/tmp/${ZIP}" "$URL"
    unzip -q -o "/tmp/${ZIP}" -d connect-plugins/
    echo "   downloaded ${CONNECTOR_VERSION} from Maven Central"
fi

echo "== 2/5 kafka + connect"
if ! docker compose -f docker-compose.cdc.yml up -d; then
    cat <<'HINT'
Compose failed. If the error says "proxy already running", podman's port
forwarder is stuck (it happens after sleep or reboot). Recover with:
    podman machine stop && podman machine start
    docker compose -f docker-compose.cdc.yml down
    ./run-cdc-demo.sh
Databases live on named volumes; nothing is lost by the restart.
HINT
    exit 1
fi
if [ -n "$CRDB_CONTAINERS" ]; then
    for c in $CRDB_CONTAINERS; do
        docker network connect cdc-demo_default "$c" 2>/dev/null || true
    done
    echo "   joined the cdc network: $(echo $CRDB_CONTAINERS | tr '\n' ' ')"
fi
printf "   waiting for connect"
for _ in $(seq 1 60); do
    if curl -fs http://localhost:${CONNECT_PORT}/connectors >/dev/null 2>&1; then
        echo " ... up"
        break
    fi
    printf "."
    sleep 2
done
curl -fs http://localhost:${CONNECT_PORT}/connectors >/dev/null 2>&1 || {
    echo "connect never came up; check: docker logs banko-cdc-connect"
    exit 1
}

echo "== 3/5 rangefeed on ${CRDB_HOST}:${CRDB_PORT}/${CRDB_DB}"
if [ -n "$CRDB_CONTAINERS" ]; then
    NODE="$(echo "$CRDB_CONTAINERS" | head -1)"
    printf "   waiting for the node"
    for _ in $(seq 1 30); do
        if docker exec "$NODE" cockroach sql --insecure \
            -e "SELECT 1" >/dev/null 2>&1; then
            break
        fi
        printf "."
        sleep 2
    done
    echo ""
    docker exec "$NODE" cockroach sql --insecure \
        -e "SET CLUSTER SETTING kv.rangefeed.enabled = true" >/dev/null
    echo "   enabled (via $NODE)"
else
    echo "   (host node: run SET CLUSTER SETTING kv.rangefeed.enabled = true;)"
fi

echo "== 4/5 register connector"
CONFIG=$(sed -e "s|\${CRDB_HOST}|$CRDB_HOST|" \
             -e "s|\${CRDB_PORT}|$CRDB_PORT|" \
             -e "s|\${CRDB_USER}|$CRDB_USER|" \
             -e "s|\${CRDB_DB}|$CRDB_DB|" \
             -e "s|\${CHANGEFEED_KAFKA_URI}|$CHANGEFEED_KAFKA_URI|" \
             spending-signals-source.json)
curl -fs -X DELETE http://localhost:${CONNECT_PORT}/connectors/banko-spending-signals-source >/dev/null 2>&1 || true
echo "$CONFIG" | curl -fs -X POST -H 'Content-Type: application/json' \
    --data @- http://localhost:${CONNECT_PORT}/connectors >/dev/null
sleep 3
echo "== 5/5 connector status"
curl -fs http://localhost:${CONNECT_PORT}/connectors/banko-spending-signals-source/status | python3 -m json.tool

cat <<'EOF'

Next:
  1. Run the app with the Kafka transport on:
       COACH_KAFKA_ENABLED=true KAFKA_BOOTSTRAP_SERVERS=localhost:29092 \
       AI_SERVICE=watsonx CDC_WEBHOOK_HMAC_SECRET=dev-only-secret \
       DATABASE_URL=<same db as CRDB_DB above> uv run banko-ai run
  2. Open http://localhost:5000/coach
  3. Insert a signal row and watch CockroachDB stream it into a nudge.
     The coach page shows the signed-in user's nudges, so target the
     username you signed up with:
       INSERT INTO spending_signals
         (user_id, signal_type, severity, payload, idempotency_key)
       VALUES
         ((SELECT user_id FROM users WHERE username = 'YOUR-USERNAME'),
          'budget_threshold', 'warn',
          '{"category": "dining", "pct_used": 0.82, "monthly_budget": 400.0,
            "spent_so_far": 328.0, "days_remaining": 9}',
          'demo:' || gen_random_uuid()::STRING);
EOF
