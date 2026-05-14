#!/usr/bin/env python3
"""
语音识别性能对比测试脚本
对比 bcut_asr、whisper_local、funasr 三种方法的处理用时
"""

import sys
import os
import time
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.utils.speech_recognizer import (
    generate_subtitle_for_video,
    get_available_speech_recognition_methods,
    SpeechRecognitionError
)

def create_test_audio(duration_seconds: int = 60) -> Path:
    """创建测试用音频文件"""
    import subprocess
    
    test_audio = Path(tempfile.mkdtemp()) / "test_audio.wav"
    
    # 使用ffmpeg生成静音音频（用于测试）
    cmd = [
        'ffmpeg',
        '-f', 'lavfi',
        '-i', f'anullsrc=r=16000:cl=mono:d={duration_seconds}',
        '-y',
        str(test_audio)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"无法创建测试音频: {result.stderr}")
    
    return test_audio

def test_single_method(method: str, video_path: Path, output_dir: Path) -> dict:
    """测试单个语音识别方法"""
    result = {
        "method": method,
        "success": False,
        "duration": 0.0,
        "error": None,
        "output_size": 0
    }
    
    try:
        output_path = output_dir / f"output_{method}.srt"
        
        start_time = time.time()
        
        # 设置环境变量确保使用正确的设备
        os.environ["SPEECH_DEVICE"] = "cpu"
        
        # 执行识别
        generate_subtitle_for_video(
            video_path,
            output_path,
            method=method,
            language="zh"
        )
        
        elapsed = time.time() - start_time
        
        result["success"] = True
        result["duration"] = elapsed
        result["output_size"] = output_path.stat().st_size if output_path.exists() else 0
        
        # 清理输出文件
        if output_path.exists():
            output_path.unlink()
        
    except SpeechRecognitionError as e:
        result["error"] = str(e)
    except Exception as e:
        result["error"] = f"意外错误: {e}"
    
    return result

def run_performance_test(test_audio: Path, iterations: int = 3):
    """运行性能测试"""
    print("=" * 70)
    print("语音识别性能对比测试")
    print("=" * 70)
    print(f"测试音频: {test_audio}")
    print(f"文件大小: {test_audio.stat().st_size / (1024 * 1024):.2f} MB")
    print(f"测试次数: {iterations}")
    print("-" * 70)
    
    # 获取可用方法
    available_methods = get_available_speech_recognition_methods()
    
    # 选择要测试的方法
    methods_to_test = ["funasr", "whisper_local", "bcut_asr"]
    
    results = []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        
        for method in methods_to_test:
            if not available_methods.get(method, False):
                print(f"⚠️ {method} 不可用，跳过")
                continue
            
            print(f"\n正在测试: {method}")
            print("-" * 50)
            
            method_results = []
            
            for i in range(iterations):
                print(f"  迭代 {i+1}/{iterations}...", end=" ")
                
                result = test_single_method(method, test_audio, output_dir)
                
                if result["success"]:
                    print(f"成功 ({result['duration']:.2f}秒)")
                else:
                    print(f"失败: {result['error']}")
                
                method_results.append(result)
            
            # 计算统计信息
            successful_results = [r for r in method_results if r["success"]]
            
            if successful_results:
                avg_duration = sum(r["duration"] for r in successful_results) / len(successful_results)
                min_duration = min(r["duration"] for r in successful_results)
                max_duration = max(r["duration"] for r in successful_results)
                
                results.append({
                    "method": method,
                    "success_count": len(successful_results),
                    "total_count": iterations,
                    "avg_duration": avg_duration,
                    "min_duration": min_duration,
                    "max_duration": max_duration,
                    "success_rate": (len(successful_results) / iterations) * 100
                })
                
                print(f"  平均耗时: {avg_duration:.2f}秒")
                print(f"  最快: {min_duration:.2f}秒")
                print(f"  最慢: {max_duration:.2f}秒")
                print(f"  成功率: {results[-1]['success_rate']:.1f}%")
            else:
                print(f"  所有测试均失败")
    
    return results

def print_results_summary(results: list):
    """打印测试结果汇总"""
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    
    if not results:
        print("没有可用的测试结果")
        return
    
    # 按平均耗时排序
    results.sort(key=lambda x: x["avg_duration"])
    
    print(f"{'方法':<15} {'成功率':<8} {'平均耗时':<10} {'最快':<10} {'最慢':<10}")
    print("-" * 70)
    
    for i, result in enumerate(results):
        print(f"{result['method']:<15} "
              f"{result['success_rate']:<8.1f}% "
              f"{result['avg_duration']:<10.2f}s "
              f"{result['min_duration']:<10.2f}s "
              f"{result['max_duration']:<10.2f}s")
    
    print("\n性能排名:")
    for i, result in enumerate(results):
        print(f"  {i+1}. {result['method']} (平均 {result['avg_duration']:.2f}秒)")
    
    # 计算相对性能
    fastest = results[0]["avg_duration"]
    print("\n相对性能对比（以最快为基准）:")
    for result in results:
        ratio = result["avg_duration"] / fastest
        print(f"  {result['method']}: {ratio:.2f}x 慢于 {results[0]['method']}")

def main():
    """主函数"""
    # 检查是否提供了测试视频路径
    if len(sys.argv) > 1:
        test_path = Path(sys.argv[1])
        if not test_path.exists():
            print(f"错误: 文件不存在 {test_path}")
            sys.exit(1)
        print(f"使用提供的测试文件: {test_path}")
    else:
        # 创建测试音频
        print("创建测试音频...")
        test_path = create_test_audio(duration_seconds=30)  # 30秒测试音频
        print(f"创建测试音频: {test_path}")
    
    # 运行测试
    results = run_performance_test(test_path, iterations=3)
    
    # 打印汇总
    print_results_summary(results)
    
    # 清理临时文件
    if not (len(sys.argv) > 1):
        test_path.unlink()

if __name__ == "__main__":
    main()
