import os
import py_compile

api_dir = 'backend/api/v1'
errors = []

for filename in sorted(os.listdir(api_dir)):
    if not filename.endswith('.py'):
        continue
    filepath = os.path.join(api_dir, filename)
    try:
        py_compile.compile(filepath, doraise=True)
        print(f'{filename}: OK')
    except py_compile.PyCompileError as e:
        print(f'{filename}: ERROR - {e}')
        errors.append((filename, str(e)))

if errors:
    print(f'\nTotal errors: {len(errors)}')
else:
    print('\nAll files OK!')
