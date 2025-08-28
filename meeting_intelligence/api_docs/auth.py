"""
Custom authentication classes for API documentation.
"""
from drf_spectacular.authentication import TokenScheme


class CustomJWTAuthentication(TokenScheme):
    """
    Custom JWT authentication scheme for API documentation.
    """
    target_component = 'JWTAuth'
    name = 'JWT Authentication'
    
    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
            'description': (
                'JWT token-based authentication. '
                'Obtain a token by making a POST request to /api/v1/auth/login/ '
                'with valid credentials. Include the token in the Authorization '
                'header as: Authorization: Bearer <token>'
            )
        }