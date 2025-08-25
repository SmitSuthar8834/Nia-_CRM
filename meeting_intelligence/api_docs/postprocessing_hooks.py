"""
DRF Spectacular postprocessing hooks for API documentation customization.
"""


def custom_postprocessing_hook(result, generator, request, public):
    """
    Custom postprocessing hook to modify the generated OpenAPI schema.
    
    This hook can be used to:
    - Add custom security schemes
    - Modify response examples
    - Add additional documentation
    """
    # Add custom security schemes
    if 'components' not in result:
        result['components'] = {}
    
    if 'securitySchemes' not in result['components']:
        result['components']['securitySchemes'] = {}
    
    # Add JWT Bearer authentication scheme
    result['components']['securitySchemes']['JWTAuth'] = {
        'type': 'http',
        'scheme': 'bearer',
        'bearerFormat': 'JWT',
        'description': 'JWT token obtained from /api/v1/auth/login/ endpoint'
    }
    
    # Add Session authentication scheme
    result['components']['securitySchemes']['SessionAuth'] = {
        'type': 'apiKey',
        'in': 'cookie',
        'name': 'sessionid',
        'description': 'Django session authentication'
    }
    
    # Add global security requirements
    if 'security' not in result:
        result['security'] = []
    
    result['security'].extend([
        {'JWTAuth': []},
        {'SessionAuth': []}
    ])
    
    # Add custom examples for common responses
    if 'components' in result and 'schemas' in result['components']:
        # Add error response examples
        result['components']['schemas']['ValidationError'] = {
            'type': 'object',
            'properties': {
                'field_name': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'example': ['This field is required.']
                }
            },
            'example': {
                'email': ['This field is required.'],
                'password': ['This field may not be blank.']
            }
        }
        
        result['components']['schemas']['AuthenticationError'] = {
            'type': 'object',
            'properties': {
                'detail': {
                    'type': 'string',
                    'example': 'Authentication credentials were not provided.'
                }
            }
        }
        
        result['components']['schemas']['PermissionError'] = {
            'type': 'object',
            'properties': {
                'detail': {
                    'type': 'string',
                    'example': 'You do not have permission to perform this action.'
                }
            }
        }
    
    return result