import os

# Fix relative imports in backend/core/ files
files_to_fix = {
    'backend/core/config.py': [
        ('from ..core.path_utils', 'from backend.core.path_utils'),
    ],
    'backend/core/dependencies.py': [
        ('from ..core.database', 'from backend.core.database'),
        ('from ..services.project_service', 'from backend.services.project_service'),
        ('from ..services.clip_service', 'from backend.services.clip_service'),
        ('from ..services.collection_service', 'from backend.services.collection_service'),
        ('from ..services.task_service', 'from backend.services.task_service'),
    ],
    'backend/core/llm_manager.py': [
        ('from ..utils.llm_client', 'from backend.utils.llm_client'),
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
