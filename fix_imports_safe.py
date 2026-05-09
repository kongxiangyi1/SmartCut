"""只修复导入语句，不破坏其他代码"""
import os
import glob
import re

def fix_imports_safely(filepath):
    """安全地修复导入语句"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # 只替换文件顶部的相对导入（不在函数内部的）
    # 匹配模式：文件开头的 from ... 导入
    lines = content.split('\n')
    in_function = False
    new_lines = []
    
    for i, line in enumerate(lines):
        # 检查是否进入函数/类定义
        stripped = line.strip()
        if stripped.startswith('def ') or stripped.startswith('class ') or stripped.startswith('async def '):
            in_function = True
        
        # 检查是否离开函数（通过缩进判断）
        if in_function and line and not line[0].isspace() and stripped and not stripped.startswith('#'):
            in_function = False
        
        # 只在文件顶部（不在函数内）修复导入
        if not in_function and stripped.startswith('from ...'):
            # 替换相对导入为绝对导入
            new_line = line.replace('from ...', 'from backend.')
            new_lines.append(new_line)
        else:
            new_lines.append(line)
    
    content = '\n'.join(new_lines)
    
    if content != original:
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
    if fix_imports_safely(filepath):
        fixed_count += 1

print(f"\n修复完成！共修复 {fixed_count} 个文件")