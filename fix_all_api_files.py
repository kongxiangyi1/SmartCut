"""批量修复所有被破坏的 API 文件"""
import os
import glob
import re

def fix_api_file(filepath):
    """修复单个 API 文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # 修复模式1：移除错误的 try-except 包装（缺少 try: 开头）
    # 模式：直接以 except ImportError: 开头的块
    pattern1 = r'(\s*)from backend\.[^\n]+\n(\s*)except ImportError:\s*\n(\s*)from backend\.[^\n]+\n'
    
    def replace1(match):
        # 返回第二个导入（except 块中的）
        lines = match.group(0).split('\n')
        for line in lines:
            if 'from backend.' in line and 'except' not in line:
                indent = len(line) - len(line.lstrip())
                return ' ' * indent + line.strip() + '\n'
        return match.group(0)
    
    content = re.sub(pattern1, replace1, content)
    
    # 修复模式2：移除正确的 try-except 包装（有 try: 开头）
    pattern2 = r'try:\s*\n(\s*)from (backend|\.\.\.)\.[^\n]+\n\s*except ImportError:\s*\n(\s*)from backend\.[^\n]+\n'
    
    def replace2(match):
        # 返回 except 块中的导入
        lines = match.group(0).split('\n')
        for line in lines:
            if 'from backend.' in line and 'except' not in line and 'try:' not in line:
                indent = len(line) - len(line.lstrip())
                return ' ' * indent + line.strip() + '\n'
        return match.group(0)
    
    content = re.sub(pattern2, replace2, content)
    
    # 修复模式3：移除多余的缩进（from backend. 前面有多余空格）
    # 只在文件顶部修复（前50行）
    lines = content.split('\n')
    for i in range(min(50, len(lines))):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith('from backend.') and line.startswith('    '):
            # 检查是否在函数外部
            in_function = False
            for j in range(i-1, max(0, i-10), -1):
                if lines[j].strip().startswith('def ') or lines[j].strip().startswith('class '):
                    in_function = True
                    break
            if not in_function:
                lines[i] = stripped
    
    content = '\n'.join(lines)
    
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
    if fix_api_file(filepath):
        fixed_count += 1

print(f"\n修复完成！共修复 {fixed_count} 个文件")