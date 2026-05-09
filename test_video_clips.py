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

# 文件路径
data_root = project_root / 'data' / 'projects' / project_id
input_video_path = data_root / 'raw' / 'input.mp4'
clips_dir = data_root / 'output' / 'clips'
collections_dir = data_root / 'output' / 'collections'

# 确保目录存在
clips_dir.mkdir(parents=True, exist_ok=True)
collections_dir.mkdir(parents=True, exist_ok=True)

print(f'📹 视频文件: {input_video_path}')
print(f'📁 切片目录: {clips_dir}')

# 创建视频处理器
processor = VideoProcessor(clips_dir=str(clips_dir), collections_dir=str(collections_dir))

# 测试切片数据（来自 step4 的输出）
clips_data = [
    {'id': '1', 'title': '测试片段1', 'start_time': '00:00:00.210', 'end_time': '00:00:07.104'},
    {'id': '2', 'title': '测试片段2', 'start_time': '00:00:07.104', 'end_time': '00:00:15.497'},
    {'id': '3', 'title': '测试片段3', 'start_time': '00:00:15.497', 'end_time': '00:00:42.773'},
]

# 禁用静音处理来测试
print('\n🚀 开始提取切片（禁用静音处理）...')
successful_clips = processor.batch_extract_clips(input_video_path, clips_data, apply_silence_processing=False)

print(f'\n✅ 提取完成！成功生成 {len(successful_clips)} 个切片')
for clip in successful_clips:
    print(f'   - {clip.name}')
