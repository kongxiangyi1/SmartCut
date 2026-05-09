import os

# Find all files with relative imports in backend/core/
for root, dirs, files in os.walk('backend/core'):
    for filename in files:
        if filename.endswith('.py'):
            filepath = os.path.join(root, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            # Check for relative imports
            if 'from ..' in content or 'from .' in content:
                print(f'{filepath}:')
                for i, line in enumerate(content.split('\n'), 1):
                    if 'from ..' in line or 'from .' in line:
                        print(f'  Line {i}: {line.strip()}')
