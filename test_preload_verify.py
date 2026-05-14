#!/usr/bin/env python3
"""
模型预加载验证测试
验证预加载后首次调用是否更快
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import time
import tempfile
import subprocess
from pathlib import Path

def create_test_audio(duration: int = 10) -> Path:
    """创建测试音频"""
    temp_dir = Path(tempfile.mkdtemp())
    audio_path = temp_dir / "test.wav"
    
    cmd = [
        'ffmpeg', '-f', 'lavfi', 
        '-i', f'anullsrc=r=16000:cl=mono:d={duration}', 
        '-y', str(audio_path)
    ]
    subprocess.run(cmd, capture_output=True)
    
    return audio_path

def test_preload_effect():
    """测试预加载效果"""
    print("=" * 70)
    print("模型预加载效果验证")
    print("=" * 70)
    
    # 设置环境变量
    os.environ["SPEECH_DEVICE"] = "cpu"
    os.environ["FUNASR_QUANTIZE"] = "true"
    
    # 创建测试音频
    test_audio = create_test_audio(5)  # 5秒静音音频
    print(f"\n测试音频: {test_audio}")
    
    from backend.utils.speech_recognizer import generate_subtitle_for_video
    
    # 第一次调用（可能需要加载模型）
    print("\n1. 第一次调用（可能需要加载模型）:")
    start_time = time.time()
    output1 = test_audio.parent / "output1.srt"
    try:
        generate_subtitle_for_video(test_audio, output1, method="funasr")
        elapsed1 = time.time() - start_time
        print(f"   耗时: {elapsed1:.2f}秒")
        output1.unlink()
    except Exception as e:
        print(f"   失败: {e}")
        return
    
    # 第二次调用（模型应该已缓存）
    print("\n2. 第二次调用（模型已缓存）:")
    start_time = time.time()
    output2 = test_audio.parent / "output2.srt"
    try:
        generate_subtitle_for_video(test_audio, output2, method="funasr")
        elapsed2 = time.time() - start_time
        print(f"   耗时: {elapsed2:.2f}秒")
        output2.unlink()
    except Exception as e:
        print(f"   失败: {e}")
        return
    
    # 计算加速比
    print("\n" + "=" * 70)
    print("测试结果")
    print("=" * 70)
    print(f"第一次调用: {elapsed1:.2f}秒")
    print(f"第二次调用: {elapsed2:.2f}秒")
    
    if elapsed2 > 0 and elapsed1 > elapsed2:
        speedup = elapsed1 / elapsed2
        print(f"加速比: {speedup:.1f}x")
        print("✅ 模型缓存有效！")
    else:
        print("❌ 模型缓存未生效或第一次调用已很快")
    
    # 清理
    test_audio.unlink()
    try:
        test_audio.parent.rmdir()
    except:
        pass

if __name__ == "__main__":
    test_preload_effect()
