import json
from pathlib import Path

json_path = Path(r'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\b0d4c113-3a61-4df7-a7f0-cc03759c3dc6\metadata\clips_metadata.json')
with open(json_path, 'r', encoding='utf-8') as f:
    clips = json.load(f)

print('JSON 文件中的 duration:')
for i, clip in enumerate(clips, 1):
    print(f"切片 {i}: duration={clip['duration']:.3f}s, start={clip['start_time']}, end={clip['end_time']}")
