"""
FunASR 集成测试脚本
测试热词校验、模型缓存和完整识别流程
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_01_module_imports():
    """测试1：模块导入"""
    print("\n" + "="*60)
    print("测试1：模块导入")
    print("="*60)

    try:
        from backend.utils.speech_recognizer import (
            SpeechRecognitionConfig,
            SpeechRecognitionMethod,
            LanguageCode,
            _validate_hotword,
            _get_funasr_model_pair,
            clear_funasr_model_cache,
            _funasr_model_cache
        )
        print("✅ 所有模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_02_hotword_validation():
    """测试2：热词校验"""
    print("\n" + "="*60)
    print("测试2：热词校验")
    print("="*60)

    from backend.utils.speech_recognizer import _validate_hotword

    test_cases = [
        ("正常热词", "人工智能 AI 语音识别", True, None),
        ("空热词", "", True, ""),
        ("超长热词", "a" * 501, False, "长度不能超过500"),
        ("过多词汇", " ".join([f"词{i}" for i in range(51)]), False, "热词数量不能超过50"),
        ("危险字符<", "测试<标签", False, "非法字符"),
        ("危险字符>", "测试>标签", False, "非法字符"),
        ("危险字符&", "测试&符号", False, "非法字符"),
        ("危险字符;", "测试;分号", False, "非法字符"),
        ("危险字符|", "测试|管道", False, "非法字符"),
        ("多字符危险", "a<b>c&d;", False, "非法字符"),
    ]

    all_passed = True
    for name, hotword, should_pass, expected_msg in test_cases:
        try:
            result = _validate_hotword(hotword)
            if should_pass:
                print(f"✅ {name}: 通过校验 (结果: '{result}')")
            else:
                print(f"❌ {name}: 应该失败但通过了")
                all_passed = False
        except ValueError as e:
            if not should_pass:
                if expected_msg and expected_msg in str(e):
                    print(f"✅ {name}: 正确拒绝 ({e})")
                elif expected_msg is None:
                    print(f"✅ {name}: 通过但无预期消息 ({e})")
                else:
                    print(f"❌ {name}: 错误消息不匹配 ({e})")
                    all_passed = False
            else:
                print(f"❌ {name}: 不应失败但失败了 ({e})")
                all_passed = False
        except Exception as e:
            print(f"❌ {name}: 意外错误 ({e})")
            all_passed = False

    return all_passed


def test_03_model_cache():
    """测试3：模型缓存机制"""
    print("\n" + "="*60)
    print("测试3：模型缓存机制")
    print("="*60)

    from backend.utils.speech_recognizer import (
        _funasr_model_cache,
        _get_funasr_model_pair,
        clear_funasr_model_cache
    )

    try:
        # 清理缓存
        clear_funasr_model_cache()
        print(f"缓存清理后状态: {len(_funasr_model_cache)} 个缓存项")

        # 首次加载（不带说话人）
        print("\n首次加载模型 (spk=False)...")
        model_pair1 = _get_funasr_model_pair(use_speaker=False)
        print(f"缓存项数量: {len(_funasr_model_cache)}")
        print(f"缓存键列表: {list(_funasr_model_cache.keys())}")

        # 再次获取同一配置（应该命中缓存）
        print("\n再次获取模型 (spk=False，命中缓存)...")
        model_pair2 = _get_funasr_model_pair(use_speaker=False)
        print(f"缓存项数量: {len(_funasr_model_cache)}")

        # 验证是同一对象
        if model_pair1 is model_pair2:
            print("✅ 缓存命中验证通过：返回同一对象")
        else:
            print("❌ 缓存命中验证失败：返回不同对象")
            return False

        # 加载带说话人的模型
        print("\n首次加载模型 (spk=True)...")
        model_pair3 = _get_funasr_model_pair(use_speaker=True)
        print(f"缓存项数量: {len(_funasr_model_cache)}")
        print(f"缓存键列表: {list(_funasr_model_cache.keys())}")

        # 验证不带说话人的模型没有被覆盖
        model_pair4 = _get_funasr_model_pair(use_speaker=False)
        if model_pair1 is model_pair4:
            print("✅ spk=False 模型未被覆盖")
        else:
            print("❌ spk=False 模型被覆盖")
            return False

        # 清理缓存
        clear_funasr_model_cache()
        print(f"\n清理后缓存项数量: {len(_funasr_model_cache)}")

        print("\n✅ 模型缓存机制测试通过")
        return True

    except Exception as e:
        print(f"❌ 模型缓存测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_04_funasr_basic():
    """测试4：FunASR 基础功能测试（需要视频文件）"""
    print("\n" + "="*60)
    print("测试4：FunASR 基础功能测试")
    print("="*60)

    try:
        from funasr import AutoModel
        print("FunASR 版本检查...")

        # 测试模型加载
        print("\n加载 paraformer-zh 模型...")
        model = AutoModel(
            model="paraformer-zh",
            vad_model="fsmn-vad",
            punc_model="ct-punc",
            device="cpu"
        )
        print("✅ paraformer-zh 模型加载成功")

        print("\n加载 fa-zh 模型...")
        model_ts = AutoModel(model="fa-zh", device="cpu")
        print("✅ fa-zh 模型加载成功")

        return True

    except Exception as e:
        print(f"❌ FunASR 基础测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_05_config_dataclass():
    """测试5：配置数据类测试"""
    print("\n" + "="*60)
    print("测试5：配置数据类测试")
    print("="*60)

    try:
        from backend.utils.speech_recognizer import (
            SpeechRecognitionConfig,
            SpeechRecognitionMethod,
            LanguageCode
        )

        # 测试默认配置
        config1 = SpeechRecognitionConfig()
        print(f"默认配置 hotword: '{config1.hotword}'")
        print(f"默认配置 enable_speaker_diarization: {config1.enable_speaker_diarization}")

        # 测试自定义配置
        config2 = SpeechRecognitionConfig(
            method=SpeechRecognitionMethod.FUNASR,
            language=LanguageCode.AUTO,
            enable_speaker_diarization=True,
            hotword="测试热词"
        )
        print(f"自定义配置 hotword: '{config2.hotword}'")
        print(f"自定义配置 enable_speaker_diarization: {config2.enable_speaker_diarization}")

        # 测试校验
        from backend.utils.speech_recognizer import _validate_hotword
        validated = _validate_hotword(config2.hotword)
        print(f"热词校验结果: '{validated}'")

        print("\n✅ 配置数据类测试通过")
        return True

    except Exception as e:
        print(f"❌ 配置数据类测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_06_speech_recognition_api():
    """测试6：语音识别 API 导入测试"""
    print("\n" + "="*60)
    print("测试6：语音识别 API 导入测试")
    print("="*60)

    try:
        from backend.api.v1.speech_recognition import (
            router,
            SpeechRecognitionRequest,
            SpeechRecognitionStatus,
            SpeechRecognitionConfigUpdate
        )

        # 检查 hotword 字段
        req = SpeechRecognitionRequest(method="funasr", hotword="测试热词")
        print(f"SpeechRecognitionRequest hotword: '{req.hotword}'")

        update = SpeechRecognitionConfigUpdate(hotword="更新热词")
        print(f"SpeechRecognitionConfigUpdate hotword: '{update.hotword}'")

        print("\n✅ API 导入测试通过")
        return True

    except Exception as e:
        print(f"❌ API 导入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_07_pipeline_adapter():
    """测试7：Pipeline 适配器测试"""
    print("\n" + "="*60)
    print("测试7：Pipeline 适配器测试")
    print("="*60)

    try:
        from backend.services.simple_pipeline_adapter import SimplePipelineAdapter

        # 检查方法存在
        adapter = SimplePipelineAdapter(project_id="test", task_id="test")

        # 检查 _get_project_hotword 方法
        if hasattr(adapter, '_get_project_hotword'):
            print("✅ _get_project_hotword 方法存在")
        else:
            print("❌ _get_project_hotword 方法不存在")
            return False

        # 调用测试
        hotword = adapter._get_project_hotword()
        print(f"获取热词结果: '{hotword}'")

        print("\n✅ Pipeline 适配器测试通过")
        return True

    except Exception as e:
        print(f"❌ Pipeline 适配器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "#"*60)
    print("# FunASR 集成测试")
    print("#"*60)

    results = []

    # 测试1：模块导入
    results.append(("模块导入", test_01_module_imports()))

    # 测试2：热词校验
    results.append(("热词校验", test_02_hotword_validation()))

    # 测试3：模型缓存
    results.append(("模型缓存", test_03_model_cache()))

    # 测试4：配置数据类
    results.append(("配置数据类", test_05_config_dataclass()))

    # 测试5：API
    results.append(("API 导入", test_06_speech_recognition_api()))

    # 测试6：Pipeline
    results.append(("Pipeline 适配器", test_07_pipeline_adapter()))

    # 测试7：FunASR 基础功能（可选，需要网络）
    results.append(("FunASR 基础功能", test_04_funasr_basic()))

    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)

    passed = 0
    failed = 0
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\n总计: {passed} 通过, {failed} 失败")

    if failed == 0:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  {failed} 个测试失败，请检查")
        return 1


if __name__ == "__main__":
    exit(main())
