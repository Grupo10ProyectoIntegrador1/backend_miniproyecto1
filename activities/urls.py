from django.urls import path
from . import views

urlpatterns = [
    path('activities/', views.activity_list_create, name='activity-list-create'),
    path('activities/<int:activity_id>/subtasks/', views.subtask_create, name='subtask-create'),
    path('activities/<int:pk>/', views.activity_detail, name='activity-detail'),
    path('subtasks/today/', views.today_subtasks, name='today-subtasks'),
    path('subtasks/<int:pk>/', views.subtask_detail, name='subtask-detail'),
]
