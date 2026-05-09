"""
FunASR fa-zh 时间戳和 CAM++ 说话人诊断脚本
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def diagnose_fa_zh_timestamp():
    """诊断 fa-zh 时间戳问题"""
    print("\n" + "="*60)
    print("诊断1：fa-zh 时间戳模型")
    print("="*60)

    try:
        from funasr import AutoModel
        import numpy as np

        # 加载 fa-zh 模型
        print("\n加载 fa-zh 模型...")
        model_ts = AutoModel(model="fa-zh", device="cpu")
        print("✅ fa-zh 模型加载成功")

        # 查找测试音频
        audio_path = Path(r"E:\直播切片项目\output\20260420_新录制\test_output\clip_001_product_0s-708s_audio.wav")

        if not audio_path.exists():
            print(f"❌ 音频文件不存在: {audio_path}")
            return False

        print(f"\n音频文件: {audio_path}")
        print(f"文件大小: {audio_path.stat().st_size / (1024*1024):.2f} MB")

        # 准备文本
        text_with_punc = "只要用心，人人都可以做尸神，这才是尸神的真谛。我希望这部电影你重新看一遍，这是我拉黑你之前给你的忠告。"

        text_file = audio_path.parent / "temp_text.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text_with_punc)

        print(f"\n文本内容: {text_with_punc}")
        print(f"文本文件: {text_file}")

        # 调用 fa-zh
        print("\n调用 fa-zh 模型...")
        result = model_ts.generate(
            input=(str(audio_path), str(text_file)),
            data_type=("sound", "text")
        )

        print(f"\n返回类型: {type(result)}")
        print(f"返回长度: {len(result) if result else 0}")

        if result and len(result) > 0:
            print(f"\n第一个元素类型: {type(result[0])}")

            if isinstance(result[0], dict):
                print(f"Keys: {result[0].keys()}")
                for key, value in result[0].items():
                    if isinstance(value, list):
                        print(f"\n{key} (列表，长度 {len(value)}):")
                        if len(value) > 0:
                            print(f"  第一个元素类型: {type(value[0])}")
                            if isinstance(value[0], dict):
                                print(f"  第一个元素 Keys: {value[0].keys()}")
                                print(f"  第一个元素内容: {value[0]}")
                            else:
                                print(f"  前3个元素: {value[:3]}")
                    else:
                        print(f"\n{key}: {value}")
            elif isinstance(result[0], list):
                print(f"列表内容 (前3个): {result[0][:3] if len(result[0]) > 3 else result[0]}")

        # 清理
        if text_file.exists():
            text_file.unlink()

        return True

    except Exception as e:
        print(f"❌ fa-zh 诊断失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def diagnose_campplus_speaker():
    """诊断 CAM++ 说话人标签问题"""
    print("\n" + "="*60)
    print("诊断2：CAM++ 说话人标签")
    print("="*60)

    try:
        from funasr import AutoModel

        # 查找测试音频
        audio_path = Path(r"E:\直播切片项目\output\20260420_新录制\test_output\clip_001_product_0s-708s_audio.wav")

        if not audio_path.exists():
            print(f"❌ 音频文件不存在: {audio_path}")
            return False

        print(f"\n音频文件: {audio_path}")

        # 1. 测试带 CAM++ 的完整模型
        print("\n" + "-"*40)
        print("测试1：paraformer-zh + CAM++ (整合模型)")
        print("-"*40)

        print("\n加载整合模型 (speech_paraformer_large_vad_punc_spk)...\n")
        model_combo = AutoModel(
            model="speech_paraformer_large_vad_punc_spk",
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 60000},
            device="cpu"
        )

        print("执行识别 (spk_diarization=True)...")
        result_combo = model_combo.generate(
            input=str(audio_path),
            batch_size_s=30,
            spk_diarization=True
        )

        print(f"\n返回类型: {type(result_combo)}")
        if result_combo:
            print(f"返回长度: {len(result_combo)}")
            first = result_combo[0]
            print(f"第一个元素类型: {type(first)}")
            if isinstance(first, dict):
                print(f"Keys: {first.keys()}")
                for key, value in first.items():
                    if isinstance(value, list):
                        print(f"\n{key} (列表，长度 {len(value)}):")
                        if value:
                            print(f"  第一个元素: {value[0]}")
                    elif isinstance(value, str):
                        print(f"\n{key}: {value[:100]}..." if len(str(value)) > 100 else f"\n{key}: {value}")
                    else:
                        print(f"\n{key}: {value}")

        # 2. 测试分离模型
        print("\n" + "-"*40)
        print("测试2：paraformer-zh + cam++ (分离模型)")
        print("-"*40)

        print("\n加载分离模型...")
        model_sep = AutoModel(
            model="paraformer-zh",
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 60000},
            punc_model="ct-punc",
            spk_model="cam++",
            device="cpu"
        )

        print("执行识别 (spk_diarization=True)...")
        result_sep = model_sep.generate(
            input=str(audio_path),
            batch_size_s=30,
            spk_diarization=True
        )

        print(f"\n返回类型: {type(result_sep)}")
        if result_sep:
            print(f"返回长度: {len(result_sep)}")
            first = result_sep[0]
            print(f"第一个元素类型: {type(first)}")
            if isinstance(first, dict):
                print(f"Keys: {first.keys()}")
                for key, value in first.items():
                    if isinstance(value, list):
                        print(f"\n{key} (列表，长度 {len(value)}):")
                        if value:
                            print(f"  前3个元素: {value[:3]}")
                    elif isinstance(value, str):
                        print(f"\n{key}: {value[:100]}..." if len(str(value)) > 100 else f"\n{key}: {value}")
                    else:
                        print(f"\n{key}: {value}")

        return True

    except Exception as e:
        print(f"❌ CAM++ 诊断失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def diagnose_srt_speaker_handling():
    """诊断 SRT 中说话人标签处理"""
    print("\n" + "="*60)
    print("诊断3：SRT 说话人标签处理")
    print("="*60)

    try:
        # 读取生成的带说话人的 SRT
        srt_path = Path(r"E:\直播切片项目\output\20260420_新录制\test_output\clip_001_product_0s-708s_spk.srt")

        if not srt_path.exists():
            print(f"❌ SRT 文件不存在: {srt_path}")
            return False

        print(f"\nSRT 文件: {srt_path}")

        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        print(f"\n文件大小: {len(content)} bytes")
        print(f"行数: {len(content.splitlines())}")

        # 检查是否包含说话人标签
        has_speaker = "[0]" in content or "[1]" in content or "[speaker" in content.lower()
        print(f"\n包含说话人标签: {has_speaker}")

        # 显示前20行
        print("\n前20行内容:")
        print("-"*40)
        lines = content.splitlines()[:20]
        for i, line in enumerate(lines, 1):
            print(f"{i}: {line}")

        return True

    except Exception as e:
        print(f"❌ SRT 诊断失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主诊断函数"""
    print("\n" + "#"*60)
    print("# FunASR fa-zh 和 CAM++ 诊断")
    print("#"*60)

    results = []

    # 诊断1：fa-zh 时间戳
    results.append(("fa-zh 时间戳", diagnose_fa_zh_timestamp()))

    # 诊断2：CAM++ 说话人
    results.append(("CAM++ 说话人", diagnose_campplus_speaker()))

    # 诊断3：SRT 说话人标签处理
    results.append(("SRT 标签处理", diagnose_srt_speaker_handling()))

    # 汇总
    print("\n" + "="*60)
    print("诊断结果汇总")
    print("="*60)

    for name, result in results:
        status = "✅ 完成" if result else "❌ 失败"
        print(f"{name}: {status}")

    return 0 if all(r for _, r in results) else 1


if __name__ == "__main__":
    exit(main())
