import os
import re

api_dir = 'backend/api/v1'

for filename in os.listdir(api_dir):
    if not filename.endswith('.py'):
        continue
    
    filepath = os.path.join(api_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Fix 1: f-string with ?) pattern
    # Pattern: f"xxx?) -> f"xxx")
    content = re.sub(r'f"([^"]*\?)', r'f"\1', content)
    content = re.sub(r'(\?)', r'')', content)
    
    # Fix 2: Regular string with ?) pattern
    # Pattern: "xxx?) -> "xxx")
    content = re.sub(r'"([^"]*\?)', r'"\1', content)
    
    # Fix 3: Single quote strings with ?)
    content = re.sub(r"'([^']*\?)", r"'\1", content)
    
    # Fix 4: Handle incomplete f-strings by finding the last { and closing the string
    lines = content.split('\n')
    fixed_lines = []
    
    for line in lines:
        # Check for unterminated f-strings
        if 'f"' in line and '?' in line and line.count('f"') > line.count('"'):
            # Find the f" and add closing quote
            parts = line.split('f"')
            if len(parts) > 1:
                last_part = parts[-1]
                # Find the last ? and replace with )
                if '?' in last_part:
                    idx = last_part.rfind('?')
                    if idx != -1 and (idx == len(last_part) - 1 or last_part[idx+1] == ')'):
                        last_part = last_part[:idx] + ')' + last_part[idx+1:]
                    # Add closing quote if missing
                    if '"' not in last_part:
                        last_part = last_part + '"'
                parts[-1] = last_part
                line = 'f"'.join(parts)
        
        fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Fixed {filename}')
    else:
        print(f'{filename}: OK')

print('Done')
