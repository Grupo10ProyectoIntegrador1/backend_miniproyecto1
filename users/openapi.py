from drf_spectacular.extensions import OpenApiAuthenticationExtension

class SupabaseJWTAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = 'users.authentication.SupabaseJWTAuthentication'
    name = 'BearerAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT'
        }