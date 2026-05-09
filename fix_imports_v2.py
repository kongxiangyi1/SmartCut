"""批量修复相对导入问题 - 只修复文件顶部的导入"""
import os
import glob

def fix_top_level_imports(filepath):
    """修复文件顶部的导入（函数外部的导入）"""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 找到函数定义之前的所有导入行
    top_lines = []
    in_function = False
    function_start_patterns = ['def ', 'class ', 'async def ']
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # 检查是否到达函数/类定义
        if any(stripped.startswith(p) for p in function_start_patterns):
            in_function = True
        
        if not in_function:
            top_lines.append((i, line))
    
    # 需要修复的导入前缀
    prefixes = [
        'from ...core.database import ',
        'from ...services.',
        'from ...schemas.',
        'from ...models.',
        'from ...utils.',
        'from ...tasks.',
        'from ...core.',
        'from ...repositories.',
    ]
    
    # 找出需要修复的导入行
    to_fix = []
    for i, line in top_lines:
        stripped = line.strip()
        if any(stripped.startswith(p) for p in prefixes):
            to_fix.append(i)
    
    if not to_fix:
        return
    
    # 创建修复后的内容
    new_lines = []
    i = 0
    while i < len(lines):
        if i in to_fix:
            original_line = lines[i].strip()
            # 添加 try-except
            for prefix in prefixes:
                if original_line.startswith(prefix):
                    backend_prefix = 'from backend.' + prefix[6:]  # 去掉 'from ...'
                    new_lines.append('try:\n')
                    new_lines.append('    ' + original_line + '\n')
                    new_lines.append('except ImportError:\n')
                    new_lines.append('    ' + backend_prefix + '\n')
                    break
            i += 1
        else:
            new_lines.append(lines[i])
            i += 1
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print(f"Fixed: {filepath}")

# 先恢复所有文件
api_files = glob.glob('backend/api/v1/*.py')
for filepath in api_files:
    fix_top_level_imports(filepath)

print("\n修复完成！")