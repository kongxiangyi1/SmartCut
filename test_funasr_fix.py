"""
测试FunASR时间戳提取功能
"""
import sys
sys.path.insert(0, 'd:/Download/autoclip-main1/autoclip-main')

from backend.utils.speech_recognizer import SpeechRecognizer
from pathlib import Path

# 使用现有的项目文件进行测试
project_id = "2716cdeb-fb3e-461d-87a8-312dcf077b9f"
video_path = Path(f"d:/Download/autoclip-main1/autoclip-main/data/projects/{project_id}/raw/input.mp4")
output_srt = Path(f"d:/Download/autoclip-main1/autoclip-main/data/projects/{project_id}/metadata/test_output.srt")

if not video_path.exists():
    print(f"视频文件不存在: {video_path}")
    sys.exit(1)

# 创建语音识别器
recognizer = SpeechRecognizer()

# 测试FunASR
try:
    print("开始测试FunASR时间戳提取...")
    result = recognizer._generate_subtitle_funasr(video_path, output_srt, None)
    print(f"测试完成！输出文件: {result}")
    
    # 检查生成的SRT文件内容
    with open(output_srt, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.strip().split('\n')
        print(f"\n生成的SRT文件有 {len(lines)} 行")
        print("\n前30行内容:")
        for i, line in enumerate(lines[:30], 1):
            print(f"{i:3d}: {line}")
            
except Exception as e:
    print(f"测试失败: {e}")
    import traceback
    traceback.print_exc()
