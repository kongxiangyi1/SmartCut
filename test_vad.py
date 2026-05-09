
import sys
sys.path.insert(0, r'e:\ClipProject\autoclip-main1\autoclip-main')

from backend.utils.speech_recognizer import _generate_subtitle_by_energy_vad
from pathlib import Path

video_path = Path(r'e:\ClipProject\autoclip-main1\autoclip-main\data\projects\7142000a-957a-4dcf-89e6-7c8a124bb8c3\raw\input.mp4')
output_path = Path(r'e:\ClipProject\autoclip-main1\autoclip-main\data\projects\7142000a-957a-4dcf-89e6-7c8a124bb8c3\metadata\input.srt')

print(f"测试视频: {video_path}")
print(f"测试输出: {output_path}")

result = _generate_subtitle_by_energy_vad(video_path, output_path)

print(f"结果: {result}")

if result and result.exists():
    print("\n字幕内容（前20行）:")
    with open(result, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 20:
                break
            print(line, end='')
