from django.http import JsonResponse
from django.db import connection

def health_check(request):
    return JsonResponse({'status': 'ok', 'message': 'Backend is connected!'})

def test_db_connection(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
        return JsonResponse({
            'status': 'ok', 
            'message': 'Supabase DB connection successful!', 
            'db_response': row[0]
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
