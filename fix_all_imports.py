"""批量修复所有 API 文件的导入问题 - 使用绝对导入"""
import os
import glob

def fix_file_imports(filepath):
    """修复单个文件的导入"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 替换所有相对导入为绝对导入
    content = content.replace('from ...core.database import ', 'from backend.core.database import ')
    content = content.replace('from ...services.', 'from backend.services.')
    content = content.replace('from ...schemas.', 'from backend.schemas.')
    content = content.replace('from ...models.', 'from backend.models.')
    content = content.replace('from ...utils.', 'from backend.utils.')
    content = content.replace('from ...tasks.', 'from backend.tasks.')
    content = content.replace('from ...core.', 'from backend.core.')
    content = content.replace('from ...repositories.', 'from backend.repositories.')
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Fixed: {filepath}")

# 获取所有 API 文件
api_files = glob.glob('backend/api/v1/*.py')
print(f"Found {len(api_files)} API files to fix")

# 修复所有文件
for filepath in api_files:
    fix_file_imports(filepath)

print("\n修复完成！")