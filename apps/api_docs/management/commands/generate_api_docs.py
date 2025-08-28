"""
Management command to generate comprehensive API documentation
"""
import json
import yaml
from django.core.management.base import BaseCommand
from django.conf import settings
from django.urls import reverse
from django.test import RequestFactory
from rest_framework.test import APIClient
from rest_framework import status


class Command(BaseCommand):
    help = 'Generate comprehensive API documentation'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'yaml'],
            default='yaml',
            help='Output format for the schema'
        )
        parser.add_argument(
            '--output',
            type=str,
            default='docs/api/openapi-schema.yaml',
            help='Output file path'
        )
        parser.add_argument(
            '--include-examples',
            action='store_true',
            help='Include request/response examples'
        )
    
    def handle(self, *args, **options):
        self.stdout.write('Generating API documentation...')
        
        try:
            # Generate OpenAPI schema
            schema = self.generate_openapi_schema()
            
            if options['include_examples']:
                schema = self.add_examples_to_schema(schema)
            
            # Write to file
            output_file = options['output']
            if options['format'] == 'json':
                with open(output_file, 'w') as f:
                    json.dump(schema, f, indent=2)
            else:
                with open(output_file, 'w') as f:
                    yaml.dump(schema, f, default_flow_style=False, indent=2)
            
            self.stdout.write(
                self.style.SUCCESS(f'API documentation generated: {output_file}')
            )
            
            # Generate additional documentation files
            self.generate_postman_collection()
            self.generate_client_examples()
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error generating documentation: {str(e)}')
            )
    
    def generate_openapi_schema(self):
        """Generate OpenAPI schema"""
        # Basic OpenAPI schema structure
        schema = {
            'openapi': '3.0.3',
            'info': {
                'title': 'NIA Meeting Intelligence API',
                'version': '1.0.0',
                'description': '''
                Comprehensive API for the NIA (AI Assistant) CRM Meeting Intelligence system.
                
                This API provides endpoints for:
                - Meeting detection and intelligence
                - Automated debriefing sessions
                - Lead management and participant matching
                - CRM synchronization with Creatio
                - AI-powered conversation analysis
                - Analytics and reporting
                
                ## Authentication
                
                The API supports two authentication methods:
                1. **JWT Token Authentication** (Recommended)
                2. **Session Authentication**
                
                ## Rate Limiting
                
                - Authenticated users: 1000 requests per hour
                - Anonymous users: 100 requests per hour
                
                ## Versioning
                
                The API uses URL-based versioning (e.g., `/api/v1/`).
                Current stable version: v1
                ''',
                'contact': {
                    'name': 'NIA Development Team',
                    'email': 'api-support@nia-intelligence.com',
                    'url': 'https://docs.nia-intelligence.com'
                },
                'license': {
                    'name': 'Proprietary License',
                    'url': 'https://nia-intelligence.com/license'
                }
            },
            'servers': [
                {
                    'url': 'http://localhost:8000/api/v1',
                    'description': 'Development server'
                },
                {
                    'url': 'https://api.nia-intelligence.com/api/v1',
                    'description': 'Production server'
                }
            ],
            'paths': {},
            'components': {
                'securitySchemes': {
                    'JWTAuth': {
                        'type': 'http',
                        'scheme': 'bearer',
                        'bearerFormat': 'JWT',
                        'description': 'JWT token obtained from /auth/login/ endpoint'
                    },
                    'SessionAuth': {
                        'type': 'apiKey',
                        'in': 'cookie',
                        'name': 'sessionid',
                        'description': 'Django session authentication'
                    }
                },
                'schemas': self.get_common_schemas()
            },
            'security': [
                {'JWTAuth': []},
                {'SessionAuth': []}
            ],
            'tags': [
                {
                    'name': 'Authentication',
                    'description': 'User authentication and authorization'
                },
                {
                    'name': 'Meetings',
                    'description': 'Meeting detection, management, and intelligence'
                },
                {
                    'name': 'Debriefings',
                    'description': 'Automated debriefing session management'
                },
                {
                    'name': 'Leads',
                    'description': 'Lead management and participant matching'
                },
                {
                    'name': 'Calendar Integration',
                    'description': 'Calendar system integration and synchronization'
                },
                {
                    'name': 'CRM Sync',
                    'description': 'Creatio CRM synchronization and data management'
                },
                {
                    'name': 'AI Engine',
                    'description': 'AI-powered conversation and data extraction'
                },
                {
                    'name': 'Analytics',
                    'description': 'Performance metrics, reporting, and analytics'
                }
            ]
        }
        
        # Add paths for each endpoint
        schema['paths'] = self.generate_api_paths()
        
        return schema
    
    def get_common_schemas(self):
        """Get common schema definitions"""
        return {
            'ValidationError': {
                'type': 'object',
                'properties': {
                    'field_name': {
                        'type': 'array',
                        'items': {'type': 'string'},
                        'example': ['This field is required.']
                    }
                },
                'example': {
                    'email': ['Enter a valid email address.'],
                    'password': ['This field may not be blank.']
                }
            },
            'AuthenticationError': {
                'type': 'object',
                'properties': {
                    'detail': {
                        'type': 'string',
                        'example': 'Authentication credentials were not provided.'
                    }
                }
            },
            'PermissionError': {
                'type': 'object',
                'properties': {
                    'detail': {
                        'type': 'string',
                        'example': 'You do not have permission to perform this action.'
                    }
                }
            },
            'Meeting': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer', 'example': 123},
                    'title': {'type': 'string', 'example': 'Product Demo - Acme Corp'},
                    'start_time': {'type': 'string', 'format': 'date-time'},
                    'end_time': {'type': 'string', 'format': 'date-time'},
                    'meeting_type': {
                        'type': 'string',
                        'enum': ['discovery', 'demo', 'negotiation', 'follow_up', 'internal', 'competitive', 'closing'],
                        'example': 'demo'
                    },
                    'is_sales_meeting': {'type': 'boolean', 'example': True},
                    'confidence_score': {'type': 'number', 'format': 'float', 'example': 0.95},
                    'debriefing_scheduled': {'type': 'boolean', 'example': True},
                    'debriefing_completed': {'type': 'boolean', 'example': False},
                    'participant_count': {'type': 'integer', 'example': 3},
                    'organizer': {'type': 'integer', 'example': 1}
                }
            },
            'Lead': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer', 'example': 456},
                    'first_name': {'type': 'string', 'example': 'John'},
                    'last_name': {'type': 'string', 'example': 'Doe'},
                    'email': {'type': 'string', 'format': 'email', 'example': 'john.doe@example.com'},
                    'phone': {'type': 'string', 'example': '+1-555-123-4567'},
                    'company': {'type': 'string', 'example': 'Acme Corp'},
                    'title': {'type': 'string', 'example': 'VP of Sales'},
                    'status': {
                        'type': 'string',
                        'enum': ['new', 'qualified', 'contacted', 'opportunity', 'proposal', 'negotiation', 'closed_won', 'closed_lost'],
                        'example': 'qualified'
                    },
                    'qualification_score': {'type': 'integer', 'example': 85},
                    'source': {'type': 'string', 'example': 'meeting'}
                }
            },
            'DebriefingSession': {
                'type': 'object',
                'properties': {
                    'id': {'type': 'integer', 'example': 789},
                    'meeting': {'type': 'integer', 'example': 123},
                    'scheduled_time': {'type': 'string', 'format': 'date-time'},
                    'status': {
                        'type': 'string',
                        'enum': ['scheduled', 'in_progress', 'completed', 'skipped', 'expired'],
                        'example': 'completed'
                    },
                    'conversation_data': {'type': 'object'},
                    'extracted_data': {'type': 'object'},
                    'user_approved': {'type': 'boolean', 'example': True}
                }
            }
        }
    
    def generate_api_paths(self):
        """Generate API paths documentation"""
        paths = {}
        
        # Authentication endpoints
        paths['/auth/login/'] = {
            'post': {
                'tags': ['Authentication'],
                'summary': 'User Login',
                'description': 'Authenticate user and return JWT tokens',
                'requestBody': {
                    'required': True,
                    'content': {
                        'application/json': {
                            'schema': {
                                'type': 'object',
                                'properties': {
                                    'username': {'type': 'string'},
                                    'password': {'type': 'string'},
                                    'totp_token': {'type': 'string', 'description': 'Optional 2FA token'}
                                },
                                'required': ['username', 'password']
                            }
                        }
                    }
                },
                'responses': {
                    '200': {
                        'description': 'Login successful',
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'object',
                                    'properties': {
                                        'access_token': {'type': 'string'},
                                        'refresh_token': {'type': 'string'},
                                        'user': {'type': 'object'}
                                    }
                                }
                            }
                        }
                    },
                    '401': {
                        'description': 'Authentication failed',
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/AuthenticationError'}
                            }
                        }
                    }
                }
            }
        }
        
        # Meeting endpoints
        paths['/meetings/'] = {
            'get': {
                'tags': ['Meetings'],
                'summary': 'List Meetings',
                'description': 'Retrieve a paginated list of meetings',
                'parameters': [
                    {
                        'name': 'meeting_type',
                        'in': 'query',
                        'schema': {
                            'type': 'string',
                            'enum': ['discovery', 'demo', 'negotiation', 'follow_up', 'internal', 'competitive', 'closing']
                        }
                    },
                    {
                        'name': 'is_sales_meeting',
                        'in': 'query',
                        'schema': {'type': 'boolean'}
                    },
                    {
                        'name': 'search',
                        'in': 'query',
                        'schema': {'type': 'string'}
                    }
                ],
                'responses': {
                    '200': {
                        'description': 'List of meetings',
                        'content': {
                            'application/json': {
                                'schema': {
                                    'type': 'object',
                                    'properties': {
                                        'count': {'type': 'integer'},
                                        'next': {'type': 'string', 'nullable': True},
                                        'previous': {'type': 'string', 'nullable': True},
                                        'results': {
                                            'type': 'array',
                                            'items': {'$ref': '#/components/schemas/Meeting'}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            'post': {
                'tags': ['Meetings'],
                'summary': 'Create Meeting',
                'description': 'Create a new meeting record',
                'requestBody': {
                    'required': True,
                    'content': {
                        'application/json': {
                            'schema': {'$ref': '#/components/schemas/Meeting'}
                        }
                    }
                },
                'responses': {
                    '201': {
                        'description': 'Meeting created',
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/Meeting'}
                            }
                        }
                    },
                    '400': {
                        'description': 'Validation error',
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/ValidationError'}
                            }
                        }
                    }
                }
            }
        }
        
        # Add more endpoints...
        paths['/meetings/{id}/'] = {
            'get': {
                'tags': ['Meetings'],
                'summary': 'Get Meeting Details',
                'parameters': [
                    {
                        'name': 'id',
                        'in': 'path',
                        'required': True,
                        'schema': {'type': 'integer'}
                    }
                ],
                'responses': {
                    '200': {
                        'description': 'Meeting details',
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/Meeting'}
                            }
                        }
                    },
                    '404': {
                        'description': 'Meeting not found'
                    }
                }
            }
        }
        
        return paths
    
    def add_examples_to_schema(self, schema):
        """Add request/response examples to schema"""
        # Add examples to existing paths
        for path, methods in schema['paths'].items():
            for method, spec in methods.items():
                if 'requestBody' in spec:
                    # Add request examples
                    pass
                if 'responses' in spec:
                    # Add response examples
                    pass
        
        return schema
    
    def generate_postman_collection(self):
        """Generate Postman collection"""
        collection = {
            'info': {
                'name': 'NIA Meeting Intelligence API',
                'description': 'Comprehensive API collection for NIA Meeting Intelligence',
                'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json'
            },
            'auth': {
                'type': 'bearer',
                'bearer': [
                    {
                        'key': 'token',
                        'value': '{{access_token}}',
                        'type': 'string'
                    }
                ]
            },
            'variable': [
                {
                    'key': 'base_url',
                    'value': 'http://localhost:8000/api/v1',
                    'type': 'string'
                },
                {
                    'key': 'access_token',
                    'value': '',
                    'type': 'string'
                }
            ],
            'item': [
                {
                    'name': 'Authentication',
                    'item': [
                        {
                            'name': 'Login',
                            'request': {
                                'method': 'POST',
                                'header': [
                                    {
                                        'key': 'Content-Type',
                                        'value': 'application/json'
                                    }
                                ],
                                'body': {
                                    'mode': 'raw',
                                    'raw': json.dumps({
                                        'username': 'your-username',
                                        'password': 'your-password'
                                    }, indent=2)
                                },
                                'url': {
                                    'raw': '{{base_url}}/auth/login/',
                                    'host': ['{{base_url}}'],
                                    'path': ['auth', 'login', '']
                                }
                            }
                        }
                    ]
                },
                {
                    'name': 'Meetings',
                    'item': [
                        {
                            'name': 'List Meetings',
                            'request': {
                                'method': 'GET',
                                'url': {
                                    'raw': '{{base_url}}/meetings/',
                                    'host': ['{{base_url}}'],
                                    'path': ['meetings', '']
                                }
                            }
                        },
                        {
                            'name': 'Create Meeting',
                            'request': {
                                'method': 'POST',
                                'header': [
                                    {
                                        'key': 'Content-Type',
                                        'value': 'application/json'
                                    }
                                ],
                                'body': {
                                    'mode': 'raw',
                                    'raw': json.dumps({
                                        'title': 'Product Demo - Acme Corp',
                                        'start_time': '2024-02-15T14:00:00Z',
                                        'end_time': '2024-02-15T15:00:00Z',
                                        'meeting_type': 'demo'
                                    }, indent=2)
                                },
                                'url': {
                                    'raw': '{{base_url}}/meetings/',
                                    'host': ['{{base_url}}'],
                                    'path': ['meetings', '']
                                }
                            }
                        }
                    ]
                }
            ]
        }
        
        with open('docs/api/postman_collection.json', 'w') as f:
            json.dump(collection, f, indent=2)
        
        self.stdout.write('Generated Postman collection: docs/api/postman_collection.json')
    
    def generate_client_examples(self):
        """Generate client library examples"""
        # Python client example
        python_client = '''
"""
NIA Meeting Intelligence API Python Client
"""
import requests
from typing import Dict, List, Optional

class NIAClient:
    def __init__(self, base_url: str, username: str = None, password: str = None, access_token: str = None):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.access_token = access_token
        
        if access_token:
            self.session.headers.update({'Authorization': f'Bearer {access_token}'})
        elif username and password:
            self.login(username, password)
    
    def login(self, username: str, password: str, totp_token: str = None) -> Dict:
        """Login and get access token"""
        data = {'username': username, 'password': password}
        if totp_token:
            data['totp_token'] = totp_token
        
        response = self.session.post(f'{self.base_url}/api/v1/auth/login/', json=data)
        response.raise_for_status()
        
        result = response.json()
        self.access_token = result['access_token']
        self.session.headers.update({'Authorization': f'Bearer {self.access_token}'})
        
        return result
    
    def list_meetings(self, **filters) -> Dict:
        """List meetings with optional filters"""
        response = self.session.get(f'{self.base_url}/api/v1/meetings/', params=filters)
        response.raise_for_status()
        return response.json()
    
    def create_meeting(self, meeting_data: Dict) -> Dict:
        """Create new meeting"""
        response = self.session.post(f'{self.base_url}/api/v1/meetings/', json=meeting_data)
        response.raise_for_status()
        return response.json()
    
    def get_meeting(self, meeting_id: int) -> Dict:
        """Get meeting details"""
        response = self.session.get(f'{self.base_url}/api/v1/meetings/{meeting_id}/')
        response.raise_for_status()
        return response.json()

# Usage example
if __name__ == '__main__':
    client = NIAClient(
        base_url='http://localhost:8000',
        username='your-username',
        password='your-password'
    )
    
    # List meetings
    meetings = client.list_meetings(meeting_type='discovery')
    print(f"Found {meetings['count']} meetings")
    
    # Create meeting
    new_meeting = client.create_meeting({
        'title': 'Product Demo - Acme Corp',
        'start_time': '2024-02-15T14:00:00Z',
        'end_time': '2024-02-15T15:00:00Z',
        'meeting_type': 'demo'
    })
    print(f"Created meeting: {new_meeting['id']}")
'''
        
        with open('docs/api/python_client.py', 'w') as f:
            f.write(python_client)
        
        self.stdout.write('Generated Python client: docs/api/python_client.py')