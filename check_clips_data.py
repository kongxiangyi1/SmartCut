import sys
sys.path.insert(0, r'E:\ClipProject\autoclip-main1\autoclip-main')
from backend.utils.video_processor import VideoProcessor
from pathlib import Path
import json

project_id = 'b0d4c113-3a61-4df7-a7f0-cc03759c3dc6'
metadata_path = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\metadata\clips_metadata.json')

with open(metadata_path, 'r', encoding='utf-8') as f:
    clips_data = json.load(f)

print('clips_data 中的 duration 值：')
for clip in clips_data:
    print(f"  id={clip['id']}, duration={clip.get('duration', 'N/A')}")
