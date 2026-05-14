#!/usr/bin/env python3
"""
环境检测验证脚本
用于验证 EnvironmentDetector 的各项功能是否正常工作
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.utils.environment_detector import EnvironmentDetector

def test_basic_detection():
    """测试基础检测功能"""
    print("=" * 60)
    print("测试1: 基础环境检测")
    print("=" * 60)
    
    # 测试本地环境检测
    is_local = EnvironmentDetector.is_local()
    print(f"• 本地环境: {'是' if is_local else '否'}")
    
    # 测试SSD检测
    has_ssd = EnvironmentDetector.has_ssd()
    print(f"• SSD存储: {'是' if has_ssd else '否'}")
    
    # 测试CPU计数
    cpu_count = EnvironmentDetector.get_cpu_count()
    print(f"• CPU核心数: {cpu_count}")
    
    # 测试内存检测
    memory = EnvironmentDetector.get_available_memory_gb()
    print(f"• 可用内存: {memory:.1f} GB")
    
    return True

def test_config_generation():
    """测试配置生成功能"""
    print("\n" + "=" * 60)
    print("测试2: 最优配置生成")
    print("=" * 60)
    
    config = EnvironmentDetector.get_optimal_config()
    
    print(f"环境类型: {config['environment']}")
    print(f"存储类型: {'SSD' if config['has_ssd'] else 'HDD'}")
    print(f"推荐配置描述: {config['description']}")
    print("\n详细配置参数:")
    print(f"  - chunk_size: {config['chunk_size_bytes'] / 1024 / 1024:.1f} MB")
    print(f"  - max_workers: {config['max_workers']}")
    print(f"  - use_streaming_write: {config['use_streaming_write']}")
    print(f"  - use_streaming_slice: {config['use_streaming_slice']}")
    print(f"  - use_hardlink: {config['use_hardlink']}")
    print(f"  - io_delay: {config['io_delay_seconds']}s")
    
    return True

def test_environment_summary():
    """测试环境摘要生成"""
    print("\n" + "=" * 60)
    print("测试3: 环境摘要")
    print("=" * 60)
    
    summary = EnvironmentDetector.get_environment_summary()
    print(summary)
    
    return True

def test_automated_test():
    """运行自动化测试套件"""
    print("\n" + "=" * 60)
    print("测试4: 自动化测试套件")
    print("=" * 60)
    
    results = EnvironmentDetector.test_environment_detection()
    
    print(f"\n测试时间: {results['timestamp']}")
    print("\n测试详情:")
    for test in results["tests"]:
        status = "✅" if test["result"] == "PASS" else "❌"
        print(f"{status} {test['name']}")
        if "value" in test:
            print(f"   → {test['value']}")
        if "error" in test:
            print(f"   ✗ {test['error']}")
    
    print("\n测试统计:")
    print(f"  通过: {results['summary']['passed']}/{results['summary']['total']}")
    print(f"  成功率: {results['summary']['success_rate']}")
    
    return results["summary"]["passed"] == results["summary"]["total"]

def test_environment_variable_override():
    """测试环境变量覆盖功能"""
    print("\n" + "=" * 60)
    print("测试5: 环境变量覆盖")
    print("=" * 60)
    
    # 测试手动设置环境变量
    original_env = os.environ.get("ENVIRONMENT")
    
    # 设置为 local
    os.environ["ENVIRONMENT"] = "local"
    EnvironmentDetector._reset_cache()
    is_local_manual = EnvironmentDetector.is_local()
    print(f"设置 ENVIRONMENT=local 后:")
    print(f"  • is_local = {is_local_manual} (预期: True)")
    
    # 设置为 server
    os.environ["ENVIRONMENT"] = "server"
    EnvironmentDetector._reset_cache()
    is_local_server = EnvironmentDetector.is_local()
    print(f"\n设置 ENVIRONMENT=server 后:")
    print(f"  • is_local = {is_local_server} (预期: False)")
    
    # 恢复原始值
    if original_env is not None:
        os.environ["ENVIRONMENT"] = original_env
    elif "ENVIRONMENT" in os.environ:
        del os.environ["ENVIRONMENT"]
    
    EnvironmentDetector._reset_cache()
    
    return is_local_manual == True and is_local_server == False

def main():
    """主测试函数"""
    print("=" * 70)
    print("环境检测模块验证脚本")
    print("=" * 70)
    
    tests = [
        ("基础检测", test_basic_detection),
        ("配置生成", test_config_generation),
        ("环境摘要", test_environment_summary),
        ("自动化测试", test_automated_test),
        ("环境变量覆盖", test_environment_variable_override),
    ]
    
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
