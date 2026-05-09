
import sys
import subprocess
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

video_path = Path(r'e:\ClipProject\autoclip-main1\autoclip-main\data\projects\7142000a-957a-4dcf-89e6-7c8a124bb8c3\raw\input.mp4')

print("=== 测试1: 检查ffmpeg ===")
try:
    result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
    print(f"ffmpeg 成功! returncode: {result.returncode}")
except Exception as e:
    print(f"ffmpeg 失败: {e}")

print("\n=== 测试2: 检查ffprobe ===")
try:
    result = subprocess.run(['ffprobe', '-version'], capture_output=True, text=True, timeout=5)
    print(f"ffprobe 成功! returncode: {result.returncode}")
except Exception as e:
    print(f"ffprobe 失败: {e}")

print("\n=== 测试3: 查看视频时长 ===")
try:
    duration_cmd = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(video_path)
    ]
    result = subprocess.run(duration_cmd, capture_output=True, text=True, timeout=30)
    print(f"duration stdout: '{result.stdout}'")
    print(f"duration stderr: '{result.stderr}'")
    print(f"returncode: {result.returncode}")
except Exception as e:
    print(f"获取时长失败: {e}")

print("\n=== 测试4: 检查是否能找到numpy ===")
try:
    import numpy as np
    print(f"numpy 可用! 版本: {np.__version__}")
except Exception as e:
    print(f"numpy 不可用: {e}")
