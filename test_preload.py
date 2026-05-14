#!/usr/bin/env python3
"""
模型预加载测试脚本
验证预加载功能是否正常工作
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import time
import asyncio

async def test_preload():
    """测试模型预加载"""
    print("=" * 70)
    print("模型预加载测试")
    print("=" * 70)
    
    # 设置环境变量
    os.environ["SPEECH_DEVICE"] = "cpu"
    os.environ["FUNASR_QUANTIZE"] = "true"
    
    # 导入预加载函数
    from backend.main import preload_speech_models
    
    print("\n1. 测试预加载功能...")
    print("-" * 50)
    
    start_time = time.time()
    await preload_speech_models()
    elapsed = time.time() - start_time
    
    print(f"\n✓ 预加载完成，总耗时: {elapsed:.2f}秒")
    
    # 验证模型是否已加载
    print("\n2. 验证模型缓存...")
    from backend.utils.speech_recognizer import _FUNASR_MODEL_CACHE
    
    if _FUNASR_MODEL_CACHE:
        print(f"✅ FunASR模型缓存已填充: {list(_FUNASR_MODEL_CACHE.keys())}")
    else:
        print("❌ FunASR模型缓存为空")
    
    # 测试首次调用速度（应该很快，因为模型已预加载）
    print("\n3. 测试首次调用速度...")
    
    # 创建测试音频
    import tempfile
    from pathlib import Path
    import subprocess
    
    test_audio = Path(tempfile.mkdtemp()) / "test.wav"
    cmd = ['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=16000:cl=mono:d=10', '-y', str(test_audio)]
    subprocess.run(cmd, capture_output=True)
    
    from backend.utils.speech_recognizer import generate_subtitle_for_video
    
    start_time = time.time()
    try:
        output_path = test_audio.parent / "output.srt"
        generate_subtitle_for_video(test_audio, output_path, method="funasr")
        elapsed = time.time() - start_time
        print(f"✅ 首次调用成功，耗时: {elapsed:.2f}秒")
        
        # 清理
        if output_path.exists():
            output_path.unlink()
    except Exception as e:
        print(f"❌ 首次调用失败: {e}")
    
    # 清理测试文件
    if test_audio.exists():
        test_audio.unlink()
        test_audio.parent.rmdir()
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(test_preload())
