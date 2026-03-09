from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from datetime import date, timedelta

from .models import Activity, Subtask
from .serializers import ActivitySerializer, SubtaskSerializer, TodaySubtaskSerializer


@extend_schema(methods=['GET'], responses=ActivitySerializer(many=True))
@extend_schema(methods=['POST'], request=ActivitySerializer, responses=ActivitySerializer)
@api_view(['GET', 'POST'])
def activity_list_create(request):
    """
    GET  /api/activities/ — Lista todas las actividades con sus subtareas.
    POST /api/activities/ — Crea una actividad con subtareas anidadas.
    """
    if request.method == 'GET':
        activities = Activity.objects.prefetch_related('subtasks').filter(
            user_id=request.user.user_id
        )
        serializer = ActivitySerializer(activities, many=True)
        return Response({
            'status': 'success',
            'data': serializer.data,
        }, status=status.HTTP_200_OK)

    # POST
    # Request needed to get user_id in the serializer validate context
    serializer = ActivitySerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        with transaction.atomic():
            activity = serializer.save(user_id=request.user.user_id)
        return Response({
            'status': 'success',
            'message': 'Actividad creada exitosamente',
            'data': ActivitySerializer(activity).data,
        }, status=status.HTTP_201_CREATED)

    if 'overload_conflict' in serializer.errors:
        return Response(serializer.errors['overload_conflict'][0], status=status.HTTP_409_CONFLICT)

    return Response({
        'status': 'error',
        'message': 'Error de validación',
        'errors': serializer.errors,
    }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(methods=['GET'], responses=ActivitySerializer)
@extend_schema(methods=['PUT', 'PATCH'], request=ActivitySerializer, responses=ActivitySerializer)
@extend_schema(methods=['DELETE'], responses=None)
@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def activity_detail(request, pk):
    """
    GET    /api/activities/<int:pk>/ — Detalle de una actividad con subtareas.
    PUT    /api/activities/<int:pk>/ — Actualiza completamente una actividad.
    PATCH  /api/activities/<int:pk>/ — Actualiza parcialmente una actividad.
    DELETE /api/activities/<int:pk>/ — Elimina una actividad.
    """
    try:
        activity = Activity.objects.prefetch_related('subtasks').get(
            pk=pk,
            user_id=request.user.user_id
            )
    except Activity.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Actividad no encontrada',
        }, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = ActivitySerializer(activity)
        return Response({
            'status': 'success',
            'data': serializer.data,
        }, status=status.HTTP_200_OK)

    elif request.method in ['PUT', 'PATCH']:
        serializer = ActivitySerializer(
            activity,
            data=request.data,
            partial=(request.method == 'PATCH'),
        )
        if serializer.is_valid():
            serializer.save()
            return Response({
                'status': 'success',
                'message': 'Actividad actualizada exitosamente',
                'data': ActivitySerializer(activity).data,
            }, status=status.HTTP_200_OK)
        return Response({
            'status': 'error',
            'message': 'Error de validación',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        activity.delete()
        return Response({
            'status': 'success',
            'message': 'Actividad eliminada exitosamente',
        }, status=status.HTTP_204_NO_CONTENT)


@extend_schema(methods=['POST'], request=SubtaskSerializer, responses=SubtaskSerializer)
@api_view(['POST'])
def subtask_create(request, activity_id):
    """
    POST /api/activities/<uuid:activity_id>/subtasks/ — Crea una subtarea para una actividad.
    """
    try:
        activity = Activity.objects.get(
            pk=activity_id,
            user_id=request.user.user_id
        )
    except Activity.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Actividad no encontrada',
        }, status=status.HTTP_404_NOT_FOUND)

    serializer = SubtaskSerializer(data=request.data, context={'activity': activity})
    if serializer.is_valid():
        try:
            serializer.save(activity=activity)
            return Response({
                'status': 'success',
                'message': 'Subtarea creada exitosamente',
                'data': serializer.data,
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            # Registrar el error real en los logs del servidor
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error al crear subtarea: {str(e)}")
            
            return Response({
                'status': 'error',
                'message': 'No se pudo guardar la subtarea. Ocurrió un error inesperado en el servidor.',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if 'overload_conflict' in serializer.errors:
        return Response(serializer.errors['overload_conflict'][0], status=status.HTTP_409_CONFLICT)

    return Response({
        'status': 'error',
        'message': 'Error de validación',
        'errors': serializer.errors,
    }, status=status.HTTP_400_BAD_REQUEST)

@extend_schema(methods=['GET'], responses=SubtaskSerializer)
@extend_schema(methods=['PUT', 'PATCH'], request=SubtaskSerializer, responses=SubtaskSerializer)
@extend_schema(methods=['DELETE'], responses=None)
@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
def subtask_detail(request, pk):
    """
    GET    /api/subtasks/<uuid:pk>/ — Detalle de una subtarea.
    PUT    /api/subtasks/<uuid:pk>/ — Actualiza completamente una subtarea.
    PATCH  /api/subtasks/<uuid:pk>/ — Actualiza parcialmente una subtarea.
    DELETE /api/subtasks/<uuid:pk>/ — Elimina una subtarea.
    """
    from .models import Subtask

    try:
        subtask = Subtask.objects.get(
            pk=pk,
            activity__user_id=request.user.user_id
        )                             
    except Subtask.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Subtarea no encontrada',
        }, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = SubtaskSerializer(subtask)
        return Response({
            'status': 'success',
            'data': serializer.data,
        }, status=status.HTTP_200_OK)

    elif request.method in ['PUT', 'PATCH']:
        serializer = SubtaskSerializer(subtask, data=request.data, partial=(request.method == 'PATCH'))
        if serializer.is_valid():
            serializer.save()
            
            # --- US-13: Recálculo de las horas bajo el nuevo plan para mandarlo en la respuesta ---
            from django.db.models import Sum
            from users.models import DailyCapacity
            
            user_id = subtask.activity.user_id
            target_date = subtask.target_date
            
            try:
                limit_hours = float(DailyCapacity.objects.get(user__user_id=user_id).daily_limit_hours)
            except DailyCapacity.DoesNotExist:
                limit_hours = 6.0
                
            planned_hours = 0.0
            if target_date:
                planned_hours = Subtask.objects.filter(
                    activity__user_id=user_id,
                    target_date=target_date
                ).exclude(status='done').aggregate(
                    total=Sum('estimated_hours')
                )['total'] or 0.0
            
            return Response({
                'status': 'success',
                'resolved': True,
                'message': 'Conflicto resuelto' if request.method == 'PATCH' else 'Subtarea actualizada exitosamente',
                'planned_hours': planned_hours,
                'limit_hours': limit_hours,
                'data': serializer.data,
            }, status=status.HTTP_200_OK)

        if 'overload_conflict' in serializer.errors:
            return Response(serializer.errors['overload_conflict'][0], status=status.HTTP_409_CONFLICT)

        return Response({
            'status': 'error',
            'message': 'Error de validación',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        subtask.delete()
        return Response({
            'status': 'success',
            'message': 'Subtarea eliminada exitosamente',
        }, status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    methods=['GET'],
    responses=TodaySubtaskSerializer(many=True),
    parameters=[
        OpenApiParameter(
            name='course',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filtrar por nombre de curso',
            required=False,
        ),
        OpenApiParameter(
            name='status',
            type=OpenApiTypes.STR,
            location=OpenApiParameter.QUERY,
            description='Filtrar por estado: pending, done, postponed, overdue',
            required=False,
        ),
        OpenApiParameter(
            name='days',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.QUERY,
            description='Limitar próximas a los siguientes N días',
            required=False,
        ),
    ],
)
@api_view(['GET'])
def today_subtasks(request):
    """
    GET /api/subtasks/today/ — Vista "Hoy": subtareas agrupadas por prioridad.

    Agrupación:
      - overdue:  target_date < hoy  (más antigua primero)
      - today:    target_date == hoy
      - upcoming: target_date > hoy  (más cercana primero)

    Desempate en todos los grupos: menor estimated_hours primero.

    Query params opcionales:
      - course: filtra por curso de la actividad padre
      - status: filtra por estado de la subtarea (pending, done, postponed, overdue)
      - days:   limita "upcoming" a los próximos N días
    """
    today = date.today()
    user_id = request.user.user_id

    # Lazy update: marcar como vencidas las subtareas y actividades pasadas
    Subtask.objects.filter(
        activity__user_id=user_id,
        target_date__lt=today,
        status='pending',
    ).update(status='overdue')

    Activity.objects.filter(
        user_id=user_id,
        due_date__lt=today,
        status='pending',
    ).update(status='overdue')

    # Base queryset (ya viene todo actualizado)
    qs = Subtask.objects.select_related('activity').filter(
        activity__user_id=user_id,
    )

    # --- Filtros opcionales ---
    course = request.query_params.get('course')
    if course:
        qs = qs.filter(activity__course=course)

    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(status=status_filter)
    else:
        # Por defecto excluir completadas
        qs = qs.exclude(status='done')

    # --- Agrupación por fecha ---
    overdue = qs.filter(
        target_date__lt=today
    ).order_by('target_date', 'estimated_hours')

    today_tasks = qs.filter(
        target_date=today
    ).order_by('estimated_hours')

    upcoming = qs.filter(
        target_date__gt=today
    ).order_by('target_date', 'estimated_hours')

    # Si se pasa ?days=N, limitar upcoming
    days = request.query_params.get('days')
    if days is not None:
        try:
            days = int(days)
            if days < 0:
                return Response({
                    'status': 'error',
                    'message': 'El parámetro "days" debe ser >= 0.',
                }, status=status.HTTP_400_BAD_REQUEST)
            limit_date = today + timedelta(days=days)
            upcoming = upcoming.filter(target_date__lte=limit_date)
        except ValueError:
            return Response({
                'status': 'error',
                'message': 'El parámetro "days" debe ser un número entero.',
            }, status=status.HTTP_400_BAD_REQUEST)

    return Response({
        'status': 'success',
        'data': {
            'overdue': TodaySubtaskSerializer(overdue, many=True).data,
            'today': TodaySubtaskSerializer(today_tasks, many=True).data,
            'upcoming': TodaySubtaskSerializer(upcoming, many=True).data,
        },
    }, status=status.HTTP_200_OK)


