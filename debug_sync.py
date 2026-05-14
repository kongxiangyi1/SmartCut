import sys
sys.path.insert(0, r'E:\ClipProject\autoclip-main1\autoclip-main')
from backend.utils.video_processor import VideoProcessor
from pathlib import Path
import json

project_id = 'b0d4c113-3a61-4df7-a7f0-cc03759c3dc6'
input_video = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\raw\input.mp4')
clips_dir = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\output\clips')

# 模拟 clips_with_titles（数字id）
clips_with_titles = [
    {'id': 1, 'generated_title': '切片1', 'start_time': '00:00:00,210', 'end_time': '00:01:34,328'},
    {'id': 2, 'generated_title': '切片2', 'start_time': '00:01:45,419', 'end_time': '00:07:37,442'},
    {'id': 3, 'generated_title': '切片3', 'start_time': '00:07:38,555', 'end_time': '00:10:45,666'},
]

print('原始 clips_with_titles:')
for clip in clips_with_titles:
    print(f"  id={clip['id']}, duration={clip.get('duration', 'N/A')}")

# 创建 clips_data（模拟 generate_clips 中的逻辑）
clips_data = []
for clip in clips_with_titles:
    clips_data.append({
        'id': clip['id'],
        'title': clip.get('generated_title', f"片段_{clip['id']}"),
        'start_time': clip['start_time'],
        'end_time': clip['end_time']
    })

# 创建 VideoProcessor
processor = VideoProcessor(clips_dir=str(clips_dir), collections_dir=str(clips_dir.parent / 'collections'))

# 调用 batch_extract_clips（串行处理，因为只有3个切片）
successful_clips = processor.batch_extract_clips(input_video, clips_data, apply_silence_processing=False)

print('\n\nbatch_extract_clips 返回后 clips_data:')
for clip in clips_data:
    print(f"  id={clip['id']}, duration={clip.get('duration', 'N/A')}")

# 模拟 step6_video.py 中的同步逻辑
print('\n\n同步 clips_data -> clips_with_titles:')
for clip_data in clips_data:
    found = False
    for clip in clips_with_titles:
        if str(clip['id']) == str(clip_data['id']):
            # 同步静音处理后的时间
            if 'start_time' in clip_data:
                clip['start_time'] = clip_data['start_time']
            if 'end_time' in clip_data:
                clip['end_time'] = clip_data['end_time']
            # 优先使用从视频获取的实际时长
            if clip_data.get('duration', 0) > 0:
                clip['duration'] = clip_data['duration']
                print(f"  同步成功: id={clip['id']}, duration={clip['duration']}")
            found = True
            break
    if not found:
        print(f"  未找到匹配的 clip: id={clip_data['id']}")

print('\n\n最终 clips_with_titles:')
for clip in clips_with_titles:
    print(f"  id={clip['id']}, duration={clip.get('duration', 'N/A')}")
