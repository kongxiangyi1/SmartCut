import json
from pathlib import Path

project_id = 'b0d4c113-3a61-4df7-a7f0-cc03759c3dc6'
output_dir = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\output')

# 检查 step6_video_output.json
step6_path = output_dir / 'step6_video_output.json'
if step6_path.exists():
    with open(step6_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f'step6_video_output.json 中的 clips_with_titles 数量: {len(data.get("clips_with_titles", []))}')

# 检查 metadata/clips_metadata.json
metadata_path = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\metadata\clips_metadata.json')
if metadata_path.exists():
    with open(metadata_path, 'r', encoding='utf-8') as f:
        clips = json.load(f)
    print(f'metadata/clips_metadata.json 中的切片数量: {len(clips)}')
