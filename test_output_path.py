import sys
sys.path.insert(0, r'E:\ClipProject\autoclip-main1\autoclip-main')
from backend.utils.video_processor import VideoProcessor
from pathlib import Path

project_id = 'b0d4c113-3a61-4df7-a7f0-cc03759c3dc6'
input_video = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\raw\input.mp4')
clips_dir = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\output\clips')

# 模拟 clips_with_titles（数字id）
clips_with_titles = [
    {'id': 1, 'generated_title': '《食神》里‘尸神’的真谛：人人皆可成神，靠的是这颗能当乒乓球打的爆浆牛肉丸', 'start_time': '00:00:00,210', 'end_time': '00:01:34,328'},
]

# 创建 clips_data
clips_data = []
for clip in clips_with_titles:
    clips_data.append({
        'id': clip['id'],
        'title': clip.get('generated_title', f"片段_{clip['id']}"),
        'start_time': clip['start_time'],
        'end_time': clip['end_time']
    })

# 模拟生成的输出路径
clip_data = clips_data[0]
safe_title = VideoProcessor.sanitize_filename(clip_data['title'])
output_path = clips_dir / f"{clip_data['id']}_{safe_title}.mp4"

print(f"预期输出路径: {output_path}")
print(f"文件是否存在: {output_path.exists()}")

# 获取实际时长
if output_path.exists():
    actual_duration = VideoProcessor.get_video_duration(output_path)
    print(f"实际视频时长: {actual_duration}")

# 检查是否有其他同名文件
print("\nclips_dir 中以 '1_' 开头的文件:")
for file in clips_dir.glob('1_*.mp4'):
    print(f"  {file.name}")
    duration = VideoProcessor.get_video_duration(file)
    print(f"    时长: {duration}")
