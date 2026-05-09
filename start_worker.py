import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.core.celery_app import celery_app

if __name__ == '__main__':
    print("启动Celery worker...")
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=1'
    ])