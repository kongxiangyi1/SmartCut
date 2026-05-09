import os

api_dir = 'backend/api/v1'
for filename in os.listdir(api_dir):
    if filename.endswith('.py'):
        filepath = os.path.join(api_dir, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Replace truncated strings ending with '?)' 
        # The pattern is like: detail="xxx?)
        # Should be: detail="xxx")
        fixed = content.replace('detail="', 'detail="')
        fixed = fixed.replace('")', '")')
        
        # Handle the specific pattern where ?) appears without proper closing
        lines = fixed.split('\n')
        result_lines = []
        for line in lines:
            if 'detail=\"' in line and '?)' in line:
                # Find the ?) and replace with ")
                idx = line.find('?)')
                if idx != -1:
                    line = line[:idx] + '")' + line[idx+2:]
            result_lines.append(line)
        
        fixed = '\n'.join(result_lines)
        
        if fixed != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(fixed)
            print(f'Fixed {filename}')
        else:
            print(f'{filename}: OK')

print('Done')
