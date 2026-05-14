import subprocess
from pathlib import Path

# 检查 ffprobe 是否可用
clips_dir = Path(r'E:\ClipProject\autoclip-main1\autoclip-main\data\projects\b0d4c113-3a61-4df7-a7f0-cc03759c3dc6\output\clips')

# 列出 clips 目录下的 mp4 文件
mp4_files = list(clips_dir.glob('*.mp4'))
print(f'找到 {len(mp4_files)} 个 mp4 文件')

if mp4_files:
    video_path = mp4_files[0]
    print(f'测试文件: {video_path}')

    # 尝试调用 ffprobe
    cmd = ['ffprobe', '-v', 'error', '-show_entries',
           'format=duration', '-of',
           'default=noprint_wrappers=1:nokey=1', str(video_path)]

    print(f'命令: {" ".join(cmd)}')

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=10)
        print(f'返回码: {result.returncode}')
        print(f'stdout: {result.stdout}')
        print(f'stderr: {result.stderr}')

        if result.returncode == 0 and result.stdout.strip():
            duration = float(result.stdout.strip())
            print(f'视频时长: {duration:.3f}s')
    except Exception as e:
        print(f'错误: {e}')
