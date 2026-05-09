import os
import re

api_dir = 'backend/api/v1'

for filename in sorted(os.listdir(api_dir)):
    if not filename.endswith('.py'):
        continue
    
    filepath = os.path.join(api_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Fix pattern: "Chinese_text"..") -> "Chinese_text")
    # This pattern occurs when Chinese characters are truncated and replaced with ".."
    content = re.sub(r'"([^"]*[\u4e00-\u9fff])"\.\."', r'"\1"', content)
    
    # Also fix: "Chinese_text"..")  -> "Chinese_text")
    content = re.sub(r'"([^"]*[\u4e00-\u9fff])"\.\."\)', r'"\1")', content)
    
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Fixed {filename}')
    else:
        print(f'{filename}: OK')

print('Done')
