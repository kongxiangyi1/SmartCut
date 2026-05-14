import sys
sys.path.insert(0, r'E:\ClipProject\autoclip-main1\autoclip-main')
from backend.utils.video_processor import VideoProcessor
from pathlib import Path
import json

project_id = 'b0d4c113-3a61-4df7-a7f0-cc03759c3dc6'
input_video = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\raw\input.mp4')
clips_dir = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\output\clips')

# 模拟 clips_with_titles
clips_with_titles = [
    {'id': 1, 'generated_title': '切片1', 'start_time': '00:00:00,210', 'end_time': '00:01:34,328'},
    {'id': 2, 'generated_title': '切片2', 'start_time': '00:01:45,419', 'end_time': '00:07:37,442'},
]

# 创建 clips_data（模拟 generate_clips 中的逻辑）
clips_data = []
for clip in clips_with_titles:
    clips_data.append({
        'id': clip['id'],
        'title': clip.get('generated_title', f"片段_{clip['id']}"),
        'start_time': clip['start_time'],
        'end_time': clip['end_time']
    })

print('原始 clips_data:')
for clip in clips_data:
    print(f"  id={clip['id']}, duration={clip.get('duration', 'N/A')}")

# 创建 VideoProcessor
processor = VideoProcessor(clips_dir=str(clips_dir), collections_dir=str(clips_dir.parent / 'collections'))

# 调用 batch_extract_clips_parallel
successful_clips = processor.batch_extract_clips_parallel(input_video, clips_data)

print('\n\nbatch_extract_clips_parallel 返回后 clips_data:')
for clip in clips_data:
    print(f"  id={clip['id']}, duration={clip.get('duration', 'N/A')}")
