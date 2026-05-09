import os
import re

api_dir = 'backend/api/v1'

# Common truncated Chinese phrases and their fixes
fixes = {
    # Regular words
    '个文?': '个文件',
    '上传?': '上传了',
    '不存?': '不存在',
    '合集不存?': '合集不存在',
    '合集中没有切?': '合集中没有切片',
    '项目不存?': '项目不存在',
    '从文件系统获?': '从文件系统获取',
    '获取合集元数?': '获取合集元数据',
    '可用模?': '可用模型',
    '提供商信?': '提供商信息',
    '信息失?': '信息失败',
    
    # Triple quotes
    '"""?': '"""\n',  # For docstrings that end with ?
    
    # With quotes
    '"不存?': '"不存在',
    '"合集不存?': '"合集不存在',
    '"项目不存?': '"项目不存在',
}

for filename in os.listdir(api_dir):
    if not filename.endswith('.py'):
        continue
    
    filepath = os.path.join(api_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Apply all fixes
    for old, new in fixes.items():
        content = content.replace(old, new)
    
    # Fix triple-quoted strings that end with ?
    # Pattern: """xxx?""" -> """xxx"""
    content = re.sub(r'"""(.*?)\?(""")?', r'"""\1"""', content)
    
    # Fix f-strings that end with ?
    content = re.sub(r'f"([^"]*)\?(")?', r'f"\1"', content)
    
    # Fix regular strings that end with ?
    content = re.sub(r'"([^"]*)\?(")?', r'"\1"', content)
    
    # Fix single quote strings that end with ?
    content = re.sub(r"'([^']*)\?(')?", r"'\1'", content)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Fixed {filename}')
    else:
        print(f'{filename}: OK')

print('Done')
