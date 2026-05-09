"""
CAM++ 说话人分离专项诊断
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def diagnose_campplus_detailed():
    """详细诊断 CAM++ 说话人分离"""
    print("\n" + "="*60)
    print("CAM++ 说话人分离详细诊断")
    print("="*60)

    audio_path = Path(r"E:\直播切片项目\output\20260420_新录制\test_output\clip_001_product_0s-708s_audio.wav")

    if not audio_path.exists():
        print(f"❌ 音频文件不存在: {audio_path}")
        return False

    print(f"\n音频文件: {audio_path}")

    try:
        from funasr import AutoModel

        # 测试1：使用分离模型，不带 spk_diarization 参数
        print("\n" + "-"*40)
        print("测试1：分离模型（不带 spk_diarization）")
        print("-"*40)

        model = AutoModel(
            model="paraformer-zh",
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 60000},
            punc_model="ct-punc",
            spk_model="cam++",
            device="cpu"
        )

        print("执行识别...")
        result1 = model.generate(input=str(audio_path), batch_size_s=30)

        print_result("测试1结果", result1)

        # 测试2：使用分离模型，带 spk_diarization 参数
        print("\n" + "-"*40)
        print("测试2：分离模型（带 spk_diarization=True）")
        print("-"*40)

        try:
            result2 = model.generate(
                input=str(audio_path),
                batch_size_s=30,
                spk_diarization=True
            )
            print_result("测试2结果", result2)
        except Exception as e:
            print(f"❌ 测试2失败: {e}")

        # 测试3：使用 CAM++ 单独进行说话人分离
        print("\n" + "-"*40)
        print("测试3：CAM++ 单独进行说话人分析")
        print("-"*40)

        campplus = AutoModel(model="cam++", device="cpu")
        print("CAM++ 模型加载成功")
        print(f"CAM++ 模型输出: 待测试（需要音频特征）")

        # 测试4：使用 FunASR 官方推荐的方式
        print("\n" + "-"*40)
        print("测试4：FunASR 1.3.1 推荐方式")
        print("-"*40)

        # FunASR 1.3.1 可能使用不同的参数名
        result4 = model.generate(
            input=str(audio_path),
            batch_size_s=30,
            return_spk=True  # 尝试不同的参数
        )
        print_result("测试4结果 (return_spk=True)", result4)

        return True

    except Exception as e:
        print(f"❌ 诊断失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_result(title, result):
    """打印结果"""
    print(f"\n{title}:")
    print(f"  类型: {type(result)}")

    if not result:
        print("  结果为空")
        return

    print(f"  长度: {len(result)}")

    first = result[0]
    print(f"  第一个元素类型: {type(first)}")

    if isinstance(first, dict):
        print(f"  Keys: {first.keys()}")

        for key, value in first.items():
            if isinstance(value, list):
                print(f"\n  {key} (列表, 长度={len(value)}):")
                if value:
                    print(f"    第一个: {value[0]}")
                    if len(value) > 1:
                        print(f"    第二个: {value[1]}")
                    if len(value) > 2:
                        print(f"    ...")
            elif isinstance(value, str):
                display = value[:100] + "..." if len(value) > 100 else value
                print(f"\n  {key}: {display}")
            else:
                print(f"\n  {key}: {value}")


def diagnose_spk_model_api():
    """诊断说话人模型的 API 用法"""
    print("\n" + "="*60)
    print("诊断 FunASR 说话人 API")
    print("="*60)

    try:
        # 查看 FunASR 中 CAM++ 的用法
        from funasr import AutoModel

        print("\n查看 AutoModel 的 model 参数...")
        print("可用的说话人模型应该包括: cam++, ecapa_tdnn, resnet34等")

        # 尝试不同的模型名称
        spk_models = ["cam++", "speech_campplus_sv_zh-cn_16k-common"]

        for model_name in spk_models:
            print(f"\n尝试加载: {model_name}")
            try:
                model = AutoModel(model=model_name, device="cpu")
                print(f"  ✅ {model_name} 加载成功")
                print(f"  模型类型: {type(model)}")
            except Exception as e:
                print(f"  ❌ {model_name} 加载失败: {e}")

        return True

    except Exception as e:
        print(f"❌ 诊断失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主诊断函数"""
    print("\n" + "#"*60)
    print("# CAM++ 说话人分离专项诊断")
    print("#"*60)

    results = []

    results.append(("CAM++ API", diagnose_spk_model_api()))
    results.append(("CAM++ 详细诊断", diagnose_campplus_detailed()))

    print("\n" + "="*60)
    print("诊断结果汇总")
    print("="*60)

    for name, result in results:
        status = "✅ 完成" if result else "❌ 失败"
        print(f"{name}: {status}")

    return 0 if all(r for _, r in results) else 1


if __name__ == "__main__":
    exit(main())
