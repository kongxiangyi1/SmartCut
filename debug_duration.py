import sys
sys.path.insert(0, r'E:\ClipProject\autoclip-main1\autoclip-main')

import json
from pathlib import Path
from backend.utils.video_processor import VideoProcessor

project_id = 'b0d4c113-3a61-4df7-a7f0-cc03759c3dc6'
metadata_path = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\metadata\clips_metadata.json')
input_video = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\raw\input.mp4')
clips_dir = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\output\clips')

# 加载 clips_data
with open(metadata_path, 'r', encoding='utf-8') as f:
    clips_data = json.load(f)

print('原始 clips_data:')
for clip in clips_data:
    print(f"  id={clip['id']}, duration={clip.get('duration', 'N/A')}")

# 创建 VideoProcessor 并调用 batch_extract_clips_parallel
processor = VideoProcessor(clips_dir=str(clips_dir), collections_dir=str(clips_dir.parent / 'collections'))

# 直接调用 _extract_clip_wrapper 来测试
def test_extract_clip(clip_data):
    from backend.utils.video_processor import VideoProcessor
    import time

    clip_id = clip_data['id']
    title = clip_data.get('title', f"片段_{clip_id}")
    start_time = clip_data['start_time']
    end_time = clip_data['end_time']

    # 转换为秒数
    clip_start_sec = start_time
    clip_end_sec = end_time
    if isinstance(start_time, str):
        clip_start_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(start_time)
    if isinstance(end_time, str):
        clip_end_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(end_time)

    # 使用标题作为文件名
    safe_title = VideoProcessor.sanitize_filename(title)
    output_path = clips_dir / f"{clip_id}_{safe_title}.mp4"

    print(f"\n处理切片 {clip_id}:")
    print(f"  原始 start_time: {start_time}, end_time: {end_time}")
    print(f"  原始 duration: {clip_data.get('duration', 'N/A')}")

    # 处理时间格式
    if isinstance(start_time, (int, float)):
        start_time = VideoProcessor.convert_seconds_to_ffmpeg_time(start_time)
    if isinstance(end_time, (int, float)):
        end_time = VideoProcessor.convert_seconds_to_ffmpeg_time(end_time)

    success = VideoProcessor.extract_clip(input_video, output_path, start_time, end_time)

    if success:
        # 获取实际视频时长
        actual_duration = VideoProcessor.get_video_duration(output_path)
        print(f"  提取成功，实际视频时长: {actual_duration:.3f}s")

        # 更新 clip_data['duration']
        clip_data['duration'] = actual_duration
        print(f"  更新后 clip_data['duration']: {clip_data['duration']}")
    else:
        print(f"  提取失败")

# 测试单个切片
test_extract_clip(clips_data[0])

print('\n\n处理后 clips_data:')
for clip in clips_data:
    print(f"  id={clip['id']}, duration={clip.get('duration', 'N/A')}")
