from django.contrib import admin
from django.urls import path
from api.views import health_check, test_db_connection

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', health_check, name='health_check'),
    path('api/test-db/', test_db_connection, name='test_db_connection'),
]
