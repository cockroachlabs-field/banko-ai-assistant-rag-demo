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

# When CockroachDB runs as the repo's compose container, talk to it over
# the container network; otherwise assume a host process.
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^banko-cockroachdb$'; then
    CRDB_DEFAULT_HOST="banko-cockroachdb"
    KAFKA_URI_DEFAULT="kafka://kafka:9092"
    CRDB_IS_CONTAINER=1
else
    CRDB_DEFAULT_HOST="host.docker.internal"
    KAFKA_URI_DEFAULT="kafka://localhost:29092"
    CRDB_IS_CONTAINER=0
fi
CRDB_HOST="${CRDB_HOST:-$CRDB_DEFAULT_HOST}"
CRDB_PORT="${CRDB_PORT:-26257}"
CRDB_USER="${CRDB_USER:-root}"
CRDB_DB="${CRDB_DB:-defaultdb}"
CHANGEFEED_KAFKA_URI="${CHANGEFEED_KAFKA_URI:-$KAFKA_URI_DEFAULT}"
CONNECTOR_VERSION="${CONNECTOR_VERSION:-3.6.0.Final}"
CONNECT_PORT="${CONNECT_PORT:-8084}"
EXAMPLES_REPO="${EXAMPLES_REPO:-$HOME/idea_workspace/debezium-cockroachdb-examples}"

echo "== 1/4 connector plugin"
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

echo "== 2/4 kafka + connect"
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
if [ "$CRDB_IS_CONTAINER" = "1" ]; then
    docker network connect cdc-demo_default banko-cockroachdb 2>/dev/null || true
    echo "   banko-cockroachdb joined the cdc network"
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

echo "== 3/4 rangefeed on ${CRDB_HOST}:${CRDB_PORT}/${CRDB_DB}"
echo "   (needs: SET CLUSTER SETTING kv.rangefeed.enabled = true;)"
echo "   run it yourself if the connector reports rangefeed errors."

echo "== 4/4 register connector"
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
curl -fs http://localhost:${CONNECT_PORT}/connectors/banko-spending-signals-source/status | python3 -m json.tool

cat <<'EOF'

Next:
  1. Run the app with the Kafka transport on:
       COACH_KAFKA_ENABLED=true KAFKA_BOOTSTRAP_SERVERS=localhost:29092 \
       AI_SERVICE=watsonx CDC_WEBHOOK_HMAC_SECRET=dev-only-secret \
       DATABASE_URL=<same db as CRDB_DB above> uv run banko-ai run
  2. Open http://localhost:5000/coach
  3. Insert a signal row and watch CockroachDB stream it into a nudge:
       INSERT INTO spending_signals
         (user_id, signal_type, severity, payload, idempotency_key)
       VALUES
         ('00000000-0000-0000-0000-000000000001', 'budget_threshold', 'warn',
          '{"category": "dining", "pct_used": 0.82, "monthly_budget": 400.0,
            "spent_so_far": 328.0, "days_remaining": 9}',
          'demo:' || gen_random_uuid()::STRING);
EOF
