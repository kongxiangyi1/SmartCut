"""
诊断方案A失败原因
分析 damo/speech_paraformer-large-vad-punc-spk_asr_nat-zh-cn 模型的实际输出
"""

import logging
from pathlib import Path
import sys

# 同时输出到文件和控制台
file_handler = logging.FileHandler('diagnose_output.txt', encoding='utf-8')
file_handler.setLevel(logging.INFO)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[file_handler, console_handler]
)

logger = logging.getLogger(__name__)


def diagnose_model_a():
    """诊断整合模型"""
    try:
        from funasr import AutoModel
    except ImportError:
        logger.error("FunASR 未安装")
        return

    # 找到测试音频
    audio_path = None
    data_dir = Path("d:/Download/autoclip-main1/autoclip-main/data/projects")
    if data_dir.exists():
        for mp4_file in data_dir.rglob("*.mp4"):
            if "input.mp4" in str(mp4_file):
                audio_path = str(mp4_file)
                break

    if not audio_path:
        logger.error("未找到测试音频")
        return

    logger.info(f"使用测试音频: {audio_path}")

    # 加载模型
    logger.info("加载模型...")
    try:
        model = AutoModel(
            model="damo/speech_paraformer-large-vad-punc-spk_asr_nat-zh-cn",
            vad_model="fsmn-vad",
            device="cpu",
            disable_update=True
        )
        logger.info("✅ 模型加载成功")
    except Exception as e:
        logger.error(f"模型加载失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return

    # 测试1: 基本识别，打印所有返回字段
    logger.info("\n" + "=" * 80)
    logger.info("测试1: 基本识别，打印所有返回字段")
    logger.info("=" * 80)

    try:
        result = model.generate(input=audio_path, batch_size_s=30)

        if result and len(result) > 0:
            first = result[0]
            logger.info(f"\n返回值类型: {type(first)}")

            if isinstance(first, dict):
                logger.info("\n所有返回的keys:")
                for key in sorted(first.keys()):
                    value = first[key]
                    logger.info(f"  {key}: {type(value)}")

                    # 打印简单类型的值
                    if isinstance(value, (str, int, float, bool)):
                        if isinstance(value, str) and len(value) > 200:
                            logger.info(f"    值预览: {value[:200]}...")
                        else:
                            logger.info(f"    值: {value}")
                    elif isinstance(value, list):
                        logger.info(f"    列表长度: {len(value)}")
                        if len(value) > 0 and isinstance(value[0], dict):
                            logger.info(f"    列表元素示例: {value[0]}")

    except Exception as e:
        logger.error(f"测试1失败: {e}")
        import traceback
        logger.error(traceback.format_exc())

    # 测试2: 尝试不同的参数组合
    logger.info("\n" + "=" * 80)
    logger.info("测试2: 尝试不同的参数组合")
    logger.info("=" * 80)

    param_combinations = [
        {"spk_diarization": True},
        {"return_spk_res": True},
        {"spk_diarization": True, "return_spk_res": True},
        {"spk_diarization": True, "span_type": "pyannote"},
        {"spk_diarization": True, "span_type": "chunk"},
    ]

    for i, params in enumerate(param_combinations):
        logger.info(f"\n--- 参数组合 {i+1}: {params} ---")
        try:
            result = model.generate(
                input=audio_path,
                batch_size_s=30,
                **params
            )

            if result and len(result) > 0:
                first = result[0]
                if isinstance(first, dict):
                    # 检查说话人相关字段
                    spk_fields = ["text_with_speaker", "spk_info", "speaker"]
                    for field in spk_fields:
                        if field in first:
                            value = first[field]
                            logger.info(f"  {field}: {type(value)}, 长度={len(value) if hasattr(value, '__len__') else 'N/A'}")
                            if isinstance(value, list) and len(value) > 0:
                                logger.info(f"    示例: {value[0]}")

        except Exception as e:
            logger.warning(f"  参数组合 {i+1} 失败: {e}")
            import traceback
            logger.warning(traceback.format_exc())


if __name__ == "__main__":
    diagnose_model_a()
    logger.info("\n✅ 诊断完成，结果已保存到 diagnose_output.txt")

