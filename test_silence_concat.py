"""
静音拼接器测试脚本
验证 silence_concat.py 模块的基本功能
"""

import sys
import os
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from backend.utils.silence_concat import SilenceConcat, SpeechSegment


def test_speech_segment():
    """测试 SpeechSegment 数据类"""
    print("测试 SpeechSegment 数据类...")
    seg = SpeechSegment(start=10.5, end=25.3)
    assert abs(seg.duration - 14.8) < 0.01, "持续时间计算错误"
    print("  ✅ SpeechSegment 测试通过")


def test_merge_segments():
    """测试区间合并功能"""
    print("测试区间合并功能...")
    
    concat = SilenceConcat(short_silence_keep=1.0)
    
    # 测试用例1：相邻区间（间隔0.5秒，应合并）
    segs1 = [
        SpeechSegment(0, 5),
        SpeechSegment(5.5, 10),
        SpeechSegment(10.3, 15)
    ]
    merged1 = concat.merge_segments(segs1)
    assert len(merged1) == 1, f"应该合并为1个区间，实际得到{len(merged1)}个"
    assert merged1[0].start == 0, "合并后开始时间错误"
    assert merged1[0].end == 15, "合并后结束时间错误"
    print("  ✅ 相邻区间合并测试通过")
    
    # 测试用例2：间隔较大（间隔2秒，不应合并）
    segs2 = [
        SpeechSegment(0, 5),
        SpeechSegment(7, 10),  # 间隔2秒
        SpeechSegment(11, 15)
    ]
    merged2 = concat.merge_segments(segs2)
    assert len(merged2) == 2, f"应该合并为2个区间，实际得到{len(merged2)}个"
    print("  ✅ 间隔较大测试通过")


def test_detect_speech_segments():
    """测试语音检测功能"""
    print("测试语音检测功能...")
    
    concat = SilenceConcat()
    
    # 创建一个临时音频文件测试
    import tempfile
    import wave
    import numpy as np
    
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        temp_path = Path(f.name)
    
    # 创建一个简单的音频文件（包含静音和语音）
    sample_rate = 16000
    duration = 10  # 10秒
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    
    # 创建有语音的音频（简单的正弦波）
    audio_data = np.zeros_like(t)
    # 在2-4秒和6-8秒添加语音
    audio_data[int(2 * sample_rate):int(4 * sample_rate)] = np.sin(2 * np.pi * 440 * t[int(2 * sample_rate):int(4 * sample_rate)]) * 32767
    audio_data[int(6 * sample_rate):int(8 * sample_rate)] = np.sin(2 * np.pi * 880 * t[int(6 * sample_rate):int(8 * sample_rate)]) * 32767
    
    # 写入WAV文件
    with wave.open(str(temp_path), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.astype(np.int16).tobytes())
    
    # 测试检测
    segments = concat.detect_speech_segments(temp_path)
    print(f"  检测到 {len(segments)} 个语音区间")
    
    # 清理
    temp_path.unlink()
    
    print("  ✅ 语音检测测试完成")


def test_import():
    """测试模块导入"""
    print("测试模块导入...")
    
    # 测试 silence_concat 模块导入
    from backend.utils import silence_concat
    assert silence_concat is not None, "silence_concat模块导入失败"
    
    # 测试全局实例
    assert hasattr(silence_concat, 'silence_concat'), "全局实例不存在"
    assert isinstance(silence_concat.silence_concat, SilenceConcat), "全局实例类型错误"
    
    print("  ✅ 模块导入测试通过")


def test_video_processor_integration():
    """测试与video_processor的集成"""
    print("测试与video_processor的集成...")
    
    from backend.utils import video_processor
    assert hasattr(video_processor, 'silence_concat_available'), "silence_concat_available标志不存在"
    
    print("  ✅ video_processor集成测试通过")


def main():
    """运行所有测试"""
    print("=" * 60)
    print("静音拼接器测试套件")
    print("=" * 60)
    
    try:
        test_import()
        test_speech_segment()
        test_merge_segments()
        test_detect_speech_segments()
        test_video_processor_integration()
        
        print("\n" + "=" * 60)
        print("✅ 所有测试通过！")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
