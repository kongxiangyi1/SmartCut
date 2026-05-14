import json
from pathlib import Path

project_id = 'b0d4c113-3a61-4df7-a7f0-cc03759c3dc6'

# 检查 clips_metadata.json
metadata_path = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\metadata\clips_metadata.json')
with open(metadata_path, 'r', encoding='utf-8') as f:
    clips_metadata = json.load(f)

print('clips_metadata.json 中的 id 和 duration:')
for clip in clips_metadata:
    print(f"  id={clip.get('id')}, duration={clip.get('duration')}")

print('\n视频文件名:')
clips_dir = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\output\clips')
for clip_file in sorted(clips_dir.glob('*.mp4')):
    print(f"  {clip_file.name}")
