"""修复被破坏的 API 文件 - 只修复导入部分"""
import os
import glob
import re

def fix_broken_file(filepath):
    """修复被破坏的文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查文件是否被破坏（有错误的 try-except 块）
    if 'try:\n    from backend.' in content or 'try:\n    from ...' in content:
        # 移除错误的 try-except 包装
        # 模式：try: 后面跟着 from backend. 或 from ...
        pattern = r'try:\s*\n\s*from (backend|\.\.\.)\.[^\n]+\n\s*except ImportError:\s*\n\s*from backend\.[^\n]+\n'
        
        def replace_func(match):
            # 提取 except 块中的导入语句
            lines = match.group(0).split('\n')
            for line in lines:
                if 'from backend.' in line and 'except' not in line:
                    # 返回正确的导入语句
                    indent = len(line) - len(line.lstrip())
                    return ' ' * indent + line.strip() + '\n'
            return match.group(0)
        
        content = re.sub(pattern, replace_func, content)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {filepath}")
        return True
    return False

# 获取所有 API 文件
api_files = glob.glob('backend/api/v1/*.py')
print(f"Found {len(api_files)} API files")

# 修复所有文件
fixed_count = 0
for filepath in api_files:
    if fix_broken_file(filepath):
        fixed_count += 1

print(f"\n修复完成！共修复 {fixed_count} 个文件")