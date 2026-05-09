import os

files_to_fix = [
    ('backend/api/v1/bilibili.py', [598, 662, 699, 821, 856, 863, 895]),
    ('backend/api/v1/youtube.py', [703, 777, 820, 944, 979, 986, 1018])
]

for filepath, lines_to_fix in files_to_fix:
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    modified = False
    for line_num in lines_to_fix:
        idx = line_num - 1
        if idx < len(lines):
            line = lines[idx]
            # Replace ?) with ") in string contexts
            if '?)' in line:
                # Count quotes before and after
                parts = line.split('?)')
                new_parts = []
                for i, part in enumerate(parts):
                    if i < len(parts) - 1:
                        # Check if this is inside a string
                        if part.count('"') % 2 == 1 or part.count("'") % 2 == 1:
                            new_parts.append(part + '")')
                        else:
                            new_parts.append(part + '?)')
                    else:
                        new_parts.append(part)
                lines[idx] = ''.join(new_parts)
                modified = True
    
    if modified:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f'Fixed {os.path.basename(filepath)}')
    else:
        print(f'{os.path.basename(filepath)}: OK')

print('Done')
