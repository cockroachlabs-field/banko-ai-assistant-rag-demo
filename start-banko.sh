#!/bin/bash

# Banko AI Assistant - Comprehensive Startup Script
# This script handles the complete setup and startup of the Banko AI Assistant

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_banner() {
    # Detect AI service from docker-compose.yml
    local ai_service="watsonx"  # default
    if [ -f "docker-compose.yml" ]; then
        ai_service=$(grep "AI_SERVICE=" docker-compose.yml | sed 's/.*AI_SERVICE=//' | tr -d ' ')
    fi
    
    # Set AI provider display name and icon
    case "$(echo ${ai_service} | tr '[:upper:]' '[:lower:]')" in
        "watsonx"|"watson")
            local ai_provider="🧠 IBM Watsonx AI"
            ;;
        "aws"|"bedrock"|"aws_bedrock")
            local ai_provider="☁️ AWS Bedrock"
            ;;
        *)
            local ai_provider="🤖 $(echo ${ai_service} | tr '[:lower:]' '[:upper:]')"
            ;;
    esac
    
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                    🏦 BANKO AI ASSISTANT 🤖                   ║"
    echo "║               Conversational Banking Assistant                ║"
    echo "║                                                               ║"
    printf "║  🚀 Starting up with CockroachDB & %-25s ║\n" "${ai_provider}"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Function to check if Docker/Podman is running
check_docker() {
    log_info "Checking container runtime..."
    
    # Check for Docker first
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        log_success "Docker is running"
        CONTAINER_CMD="docker"
        COMPOSE_CMD="docker-compose"
        return 0
    fi
    
    # Check for Podman
    if command -v podman >/dev/null 2>&1; then
        log_success "Podman detected"
        CONTAINER_CMD="podman"
        # Check if podman-compose is available
        if command -v podman-compose >/dev/null 2>&1; then
            COMPOSE_CMD="podman-compose"
        else
            log_warning "podman-compose not found. Installing/using docker-compose with Podman..."
            COMPOSE_CMD="docker-compose"
        fi
        return 0
    fi
    
    log_error "Neither Docker nor Podman is available or running."
    log_error "Please install and start Docker Desktop or Podman."
    exit 1
}

# Function to clean up existing containers
cleanup_containers() {
    log_info "Cleaning up existing containers..."
    
    # Stop and remove existing containers
    if ${CONTAINER_CMD} ps -a --format '{{.Names}}' | grep -q "banko-cockroachdb"; then
        log_warning "Removing existing banko-cockroachdb container..."
        ${CONTAINER_CMD} stop banko-cockroachdb >/dev/null 2>&1 || true
        ${CONTAINER_CMD} rm banko-cockroachdb >/dev/null 2>&1 || true
    fi
    
    if ${CONTAINER_CMD} ps -a --format '{{.Names}}' | grep -q "banko-db-init"; then
        log_warning "Removing existing banko-db-init container..."
        ${CONTAINER_CMD} stop banko-db-init >/dev/null 2>&1 || true
        ${CONTAINER_CMD} rm banko-db-init >/dev/null 2>&1 || true
    fi
    
    if ${CONTAINER_CMD} ps -a --format '{{.Names}}' | grep -q "banko-app"; then
        log_warning "Removing existing banko-app container..."
        ${CONTAINER_CMD} stop banko-app >/dev/null 2>&1 || true
        ${CONTAINER_CMD} rm banko-app >/dev/null 2>&1 || true
    fi
    
    log_success "Container cleanup complete"
}

# Function to check config file
check_config() {
    log_info "Checking configuration..."
    
    if [ ! -f "config.py" ]; then
        log_warning "config.py not found. Creating from template..."
        cp config.example.py config.py
        log_error "IMPORTANT: Please edit config.py with your actual API keys!"
        log_error "Required: WATSONX_API_KEY, WATSONX_PROJECT_ID"
        echo
        echo "Press Enter to continue once you've updated config.py, or Ctrl+C to exit..."
        read
    fi
    
    log_success "Configuration file exists"
}

# Function to start services with Docker Compose
start_services() {
    log_info "Starting Banko AI services..."
    
    # Start all services
    ${COMPOSE_CMD} up -d --remove-orphans
    
    log_success "Services started successfully"
}

# Function to wait for database initialization
wait_for_database() {
    log_info "Waiting for database initialization..."
    
    # Wait for CockroachDB to be healthy
    log_info "Waiting for CockroachDB to be ready..."
    while ! ${CONTAINER_CMD} exec banko-cockroachdb ./cockroach sql --insecure --execute="SELECT 1;" >/dev/null 2>&1; do
        echo -n "."
        sleep 2
    done
    echo
    log_success "CockroachDB is ready"
    
    # Wait for db-init to complete
    log_info "Waiting for database initialization to complete..."
    while ${CONTAINER_CMD} ps --format '{{.Names}}' | grep -q "banko-db-init"; do
        echo -n "."
        sleep 2
    done
    echo
    log_success "Database initialization complete"
}

# Function to initialize database with sample data
init_database_data() {
    log_info "Setting up database schema and sample data..."
    
    # Check if we need to create tables and load data
    table_exists=$(${CONTAINER_CMD} exec banko-cockroachdb ./cockroach sql --insecure --execute="SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'expenses');" --format=csv | tail -n 1 | tr -d '\r' | tr -d '\n')
    
    if [ "$table_exists" = "f" ]; then
        log_info "Creating expenses table..."
        ${CONTAINER_CMD} exec banko-cockroachdb ./cockroach sql --insecure --execute="
        CREATE TABLE expenses (
            expense_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL,
            expense_date DATE NOT NULL,
            expense_amount DECIMAL(10,2) NOT NULL,
            shopping_type STRING NOT NULL,
            description STRING,
            merchant STRING,
            payment_method STRING NOT NULL,
            recurring BOOL DEFAULT FALSE,
            tags STRING[],
            embedding vector(384),
            VECTOR INDEX (embedding)
        );"
        log_success "Expenses table created"
        
        # Load sample data
        log_info "Loading sample expense data..."
        if [ -f "vector_search/expense_data.csv" ]; then
            # Use Python to load data with embeddings
            ${CONTAINER_CMD} exec -i banko-app python -c "
import sys
sys.path.append('/app/vector_search')
from insert_data import read_csv_data, insert_content
print('Loading sample data...')
data = read_csv_data('/app/vector_search/expense_data.csv')
insert_content(data)
print('Sample data loaded successfully!')
"
            log_success "Sample data loaded (3,000 expense records)"
        else
            log_warning "No sample data file found. You can add data manually later."
        fi
    else
        log_success "Database already contains expense data"
    fi
}

# Function to check service health
check_services() {
    log_info "Checking service health..."
    
    # Check CockroachDB
    if curl -f http://localhost:8080/health?ready=1 >/dev/null 2>&1; then
        log_success "CockroachDB Admin UI: http://localhost:8080"
    else
        log_warning "CockroachDB Admin UI not accessible"
    fi
    
    # Check Flask app
    if curl -f http://localhost:5000/ai-status >/dev/null 2>&1; then
        log_success "Banko AI Assistant: http://localhost:5000"
    else
        log_warning "Flask app not yet ready (may still be starting up)"
    fi
}

# Function to show final status
show_final_status() {
    # Detect AI service for final status
    local ai_service="watsonx"  # default
    if [ -f "docker-compose.yml" ]; then
        ai_service=$(grep "AI_SERVICE=" docker-compose.yml | sed 's/.*AI_SERVICE=//' | tr -d ' ')
    fi
    
    # Set AI provider display name
    case "$(echo ${ai_service} | tr '[:upper:]' '[:lower:]')" in
        "watsonx"|"watson")
            local ai_provider="🧠 IBM Watsonx AI"
            ;;
        "aws"|"bedrock"|"aws_bedrock")
            local ai_provider="☁️ AWS Bedrock"
            ;;
        *)
            local ai_provider="🤖 $(echo ${ai_service} | tr '[:lower:]' '[:upper:]')"
            ;;
    esac
    
    echo
    echo -e "${GREEN}🎉 BANKO AI ASSISTANT IS READY! 🎉${NC}"
    echo -e "${BLUE}   Powered by ${ai_provider} & 🗄️ CockroachDB${NC}"
    echo
    echo "📊 Access Points:"
    echo "  🏦 Banko AI Assistant:    http://localhost:5000"
    echo "  📈 Database Admin UI:     http://localhost:8080"
    echo "  🔍 API Status:           http://localhost:5000/ai-status"
    echo
    echo "🔧 Useful Commands:"
    echo "  📋 View logs:            docker-compose logs -f"
    echo "  🛑 Stop services:        docker-compose down"
    echo "  🔄 Restart:              ./start-banko.sh"
    echo "  🗄️  Database shell:       docker exec -it banko-cockroachdb ./cockroach sql --insecure"
    echo "  🔍 Query trace logs:     docker logs banko-cockroachdb | grep \"QUERY\""
    echo "  📊 Live query tracing:   docker logs -f banko-cockroachdb | grep --color=always \"QUERY\\|SELECT\\|INSERT\\|UPDATE\""
    echo
    echo "💡 Tip: Check the AI status endpoint to verify ${ai_service} integration"
    echo
}

# Main execution
main() {
    print_banner
    
    # Ensure we're in the right directory
    if [ ! -f "docker-compose.yml" ]; then
        log_error "docker-compose.yml not found. Please run this script from the project root directory."
        exit 1
    fi
    
    # Run all setup steps
    check_docker
    cleanup_containers
    check_config
    start_services
    wait_for_database
    
    # Optional: Initialize database data (only if using Docker Compose with app service)
    if ${CONTAINER_CMD} ps --format '{{.Names}}' | grep -q "banko-app"; then
        init_database_data
    else
        log_info "Skipping data initialization (run manually if needed)"
    fi
    
    check_services
    show_final_status
    
    # Keep script running to show logs
    log_info "Showing service logs (Ctrl+C to exit)..."
    ${COMPOSE_CMD} logs -f
}

# Handle Ctrl+C gracefully
trap 'echo -e "\n${YELLOW}Stopping services...${NC}"; ${COMPOSE_CMD} down; exit 0' INT

# Parse command line arguments
case "${1:-}" in
    "stop")
        check_docker  # Set COMPOSE_CMD
        log_info "Stopping Banko AI services..."
        ${COMPOSE_CMD} down
        log_success "Services stopped"
        exit 0
        ;;
    "restart")
        check_docker  # Set COMPOSE_CMD
        log_info "Restarting Banko AI services..."
        ${COMPOSE_CMD} down
        sleep 2
        main
        ;;
    "logs")
        check_docker  # Set COMPOSE_CMD
        ${COMPOSE_CMD} logs -f
        exit 0
        ;;
    "status")
        check_docker  # Set COMPOSE_CMD
        ${COMPOSE_CMD} ps
        echo
        curl -s http://localhost:5000/ai-status | python -m json.tool 2>/dev/null || echo "Service not responding"
        exit 0
        ;;
    "query-logs"|"querylogs"|"trace")
        echo "🔍 Starting live SQL query trace logs for demo..."
        echo "   (Press Ctrl+C to exit)"
        echo "   💡 Tip: Use './scripts/watch-queries.sh' for enhanced demo mode"
        echo "   🔧 Add --debug flag for raw SQL: './scripts/watch-queries.sh --debug'"
        echo
        check_docker  # Set CONTAINER_CMD
        ${CONTAINER_CMD} logs -f banko-cockroachdb 2>&1 | grep --color=always --line-buffered "QUERY\|SELECT\|INSERT\|UPDATE\|DELETE\|<.*>\|executor\.go"
        exit 0
        ;;
    "help"|"-h"|"--help")
        echo "Banko AI Assistant Startup Script"
        echo
        echo "Usage: $0 [command]"
        echo
        echo "Commands:"
        echo "  (no args)    Start all services"
        echo "  stop         Stop all services"
        echo "  restart      Restart all services"
        echo "  logs         Show service logs"
        echo "  status       Show service status"
        echo "  query-logs   Show live SQL query trace logs (demo mode)"
        echo "  help         Show this help message"
        exit 0
        ;;
    "")
        main
        ;;
    *)
        log_error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
