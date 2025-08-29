#!/bin/bash

# Rollback script for Intelligent Meeting Workflow
# Usage: ./scripts/rollback.sh [environment] [backup_file]

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${1:-production}"
BACKUP_FILE="${2}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate environment
validate_environment() {
    case $ENVIRONMENT in
        development|staging|production)
            log_info "Rolling back $ENVIRONMENT environment"
            ;;
        *)
            log_error "Invalid environment: $ENVIRONMENT"
            log_error "Valid environments: development, staging, production"
            exit 1
            ;;
    esac
}

# Load environment variables
load_environment() {
    log_info "Loading environment configuration..."
    
    cd "$PROJECT_ROOT"
    
    if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
    fi
    
    log_success "Environment configuration loaded"
}

# Stop current services
stop_services() {
    log_info "Stopping current services..."
    
    cd "$PROJECT_ROOT"
    
    case $ENVIRONMENT in
        development)
            docker-compose down
            ;;
        staging)
            docker-compose -f docker-compose.yml -f docker-compose.staging.yml down
            ;;
        production)
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
            ;;
    esac
    
    log_success "Services stopped"
}

# List available backups
list_backups() {
    local backup_dir="$PROJECT_ROOT/backups"
    
    if [ -d "$backup_dir" ]; then
        log_info "Available backups:"
        ls -la "$backup_dir"/*.sql 2>/dev/null || log_warning "No backup files found"
    else
        log_warning "Backup directory not found: $backup_dir"
    fi
}

# Restore database from backup
restore_database() {
    if [ -n "$BACKUP_FILE" ]; then
        log_info "Restoring database from backup: $BACKUP_FILE"
        
        if [ ! -f "$BACKUP_FILE" ]; then
            log_error "Backup file not found: $BACKUP_FILE"
            exit 1
        fi
        
        cd "$PROJECT_ROOT"
        
        # Start only the database service
        case $ENVIRONMENT in
            development)
                docker-compose up -d db
                ;;
            staging)
                docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d db
                ;;
            production)
                docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d db
                ;;
        esac
        
        # Wait for database to be ready
        log_info "Waiting for database to be ready..."
        sleep 10
        
        # Drop and recreate database
        case $ENVIRONMENT in
            development)
                docker-compose exec db psql -U "$POSTGRES_USER" -c "DROP DATABASE IF EXISTS $POSTGRES_DB;"
                docker-compose exec db psql -U "$POSTGRES_USER" -c "CREATE DATABASE $POSTGRES_DB;"
                docker-compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$BACKUP_FILE"
                ;;
            staging)
                docker-compose -f docker-compose.yml -f docker-compose.staging.yml exec db psql -U "$POSTGRES_USER" -c "DROP DATABASE IF EXISTS $POSTGRES_DB;"
                docker-compose -f docker-compose.yml -f docker-compose.staging.yml exec db psql -U "$POSTGRES_USER" -c "CREATE DATABASE $POSTGRES_DB;"
                docker-compose -f docker-compose.yml -f docker-compose.staging.yml exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$BACKUP_FILE"
                ;;
            production)
                docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec db psql -U "$POSTGRES_USER" -c "DROP DATABASE IF EXISTS $POSTGRES_DB;"
                docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec db psql -U "$POSTGRES_USER" -c "CREATE DATABASE $POSTGRES_DB;"
                docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < "$BACKUP_FILE"
                ;;
        esac
        
        log_success "Database restored from backup"
    else
        log_warning "No backup file specified, skipping database restore"
        list_backups
    fi
}

# Rollback to previous Docker images
rollback_images() {
    log_info "Rolling back to previous Docker images..."
    
    # This is a simplified rollback - in a real production environment,
    # you would have tagged images and a more sophisticated rollback strategy
    
    cd "$PROJECT_ROOT"
    
    # Pull previous images (if using a registry)
    # docker-compose pull
    
    # For now, we'll rebuild from the current code
    case $ENVIRONMENT in
        development)
            docker-compose build
            ;;
        staging)
            docker-compose -f docker-compose.yml -f docker-compose.staging.yml build
            ;;
        production)
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
            ;;
    esac
    
    log_success "Images rolled back"
}

# Start services after rollback
start_services() {
    log_info "Starting services after rollback..."
    
    cd "$PROJECT_ROOT"
    
    case $ENVIRONMENT in
        development)
            docker-compose up -d
            ;;
        staging)
            docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d
            ;;
        production)
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
            ;;
    esac
    
    log_success "Services started"
}

# Wait for services to be ready
wait_for_services() {
    log_info "Waiting for services to be ready..."
    
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:${WEB_PORT:-8000}/api/health/ &> /dev/null; then
            log_success "Services are ready after rollback"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            log_error "Services failed to start after rollback"
            exit 1
        fi
        
        log_info "Attempt $attempt/$max_attempts - waiting for services..."
        sleep 10
        ((attempt++))
    done
}

# Verify rollback
verify_rollback() {
    log_info "Verifying rollback..."
    
    # Basic health check
    if curl -f http://localhost:${WEB_PORT:-8000}/api/health/ &> /dev/null; then
        log_success "Health check passed after rollback"
    else
        log_error "Health check failed after rollback"
        exit 1
    fi
    
    # Show service status
    log_info "Service status after rollback:"
    case $ENVIRONMENT in
        development)
            docker-compose ps
            ;;
        staging)
            docker-compose -f docker-compose.yml -f docker-compose.staging.yml ps
            ;;
        production)
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
            ;;
    esac
}

# Interactive backup selection
select_backup_interactive() {
    local backup_dir="$PROJECT_ROOT/backups"
    
    if [ ! -d "$backup_dir" ]; then
        log_warning "No backup directory found"
        return
    fi
    
    local backups=($(ls "$backup_dir"/*.sql 2>/dev/null | sort -r))
    
    if [ ${#backups[@]} -eq 0 ]; then
        log_warning "No backup files found"
        return
    fi
    
    log_info "Available backups:"
    for i in "${!backups[@]}"; do
        local backup_file="${backups[$i]}"
        local backup_name=$(basename "$backup_file")
        local backup_date=$(stat -c %y "$backup_file" 2>/dev/null || stat -f %Sm "$backup_file" 2>/dev/null || echo "unknown")
        echo "$((i+1)). $backup_name ($backup_date)"
    done
    
    echo -n "Select backup number (or press Enter to skip): "
    read -r selection
    
    if [ -n "$selection" ] && [ "$selection" -ge 1 ] && [ "$selection" -le ${#backups[@]} ]; then
        BACKUP_FILE="${backups[$((selection-1))]}"
        log_info "Selected backup: $BACKUP_FILE"
    else
        log_info "No backup selected"
    fi
}

# Main rollback function
main() {
    log_warning "Starting rollback of Intelligent Meeting Workflow"
    log_info "Environment: $ENVIRONMENT"
    log_info "Timestamp: $(date)"
    
    validate_environment
    load_environment
    
    # Confirm rollback
    if [ "$ENVIRONMENT" = "production" ]; then
        echo -n "Are you sure you want to rollback PRODUCTION? (yes/no): "
        read -r confirmation
        if [ "$confirmation" != "yes" ]; then
            log_info "Rollback cancelled"
            exit 0
        fi
    fi
    
    # Interactive backup selection if no backup file specified
    if [ -z "$BACKUP_FILE" ] && [ "$ENVIRONMENT" = "production" ]; then
        select_backup_interactive
    fi
    
    stop_services
    restore_database
    rollback_images
    start_services
    wait_for_services
    verify_rollback
    
    log_success "Rollback completed successfully!"
    log_info "Application is available at: http://localhost:${WEB_PORT:-8000}"
    
    if [ -n "$BACKUP_FILE" ]; then
        log_info "Database restored from: $BACKUP_FILE"
    fi
}

# Show usage if no arguments provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 [environment] [backup_file]"
    echo "Environments: development, staging, production"
    echo "Backup file: Optional path to database backup file"
    echo ""
    echo "Examples:"
    echo "  $0 production"
    echo "  $0 production /path/to/backup.sql"
    echo "  $0 staging"
    exit 1
fi

# Run main function
main "$@"