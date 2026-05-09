"""批量修复相对导入问题"""
import os
import glob

def fix_imports(filepath):
    """修复单个文件的导入"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 需要修复的导入模式
    patterns = [
        ('from ...core.database import ', 'try:\n    from ...core.database import ', 'except ImportError:\n    from backend.core.database import '),
        ('from ...services.', 'try:\n    from ...services.', 'except ImportError:\n    from backend.services.'),
        ('from ...schemas.', 'try:\n    from ...schemas.', 'except ImportError:\n    from backend.schemas.'),
        ('from ...models.', 'try:\n    from ...models.', 'except ImportError:\n    from backend.models.'),
        ('from ...utils.', 'try:\n    from ...utils.', 'except ImportError:\n    from backend.utils.'),
        ('from ...tasks.', 'try:\n    from ...tasks.', 'except ImportError:\n    from backend.tasks.'),
        ('from ...core.', 'try:\n    from ...core.', 'except ImportError:\n    from backend.core.'),
        ('from ...repositories.', 'try:\n    from ...repositories.', 'except ImportError:\n    from backend.repositories.'),
    ]
    
    original_content = content
    for old_prefix, try_prefix, except_prefix in patterns:
        lines = content.split('\n')
        new_lines = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.strip().startswith(old_prefix) and not line.strip().startswith('try:') and not line.strip().startswith('except'):
                # 检查是否已经在 try-except 块中
                in_try = False
                for j in range(max(0, i-2), i):
                    if lines[j].strip().startswith('try:'):
                        in_try = True
                        break
                if not in_try:
                    # 添加 try-except 包装
                    new_lines.append(try_prefix + line.strip()[len(old_prefix):])
                    new_lines.append(except_prefix + line.strip()[len(old_prefix):])
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
            i += 1
        content = '\n'.join(new_lines)
    
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {filepath}")

# 修复所有 API 文件
api_files = glob.glob('backend/api/v1/*.py')
for filepath in api_files:
    fix_imports(filepath)

print("\n修复完成！")