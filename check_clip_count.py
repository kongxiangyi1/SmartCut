import json
from pathlib import Path

project_id = 'b0d4c113-3a61-4df7-a7f0-cc03759c3dc6'

# 检查 step4_titles.json
step4_path = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\step4_titles.json')
if step4_path.exists():
    with open(step4_path, 'r', encoding='utf-8') as f:
        clips = json.load(f)
    print(f'step4_titles.json 中的切片数量: {len(clips)}')

# 检查 clips_with_titles_path
clips_with_titles_path = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\clips_with_titles.json')
if clips_with_titles_path.exists():
    with open(clips_with_titles_path, 'r', encoding='utf-8') as f:
        clips = json.load(f)
    print(f'clips_with_titles.json 中的切片数量: {len(clips)}')
