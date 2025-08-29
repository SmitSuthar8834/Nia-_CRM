#!/bin/bash

# Deployment script for Intelligent Meeting Workflow
# Usage: ./scripts/deploy.sh [environment]
# Environments: development, staging, production

set -e  # Exit on any error

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${1:-development}"

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
            log_info "Deploying to $ENVIRONMENT environment"
            ;;
        *)
            log_error "Invalid environment: $ENVIRONMENT"
            log_error "Valid environments: development, staging, production"
            exit 1
            ;;
    esac
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker is not running"
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Load environment variables
load_environment() {
    log_info "Loading environment configuration..."
    
    cd "$PROJECT_ROOT"
    
    # Check if .env file exists
    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            log_warning ".env file not found, copying from .env.example"
            cp .env.example .env
            log_warning "Please update .env file with your actual configuration"
        else
            log_error ".env.example file not found"
            exit 1
        fi
    fi
    
    # Load environment variables
    export $(grep -v '^#' .env | xargs)
    
    # Set environment-specific variables
    case $ENVIRONMENT in
        development)
            export DEBUG=1
            export BUILD_TARGET=development
            ;;
        staging)
            export DEBUG=0
            export BUILD_TARGET=production
            export DJANGO_SETTINGS_MODULE=intelligent_meeting_workflow.settings.staging
            ;;
        production)
            export DEBUG=0
            export BUILD_TARGET=production
            export DJANGO_SETTINGS_MODULE=intelligent_meeting_workflow.settings.production
            ;;
    esac
    
    log_success "Environment configuration loaded"
}

# Build Docker images
build_images() {
    log_info "Building Docker images..."
    
    cd "$PROJECT_ROOT"
    
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
    
    log_success "Docker images built successfully"
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    
    cd "$PROJECT_ROOT"
    
    case $ENVIRONMENT in
        development)
            docker-compose run --rm web python manage.py migrate
            ;;
        staging)
            docker-compose -f docker-compose.yml -f docker-compose.staging.yml run --rm web python manage.py migrate
            ;;
        production)
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml run --rm web python manage.py migrate
            ;;
    esac
    
    log_success "Database migrations completed"
}

# Collect static files
collect_static() {
    if [ "$ENVIRONMENT" != "development" ]; then
        log_info "Collecting static files..."
        
        cd "$PROJECT_ROOT"
        
        case $ENVIRONMENT in
            staging)
                docker-compose -f docker-compose.yml -f docker-compose.staging.yml run --rm web python manage.py collectstatic --noinput
                ;;
            production)
                docker-compose -f docker-compose.yml -f docker-compose.prod.yml run --rm web python manage.py collectstatic --noinput
                ;;
        esac
        
        log_success "Static files collected"
    fi
}

# Start services
start_services() {
    log_info "Starting services..."
    
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
    
    log_success "Services started successfully"
}

# Wait for services to be ready
wait_for_services() {
    log_info "Waiting for services to be ready..."
    
    # Wait for web service to be healthy
    local max_attempts=30
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -f http://localhost:${WEB_PORT:-8000}/api/health/ &> /dev/null; then
            log_success "Web service is ready"
            break
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            log_error "Web service failed to start within expected time"
            exit 1
        fi
        
        log_info "Attempt $attempt/$max_attempts - waiting for web service..."
        sleep 10
        ((attempt++))
    done
}

# Run health checks
run_health_checks() {
    log_info "Running health checks..."
    
    # Basic health check
    if curl -f http://localhost:${WEB_PORT:-8000}/api/health/ &> /dev/null; then
        log_success "Basic health check passed"
    else
        log_error "Basic health check failed"
        exit 1
    fi
    
    # Detailed health check
    local health_response=$(curl -s http://localhost:${WEB_PORT:-8000}/api/health/detailed/)
    local health_status=$(echo "$health_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unknown")
    
    if [ "$health_status" = "healthy" ]; then
        log_success "Detailed health check passed"
    else
        log_warning "Detailed health check shows issues: $health_status"
        echo "$health_response" | python3 -m json.tool
    fi
}

# Create backup (for production)
create_backup() {
    if [ "$ENVIRONMENT" = "production" ]; then
        log_info "Creating database backup..."
        
        local backup_dir="$PROJECT_ROOT/backups"
        local backup_file="$backup_dir/backup_$(date +%Y%m%d_%H%M%S).sql"
        
        mkdir -p "$backup_dir"
        
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$backup_file"
        
        if [ -f "$backup_file" ] && [ -s "$backup_file" ]; then
            log_success "Database backup created: $backup_file"
        else
            log_error "Database backup failed"
            exit 1
        fi
    fi
}

# Rollback function
rollback() {
    log_warning "Rolling back deployment..."
    
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
    
    log_info "Rollback completed"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up..."
    
    # Remove unused Docker images
    docker image prune -f
    
    # Remove unused volumes (be careful in production)
    if [ "$ENVIRONMENT" = "development" ]; then
        docker volume prune -f
    fi
    
    log_success "Cleanup completed"
}

# Main deployment function
main() {
    log_info "Starting deployment of Intelligent Meeting Workflow"
    log_info "Environment: $ENVIRONMENT"
    log_info "Timestamp: $(date)"
    
    # Set up error handling
    trap rollback ERR
    
    validate_environment
    check_prerequisites
    load_environment
    
    # Create backup before production deployment
    if [ "$ENVIRONMENT" = "production" ]; then
        create_backup
    fi
    
    build_images
    run_migrations
    collect_static
    start_services
    wait_for_services
    run_health_checks
    
    # Cleanup old resources
    cleanup
    
    log_success "Deployment completed successfully!"
    log_info "Application is available at: http://localhost:${WEB_PORT:-8000}"
    
    if [ "$ENVIRONMENT" != "development" ]; then
        log_info "Admin interface: http://localhost:${WEB_PORT:-8000}/admin/"
        log_info "Health check: http://localhost:${WEB_PORT:-8000}/api/health/"
    fi
    
    # Show running services
    log_info "Running services:"
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

# Run main function
main "$@"