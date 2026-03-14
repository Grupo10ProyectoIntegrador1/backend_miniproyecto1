from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema
import jwt
import os
from jwt import PyJWKClient

from .models import User, DailyCapacity
from .serializers import UserSerializer, DailyCapacitySerializer
from .authentication import SupabaseJWTAuthentication

@extend_schema(methods=['POST'], request=UserSerializer, responses=UserSerializer)
@api_view(['POST'])
@authentication_classes([SupabaseJWTAuthentication])
@permission_classes([AllowAny])
def register(request):
    """ 
    Crea el perfil del usuario en public.user despues de que Supabase Auth 
    confimo el email.
    El Jwt ya viene verificado, extraemos el uuid del token
    """

    #verificamos manualmente el jwt para obtener el uuid
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return Response({
            'status': 'error',
            'message': 'Token requerido.',
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    token = auth_header.split(' ')[1]
    supabase_url = os.environ.get('SUPABASE_URL')
    jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"

    try:
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=['ES256'],
            audience='authenticated',
            options={'verify_iat': False}
        )
    except Exception as e:
        return Response({
            'status': 'error',
            'message': f'Token inválido: {str(e)}',
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    uuid_user = payload.get('sub')

    # Verificamos si el usuario ya existe
    if User.objects.filter(uuid_user=uuid_user).exists():
        return Response({
            'status': 'error',
            'message': 'El usuario ya está registrado.',
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Creamos el perfil en public.user
    serializer = UserSerializer(data={**request.data, 'uuid_user': uuid_user})
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            'status': 'success',
            'message': 'Usuario registrado exitosamente.',
            'data': UserSerializer(user).data,
        }, status=status.HTTP_201_CREATED)

    return Response({
        'status': 'error',
        'message': 'Error de validación',
        'errors': serializer.errors,
    }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(methods=['GET'], responses=UserSerializer)
@api_view(['GET'])
@authentication_classes([SupabaseJWTAuthentication])
@permission_classes([IsAuthenticated])
def profile(request):
    """Retorna el perfil del usuario autenticado."""
    serializer = UserSerializer(request.user)
    return Response({
        'status': 'success',
        'data': serializer.data,
    }, status=status.HTTP_200_OK)


@extend_schema(methods=['GET'], responses=DailyCapacitySerializer)
@extend_schema(methods=['PUT', 'PATCH'], request=DailyCapacitySerializer, responses=DailyCapacitySerializer)
@api_view(['GET', 'PUT', 'PATCH'])
@authentication_classes([SupabaseJWTAuthentication])
@permission_classes([IsAuthenticated])
def daily_capacity_view(request):
    """
    GET: Obtener límite actual del usuario. Si no existe, devuelve el por defecto (6.0h).
    PUT/PATCH: Actualiza o guarda un nuevo valor de límite para el usuario.
    """
    try:
        capacity = DailyCapacity.objects.get(user=request.user)
    except DailyCapacity.DoesNotExist:
        capacity = None

    if request.method == 'GET':
        if capacity:
            serializer = DailyCapacitySerializer(capacity)
            return Response({
                'status': 'success',
                'data': serializer.data,
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'status': 'success',
                'data': {
                    'daily_limit_hours': 6.0
                },
            }, status=status.HTTP_200_OK)

    elif request.method in ['PUT', 'PATCH']:
        serializer = DailyCapacitySerializer(
            capacity,
            data=request.data,
            partial=(request.method == 'PATCH'),
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response({
                'status': 'success',
                'message': 'Capacidad actualizada',
                'data': serializer.data,
            }, status=status.HTTP_200_OK)

        return Response({
            'status': 'error',
            'message': 'El límite debe estar entre 1 y 16 horas. Intenta de nuevo.',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
