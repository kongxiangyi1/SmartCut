"""
VAD预处理器 — Silero VAD 版本
在语音识别前使用VAD跳过静音片段，提升处理效率

变更：用 Silero VAD（ONNX）替换 FunASR fsmn-vad
- 模型体积: 1GB+ → 2MB
- 加载时间: 30s+ → <1s
- 精度: 更好（6000+ 语言训练）
"""
import logging
import os
from pathlib import Path
from typing import List, Tuple, Optional

from backend.utils.silero_vad_wrapper import SileroVADWrapper

logger = logging.getLogger(__name__)


class VADPreprocessor:
    """VAD预处理器，用于检测语音活动区间并提取有效语音片段"""

    def __init__(
        self,
        enable_vad: bool = True,
        gap_threshold: float = 0.5,
        min_segment_duration: float = 0.3,
        silero_threshold: float = 0.5,
    ):
        self.enable_vad = enable_vad and os.environ.get("ENABLE_VAD", "true").lower() == "true"
        self.gap_threshold = gap_threshold
        self.min_segment_duration = min_segment_duration
        self.silero_threshold = silero_threshold
        self.vad_wrapper: Optional[SileroVADWrapper] = None

        if self.enable_vad:
            self._init_vad()

    def _init_vad(self):
        """初始化 Silero VAD 模型"""
        try:
            use_onnx = os.environ.get("SILERO_VAD_ONNX", "true").lower() == "true"
            logger.info(f"[VAD] 初始化 Silero VAD 模型 (ONNX={use_onnx})")
            self.vad_wrapper = SileroVADWrapper(
                onnx=use_onnx,
                threshold=self.silero_threshold,
                min_speech_duration_ms=int(self.min_segment_duration * 1000),
                min_silence_duration_ms=int(self.gap_threshold * 1000),
            )
            # 触发一次加载（验证模型可用）
            self.vad_wrapper._load_model()
            logger.info("[VAD] [OK] Silero VAD 模型初始化成功")
        except Exception as e:
            logger.warning(f"[VAD] [WARN] Silero VAD 初始化失败: {e}，将跳过 VAD 预处理")
            self.enable_vad = False

    def detect_speech_segments(self, audio_path: Path) -> List[Tuple[float, float]]:
        """
        检测语音活动区间

        Args:
            audio_path: 音频文件路径（16kHz WAV）

        Returns:
            语音区间列表 [(start, end), ...]，单位为秒
        """
        if not self.enable_vad or self.vad_wrapper is None:
            logger.info("[VAD] VAD未启用，返回完整音频区间")
            return [(0.0, float('inf'))]

        try:
            logger.info(f"[VAD] 开始 Silero VAD 检测: {audio_path}")
            speech_segments = self.vad_wrapper.detect_speech(audio_path)

            total_speech_duration = sum(end - start for start, end in speech_segments)
            logger.info(
                f"[VAD] [OK] 检测完成: {len(speech_segments)}个语音片段，"
                f"总时长{total_speech_duration:.1f}秒"
            )
            return speech_segments

        except Exception as e:
            logger.error(f"[VAD] [FAIL] VAD检测失败: {e}，将跳过VAD预处理")
            return [(0.0, float('inf'))]

    def extract_speech_segments(
        self,
        audio_path: Path,
        speech_segments: List[Tuple[float, float]],
        output_dir: Path,
    ) -> List[Path]:
        """
        提取语音片段到独立的 WAV 文件

        与原有实现保持一致，仅 VAD 检测方式变更，提取逻辑不变。
        """
        if not speech_segments or speech_segments == [(0.0, float('inf'))]:
            return [audio_path]

        output_dir.mkdir(parents=True, exist_ok=True)
        segment_paths = []

        for i, (start, end) in enumerate(speech_segments):
            segment_path = output_dir / f"segment_{i:03d}.wav"
            import subprocess
            cmd = [
                'ffmpeg',
                '-i', str(audio_path),
                '-ss', str(start),
                '-t', str(end - start),
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                '-y',
                str(segment_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                segment_paths.append(segment_path)
            else:
                logger.warning(f"[VAD] 片段提取失败: {segment_path}")

        logger.info(f"[VAD] 提取了{len(segment_paths)}个语音片段")
        return segment_paths

    def get_audio_duration(self, audio_path: Path) -> float:
        """获取音频时长（秒）"""
        import subprocess
        cmd = [
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(audio_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            try:
                return float(result.stdout.strip())
            except ValueError:
                return 0.0
        return 0.0

    def calculate_skip_ratio(
        self,
        audio_path: Path,
        speech_segments: List[Tuple[float, float]],
    ) -> float:
        """计算静音跳过比例（0.0 - 1.0）"""
        total_duration = self.get_audio_duration(audio_path)
        if total_duration <= 0:
            return 0.0
        speech_duration = sum(end - start for start, end in speech_segments)
        return (total_duration - speech_duration) / total_duration


def get_vad_preprocessor() -> VADPreprocessor:
    """获取VAD预处理器单例"""
    global _vad_preprocessor_instance
    if _vad_preprocessor_instance is None:
        _vad_preprocessor_instance = VADPreprocessor()
    return _vad_preprocessor_instance


_vad_preprocessor_instance: Optional[VADPreprocessor] = None