# PowerShell deployment script for Intelligent Meeting Workflow
# Usage: .\scripts\deploy.ps1 [environment]
# Environments: development, staging, production

param(
    [Parameter(Position=0)]
    [ValidateSet("development", "staging", "production")]
    [string]$Environment = "development"
)

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Logging functions
function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Check prerequisites
function Test-Prerequisites {
    Write-Info "Checking prerequisites..."
    
    # Check Docker
    try {
        docker --version | Out-Null
        docker info | Out-Null
        Write-Success "Docker is available and running"
    }
    catch {
        Write-Error "Docker is not available or not running"
        exit 1
    }
    
    # Check Docker Compose
    try {
        docker-compose --version | Out-Null
        Write-Success "Docker Compose is available"
    }
    catch {
        Write-Error "Docker Compose is not available"
        exit 1
    }
}

# Load environment configuration
function Initialize-Environment {
    Write-Info "Loading environment configuration..."
    
    Set-Location $ProjectRoot
    
    # Check for .env file
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Write-Warning ".env file not found, copying from .env.example"
            Copy-Item ".env.example" ".env"
            Write-Warning "Please update .env file with your actual configuration"
        }
        else {
            Write-Error ".env.example file not found"
            exit 1
        }
    }
    
    # Set environment-specific variables
    switch ($Environment) {
        "development" {
            $env:DEBUG = "1"
            $env:BUILD_TARGET = "development"
        }
        "staging" {
            $env:DEBUG = "0"
            $env:BUILD_TARGET = "production"
            $env:DJANGO_SETTINGS_MODULE = "intelligent_meeting_workflow.settings.staging"
        }
        "production" {
            $env:DEBUG = "0"
            $env:BUILD_TARGET = "production"
            $env:DJANGO_SETTINGS_MODULE = "intelligent_meeting_workflow.settings.production"
        }
    }
    
    Write-Success "Environment configuration loaded"
}

# Build Docker images
function Build-Images {
    Write-Info "Building Docker images..."
    
    Set-Location $ProjectRoot
    
    switch ($Environment) {
        "development" {
            docker-compose build
        }
        "staging" {
            docker-compose -f docker-compose.yml -f docker-compose.staging.yml build
        }
        "production" {
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
        }
    }
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Docker build failed"
        exit 1
    }
    
    Write-Success "Docker images built successfully"
}

# Run database migrations
function Invoke-Migrations {
    Write-Info "Running database migrations..."
    
    Set-Location $ProjectRoot
    
    switch ($Environment) {
        "development" {
            docker-compose run --rm web python manage.py migrate
        }
        "staging" {
            docker-compose -f docker-compose.yml -f docker-compose.staging.yml run --rm web python manage.py migrate
        }
        "production" {
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml run --rm web python manage.py migrate
        }
    }
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Database migrations failed"
        exit 1
    }
    
    Write-Success "Database migrations completed"
}

# Collect static files
function Invoke-CollectStatic {
    if ($Environment -ne "development") {
        Write-Info "Collecting static files..."
        
        Set-Location $ProjectRoot
        
        switch ($Environment) {
            "staging" {
                docker-compose -f docker-compose.yml -f docker-compose.staging.yml run --rm web python manage.py collectstatic --noinput
            }
            "production" {
                docker-compose -f docker-compose.yml -f docker-compose.prod.yml run --rm web python manage.py collectstatic --noinput
            }
        }
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Static file collection failed"
            exit 1
        }
        
        Write-Success "Static files collected"
    }
}

# Start services
function Start-Services {
    Write-Info "Starting services..."
    
    Set-Location $ProjectRoot
    
    switch ($Environment) {
        "development" {
            docker-compose up -d
        }
        "staging" {
            docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d
        }
        "production" {
            docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
        }
    }
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to start services"
        exit 1
    }
    
    Write-Success "Services started successfully"
}

# Wait for services to be ready
function Wait-ForServices {
    Write-Info "Waiting for services to be ready..."
    
    $maxAttempts = 30
    $attempt = 1
    $webPort = if ($env:WEB_PORT) { $env:WEB_PORT } else { "8000" }
    
    while ($attempt -le $maxAttempts) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$webPort/api/health/" -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                Write-Success "Web service is ready"
                return
            }
        }
        catch {
            # Service not ready yet
        }
        
        if ($attempt -eq $maxAttempts) {
            Write-Error "Web service failed to start within expected time"
            exit 1
        }
        
        Write-Info "Attempt $attempt/$maxAttempts - waiting for web service..."
        Start-Sleep -Seconds 10
        $attempt++
    }
}

# Run health checks
function Test-Health {
    Write-Info "Running health checks..."
    
    $webPort = if ($env:WEB_PORT) { $env:WEB_PORT } else { "8000" }
    
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$webPort/api/health/" -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Success "Basic health check passed"
        }
        else {
            Write-Error "Basic health check failed"
            exit 1
        }
    }
    catch {
        Write-Error "Basic health check failed: $($_.Exception.Message)"
        exit 1
    }
    
    # Detailed health check
    try {
        $detailedResponse = Invoke-WebRequest -Uri "http://localhost:$webPort/api/health/detailed/" -UseBasicParsing
        $healthData = $detailedResponse.Content | ConvertFrom-Json
        
        if ($healthData.status -eq "healthy") {
            Write-Success "Detailed health check passed"
        }
        else {
            Write-Warning "Detailed health check shows issues: $($healthData.status)"
            Write-Host $detailedResponse.Content
        }
    }
    catch {
        Write-Warning "Could not retrieve detailed health status"
    }
}

# Create backup (for production)
function New-Backup {
    if ($Environment -eq "production") {
        Write-Info "Creating database backup..."
        
        $backupDir = Join-Path $ProjectRoot "backups"
        $backupFile = Join-Path $backupDir "backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"
        
        if (-not (Test-Path $backupDir)) {
            New-Item -ItemType Directory -Path $backupDir | Out-Null
        }
        
        Set-Location $ProjectRoot
        
        $postgresUser = if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { "postgres" }
        $postgresDb = if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { "intelligent_meeting_workflow" }
        
        docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db pg_dump -U $postgresUser $postgresDb | Out-File -FilePath $backupFile -Encoding UTF8
        
        if ((Test-Path $backupFile) -and ((Get-Item $backupFile).Length -gt 0)) {
            Write-Success "Database backup created: $backupFile"
        }
        else {
            Write-Error "Database backup failed"
            exit 1
        }
    }
}

# Cleanup function
function Invoke-Cleanup {
    Write-Info "Cleaning up..."
    
    # Remove unused Docker images
    docker image prune -f | Out-Null
    
    # Remove unused volumes (be careful in production)
    if ($Environment -eq "development") {
        docker volume prune -f | Out-Null
    }
    
    Write-Success "Cleanup completed"
}

# Main deployment function
function Start-Deployment {
    Write-Info "Starting deployment of Intelligent Meeting Workflow"
    Write-Info "Environment: $Environment"
    Write-Info "Timestamp: $(Get-Date)"
    
    try {
        Test-Prerequisites
        Initialize-Environment
        
        # Create backup before production deployment
        if ($Environment -eq "production") {
            New-Backup
        }
        
        Build-Images
        Invoke-Migrations
        Invoke-CollectStatic
        Start-Services
        Wait-ForServices
        Test-Health
        
        # Cleanup old resources
        Invoke-Cleanup
        
        Write-Success "Deployment completed successfully!"
        
        $webPort = if ($env:WEB_PORT) { $env:WEB_PORT } else { "8000" }
        Write-Info "Application is available at: http://localhost:$webPort"
        
        if ($Environment -ne "development") {
            Write-Info "Admin interface: http://localhost:$webPort/admin/"
            Write-Info "Health check: http://localhost:$webPort/api/health/"
        }
        
        # Show running services
        Write-Info "Running services:"
        Set-Location $ProjectRoot
        switch ($Environment) {
            "development" {
                docker-compose ps
            }
            "staging" {
                docker-compose -f docker-compose.yml -f docker-compose.staging.yml ps
            }
            "production" {
                docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps
            }
        }
    }
    catch {
        Write-Error "Deployment failed: $($_.Exception.Message)"
        
        # Rollback on failure
        Write-Warning "Rolling back deployment..."
        Set-Location $ProjectRoot
        switch ($Environment) {
            "development" {
                docker-compose down
            }
            "staging" {
                docker-compose -f docker-compose.yml -f docker-compose.staging.yml down
            }
            "production" {
                docker-compose -f docker-compose.yml -f docker-compose.prod.yml down
            }
        }
        exit 1
    }
}

# Run deployment
Start-Deployment