"""
FunASR 完整视频识别测试
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def test_video_recognition():
    """测试完整视频识别流程"""
    print("\n" + "="*60)
    print("FunASR 完整视频识别测试")
    print("="*60)

    video_path = Path(r"E:\直播切片项目\output\20260420_新录制\clip_001_product_0s-708s.mp4")

    if not video_path.exists():
        print(f"❌ 视频文件不存在: {video_path}")
        return False

    file_size = video_path.stat().st_size
    print(f"视频路径: {video_path}")
    print(f"文件大小: {file_size / (1024*1024):.2f} MB")

    # 创建临时输出目录
    output_dir = Path(r"E:\直播切片项目\output\20260420_新录制\test_output")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{video_path.stem}.srt"

    try:
        from backend.utils.speech_recognizer import (
            SpeechRecognitionConfig,
            SpeechRecognitionMethod,
            LanguageCode,
            generate_subtitle_for_video
        )

        # 测试1：不带说话人分离
        print("\n" + "-"*40)
        print("测试1：不带说话人分离")
        print("-"*40)

        config1 = SpeechRecognitionConfig(
            method=SpeechRecognitionMethod.FUNASR,
            language=LanguageCode.AUTO,
            enable_timestamps=True,
            enable_punctuation=True,
            enable_speaker_diarization=False,
            hotword=""
        )

        print(f"配置: enable_speaker_diarization={config1.enable_speaker_diarization}")
        print("开始识别...")

        srt_path1 = generate_subtitle_for_video(
            video_path,
            output_path=output_path,
            config=config1
        )

        if srt_path1 and srt_path1.exists():
            srt_size = srt_path1.stat().st_size
            print(f"✅ 字幕生成成功: {srt_path1}")
            print(f"   文件大小: {srt_size} bytes")

            # 读取前几行预览
            with open(srt_path1, 'r', encoding='utf-8') as f:
                lines = f.readlines()[:20]
                print("\n字幕预览（前20行）:")
                print("-"*40)
                for line in lines:
                    print(line.rstrip())
        else:
            print("❌ 字幕生成失败")
            return False

        # 测试2：带说话人分离
        print("\n" + "-"*40)
        print("测试2：带说话人分离")
        print("-"*40)

        output_path2 = output_dir / f"{video_path.stem}_spk.srt"
        config2 = SpeechRecognitionConfig(
            method=SpeechRecognitionMethod.FUNASR,
            language=LanguageCode.AUTO,
            enable_timestamps=True,
            enable_punctuation=True,
            enable_speaker_diarization=True,
            hotword=""
        )

        print(f"配置: enable_speaker_diarization={config2.enable_speaker_diarization}")
        print("开始识别...")

        srt_path2 = generate_subtitle_for_video(
            video_path,
            output_path=output_path2,
            config=config2
        )

        if srt_path2 and srt_path2.exists():
            srt_size = srt_path2.stat().st_size
            print(f"✅ 字幕生成成功: {srt_path2}")
            print(f"   文件大小: {srt_size} bytes")

            with open(srt_path2, 'r', encoding='utf-8') as f:
                lines = f.readlines()[:20]
                print("\n字幕预览（前20行）:")
                print("-"*40)
                for line in lines:
                    print(line.rstrip())
        else:
            print("❌ 字幕生成失败")
            return False

        # 测试3：带热词
        print("\n" + "-"*40)
        print("测试3：带热词")
        print("-"*40)

        output_path3 = output_dir / f"{video_path.stem}_hotword.srt"
        config3 = SpeechRecognitionConfig(
            method=SpeechRecognitionMethod.FUNASR,
            language=LanguageCode.AUTO,
            enable_timestamps=True,
            enable_punctuation=True,
            enable_speaker_diarization=True,
            hotword="直播 短视频 主播"
        )

        print(f"配置: hotword='{config3.hotword}'")
        print("开始识别...")

        srt_path3 = generate_subtitle_for_video(
            video_path,
            output_path=output_path3,
            config=config3
        )

        if srt_path3 and srt_path3.exists():
            srt_size = srt_path3.stat().st_size
            print(f"✅ 字幕生成成功: {srt_path3}")
            print(f"   文件大小: {srt_size} bytes")
        else:
            print("❌ 字幕生成失败")
            return False

        print("\n" + "="*60)
        print("🎉 所有视频识别测试通过！")
        print("="*60)

        # 对比结果
        print("\n结果对比:")
        print(f"  无说话人分离: {srt_path1.stat().st_size} bytes")
        print(f"  带说话人分离: {srt_path2.stat().st_size} bytes")
        print(f"  带热词:       {srt_path3.stat().st_size} bytes")

        return True

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_video_recognition()
    sys.exit(0 if success else 1)
