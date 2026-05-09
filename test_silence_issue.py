import sys
from pathlib import Path

project_root = Path('.')
sys.path.insert(0, str(project_root))

project_id = '954f08fd-d15b-410e-bc1f-b051f9a40ba3'

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

from backend.utils.video_processor import VideoProcessor
from backend.utils.silence_processor import SilenceProcessor

# 文件路径
data_root = project_root / 'data' / 'projects' / project_id
input_video_path = data_root / 'raw' / 'input.mp4'

print(f'📹 视频文件: {input_video_path}')

# 测试静音处理器
processor = SilenceProcessor()
audio_path = data_root / 'raw' / 'input_audio.wav'

# 提取音频
print('\n🎵 提取音频...')
success = SilenceProcessor.extract_audio_from_video(input_video_path, audio_path)
print(f'音频提取成功: {success}')

# 测试开头静音检测
print('\n🔍 检测开头静音...')
first_speech_start = processor.find_first_speech_start(audio_path)
print(f'第一个语音开始时间: {first_speech_start:.2f} 秒')

# 测试跳过时间
skip_time = processor.skip_leading_silence(audio_path)
print(f'需要跳过的开头静音时间: {skip_time:.2f} 秒')

# 测试切片数据（来自 step4 的输出）
clips_data = [
    {'id': '1', 'title': '片段1', 'start_time': '00:00:00,210', 'end_time': '00:00:07,104'},
    {'id': '2', 'title': '片段2', 'start_time': '00:00:07,104', 'end_time': '00:00:15,497'},
    {'id': '3', 'title': '片段3', 'start_time': '00:00:15,497', 'end_time': '00:00:42,773'},
]

print('\n📋 原始切片数据:')
for clip in clips_data:
    print(f"  - {clip['id']}: {clip['start_time']} -> {clip['end_time']}")

# 应用跳过时间后会发生什么
print(f'\n⏭️ 应用开头静音跳过 ({skip_time:.2f}秒):')
for clip in clips_data:
    start_str = clip['start_time']
    end_str = clip['end_time']
    
    # 转换时间格式
    if ',' in start_str:
        start_str = start_str.replace(',', '.')
    if ',' in end_str:
        end_str = end_str.replace(',', '.')
    
    start = VideoProcessor.convert_ffmpeg_time_to_seconds(start_str)
    end = VideoProcessor.convert_ffmpeg_time_to_seconds(end_str)
    
    adjusted_start = start + skip_time
    adjusted_end = end + skip_time
    
    status = '✅ 有效' if adjusted_start < adjusted_end else '❌ 被丢弃'
    print(f"  - {clip['id']}: {start:.2f} -> {end:.2f} => {adjusted_start:.2f} -> {adjusted_end:.2f} [{status}]")

# 清理临时文件
audio_path.unlink(missing_ok=True)
