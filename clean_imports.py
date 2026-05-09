"""移除所有 try-except 包装，只保留绝对导入"""
import os
import glob

def clean_file(filepath):
    """清理文件中的 try-except 包装"""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 移除 try-except 块，只保留最终的绝对导入
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # 检查是否是 try-except 块的开始
        if stripped.startswith('try:'):
            # 找到对应的 except ImportError:
            j = i + 1
            found_except = False
            while j < len(lines):
                j_stripped = lines[j].strip()
                if j_stripped.startswith('except ImportError:'):
                    found_except = True
                    break
                j += 1
            
            if found_except:
                # 获取 except 块后面的导入行
                k = j + 1
                while k < len(lines):
                    k_stripped = lines[k].strip()
                    if k_stripped and not k_stripped.startswith('#'):
                        # 找到导入行，使用它
                        indent_count = (len(lines[k]) - len(lines[k].lstrip())) // 4
                        indent = '    ' * indent_count
                        new_lines.append(indent + k_stripped + '\n')
                        break
                    k += 1
                # 跳过整个 try-except 块
                i = k + 1
                continue
        
        # 正常处理
        new_lines.append(line)
        i += 1
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print(f"Cleaned: {filepath}")

# 获取所有 API 文件
api_files = glob.glob('backend/api/v1/*.py')
print(f"Found {len(api_files)} API files to clean")

# 清理所有文件
for filepath in api_files:
    clean_file(filepath)

print("\n清理完成！")