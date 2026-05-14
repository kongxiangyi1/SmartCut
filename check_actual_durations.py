import subprocess
from pathlib import Path

project_id = 'b0d4c113-3a61-4df7-a7f0-cc03759c3dc6'
clips_dir = Path(fr'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\{project_id}\output\clips')

print('对比实际视频时长与数据库记录:')
print('=' * 70)

for clip_file in sorted(clips_dir.glob('*.mp4')):
    cmd = ['ffprobe', '-v', 'error', '-show_entries',
           'format=duration', '-of',
           'default=noprint_wrappers=1:nokey=1', str(clip_file)]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
    actual_duration = float(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else 0

    print(f'{clip_file.name}')
    print(f'  实际时长: {actual_duration:.3f}s')
