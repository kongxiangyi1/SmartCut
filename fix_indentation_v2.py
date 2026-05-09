"""修复 projects.py 中所有 try-except 的缩进问题 - 完整版"""
import re

# 读取文件
with open('backend/api/v1/projects.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 模式：匹配错误缩进的 try-except 块
# 找到所有以 try: 开头但后面的 except 没有正确缩进的情况
pattern = r'(try:\n)(\s*from ...\.[a-z_]+ import .+?\n)(\s*except ImportError:\n)(\s*from backend\.[a-z_]+ import .+?\n)'

def fix_match(match):
    # 获取匹配内容
    try_line = match.group(1)
    from_line1 = match.group(2)
    except_line = match.group(3)
    from_line2 = match.group(4)
    
    # 检查是否需要修复（except没有正确缩进）
    if len(from_line1.strip()) > 0 and len(from_line1) - len(from_line1.lstrip()) == 0:
        # 需要修复：添加适当的缩进
        indent = '    '
        fixed = try_line + indent + from_line1.strip() + '\n' + indent + except_line.strip() + '\n' + indent + from_line2.strip() + '\n'
        return fixed
    return match.group(0)

# 应用修复
fixed_content = re.sub(pattern, fix_match, content, flags=re.MULTILINE)

# 写入修复后的内容
with open('backend/api/v1/projects.py', 'w', encoding='utf-8') as f:
    f.write(fixed_content)

print("修复完成！")