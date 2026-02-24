from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import transaction

from .models import Activity
from .serializers import ActivitySerializer, SubtaskSerializer


@api_view(['GET', 'POST'])
def activity_list_create(request):
    """
    GET  /api/activities/ — Lista todas las actividades con sus subtareas.
    POST /api/activities/ — Crea una actividad con subtareas anidadas.
    """
    if request.method == 'GET':
        activities = Activity.objects.prefetch_related('subtasks').all()
        serializer = ActivitySerializer(activities, many=True)
        return Response({
            'status': 'success',
            'data': serializer.data,
        }, status=status.HTTP_200_OK)

    # POST
    serializer = ActivitySerializer(data=request.data)
    if serializer.is_valid():
        with transaction.atomic():
            activity = serializer.save()
        return Response({
            'status': 'success',
            'message': 'Actividad creada exitosamente',
            'data': ActivitySerializer(activity).data,
        }, status=status.HTTP_201_CREATED)

    return Response({
        'status': 'error',
        'message': 'Error de validación',
        'errors': serializer.errors,
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def activity_detail(request, pk):
    """
    GET /api/activities/<uuid:pk>/ — Detalle de una actividad con subtareas.
    """
    try:
        activity = Activity.objects.prefetch_related('subtasks').get(pk=pk)
    except Activity.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Actividad no encontrada',
        }, status=status.HTTP_404_NOT_FOUND)

    serializer = ActivitySerializer(activity)
    return Response({
        'status': 'success',
        'data': serializer.data,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def subtask_create(request, activity_id):
    """
    POST /api/activities/<uuid:activity_id>/subtasks/ — Crea una subtarea para una actividad.
    """
    try:
        activity = Activity.objects.get(pk=activity_id)
    except Activity.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Actividad no encontrada',
        }, status=status.HTTP_404_NOT_FOUND)

    serializer = SubtaskSerializer(data=request.data)
    if serializer.is_valid():
        try:
            serializer.save(activity=activity)
            return Response({
                'status': 'success',
                'message': 'Subtarea creada exitosamente',
                'data': serializer.data,
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({
                'status': 'error',
                'message': 'No se pudo guardar la subtarea',
                'details': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        'status': 'error',
        'message': 'Error de validación',
        'errors': serializer.errors,
    }, status=status.HTTP_400_BAD_REQUEST)
