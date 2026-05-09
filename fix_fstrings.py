import os
import re

api_dir = 'backend/api/v1'

# Pattern: Chinese text followed by " which should be :" or similar
# e.g., f"xxx失" {var}") -> f"xxx失败: {var}")
# e.g., f"xxx已创" {var}") -> f"xxx已创建: {var}")

# Find all lines with potential truncated Chinese in f-strings
for filename in sorted(os.listdir(api_dir)):
    if not filename.endswith('.py'):
        continue
    
    filepath = os.path.join(api_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    modified = False
    for i, line in enumerate(lines):
        # Pattern: f"Chinese_text" {var}") - missing colon and continuation
        match = re.search(r'f"([^"]*[\u4e00-\u9fff])" (\{[^}]+\}")', line)
        if match:
            prefix = match.group(1)
            var = match.group(2)
            # Common truncation patterns
            replacements = {
                '失': '失败:',
                '已创': '已创建:',
                '获取成': '获取成功:',
                '获取当前提供商信': '获取当前提供商信息:',
                '缩略图获取成': '缩略图获取成功:',
                '下载YouTube缩略图失': '下载YouTube缩略图失败:',
                '处理YouTube缩略图失': '处理YouTube缩略图失败:',
                '解析B站视频失': '解析B站视频失败:',
                '开始解析B站视': '开始解析B站视频:',
                '不支持的提供商类': '不支持的提供商类型:',
                '更新LLM管理器失': '更新LLM管理器失败:',
            }
            new_prefix = replacements.get(prefix, prefix + ':')
            old = match.group(0)
            new = f'f"{new_prefix} {var}'
            line = line.replace(old, new)
            lines[i] = line
            modified = True
    
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f'Fixed {filename}')
    else:
        print(f'{filename}: OK')

print('Done')
