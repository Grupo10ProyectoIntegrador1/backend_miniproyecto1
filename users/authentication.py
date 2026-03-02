import jwt
import os
import requests
from jwt import PyJWKClient
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import User


class SupabaseJWTAuthentication(BaseAuthentication):
    """ 
    Valida el JWT emitido por Supabase usando ES256
    Obtiene la clave publica desde el JWKS endpoint de Supabase
    """

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization', '')

        # Si no hay token, dejamos pasar(DRF maneja esos errores), depronto poner mensaje mas adelante
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]

        supabase_url = os.environ.get('SUPABASE_URL')
        if not supabase_url:
            raise AuthenticationFailed('SUPABASE_URL no configurada.')
        
        #Supabase expone su clave publica aca
        jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"


        #Verificamos y decodificamos el token
        try:
            #PyJWKClient descarga y cachea la clave publica automatiocamente
            jwks_client = PyJWKClient(jwks_url)
            signing_key = jwks_client.get_signing_key_from_jwt(token)

            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=['ES256'],
                audience='authenticated',
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token expirado.')
        except jwt.InvalidAudienceError:
            raise AuthenticationFailed('Audience inválido.')
        except jwt.InvalidTokenError as e:
            raise AuthenticationFailed(f'Token inválido: {str(e)}')
        except Exception as e:
            raise AuthenticationFailed(f'Error de autenticación: {str(e)}')
    
        
        #El uuid del usuario viene en el campo 'sub' del JWT
        uuid_user = payload.get('sub')
        if not uuid_user:
            raise AuthenticationFailed('Token sin UUID de usuario.')
        
        #Buscamos el usuario en public.user usando el UUID
        try:
            user = User.objects.get(uuid_user=uuid_user)
        except User.DoesNotExist:
            return None
        
        return (user, token)