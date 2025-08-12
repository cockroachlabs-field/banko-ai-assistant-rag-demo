#!/bin/bash

# Banko AI - Database Query Watcher for Demo
# This script shows live SQL queries for demonstration purposes

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if container is running
check_container() {
    if ! docker ps | grep -q "banko-cockroachdb"; then
        echo -e "${RED}❌ Error: CockroachDB container is not running${NC}"
        echo "Please start the services first with: ./start-banko.sh"
        exit 1
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
    echo -e "${GREEN}📊 Monitoring CockroachDB for SQL queries...${NC}"
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

# Main monitoring function
watch_queries() {
    # Use docker or podman
    CONTAINER_CMD="docker"
    if command -v podman >/dev/null 2>&1 && ! command -v docker >/dev/null 2>&1; then
        CONTAINER_CMD="podman"
    fi

    # Monitor SQL execution log file directly for better performance
    ${CONTAINER_CMD} exec banko-cockroachdb tail -f /cockroach/cockroach-data/logs/cockroach-sql-exec.log 2>/dev/null | while read line; do
        # Parse the JSON log format and extract relevant information
        if echo "$line" | grep -q "query_execute"; then
            # Extract simple timestamp (just use current time for demo)
            current_time=$(date '+%H:%M:%S')
            
            # Extract the SQL statement from JSON
            statement=$(echo "$line" | sed 's/.*"Statement":"//;s/","Tag":.*//' | sed 's/\\"/"/g')
            
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
                
            elif echo "$line" | grep -qE '"User":"root"' && ! echo "$line" | grep -q "internal" && echo "$statement" | grep -qE "(SELECT|INSERT|UPDATE|DELETE)"; then
                # User queries (non-internal, non-system)
                clean_query=$(echo "$statement" | cut -c1-80)
                echo -e "${current_time} ${GREEN}📊 USER QUERY:${NC} ${clean_query}..."
            fi
        fi
    done
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
    # Check for debug flag
    DEBUG_MODE=false
    if [[ "$1" == "--debug" || "$1" == "-d" ]]; then
        DEBUG_MODE=true
        echo "🔧 Debug mode enabled - showing raw SQL queries"
        echo
    fi
    
    check_container
    show_header
    watch_queries
}

# Run if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
