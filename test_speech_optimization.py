#!/usr/bin/env python3
"""
语音转写优化测试脚本
用于验证GPU加速和模型量化的效果
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import time
from pathlib import Path
from backend.utils.speech_recognizer import (
    _detect_compute_device,
    get_available_speech_recognition_methods,
    generate_subtitle_for_video,
    SpeechRecognitionError
)

def test_device_detection():
    """测试设备自动检测功能"""
    print("=" * 60)
    print("测试1: 设备自动检测")
    print("=" * 60)
    
    # 测试默认检测
    device = _detect_compute_device()
    print(f"• 自动检测设备: {device}")
    
    # 测试环境变量覆盖
    original_device = os.environ.get("SPEECH_DEVICE")
    
    os.environ["SPEECH_DEVICE"] = "cpu"
    device_cpu = _detect_compute_device()
    print(f"• 设置 SPEECH_DEVICE=cpu: {device_cpu}")
    
    os.environ["SPEECH_DEVICE"] = "cuda"
    device_cuda = _detect_compute_device()
    print(f"• 设置 SPEECH_DEVICE=cuda: {device_cuda}")
    
    # 恢复原始值
    if original_device is not None:
        os.environ["SPEECH_DEVICE"] = original_device
    elif "SPEECH_DEVICE" in os.environ:
        del os.environ["SPEECH_DEVICE"]
    
    return True

def test_available_methods():
    """测试可用语音识别方法检测"""
    print("\n" + "=" * 60)
    print("测试2: 可用方法检测")
    print("=" * 60)
    
    methods = get_available_speech_recognition_methods()
    
    print("可用的语音识别方法:")
    for method, available in methods.items():
        status = "✅" if available else "❌"
        print(f"  {status} {method}")
    
    return True

def test_quantization_config():
    """测试量化配置"""
    print("\n" + "=" * 60)
    print("测试3: 量化配置")
    print("=" * 60)
    
    # 测试量化配置
    os.environ["FUNASR_QUANTIZE"] = "true"
    print(f"• FUNASR_QUANTIZE=true: 启用INT8量化")
    
    os.environ["FUNASR_QUANTIZE"] = "false"
    print(f"• FUNASR_QUANTIZE=false: 禁用量化（全精度）")
    
    # 恢复默认值
    os.environ["FUNASR_QUANTIZE"] = "true"
    
    return True

def test_speech_recognition(test_video_path: str = None):
    """测试实际语音识别（需要视频文件）"""
    print("\n" + "=" * 60)
    print("测试4: 实际语音识别")
    print("=" * 60)
    
    # 检查是否提供了测试视频
    if test_video_path is None:
        print("⚠️ 未提供测试视频路径，跳过实际识别测试")
        print("   使用方法: python test_speech_optimization.py <video_path>")
        return True
    
    video_path = Path(test_video_path)
    if not video_path.exists():
        print(f"❌ 测试视频不存在: {video_path}")
        return False
    
    print(f"• 测试视频: {video_path}")
    print(f"• 文件大小: {video_path.stat().st_size / (1024 * 1024):.2f} MB")
    
    # 测试识别
    try:
        start_time = time.time()
        
        # 设置为CPU模式进行测试（避免首次加载时间干扰）
        os.environ["SPEECH_DEVICE"] = "cpu"
        
        output_path = video_path.parent / f"{video_path.stem}_test.srt"
        result_path = generate_subtitle_for_video(
            video_path,
            output_path,
            method="funasr",
            language="zh"
        )
        
        elapsed = time.time() - start_time
        
        print(f"✅ 识别成功")
        print(f"• 输出文件: {result_path}")
        print(f"• 耗时: {elapsed:.2f}秒")
        
        # 清理测试文件
        if result_path.exists():
            result_path.unlink()
        
    except SpeechRecognitionError as e:
        print(f"❌ 识别失败: {e}")
        return False
    
    return True

def main():
    """主测试函数"""
    print("=" * 70)
    print("语音转写优化测试脚本")
    print("=" * 70)
    
    tests = [
        ("设备检测", test_device_detection),
        ("可用方法", test_available_methods),
        ("量化配置", test_quantization_config),
    ]
    
    # 如果提供了视频路径，添加实际识别测试
    if len(sys.argv) > 1:
        tests.append(("实际识别", lambda: test_speech_recognition(sys.argv[1])))
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            if result:
                passed += 1
                print(f"\n✓ {test_name} 测试通过")
            else:
                print(f"\n✗ {test_name} 测试失败")
        except Exception as e:
            print(f"\n✗ {test_name} 测试异常: {e}")
    
    print("\n" + "=" * 70)
    print(f"测试总结: {passed}/{total} 通过")
    print(f"成功率: {(passed / total * 100):.1f}%")
    print("=" * 70)
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
