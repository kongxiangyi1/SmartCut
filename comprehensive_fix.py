import os

api_dir = 'backend/api/v1'

# Common truncated Chinese phrases and their fixes
fixes = {
    '个文?': '个文件',
    '个文?)': '个文件)',
    '上传?': '上传了',
    '不存?': '不存在',
    '不存在?)': '不存在)',
    '合集不存?': '合集不存在',
    '合集中没有切?': '合集中没有切片',
    '项目不存?': '项目不存在',
    '从文件系统获?': '从文件系统获取',
    '获取合集元数?': '获取合集元数据',
}

for filename in os.listdir(api_dir):
    if not filename.endswith('.py'):
        continue
    
    filepath = os.path.join(api_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    for old, new in fixes.items():
        content = content.replace(old, new)
    
    # Also fix standalone ? at end of strings
    lines = content.split('\n')
    fixed_lines = []
    for line in lines:
        # Handle f-strings that end with ?
        if 'f"' in line:
            parts = line.split('f"')
            for i in range(1, len(parts)):
                part = parts[i]
                # If there's no closing quote and ends with ?
                if '"' not in part and part.strip().endswith('?'):
                    parts[i] = part[:-1] + '"'
            line = 'f"'.join(parts)
        
        # Handle regular strings that end with ?
        if '"' in line and line.count('"') % 2 == 1:
            parts = line.split('"')
            if parts[-1].strip() == '' or parts[-1].strip() == ')':
                if parts[-2].strip().endswith('?'):
                    parts[-2] = parts[-2][:-1]
                line = '"'.join(parts)
        
        fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Fixed {filename}')
    else:
        print(f'{filename}: OK')

print('Done')
