#!/bin/bash

# Banko AI Assistant - Simple Database Startup Script
# This script starts just the CockroachDB database, avoiding container naming issues

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
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                 🗄️  BANKO DATABASE SETUP 🗄️                   ║"
    echo "║               CockroachDB with Vector Search                  ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Function to detect container runtime
detect_container_runtime() {
    log_info "Detecting container runtime..."
    
    # Check for Docker first
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        log_success "Docker detected and running"
        CONTAINER_CMD="docker"
        COMPOSE_CMD="docker-compose"
        return 0
    fi
    
    # Check for Podman
    if command -v podman >/dev/null 2>&1; then
        log_success "Podman detected"
        CONTAINER_CMD="podman"
        if command -v podman-compose >/dev/null 2>&1; then
            COMPOSE_CMD="podman-compose"
        else
            COMPOSE_CMD="docker-compose"
        fi
        return 0
    fi
    
    log_error "Neither Docker nor Podman found!"
    exit 1
}

# Function to clean up and start database
setup_database() {
    log_info "Setting up CockroachDB database..."
    
    # Clean up existing containers
    log_info "Cleaning up existing containers..."
    ${CONTAINER_CMD} stop banko-cockroachdb banko-db-init 2>/dev/null || true
    ${CONTAINER_CMD} rm banko-cockroachdb banko-db-init 2>/dev/null || true
    
    # Use the simple compose file
    log_info "Starting database services..."
    ${COMPOSE_CMD} -f docker-compose.simple.yml up -d
    
    # Wait for database to be ready
    log_info "Waiting for CockroachDB to be ready..."
    local retries=30
    while [ $retries -gt 0 ]; do
        if curl -f http://localhost:8080/health?ready=1 >/dev/null 2>&1; then
            log_success "CockroachDB is ready!"
            break
        fi
        echo -n "."
        sleep 2
        retries=$((retries - 1))
    done
    
    if [ $retries -eq 0 ]; then
        log_error "Database failed to start within timeout"
        exit 1
    fi
}

# Function to initialize database schema and data
init_database() {
    log_info "Initializing database schema and sample data..."
    
    # Wait for db-init to complete
    log_info "Waiting for vector features to be enabled..."
    while ${CONTAINER_CMD} ps --format '{{.Names}}' | grep -q "banko-db-init"; do
        echo -n "."
        sleep 2
    done
    echo
    
    # Create table and load data using Python scripts
    log_info "Creating expense table..."
    source .venv/bin/activate 2>/dev/null || {
        log_warning "Virtual environment not found, using system Python"
    }
    
    cd vector_search
    python create_table.py || {
        log_error "Failed to create table"
        exit 1
    }
    
    log_info "Loading sample data (this may take a minute)..."
    python insert_data.py || {
        log_error "Failed to load sample data"
        exit 1
    }
    
    cd ..
    log_success "Database initialization complete!"
}

# Function to show status and next steps
show_status() {
    echo
    echo -e "${GREEN}🎉 DATABASE SETUP COMPLETE! 🎉${NC}"
    echo
    echo "📊 Database Status:"
    echo "  🗄️  CockroachDB:          http://localhost:26257"
    echo "  📈 Admin UI:             http://localhost:8080"
    echo "  📋 Sample Records:       3,000 expense entries"
    echo
    echo "🚀 Next Steps:"
    echo "  1. Run the Flask app:"
    echo "     export AI_SERVICE=watsonx"
    echo "     python app.py"
    echo
    echo "  2. Test vector search:"
    echo "     python scripts/demo_standalone_search.py"
    echo
    echo "  3. Stop database when done:"
    echo "     ${COMPOSE_CMD} -f docker-compose.simple.yml down"
    echo
}

# Main execution
main() {
    print_banner
    
    detect_container_runtime
    setup_database
    init_database
    show_status
    
    log_info "Database is running in the background"
    log_info "Use '${COMPOSE_CMD} -f docker-compose.simple.yml logs -f' to view logs"
}

# Parse command line arguments
case "${1:-}" in
    "stop")
        detect_container_runtime
        log_info "Stopping database services..."
        ${COMPOSE_CMD} -f docker-compose.simple.yml down
        log_success "Database stopped"
        exit 0
        ;;
    "status")
        detect_container_runtime
        ${COMPOSE_CMD} -f docker-compose.simple.yml ps
        echo
        curl -s http://localhost:8080/health?ready=1 >/dev/null && echo "✅ Database is healthy" || echo "❌ Database not responding"
        exit 0
        ;;
    "logs")
        detect_container_runtime
        ${COMPOSE_CMD} -f docker-compose.simple.yml logs -f
        exit 0
        ;;
    "help"|"-h"|"--help")
        echo "Banko AI Database Setup Script"
        echo
        echo "Usage: $0 [command]"
        echo
        echo "Commands:"
        echo "  (no args)    Setup and start database"
        echo "  stop         Stop database services"
        echo "  status       Show database status"
        echo "  logs         Show database logs"
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
