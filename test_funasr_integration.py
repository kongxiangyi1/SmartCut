"""
FunASR 整合模型测试脚本
验证 speech_paraformer-large-vad-punc-spk_asr_nat-zh-cn 模型

测试内容:
1. 说话人识别 (spk_diarization)
2. 热词功能 (hotword)
3. 时间戳输出
"""

import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_integrated_model(audio_path: str):
    """测试 FunASR 整合模型"""
    try:
        from funasr import AutoModel
    except ImportError:
        logger.error("FunASR 未安装，请运行: pip install funasr")
        return False

    logger.info("=" * 60)
    logger.info("测试 FunASR 整合模型")
    logger.info("模型: speech_paraformer-large-vad-punc-spk_asr_nat-zh-cn")
    logger.info("=" * 60)

    try:
        # 加载整合模型 (正确的模型名称格式)
        logger.info("正在加载模型...")
        # 尝试多种模型名称格式
        model_names = [
            "damo/speech_paraformer-large-vad-punc-spk_asr_nat-zh-cn",
            "iic/speech_paraformer-large-vad-punc-spk_asr_nat-zh-cn",
        ]
        
        model = None
        loaded_model_name = None
        for model_name in model_names:
            try:
                logger.info(f"尝试加载模型: {model_name}")
                model = AutoModel(
                    model=model_name,
                    vad_model="fsmn-vad",
                    device="cpu",
                    disable_update=True
                )
                loaded_model_name = model_name
                logger.info(f"✅ 模型加载成功: {model_name}")
                break
            except Exception as e:
                logger.warning(f"❌ 模型 {model_name} 加载失败: {e}")
                continue
        
        if model is None:
            logger.error("所有整合模型都加载失败，将使用分步模型")
            return False

        # 测试1: 基本识别（不带说话人分离）
        logger.info("\n" + "=" * 60)
        logger.info("测试1: 基本识别（不带说话人分离）")
        logger.info("=" * 60)
        result = model.generate(input=audio_path, batch_size_s=30)
        logger.info(f"返回类型: {type(result)}")
        logger.info(f"返回长度: {len(result) if hasattr(result, '__len__') else 'N/A'}")

        if result and len(result) > 0:
            first = result[0]
            logger.info(f"返回的keys: {first.keys() if isinstance(first, dict) else 'N/A'}")
            logger.info(f"文本: {first.get('text', 'N/A')[:200]}...")

        # 测试2: 说话人分离
        logger.info("\n" + "=" * 60)
        logger.info("测试2: 说话人分离 (spk_diarization=True)")
        logger.info("=" * 60)
        result_spk = model.generate(
            input=audio_path,
            batch_size_s=30,
            spk_diarization=True
        )

        if result_spk and len(result_spk) > 0:
            first_spk = result_spk[0]
            logger.info(f"返回的keys: {first_spk.keys() if isinstance(first_spk, dict) else 'N/A'}")

            # 检查说话人结果
            text_with_speaker = first_spk.get("text_with_speaker", [])
            logger.info(f"text_with_speaker 长度: {len(text_with_speaker)}")

            if text_with_speaker:
                logger.info("说话人识别结果:")
                for i, item in enumerate(text_with_speaker[:5]):  # 只显示前5条
                    logger.info(f"  [{i}] speaker={item.get('speaker')}, text={item.get('text')[:50]}...")
            else:
                logger.warning("text_with_speaker 为空")

            # 检查时间戳
            timestamp = first_spk.get("timestamp", [])
            logger.info(f"timestamp 长度: {len(timestamp)}")
            if timestamp:
                logger.info("时间戳示例:")
                for i, ts in enumerate(timestamp[:3]):
                    logger.info(f"  [{i}] start={ts.get('start')}, end={ts.get('end')}")

        # 测试3: 热词功能
        logger.info("\n" + "=" * 60)
        logger.info("测试3: 热词功能 (hotword='产品 功能'")
        logger.info("=" * 60)
        result_hot = model.generate(
            input=audio_path,
            batch_size_s=30,
            hotword="产品 功能"  # 测试热词
        )

        if result_hot and len(result_hot) > 0:
            text_hot = result_hot[0].get('text', '')
            logger.info(f"热词识别文本: {text_hot[:200]}...")

        logger.info("\n" + "=" * 60)
        logger.info("✅ 所有测试完成!")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_fallback_models(audio_path: str):
    """测试分步模型（方案B）"""
    try:
        from funasr import AutoModel
    except ImportError:
        logger.error("FunASR 未安装")
        return False

    logger.info("\n" + "=" * 60)
    logger.info("测试分步模型（方案B）")
    logger.info("=" * 60)

    try:
        # 步骤1: paraformer-zh + CAM++
        logger.info("步骤1: 加载 paraformer-zh + cam++")
        model_asr = AutoModel(
            model="paraformer-zh",
            vad_model="fsmn-vad",
            punc_model="ct-punc",
            spk_model="cam++",
            device="cpu"
        )

        logger.info("步骤1: 识别文本和说话人")
        result = model_asr.generate(
            input=audio_path,
            batch_size_s=30,
            spk_diarization=True
        )

        if result and len(result) > 0:
            first = result[0]
            logger.info(f"返回keys: {first.keys()}")
            logger.info(f"文本: {first.get('text', '')[:100]}...")

            # 检查说话人
            text_with_speaker = first.get("text_with_speaker", [])
            logger.info(f"说话人结果: {len(text_with_speaker)} 条")

            if text_with_speaker:
                for i, item in enumerate(text_with_speaker[:3]):
                    logger.info(f"  [{i}] speaker={item.get('speaker')}, text={item.get('text')[:50]}...")

        # 步骤2: fa-zh 时间戳
        logger.info("步骤2: 加载 fa-zh 时间戳模型")
        model_ts = AutoModel(model="fa-zh", device="cpu")

        text_file = Path(audio_path).parent / "temp_text.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(result[0].get('text', '') if result else '')

        logger.info("步骤2: 预测时间戳")
        ts_result = model_ts.generate(
            input=(audio_path, str(text_file)),
            data_type=("sound", "text")
        )

        if ts_result and len(ts_result) > 0:
            first_ts = ts_result[0]
            logger.info(f"时间戳keys: {first_ts.keys() if isinstance(first_ts, dict) else 'N/A'}")

            if 'sentence_info' in first_ts:
                sentences = first_ts['sentence_info']
                logger.info(f"句子数量: {len(sentences)}")
                for i, sent in enumerate(sentences[:3]):
                    logger.info(f"  [{i}] start={sent.get('start')}, end={sent.get('end')}, text={sent.get('text')[:30]}...")

        # 清理
        if text_file.exists():
            text_file.unlink()

        logger.info("\n✅ 分步模型测试完成!")
        return True

    except Exception as e:
        logger.error(f"分步模型测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    # 使用项目中的音频文件
    test_audio = Path("d:/Download/autoclip-main1/autoclip-main/data/projects")

    # 查找项目中的音频文件
    audio_files = []
    if test_audio.exists():
        for mp4_file in test_audio.rglob("*.mp4"):
            if "input.mp4" in str(mp4_file):  # 优先使用原始输入视频
                audio_files.insert(0, mp4_file)
            else:
                audio_files.append(mp4_file)

    if not audio_files:
        logger.error("未找到测试音频文件")
        return

    audio_path = str(audio_files[0])
    logger.info(f"使用测试音频: {audio_path}")

    print("\n" + "=" * 80)
    print("自动运行测试: 整合模型 + 分步模型")
    print("=" * 80)

    # 自动运行所有测试
    success1 = test_integrated_model(audio_path)
    success2 = test_fallback_models(audio_path)

    print("\n" + "=" * 80)
    print("测试结果汇总:")
    print(f"  整合模型测试: {'✅ 成功' if success1 else '❌ 失败'}")
    print(f"  分步模型测试: {'✅ 成功' if success2 else '❌ 失败'}")
    print("=" * 80)


if __name__ == "__main__":
    main()
