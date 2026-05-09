import os
import re

# Fix relative imports in backend/api/ files
files_to_fix = {
    'backend/api/account_health.py': [
        ('from ..core.database', 'from backend.core.database'),
        ('from ..models.bilibili', 'from backend.models.bilibili'),
        ('from ..services.account_health_service', 'from backend.services.account_health_service'),
    ],
    'backend/api/upload_queue.py': [
        ('from ..models.bilibili', 'from backend.models.bilibili'),
    ],
    'backend/api/v1/clips.py': [
        ('from ...utils.llm_client', 'from backend.utils.llm_client'),
        ('from ...core.shared_config', 'from backend.core.shared_config'),
        ('from ...models.project', 'from backend.models.project'),
        ('from ...core.config', 'from backend.core.config'),
        ('from ...services.data_sync_service', 'from backend.services.data_sync_service'),
    ],
    'backend/api/v1/projects.py': [
        ('from ...core.path_utils', 'from backend.core.path_utils'),
        ('from ...utils.thumbnail_generator', 'from backend.utils.thumbnail_generator'),
        ('from ...tasks.import_processing', 'from backend.tasks.import_processing'),
        ('from ...services.clip_service', 'from backend.services.clip_service'),
        ('from ...services.collection_service', 'from backend.services.collection_service'),
        ('from ...core.database', 'from backend.core.database'),
        ('from ...services.data_sync_service', 'from backend.services.data_sync_service'),
        ('from ...models.task', 'from backend.models.task'),
        ('from ...core.celery_app', 'from backend.core.celery_app'),
        ('from ...models.project', 'from backend.models.project'),
        ('from ...models.clip', 'from backend.models.clip'),
        ('from ...models.collection', 'from backend.models.collection'),
        ('from ...utils.video_processor', 'from backend.utils.video_processor'),
    ],
    'backend/api/v1/__init__.py': [
        ('from ..upload_queue', 'from backend.api.upload_queue'),
        ('from ..account_health', 'from backend.api.account_health'),
    ],
}

for filepath, replacements in files_to_fix.items():
    if not os.path.exists(filepath):
        print(f'{filepath}: NOT FOUND')
        continue

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    for old, new in replacements:
        content = content.replace(old, new)

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Fixed {filepath}')
    else:
        print(f'{filepath}: No changes')

print('Done')
