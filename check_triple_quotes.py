with open('backend/api/v1/bilibili.py', 'r', encoding='utf-8') as f:
    content = f.read()
    triple_count = content.count('"""')
    print(f'Triple quote count: {triple_count}')
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if '"""' in line:
            print(f'Line {i+1}: {repr(line)}')
