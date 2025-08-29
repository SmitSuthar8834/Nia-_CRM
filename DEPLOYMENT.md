# Deployment Guide - Intelligent Meeting Workflow

This guide covers the deployment of the Intelligent Meeting Workflow system across different environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Configuration](#environment-configuration)
- [Deployment Methods](#deployment-methods)
- [Environment-Specific Deployments](#environment-specific-deployments)
- [Health Checks and Monitoring](#health-checks-and-monitoring)
- [Rollback Procedures](#rollback-procedures)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **Operating System**: Linux, macOS, or Windows with WSL2
- **Memory**: Minimum 4GB RAM (8GB recommended for production)
- **Storage**: Minimum 20GB free space
- **Network**: Internet access for external API integrations

### External Services

Before deployment, ensure you have access to:

1. **CRM Systems** (at least one):
   - Salesforce (Client ID, Secret, Username, Password)
   - HubSpot (API Key)
   - Creatio (API URL, Username, Password)

2. **AI Services**:
   - Google Gemini API Key

3. **Video Platforms** (at least one):
   - Google Meet (Client ID, Secret)
   - Microsoft Teams (Client ID, Secret, Tenant ID)
   - Zoom (Client ID, Secret)

4. **Optional Services**:
   - Email SMTP server
   - Sentry for error tracking
   - n8n for workflow automation

## Environment Configuration

### 1. Copy Environment Template

```bash
cp .env.example .env
```

### 2. Configure Environment Variables

Edit the `.env` file with your actual values:

```bash
# Django Configuration
SECRET_KEY=your-production-secret-key-here
DEBUG=0  # Set to 0 for production
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
POSTGRES_DB=intelligent_meeting_workflow
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-secure-password

# CRM Integrations
SALESFORCE_CLIENT_ID=your-salesforce-client-id
SALESFORCE_CLIENT_SECRET=your-salesforce-client-secret
SALESFORCE_USERNAME=your-salesforce-username
SALESFORCE_PASSWORD=your-salesforce-password

HUBSPOT_API_KEY=your-hubspot-api-key

CREATIO_API_URL=https://your-creatio-instance.com
CREATIO_USERNAME=your-creatio-username
CREATIO_PASSWORD=your-creatio-password

# AI Services
GEMINI_API_KEY=your-gemini-api-key

# Video Platforms
GOOGLE_MEET_CLIENT_ID=your-google-meet-client-id
GOOGLE_MEET_CLIENT_SECRET=your-google-meet-client-secret

TEAMS_CLIENT_ID=your-teams-client-id
TEAMS_CLIENT_SECRET=your-teams-client-secret
TEAMS_TENANT_ID=your-teams-tenant-id

ZOOM_CLIENT_ID=your-zoom-client-id
ZOOM_CLIENT_SECRET=your-zoom-client-secret
```

## Deployment Methods

### Method 1: Automated Deployment Script (Recommended)

#### Linux/macOS:
```bash
# Make script executable
chmod +x scripts/deploy.sh

# Deploy to development
./scripts/deploy.sh development

# Deploy to staging
./scripts/deploy.sh staging

# Deploy to production
./scripts/deploy.sh production
```

#### Windows (PowerShell):
```powershell
# Deploy to development
.\scripts\deploy.ps1 development

# Deploy to staging
.\scripts\deploy.ps1 staging

# Deploy to production
.\scripts\deploy.ps1 production
```

### Method 2: Manual Docker Compose

#### Development Environment:
```bash
# Build and start services
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser (optional)
docker-compose exec web python manage.py createsuperuser
```

#### Staging Environment:
```bash
# Build and start services
docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d

# Run migrations
docker-compose -f docker-compose.yml -f docker-compose.staging.yml exec web python manage.py migrate

# Collect static files
docker-compose -f docker-compose.yml -f docker-compose.staging.yml exec web python manage.py collectstatic --noinput
```

#### Production Environment:
```bash
# Build and start services
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Run migrations
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py migrate

# Collect static files
docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

## Environment-Specific Deployments

### Development Environment

**Purpose**: Local development and testing

**Configuration**:
- DEBUG=1
- Single worker processes
- Hot reloading enabled
- All logs visible
- No SSL/HTTPS

**Access**:
- Application: http://localhost:8000
- Admin: http://localhost:8000/admin/
- n8n: http://localhost:5678 (if enabled)

### Staging Environment

**Purpose**: Pre-production testing and validation

**Configuration**:
- DEBUG=0
- Production-like settings
- Reduced worker processes
- SSL optional
- Detailed logging

**Features**:
- Nginx reverse proxy
- Production Docker images
- Database optimizations
- n8n workflows enabled

### Production Environment

**Purpose**: Live production system

**Configuration**:
- DEBUG=0
- Optimized worker processes
- SSL/HTTPS required
- Error logging only
- Security headers enabled

**Features**:
- Nginx with SSL termination
- Database connection pooling
- Redis persistence
- Automated backups
- Health checks
- Monitoring (optional)

## Health Checks and Monitoring

### Health Check Endpoints

- **Basic Health**: `GET /api/health/`
- **Detailed Health**: `GET /api/health/detailed/`
- **Readiness Check**: `GET /api/readiness/`
- **Liveness Check**: `GET /api/liveness/`

### Monitoring Script

```bash
# Check system status
./scripts/monitoring.sh status

# View logs
./scripts/monitoring.sh logs web 100

# Show metrics
./scripts/monitoring.sh metrics

# Comprehensive health check
./scripts/monitoring.sh health

# Restart services
./scripts/monitoring.sh restart web
```

### Docker Health Checks

All services include built-in health checks:

```bash
# Check container health
docker-compose ps

# View health check logs
docker inspect <container_name> | grep -A 10 Health
```

## Rollback Procedures

### Automated Rollback

#### Linux/macOS:
```bash
# Rollback production with database restore
./scripts/rollback.sh production /path/to/backup.sql

# Rollback staging
./scripts/rollback.sh staging
```

#### Windows (PowerShell):
```powershell
# Manual rollback steps
docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
# Restore database from backup
# Restart services
```

### Manual Rollback Steps

1. **Stop Current Services**:
   ```bash
   docker-compose down
   ```

2. **Restore Database** (if needed):
   ```bash
   docker-compose up -d db
   docker-compose exec -T db psql -U postgres -d intelligent_meeting_workflow < backup.sql
   ```

3. **Start Previous Version**:
   ```bash
   docker-compose up -d
   ```

## SSL/HTTPS Configuration

### Production SSL Setup

1. **Obtain SSL Certificates**:
   - Use Let's Encrypt with Certbot
   - Or upload your own certificates to `docker/nginx/ssl/`

2. **Update Nginx Configuration**:
   - Uncomment HTTPS server block in `docker/nginx/default.conf`
   - Update certificate paths

3. **Update Environment Variables**:
   ```bash
   SECURE_SSL_REDIRECT=1
   SECURE_HSTS_SECONDS=31536000
   SESSION_COOKIE_SECURE=1
   CSRF_COOKIE_SECURE=1
   ```

### Let's Encrypt Setup

```bash
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## Database Management

### Backup Creation

```bash
# Automated backup
./scripts/monitoring.sh backup

# Manual backup
docker-compose exec -T db pg_dump -U postgres intelligent_meeting_workflow > backup.sql
```

### Database Restore

```bash
# Stop services
docker-compose down

# Start only database
docker-compose up -d db

# Restore from backup
docker-compose exec -T db psql -U postgres -d intelligent_meeting_workflow < backup.sql

# Start all services
docker-compose up -d
```

### Database Migrations

```bash
# Create new migration
docker-compose exec web python manage.py makemigrations

# Apply migrations
docker-compose exec web python manage.py migrate

# Show migration status
docker-compose exec web python manage.py showmigrations
```

## Performance Optimization

### Production Optimizations

1. **Database Tuning**:
   - Connection pooling enabled
   - Optimized PostgreSQL settings
   - Regular VACUUM and ANALYZE

2. **Caching**:
   - Redis for session storage
   - Application-level caching
   - Static file caching

3. **Web Server**:
   - Gunicorn with gevent workers
   - Nginx reverse proxy
   - Static file serving

4. **Monitoring**:
   - Health check endpoints
   - Application metrics
   - Error tracking

### Scaling Considerations

- **Horizontal Scaling**: Use Docker Swarm or Kubernetes
- **Database Scaling**: Read replicas, connection pooling
- **Cache Scaling**: Redis Cluster
- **Load Balancing**: Multiple Nginx instances

## Troubleshooting

### Common Issues

#### 1. Services Won't Start

```bash
# Check logs
docker-compose logs web

# Check container status
docker-compose ps

# Restart specific service
docker-compose restart web
```

#### 2. Database Connection Issues

```bash
# Check database logs
docker-compose logs db

# Test database connection
docker-compose exec web python manage.py dbshell

# Reset database (development only)
docker-compose down -v
docker-compose up -d
```

#### 3. Permission Issues

```bash
# Fix file permissions
sudo chown -R $USER:$USER .

# Fix Docker socket permissions
sudo usermod -aG docker $USER
```

#### 4. Port Conflicts

```bash
# Check port usage
netstat -tlnp | grep :8000

# Change ports in .env file
WEB_PORT=8001
POSTGRES_PORT=5433
```

### Log Analysis

```bash
# View all logs
docker-compose logs

# Follow logs in real-time
docker-compose logs -f web

# View specific service logs
docker-compose logs celery

# Filter logs by time
docker-compose logs --since="2024-01-01T00:00:00"
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Monitor database performance
docker-compose exec db psql -U postgres -d intelligent_meeting_workflow -c "SELECT * FROM pg_stat_activity;"

# Check Redis memory usage
docker-compose exec redis redis-cli info memory
```

## Security Considerations

### Production Security Checklist

- [ ] Change default passwords
- [ ] Use strong SECRET_KEY
- [ ] Enable HTTPS/SSL
- [ ] Configure CORS properly
- [ ] Set up firewall rules
- [ ] Regular security updates
- [ ] Monitor access logs
- [ ] Backup encryption
- [ ] API rate limiting
- [ ] Input validation

### Network Security

```bash
# Restrict database access
# In docker-compose.yml, remove ports mapping for db service

# Use Docker networks
docker network create intelligent_meeting_network
```

## Maintenance

### Regular Maintenance Tasks

1. **Daily**:
   - Monitor health checks
   - Review error logs
   - Check disk space

2. **Weekly**:
   - Database backups
   - Security updates
   - Performance review

3. **Monthly**:
   - Full system backup
   - Dependency updates
   - Security audit

### Update Procedures

```bash
# Update application code
git pull origin main

# Rebuild images
docker-compose build

# Apply migrations
docker-compose exec web python manage.py migrate

# Restart services
docker-compose restart
```

## Support and Documentation

- **Application Logs**: Check Docker container logs
- **Database Logs**: PostgreSQL logs in container
- **Web Server Logs**: Nginx access and error logs
- **Health Checks**: Use monitoring endpoints
- **Metrics**: Application and system metrics

For additional support, refer to the application documentation and health check endpoints.