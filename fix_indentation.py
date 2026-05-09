"""修复 projects.py 中所有 try-except 的缩进问题"""
import re

# 读取文件
with open('backend/api/v1/projects.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 修复逻辑：找到所有以 'try:' 开头但前面不是空格的行
# 需要检查前一行是否有冒号（if/else/elif等），然后添加适当的缩进
new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    stripped = line.strip()
    
    # 检查是否是需要修复的 try:
    if stripped == 'try:' and len(line) - len(line.lstrip()) == 0:
        # 找到前面的上下文
        prev_line = ''
        j = i - 1
        while j >= 0:
            prev_stripped = lines[j].strip()
            if prev_stripped:
                prev_line = prev_stripped
                prev_indent = len(lines[j]) - len(lines[j].lstrip())
                break
            j -= 1
        
        # 根据上下文确定缩进级别
        if prev_line.endswith(':'):
            # 如果前一行是 if/else/elif/for/while 等，需要额外缩进
            new_indent = '    ' * ((prev_indent // 4) + 1)
        else:
            # 否则使用与前一行相同的缩进
            new_indent = '    ' * (prev_indent // 4)
        
        # 添加修复后的 try 行
        new_lines.append(new_indent + 'try:\n')
        
        # 修复后续的 except 行
        i += 1
        while i < len(lines):
            curr_line = lines[i]
            curr_stripped = curr_line.strip()
            if curr_stripped.startswith('except') or curr_stripped.startswith('finally'):
                new_lines.append(new_indent + curr_stripped + '\n')
                i += 1
            else:
                break
                
    else:
        new_lines.append(line)
        i += 1

# 写入修复后的内容
with open('backend/api/v1/projects.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("修复完成！")