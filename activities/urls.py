from django.urls import path
from . import views

urlpatterns = [
    path('activities/', views.activity_list_create, name='activity-list-create'),
    path('activities/<uuid:pk>/', views.activity_detail, name='activity-detail'),
    path('activities/<uuid:activity_id>/subtasks/', views.subtask_create, name='subtask-create'),
]
