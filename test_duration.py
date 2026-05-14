import sys
sys.path.insert(0, r'E:\ClipProject\autoclip-main1\autoclip-main')
from backend.utils.video_processor import VideoProcessor
from pathlib import Path

project_id = 'b0d4c113-3a61-4df7-a7f0-cc03759c3dc6'
clips_dir = Path(rf'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\output\clips')

print('测试 get_video_duration:')
print('=' * 50)

for clip_file in sorted(clips_dir.glob('*.mp4'))[:2]:  # 只测试前2个
    print(f'\n文件: {clip_file.name}')
    actual_duration = VideoProcessor.get_video_duration(clip_file)
    print(f'get_video_duration 返回: {actual_duration}')
    print(f'get_video_duration 返回类型: {type(actual_duration)}')
    
    # 手动验证
    import subprocess
    import shutil
    import re
    
    ffprobe_path = shutil.which('ffprobe')
    if ffprobe_path:
        cmd = [ffprobe_path, '-v', 'error', '-show_entries',
               'format=duration', '-of',
               'default=noprint_wrappers=1:nokey=1', str(clip_file)]
        result = subprocess.run(cmd, capture_output=True, text=True,
                              encoding='utf-8', errors='ignore')
        if result.returncode == 0 and result.stdout.strip():
            print(f'ffprobe 直接调用: {float(result.stdout.strip())}')
