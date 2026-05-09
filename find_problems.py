import os

api_dir = 'backend/api/v1'
for filename in os.listdir(api_dir):
    if not filename.endswith('.py'):
        continue
    
    filepath = os.path.join(api_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    problems = []
    for i, line in enumerate(lines):
        if '?)' in line and ('f"' in line or '"' in line or "'" in line):
            problems.append(i + 1)
    
    if problems:
        print(f'{filename}: {len(problems)} problems at lines {problems}')
