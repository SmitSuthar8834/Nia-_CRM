#!/bin/bash

# Monitoring script for Intelligent Meeting Workflow
# Usage: ./scripts/monitoring.sh [command]
# Commands: status, logs, metrics, health, restart

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMMAND="${1:-status}"

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

# Load environment
load_environment() {
    cd "$PROJECT_ROOT"
    if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
    fi
}

# Show system status
show_status() {
    log_info "System Status - $(date)"
    echo "=================================="
    
    cd "$PROJECT_ROOT"
    
    # Show Docker containers
    log_info "Docker Containers:"
    docker-compose ps
    echo ""
    
    # Show resource usage
    log_info "Resource Usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
    echo ""
    
    # Show disk usage
    log_info "Disk Usage:"
    df -h | grep -E "(Filesystem|/dev/)"
    echo ""
    
    # Show network ports
    log_info "Network Ports:"
    netstat -tlnp 2>/dev/null | grep -E ":(8000|5432|6379|5678|80|443)" || echo "No relevant ports found"
    echo ""
}

# Show application logs
show_logs() {
    local service="${2:-web}"
    local lines="${3:-100}"
    
    log_info "Showing last $lines lines of $service logs"
    echo "=================================="
    
    cd "$PROJECT_ROOT"
    docker-compose logs --tail="$lines" -f "$service"
}

# Show metrics
show_metrics() {
    log_info "Application Metrics - $(date)"
    echo "=================================="
    
    # Health check
    log_info "Health Status:"
    if curl -s http://localhost:${WEB_PORT:-8000}/api/health/detailed/ | python3 -m json.tool 2>/dev/null; then
        echo ""
    else
        log_error "Failed to retrieve health status"
    fi
    
    # Database metrics
    log_info "Database Metrics:"
    cd "$PROJECT_ROOT"
    docker-compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
        SELECT 
            schemaname,
            tablename,
            n_tup_ins as inserts,
            n_tup_upd as updates,
            n_tup_del as deletes,
            n_live_tup as live_tuples
        FROM pg_stat_user_tables 
        ORDER BY n_live_tup DESC 
        LIMIT 10;
    " 2>/dev/null || log_warning "Could not retrieve database metrics"
    echo ""
    
    # Redis metrics
    log_info "Redis Metrics:"
    docker-compose exec redis redis-cli info memory | grep -E "(used_memory_human|used_memory_peak_human)" || log_warning "Could not retrieve Redis metrics"
    echo ""
    
    # Application-specific metrics
    log_info "Application Metrics:"
    echo "Active meetings: $(curl -s http://localhost:${WEB_PORT:-8000}/api/meetings/?status=in_progress | python3 -c "import sys, json; print(json.load(sys.stdin).get('count', 'N/A'))" 2>/dev/null || echo "N/A")"
    echo "Pending validations: $(curl -s http://localhost:${WEB_PORT:-8000}/api/validation/sessions/?status=pending | python3 -c "import sys, json; print(json.load(sys.stdin).get('count', 'N/A'))" 2>/dev/null || echo "N/A")"
    echo ""
}

# Comprehensive health check
health_check() {
    log_info "Comprehensive Health Check - $(date)"
    echo "=================================="
    
    local overall_healthy=true
    
    # Check if services are running
    log_info "Service Status:"
    cd "$PROJECT_ROOT"
    
    local services=("web" "db" "redis" "celery" "celery-beat")
    for service in "${services[@]}"; do
        if docker-compose ps "$service" | grep -q "Up"; then
            echo "✅ $service: Running"
        else
            echo "❌ $service: Not running"
            overall_healthy=false
        fi
    done
    echo ""
    
    # Check application health endpoint
    log_info "Application Health:"
    if curl -f http://localhost:${WEB_PORT:-8000}/api/health/ &> /dev/null; then
        echo "✅ Web application: Healthy"
        
        # Get detailed health info
        local health_response=$(curl -s http://localhost:${WEB_PORT:-8000}/api/health/detailed/)
        local db_status=$(echo "$health_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['components']['database']['status'])" 2>/dev/null || echo "unknown")
        local cache_status=$(echo "$health_response" | python3 -c "import sys, json; print(json.load(sys.stdin)['components']['cache']['status'])" 2>/dev/null || echo "unknown")
        
        if [ "$db_status" = "healthy" ]; then
            echo "✅ Database: Healthy"
        else
            echo "❌ Database: $db_status"
            overall_healthy=false
        fi
        
        if [ "$cache_status" = "healthy" ]; then
            echo "✅ Cache: Healthy"
        else
            echo "❌ Cache: $cache_status"
            overall_healthy=false
        fi
    else
        echo "❌ Web application: Unhealthy"
        overall_healthy=false
    fi
    echo ""
    
    # Check disk space
    log_info "Disk Space:"
    local disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$disk_usage" -lt 80 ]; then
        echo "✅ Disk space: ${disk_usage}% used"
    elif [ "$disk_usage" -lt 90 ]; then
        echo "⚠️  Disk space: ${disk_usage}% used (Warning)"
        log_warning "Disk space is getting low"
    else
        echo "❌ Disk space: ${disk_usage}% used (Critical)"
        overall_healthy=false
    fi
    echo ""
    
    # Check memory usage
    log_info "Memory Usage:"
    local memory_usage=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
    if [ "$memory_usage" -lt 80 ]; then
        echo "✅ Memory: ${memory_usage}% used"
    elif [ "$memory_usage" -lt 90 ]; then
        echo "⚠️  Memory: ${memory_usage}% used (Warning)"
        log_warning "Memory usage is high"
    else
        echo "❌ Memory: ${memory_usage}% used (Critical)"
        overall_healthy=false
    fi
    echo ""
    
    # Overall status
    if [ "$overall_healthy" = true ]; then
        log_success "Overall System Status: HEALTHY"
    else
        log_error "Overall System Status: UNHEALTHY"
        exit 1
    fi
}

# Restart services
restart_services() {
    local service="${2:-all}"
    
    log_info "Restarting services: $service"
    
    cd "$PROJECT_ROOT"
    
    if [ "$service" = "all" ]; then
        docker-compose restart
        log_success "All services restarted"
    else
        docker-compose restart "$service"
        log_success "Service $service restarted"
    fi
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 10
    
    if curl -f http://localhost:${WEB_PORT:-8000}/api/health/ &> /dev/null; then
        log_success "Services are ready"
    else
        log_error "Services may not be ready yet"
    fi
}

# Clean up resources
cleanup() {
    log_info "Cleaning up Docker resources"
    
    # Remove stopped containers
    docker container prune -f
    
    # Remove unused images
    docker image prune -f
    
    # Remove unused networks
    docker network prune -f
    
    # Remove unused volumes (be careful!)
    echo -n "Remove unused volumes? (y/N): "
    read -r confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        docker volume prune -f
        log_success "Volumes cleaned up"
    fi
    
    log_success "Cleanup completed"
}

# Backup database
backup_database() {
    log_info "Creating database backup"
    
    local backup_dir="$PROJECT_ROOT/backups"
    local backup_file="$backup_dir/backup_$(date +%Y%m%d_%H%M%S).sql"
    
    mkdir -p "$backup_dir"
    
    cd "$PROJECT_ROOT"
    docker-compose exec -T db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > "$backup_file"
    
    if [ -f "$backup_file" ] && [ -s "$backup_file" ]; then
        log_success "Database backup created: $backup_file"
        
        # Keep only last 10 backups
        ls -t "$backup_dir"/backup_*.sql | tail -n +11 | xargs -r rm
        log_info "Old backups cleaned up (keeping last 10)"
    else
        log_error "Database backup failed"
        exit 1
    fi
}

# Show usage
show_usage() {
    echo "Usage: $0 [command] [options]"
    echo ""
    echo "Commands:"
    echo "  status                 Show system status"
    echo "  logs [service] [lines] Show logs (default: web, 100 lines)"
    echo "  metrics                Show application metrics"
    echo "  health                 Run comprehensive health check"
    echo "  restart [service]      Restart services (default: all)"
    echo "  cleanup                Clean up Docker resources"
    echo "  backup                 Create database backup"
    echo ""
    echo "Examples:"
    echo "  $0 status"
    echo "  $0 logs web 50"
    echo "  $0 logs celery"
    echo "  $0 restart web"
    echo "  $0 health"
}

# Main function
main() {
    load_environment
    
    case $COMMAND in
        status)
            show_status
            ;;
        logs)
            show_logs "$@"
            ;;
        metrics)
            show_metrics
            ;;
        health)
            health_check
            ;;
        restart)
            restart_services "$@"
            ;;
        cleanup)
            cleanup
            ;;
        backup)
            backup_database
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            log_error "Unknown command: $COMMAND"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"