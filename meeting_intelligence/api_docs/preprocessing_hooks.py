"""
DRF Spectacular preprocessing hooks for API documentation customization.
"""


def custom_preprocessing_hook(endpoints):
    """
    Custom preprocessing hook to modify API endpoints before schema generation.
    
    This hook can be used to:
    - Filter out internal endpoints
    - Add custom metadata to endpoints
    - Modify endpoint descriptions
    """
    filtered_endpoints = []
    
    for (path, path_regex, method, callback) in endpoints:
        # Skip internal admin endpoints from documentation
        if path.startswith('/admin/'):
            continue
            
        # Add custom metadata for meeting intelligence endpoints
        if 'meetings' in path:
            # Add meeting-specific metadata
            pass
        elif 'debriefings' in path:
            # Add debriefing-specific metadata
            pass
        elif 'leads' in path:
            # Add lead-specific metadata
            pass
        elif 'crm' in path:
            # Add CRM-specific metadata
            pass
        elif 'ai' in path:
            # Add AI-specific metadata
            pass
        elif 'analytics' in path:
            # Add analytics-specific metadata
            pass
            
        filtered_endpoints.append((path, path_regex, method, callback))
    
    return filtered_endpoints