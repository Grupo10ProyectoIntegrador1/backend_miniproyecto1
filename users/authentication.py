import jwt
import os
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import User


class SupabaseJWTAuthentication(BaseAuthentication):
    """ 
    Valida el JWT emitido por Supabase
    Extrae el UUID del token, busca el user_id entero en public.user
    y lo pone disponible en request.user
    """

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization', '')

        # Si no hay token, dejamos pasar(DRF maneja esos errores), depronto poner mensaje mas adelante
        if not auth_header.startswith('Bearer '):
            return None
        
        token = auth_header.split(' ')[1]
        secret = os.environ.get('SUPABASE_JWT_SECRET')

        if not secret:
            raise AuthenticationFailed('SUPABASE_JWT_SECRET no configurado.')
        
        #Verificamos y decodificamos el token
        try:
            payload = jwt.decode(
                token,
                secret,
                algorithms=['HS256'],
                audience='authenticated',
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token expirado.')
        except jwt.InvalidAudienceError:
            raise AuthenticationFailed('Audience inválido.')
        except jwt.InvalidTokenError as e:
            raise AuthenticationFailed(f'Token inválido: {str(e)}')
        
        #El uuid del usuario viene en el campo 'sub' del JWT
        uuid_user = payload.get('sub')
        if not uuid_user:
            raise AuthenticationFailed('Token sin UUID de usuario.')
        
        #Buscamos el usuario en public.user usando el UUID
        try:
            user = User.objects.get(uuid_user=uuid_user)
        except User.DoesNotExist:
            raise AuthenticationFailed('Usuario no encontrado.')
        
        return (user, token)