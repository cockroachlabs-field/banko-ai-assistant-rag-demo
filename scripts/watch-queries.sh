#!/bin/bash

# Banko AI - Database Query Watcher for Demo
# This script shows live SQL queries for demonstration purposes
# Supports: Docker containers, local CockroachDB binary, and CockroachDB Cloud

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Global variables
DEPLOYMENT_TYPE=""
DEBUG_MODE=false
DB_URL=""
COCKROACH_BINARY=""
LOG_DIR=""
CONTAINER_NAME="banko-cockroachdb"
SQL_ONLY=false

# Show usage information
show_usage() {
    echo -e "${BLUE}Usage: $0 [OPTIONS]${NC}"
    echo
    echo -e "${YELLOW}Options:${NC}"
    echo "  -h, --help              Show this help message"
    echo "  -d, --debug             Enable debug mode (show raw SQL)"
    echo "  -t, --type TYPE         Force deployment type: container|local|cloud"
    echo "  -u, --url URL           Database connection URL (for cloud/local)"
    echo "  -b, --binary PATH       Path to cockroach binary (for local)"
    echo "  -l, --logs PATH         Path to CockroachDB logs directory (for local)"
    echo "  -c, --container NAME    Container name (default: banko-cockroachdb)"
    echo "  -s, --sql-only          Force SQL-based monitoring (skip log files)"
    echo
    echo -e "${YELLOW}Deployment Types:${NC}"
    echo "  container               Docker/Podman container (default detection)"
    echo "  local                   Local CockroachDB binary"
    echo "  cloud                   CockroachDB Cloud (managed service)"
    echo
    echo -e "${YELLOW}Examples:${NC}"
    echo "  $0                                    # Auto-detect deployment"
    echo "  $0 --type container                   # Force container mode"
    echo "  $0 --type local --sql-only            # Local with SQL monitoring"
    echo "  $0 --type local --logs /path/to/logs  # Try log file monitoring"
    echo "  $0 --type cloud --url 'postgresql://user:pass@host:26257/db'"
    echo
    echo -e "${YELLOW}💡 For log file monitoring, you may need to enable SQL logging:${NC}"
    echo "  cockroach sql --insecure --execute=\"SET CLUSTER SETTING sql.log.all_statements.enabled = true;\""
    echo
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_usage
                exit 0
                ;;
            -d|--debug)
                DEBUG_MODE=true
                shift
                ;;
            -t|--type)
                DEPLOYMENT_TYPE="$2"
                shift 2
                ;;
            -u|--url)
                DB_URL="$2"
                shift 2
                ;;
            -b|--binary)
                COCKROACH_BINARY="$2"
                shift 2
                ;;
            -l|--logs)
                LOG_DIR="$2"
                shift 2
                ;;
            -c|--container)
                CONTAINER_NAME="$2"
                shift 2
                ;;
            -s|--sql-only)
                SQL_ONLY=true
                shift
                ;;
            *)
                echo -e "${RED}❌ Unknown option: $1${NC}"
                show_usage
                exit 1
                ;;
        esac
    done
}

# Auto-detect deployment type
detect_deployment_type() {
    if [[ -n "$DEPLOYMENT_TYPE" ]]; then
        echo -e "${CYAN}🔧 Using forced deployment type: $DEPLOYMENT_TYPE${NC}"
        return
    fi

    # Check for container first
    if docker ps 2>/dev/null | grep -q "$CONTAINER_NAME" || podman ps 2>/dev/null | grep -q "$CONTAINER_NAME"; then
        DEPLOYMENT_TYPE="container"
        echo -e "${CYAN}🐳 Detected: Container deployment${NC}"
        return
    fi

    # Check for local binary
    if command -v cockroach >/dev/null 2>&1 || [[ -n "$COCKROACH_BINARY" ]]; then
        DEPLOYMENT_TYPE="local"
        echo -e "${CYAN}💻 Detected: Local binary deployment${NC}"
        return
    fi

    # Check for cloud connection (if DB_URL is provided or in environment)
    local db_url="${DB_URL:-${DATABASE_URL:-}}"
    if [[ -n "$db_url" ]] && [[ "$db_url" != *"localhost"* ]] && [[ "$db_url" != *"127.0.0.1"* ]]; then
        DEPLOYMENT_TYPE="cloud"
        echo -e "${CYAN}☁️  Detected: Cloud deployment${NC}"
        return
    fi

    # Default fallback
    echo -e "${YELLOW}⚠️  Could not auto-detect deployment type. Trying container mode...${NC}"
    DEPLOYMENT_TYPE="container"
}

# Check if container is running
check_container() {
    local container_cmd="docker"
    if command -v podman >/dev/null 2>&1 && ! command -v docker >/dev/null 2>&1; then
        container_cmd="podman"
    fi

    if ! $container_cmd ps | grep -q "$CONTAINER_NAME"; then
        echo -e "${RED}❌ Error: CockroachDB container '$CONTAINER_NAME' is not running${NC}"
        echo "Please start the services first with: ./start-banko.sh"
        echo "Or use --type local/cloud for other deployment types"
        exit 1
    fi
}

# Check local binary setup
check_local_binary() {
    local binary_path="${COCKROACH_BINARY:-cockroach}"
    
    if ! command -v "$binary_path" >/dev/null 2>&1; then
        echo -e "${RED}❌ Error: CockroachDB binary not found at '$binary_path'${NC}"
        echo "Please specify the correct path with --binary or ensure cockroach is in PATH"
        exit 1
    fi

    # Try to detect log directory if not provided
    if [[ -z "$LOG_DIR" ]]; then
        # Common log locations
        local possible_dirs=(
            "$HOME/.cockroach-data/logs"
            "/var/lib/cockroach/logs"
            "./cockroach-data/logs"
            "/tmp/cockroach-data/logs"
        )
        
        for dir in "${possible_dirs[@]}"; do
            if [[ -d "$dir" ]]; then
                LOG_DIR="$dir"
                echo -e "${CYAN}📁 Found log directory: $LOG_DIR${NC}"
                break
            fi
        done
        
        if [[ -z "$LOG_DIR" ]]; then
            echo -e "${YELLOW}⚠️  Could not find log directory. Monitoring will use SQL queries instead.${NC}"
        fi
    fi
}

# Check cloud connection
check_cloud_connection() {
    local db_url="${DB_URL:-${DATABASE_URL:-}}"
    
    if [[ -z "$db_url" ]]; then
        echo -e "${RED}❌ Error: Database URL required for cloud deployment${NC}"
        echo "Please provide --url or set DATABASE_URL environment variable"
        exit 1
    fi

    # Test connection
    echo -e "${CYAN}🔗 Testing cloud connection...${NC}"
    if command -v psql >/dev/null 2>&1; then
        if ! psql "$db_url" -c "SELECT 1;" >/dev/null 2>&1; then
            echo -e "${RED}❌ Error: Cannot connect to CockroachDB Cloud${NC}"
            echo "Please check your connection URL and credentials"
            exit 1
        fi
        echo -e "${GREEN}✅ Cloud connection successful${NC}"
    else
        echo -e "${YELLOW}⚠️  psql not found. Skipping connection test.${NC}"
    fi
}

# Display header
show_header() {
    clear
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║                 🔍 BANKO AI QUERY WATCHER                    ║${NC}"
    echo -e "${BLUE}║                Live SQL Query Trace Monitor                  ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo
    
    # Show deployment type
    case "$DEPLOYMENT_TYPE" in
        "container")
            echo -e "${GREEN}📊 Monitoring CockroachDB Container for SQL queries...${NC}"
            echo -e "${CYAN}🐳 Mode: Docker/Podman Container ($CONTAINER_NAME)${NC}"
            ;;
        "local")
            echo -e "${GREEN}📊 Monitoring Local CockroachDB for SQL queries...${NC}"
            echo -e "${CYAN}💻 Mode: Local Binary${NC}"
            if [[ -n "$LOG_DIR" ]]; then
                echo -e "${CYAN}📁 Logs: $LOG_DIR${NC}"
            else
                echo -e "${CYAN}🔗 Method: SQL Query Monitoring${NC}"
            fi
            ;;
        "cloud")
            echo -e "${GREEN}📊 Monitoring CockroachDB Cloud for SQL queries...${NC}"
            echo -e "${CYAN}☁️  Mode: CockroachDB Cloud${NC}"
            echo -e "${CYAN}🔗 Method: SQL Query Monitoring${NC}"
            ;;
    esac
    
    echo -e "${YELLOW}💡 Tip: Run searches in the Banko AI UI to see vector queries here${NC}"
    echo -e "${YELLOW}🛑 Press Ctrl+C to stop monitoring${NC}"
    echo
    echo -e "${BLUE}🔍 Watching for:${NC}"
    echo "   • Vector similarity searches"
    echo "   • Expense data queries"
    echo "   • Embedding operations"
    echo "   • Database transactions"
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo
}

# Parse log line and display query information
parse_and_display_query() {
    local line="$1"
    local source="$2"  # "log" or "sql"
    
    local current_time=$(date '+%H:%M:%S')
    local statement=""
    
    if [[ "$source" == "log" ]]; then
        # Parse JSON log format
        if echo "$line" | grep -q "query_execute"; then
            statement=$(echo "$line" | sed 's/.*"Statement":"//;s/","Tag":.*//' | sed 's/\\"/"/g')
        else
            return
        fi
    else
        # Direct SQL statement
        statement="$line"
    fi
            
            # Determine query type and display appropriately
            if echo "$statement" | grep -q "expenses.*embedding.*<->" || echo "$statement" | grep -q "embedding.*<->.*expenses"; then
                # Vector similarity search - show simplified version
                echo -e "${current_time} ${BLUE}🧮 VECTOR SEARCH:${NC} Finding similar expenses using AI embeddings"
                if [[ "$DEBUG_MODE" == "true" ]]; then
                    # Show actual SQL in debug mode (truncated for readability)
                    clean_statement=$(echo "$statement" | sed 's/embedding <-> ‹.*›/embedding <-> [384-dim-vector]/g')
                    echo -e "    ${BLUE}├─${NC} SQL: $(echo "$clean_statement" | cut -c1-120)..."
                else
                    echo -e "    ${BLUE}├─${NC} Query: SELECT expense_id, description, expense_amount, merchant..."
                fi
                echo -e "    ${BLUE}├─${NC} Method: embedding <-> '[384-dim vector]' AS similarity_score"
                echo -e "    ${BLUE}└─${NC} Order: ORDER BY embedding distance LIMIT 10"
                
            elif echo "$statement" | grep -q "SELECT.*expenses" && ! echo "$statement" | grep -q "embedding"; then
                # Regular expense query
                echo -e "${current_time} ${GREEN}🔍 EXPENSE QUERY:${NC} Standard database lookup"
                if [[ "$DEBUG_MODE" == "true" ]]; then
                    clean_query=$(echo "$statement" | cut -c1-120)
                    echo -e "    ${GREEN}└─${NC} SQL: ${clean_query}..."
                else
                    echo -e "    ${GREEN}└─${NC} Searching expense records with filters"
                fi
                
            elif echo "$statement" | grep -q "INSERT.*expenses"; then
                echo -e "${current_time} ${YELLOW}💾 DATA INSERT:${NC} Adding new expense record"
                if echo "$statement" | grep -q "embedding"; then
                    echo -e "    ${YELLOW}└─${NC} Including AI-generated embedding vector"
                fi
                
            elif echo "$statement" | grep -q "UPDATE.*expenses"; then
                echo -e "${current_time} ${YELLOW}💾 DATA UPDATE:${NC} Modifying expense record"
                
            elif echo "$statement" | grep -q "CREATE TABLE.*expenses"; then
                echo -e "${current_time} ${GREEN}🏗️  SCHEMA:${NC} Creating expenses table structure"
                
            elif echo "$statement" | grep -q "CREATE INDEX.*embedding"; then
                echo -e "${current_time} ${GREEN}🏗️  INDEX:${NC} Creating vector search index for embeddings"
                
            elif echo "$statement" | grep -qE "SET CLUSTER SETTING.*vector" && ! echo "$line" | grep -q "internal"; then
                echo -e "${current_time} ${GREEN}⚙️  CONFIG:${NC} Enabling vector search capabilities"
                
    elif [[ "$source" == "log" ]] && echo "$line" | grep -qE '"User":"root"' && ! echo "$line" | grep -q "internal" && echo "$statement" | grep -qE "(SELECT|INSERT|UPDATE|DELETE)"; then
        # User queries (non-internal, non-system) - only for log parsing
                clean_query=$(echo "$statement" | cut -c1-80)
                echo -e "${current_time} ${GREEN}📊 USER QUERY:${NC} ${clean_query}..."
    fi
}

# Monitor container logs
watch_container_queries() {
    local container_cmd="docker"
    if command -v podman >/dev/null 2>&1 && ! command -v docker >/dev/null 2>&1; then
        container_cmd="podman"
    fi

    # Monitor SQL execution log file directly for better performance
    ${container_cmd} exec "$CONTAINER_NAME" tail -f /cockroach/cockroach-data/logs/cockroach-sql-exec.log 2>/dev/null | while read line; do
        parse_and_display_query "$line" "log"
    done
}

# Monitor local binary logs
watch_local_queries() {
    # Check if SQL-only mode is requested or if SQL monitoring should be preferred
    if [[ "$SQL_ONLY" == "true" ]]; then
        echo -e "${CYAN}🔗 SQL-only mode requested${NC}"
        watch_sql_queries
        return
    fi
    
    # For local deployments, prefer SQL monitoring as it's more reliable
    # Only try log file monitoring if specifically requested with log directory
    if [[ -z "$LOG_DIR" ]]; then
        echo -e "${CYAN}💡 Using SQL-based monitoring (recommended for local deployments)${NC}"
        echo -e "${YELLOW}💡 Tip: Use --logs /path/to/logs to try log file monitoring${NC}"
        watch_sql_queries
        return
    fi
    
    # User specifically requested log directory, so try to find log files
    local log_file=""
    # Check for different possible SQL log files
    local possible_logs=(
        "$LOG_DIR/cockroach-sql-exec.log"
        "$LOG_DIR/cockroach-sql-slow.log"
        "$LOG_DIR/cockroach.log"
        "$LOG_DIR/cockroach-sql-auth.log"
    )
    
    if [[ -d "$LOG_DIR" ]]; then
        
        for log in "${possible_logs[@]}"; do
            if [[ -f "$log" ]]; then
                log_file="$log"
                echo -e "${CYAN}📄 Found log file: $(basename "$log")${NC}"
                break
            fi
        done
    fi
    
    if [[ -n "$log_file" ]]; then
        echo -e "${CYAN}📊 Attempting log file monitoring...${NC}"
        echo -e "${YELLOW}⚠️  Note: CockroachDB may not log SQL execution by default${NC}"
        echo -e "${CYAN}🔧 Checking and enabling SQL execution logging...${NC}"
        
        # Check if SQL execution logging is already enabled
        local check_result=""
        local sql_cmd_local=""
        if command -v cockroach >/dev/null 2>&1; then
            sql_cmd_local="cockroach sql"
        elif [[ -n "$COCKROACH_BINARY" ]] && command -v "$COCKROACH_BINARY" >/dev/null 2>&1; then
            sql_cmd_local="$COCKROACH_BINARY sql"
        fi
        
        if [[ -n "$sql_cmd_local" ]]; then
            # Check current setting
            check_result=$($sql_cmd_local --url="postgresql://root@localhost:26257/defaultdb?sslmode=disable" --execute="SHOW CLUSTER SETTING sql.log.all_statements.enabled;" --format=tsv 2>/dev/null | tail -1)
            
            if [[ "$check_result" == "true" ]]; then
                echo -e "${GREEN}✅ SQL execution logging is already enabled${NC}"
            else
                echo -e "${YELLOW}⚙️  SQL execution logging is disabled, enabling...${NC}"
                # Enable SQL execution logging (using the preferred setting name)
                local enable_result=$($sql_cmd_local --url="postgresql://root@localhost:26257/defaultdb?sslmode=disable" --execute="SET CLUSTER SETTING sql.log.all_statements.enabled = true;" 2>/dev/null)
                
                if [[ $? -eq 0 ]]; then
                    echo -e "${GREEN}✅ SQL execution logging enabled${NC}"
                    echo -e "${CYAN}💡 Note: It may take a few seconds for logging to start${NC}"
                else
                    echo -e "${YELLOW}⚠️  Could not enable SQL logging automatically${NC}"
                    echo -e "${YELLOW}💡 Run manually: SET CLUSTER SETTING sql.log.all_statements.enabled = true;${NC}"
                fi
            fi
        else
            echo -e "${YELLOW}⚠️  Could not check SQL logging status${NC}"
            echo -e "${YELLOW}💡 Run manually: SET CLUSTER SETTING sql.log.all_statements.enabled = true;${NC}"
        fi
        
        echo -e "${YELLOW}💡 If no queries appear, try: $0 --sql-only${NC}"
        echo
        
        # Monitor the log file and filter for SQL queries
        echo -e "${CYAN}🔍 Monitoring $(basename "$log_file") for SQL statements...${NC}"
        echo -e "${YELLOW}💡 This will run continuously - press Ctrl+C to stop${NC}"
        echo
        
        # Use a persistent monitoring approach without timeout
        local query_count=0
        local last_activity=$(date +%s)
        
        while true; do
            # Check if log file still exists (handle rotation)
            if [[ ! -f "$log_file" ]]; then
                echo -e "${YELLOW}⚠️  Log file disappeared, checking for new log files...${NC}"
                sleep 2
                
                # Try to find the log file again (it might have rotated)
                for log in "${possible_logs[@]}"; do
                    if [[ -f "$log" ]]; then
                        log_file="$log"
                        echo -e "${CYAN}📄 Found new log file: $(basename "$log")${NC}"
                        break
                    fi
                done
                
                if [[ ! -f "$log_file" ]]; then
                    echo -e "${RED}❌ No log file found, switching to SQL monitoring${NC}"
                    watch_sql_queries
                    return
                fi
            fi
            
            # Monitor the log file with a shorter timeout and restart if needed
            timeout 30 tail -f "$log_file" 2>/dev/null | while read line; do
                # Look for SQL statements in various log formats
                if echo "$line" | grep -qE "(SELECT|INSERT|UPDATE|DELETE|CREATE)"; then
                    # Check if it's expense-related or important user query
                    if echo "$line" | grep -qE "expenses" || (echo "$line" | grep -qE "(SELECT|INSERT|UPDATE|DELETE)" && ! echo "$line" | grep -qE "(system\.|crdb_internal|information_schema|pg_catalog|job_|protected_ts|settings|cluster_setting)"); then
                        query_count=$((query_count + 1))
                        last_activity=$(date +%s)
                        
                        # Extract timestamp from log line (CockroachDB format: I250814 23:45:30.123456)
                        local timestamp=$(echo "$line" | grep -oE 'I[0-9]{6} [0-9]{2}:[0-9]{2}:[0-9]{2}' | head -1)
                        if [[ -n "$timestamp" ]]; then
                            # Convert CockroachDB timestamp format to readable time
                            local time_part=$(echo "$timestamp" | cut -d' ' -f2)
                            timestamp="$time_part"
                        else
                            timestamp=$(date '+%H:%M:%S')
                        fi
                        
                        # Extract SQL statement from log line - handle different log formats
                        local statement=""
                        if echo "$line" | grep -q '"Statement":'; then
                            # JSON format log entry
                            statement=$(echo "$line" | sed 's/.*"Statement":"//;s/",".*//g' | sed 's/\\"/"/g')
                        else
                            # Plain text format
                            statement=$(echo "$line" | grep -oE "(SELECT|INSERT|UPDATE|DELETE|CREATE)[^;]*" | head -1)
                        fi
                        
                        if [[ -n "$statement" ]]; then
                            echo -e "${timestamp} ${GREEN}🔍 LIVE QUERY #${query_count}:${NC} Found SQL in logs"
                            if [[ "$DEBUG_MODE" == "true" ]]; then
                                echo -e "    ${GREEN}└─${NC} SQL: $(echo "$statement" | cut -c1-100)..."
                            fi
                            parse_and_display_query "$statement" "sql"
                        fi
                    fi
                fi
            done
            
            # If tail exits, show status and restart
            local current_time=$(date +%s)
            local time_since_activity=$((current_time - last_activity))
            
            if [[ $time_since_activity -gt 60 ]]; then
                echo -e "${CYAN}🔄 Log monitoring restarted (${query_count} queries detected so far, ${time_since_activity}s since last activity)${NC}"
            else
                echo -e "${CYAN}🔄 Log monitoring restarted (${query_count} queries detected so far)${NC}"
            fi
            
            sleep 1
        done
    else
        # Fallback to SQL-based monitoring
        if [[ -n "$LOG_DIR" ]]; then
            echo -e "${YELLOW}📝 No SQL execution logs found in $LOG_DIR${NC}"
            echo -e "${YELLOW}📝 Available log files:${NC}"
            ls -1 "$LOG_DIR"/*.log 2>/dev/null | head -5 | while read log; do
                echo -e "${YELLOW}   - $(basename "$log")${NC}"
            done
            echo
        fi
        echo -e "${CYAN}🔄 Switching to SQL-based monitoring...${NC}"
        watch_sql_queries
    fi
}

# Monitor via SQL queries (for cloud or when logs aren't accessible)
watch_sql_queries() {
    local db_url="${DB_URL:-${DATABASE_URL:-cockroachdb://root@localhost:26257/defaultdb?sslmode=disable}}"
    local last_timestamp=""
    
    # Check if we have cockroach binary or psql for SQL access (prefer cockroach)
    local sql_cmd=""
    if command -v cockroach >/dev/null 2>&1; then
        sql_cmd="cockroach sql"
        # Convert cockroachdb:// URL to postgresql:// for cockroach binary
        db_url=$(echo "$db_url" | sed 's/cockroachdb:/postgresql:/')
    elif [[ -n "$COCKROACH_BINARY" ]] && command -v "$COCKROACH_BINARY" >/dev/null 2>&1; then
        sql_cmd="$COCKROACH_BINARY sql"
        # Convert cockroachdb:// URL to postgresql:// for cockroach binary
        db_url=$(echo "$db_url" | sed 's/cockroachdb:/postgresql:/')
    elif command -v psql >/dev/null 2>&1; then
        sql_cmd="psql"
        # Convert cockroachdb:// URL to postgresql:// for psql
        db_url=$(echo "$db_url" | sed 's/cockroachdb:/postgresql:/')
    else
        echo -e "${RED}❌ Error: No SQL client available (cockroach binary or psql)${NC}"
        exit 1
    fi
    
    echo -e "${CYAN}🔄 Polling database for query activity every 2 seconds...${NC}"
    echo -e "${YELLOW}Note: This method shows completed queries, not real-time execution${NC}"
    echo
    
    # Show recent activity on startup
    echo -e "${CYAN}📋 Recent expense-related queries:${NC}"
    local startup_query="SELECT 
        metadata->>'query' as statement,
        statistics->'statistics'->>'cnt' as count,
        statistics->'statistics'->>'lastExecAt' as last_exec
    FROM crdb_internal.statement_statistics 
    WHERE metadata->>'query' LIKE '%expenses%' 
        AND metadata->>'query' NOT LIKE '%crdb_internal%'
        AND metadata->>'query' NOT LIKE '%information_schema%'
        AND metadata->>'query' NOT LIKE '%statement_statistics%'
    ORDER BY statistics->'statistics'->>'lastExecAt' DESC 
    LIMIT 5;"
    
    if [[ "$DEBUG_MODE" == "true" ]]; then
        echo -e "${CYAN}Debug: Using SQL command: $sql_cmd${NC}"
        echo -e "${CYAN}Debug: Database URL: $db_url${NC}"
        echo -e "${CYAN}Debug: Startup query:${NC}"
        echo "$startup_query"
        echo "---"
    fi
    
    local startup_result=""
    if [[ "$sql_cmd" == "psql" ]]; then
        startup_result=$(psql "$db_url" -t -c "$startup_query" 2>/dev/null)
    else
        if [[ "$DEBUG_MODE" == "true" ]]; then
            echo -e "${CYAN}Debug: Running cockroach command...${NC}"
            startup_result=$($sql_cmd --url="$db_url" --execute="$startup_query" --format=tsv 2>&1)
        else
            startup_result=$($sql_cmd --url="$db_url" --execute="$startup_query" --format=tsv 2>/dev/null)
        fi
    fi
    
    if [[ -n "$startup_result" ]]; then
        if [[ "$DEBUG_MODE" == "true" ]]; then
            echo -e "${CYAN}Debug: Found startup result:${NC}"
            echo "$startup_result"
            echo "---"
        fi
        echo "$startup_result" | while IFS=$'\t' read -r statement count last_exec; do
            if [[ -n "$statement" ]] && [[ "$statement" != "NULL" ]]; then
                parse_and_display_query "$statement" "sql"
            fi
        done
        echo -e "${CYAN}━━━ Now monitoring for new activity ━━━${NC}"
        echo
    else
        if [[ "$DEBUG_MODE" == "true" ]]; then
            echo -e "${CYAN}Debug: No startup result found${NC}"
        fi
        echo -e "${YELLOW}No recent expense queries found${NC}"
        echo
    fi
    
    # Store the latest timestamp to avoid showing duplicates
    local latest_timestamp=""
    if [[ -n "$startup_result" ]]; then
        latest_timestamp=$(echo "$startup_result" | head -1 | cut -f3)
    fi
    
    local poll_count=0
    local last_activity_time=$(date +%s)
    
    while true; do
        poll_count=$((poll_count + 1))
        
        # Show a progress indicator every 30 polls (60 seconds) if no new activity
        local current_time=$(date +%s)
        local time_since_activity=$((current_time - last_activity_time))
        
        if [[ $((poll_count % 30)) -eq 0 ]] && [[ $time_since_activity -gt 60 ]]; then
            echo -e "${CYAN}🔄 Still monitoring... (${poll_count} polls completed, ${time_since_activity}s since last activity)${NC}"
            echo -e "${YELLOW}💡 Try running some queries in the Banko AI app to see them here${NC}"
        fi
        
        # Query the statement statistics to detect new activity
        # Extract the actual query from the JSON metadata field
        local query="SELECT 
            metadata->>'query' as statement,
            statistics->'statistics'->>'cnt' as count,
            statistics->'statistics'->>'lastExecAt' as last_exec,
            statistics->'statistics'->'latencyInfo'->>'max' as max_latency
        FROM crdb_internal.statement_statistics 
        WHERE (metadata->>'query' LIKE '%expenses%' 
            OR metadata->>'query' LIKE '%SELECT%'
            OR metadata->>'query' LIKE '%INSERT%'
            OR metadata->>'query' LIKE '%UPDATE%'
            OR metadata->>'query' LIKE '%DELETE%')
            AND metadata->>'query' NOT LIKE '%crdb_internal%'
            AND metadata->>'query' NOT LIKE '%information_schema%'
            AND metadata->>'query' NOT LIKE '%statement_statistics%'
            AND metadata->>'query' NOT LIKE '%pg_catalog%'
            AND statistics->'statistics'->>'lastExecAt' > '$(date -u -d '5 minutes ago' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -v-5M '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo '2025-01-01T00:00:00Z')'
        ORDER BY statistics->'statistics'->>'lastExecAt' DESC 
        LIMIT 15;"
        
        local result=""
        if [[ "$sql_cmd" == "psql" ]]; then
            result=$(timeout 10 psql "$db_url" -t -c "$query" 2>/dev/null)
        else
            result=$(timeout 10 $sql_cmd --url="$db_url" --execute="$query" --format=tsv 2>/dev/null)
        fi
        
        # Check if command timed out or failed
        local exit_code=$?
        if [[ $exit_code -eq 124 ]]; then
            echo -e "${YELLOW}⚠️  Database query timed out, retrying...${NC}"
            sleep 5
            continue
        elif [[ $exit_code -ne 0 ]]; then
            echo -e "${RED}❌ Database connection error, retrying in 5 seconds...${NC}"
            sleep 5
            continue
        fi
        
        if [[ -n "$result" ]]; then
            # Process each line of results
            local found_new=false
            while IFS=$'\t' read -r statement count last_exec max_latency; do
                if [[ -n "$statement" ]] && [[ "$statement" != "NULL" ]]; then
                    # Only show if this is a new timestamp
                    if [[ "$last_exec" != "$latest_timestamp" ]] && [[ "$last_exec" > "$latest_timestamp" ]]; then
                        parse_and_display_query "$statement" "sql"
                        latest_timestamp="$last_exec"
                        found_new=true
                    fi
                fi
            done <<< "$result"
            
            # Reset poll count and update activity time if we found new activity
            if [[ "$found_new" == "true" ]]; then
                poll_count=0
                last_activity_time=$(date +%s)
            fi
        fi
        
        sleep 2
    done
}

# Main monitoring function
watch_queries() {
    case "$DEPLOYMENT_TYPE" in
        "container")
            watch_container_queries
            ;;
        "local")
            watch_local_queries
            ;;
        "cloud")
            watch_sql_queries
            ;;
        *)
            echo -e "${RED}❌ Error: Unknown deployment type: $DEPLOYMENT_TYPE${NC}"
            exit 1
            ;;
    esac
}

# Cleanup function
cleanup() {
    echo
    echo -e "${YELLOW}👋 Query monitoring stopped${NC}"
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM

# Main execution
main() {
    # Parse command line arguments
    parse_args "$@"
    
    # Auto-detect deployment type if not specified
    detect_deployment_type
    
    # Validate deployment type
    case "$DEPLOYMENT_TYPE" in
        "container")
            check_container
            ;;
        "local")
            check_local_binary
            ;;
        "cloud")
            check_cloud_connection
            ;;
        *)
            echo -e "${RED}❌ Error: Invalid deployment type: $DEPLOYMENT_TYPE${NC}"
            echo "Valid types: container, local, cloud"
            exit 1
            ;;
    esac
    
    if [[ "$DEBUG_MODE" == "true" ]]; then
        echo -e "${CYAN}🔧 Debug mode enabled - showing raw SQL queries${NC}"
        echo
    fi
    
    show_header
    watch_queries
}

# Run if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
