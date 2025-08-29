# Project Cleanup Plan

## Files and Directories to Remove

### 1. Duplicate Django Project
```bash
rm -rf meeting_intelligence/
```

### 2. Unused Apps in apps/ Directory
```bash
rm -rf apps/analytics/
rm -rf apps/api_docs/
rm -rf apps/calendar_integration/
rm -rf apps/crm_sync/
rm -rf apps/debriefings/
rm -rf apps/leads/          # Duplicate of root leads/
rm -rf apps/meetings/       # Duplicate of root meetings/
rm -rf apps/ai_engine/      # Functionality covered by ai_assistant/
```

### 3. Cache and Log Files
```bash
rm -f django.log
find . -name "__pycache__" -type d -exec rm -rf {} +
rm -rf .pytest_cache/
```

### 4. Development Files
```bash
rm -f ADMIN_MANAGEMENT_README.md
```

## Core System Structure (Keep These)

### Essential Apps
- `apps/accounts/` - Authentication and user management (newly implemented)
- `leads/` - Lead management (root level)
- `meetings/` - Core meeting workflow functionality
- `ai_assistant/` - AI processing and summary generation

### Essential Infrastructure
- `intelligent_meeting_workflow/` - Main Django project
- `frontend/` - React validation dashboard
- `n8n_workflows/` - Automation workflows
- `docs/` - Project documentation
- `.kiro/` - Kiro IDE specifications

### Configuration Files
- `manage.py`, `requirements.txt`, `docker-compose.yml`, `Dockerfile`
- `.env.example`, `.gitignore`, `pytest.ini`
- `README.md`

## Updated INSTALLED_APPS

After cleanup, the INSTALLED_APPS should be:

```python
LOCAL_APPS = [
    'apps.accounts',    # Authentication and security
    'leads',           # Lead management
    'meetings',        # Core meeting workflow
    'ai_assistant',    # AI processing
]
```

## Benefits of Cleanup

1. **Reduced Complexity** - Eliminates duplicate and unused code
2. **Clearer Architecture** - Focuses on core meeting workflow functionality
3. **Easier Maintenance** - Fewer components to maintain and update
4. **Better Performance** - Smaller codebase, faster builds and deployments
5. **Reduced Confusion** - Clear separation between core and non-core functionality

## Verification Steps

After cleanup:
1. Run `python manage.py check` to ensure no broken imports
2. Run tests to verify core functionality still works
3. Update any documentation that references removed components
4. Update deployment scripts if they reference removed directories