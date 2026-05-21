"""
VAD预处理器
在语音识别前使用VAD跳过静音片段，提升处理效率
"""
import logging
import os
from typing import List, Tuple, Optional
from pathlib import Path
import subprocess
import tempfile

logger = logging.getLogger(__name__)


class VADPreprocessor:
    """VAD预处理器，用于检测语音活动区间并提取有效语音片段"""

    def __init__(
        self,
        enable_vad: bool = True,
        gap_threshold: float = 0.5,
        min_segment_duration: float = 0.3
    ):
        self.enable_vad = enable_vad and os.environ.get("ENABLE_VAD", "true").lower() == "true"
        self.gap_threshold = gap_threshold
        self.min_segment_duration = min_segment_duration
        self.vad_model = None

        if self.enable_vad:
            self._init_vad()

    def _init_vad(self):
        """初始化VAD模型"""
        try:
            from funasr import AutoModel
            device = os.environ.get("SPEECH_DEVICE", "cpu")
            logger.info(f"[VAD] 初始化VAD模型，设备: {device}")

            self.vad_model = AutoModel(
                model="fsmn-vad",
                device=device,
                disable_update=True
            )
            logger.info("[VAD] [OK] VAD模型初始化成功")
        except ImportError:
            logger.warning("[VAD] [WARN] FunASR未安装，VAD预处理不可用")
            self.enable_vad = False
        except Exception as e:
            logger.warning(f"[VAD] [WARN] VAD模型初始化失败: {e}，将跳过VAD预处理")
            self.enable_vad = False

    def detect_speech_segments(self, audio_path: Path) -> List[Tuple[float, float]]:
        """
        检测语音活动区间

        Args:
            audio_path: 音频文件路径

        Returns:
            语音区间列表 [(start, end), ...]，单位为秒
        """
        if not self.enable_vad or self.vad_model is None:
            logger.info("[VAD] VAD未启用，返回完整音频区间")
            return [(0.0, float('inf'))]

        try:
            logger.info(f"[VAD] 开始VAD检测: {audio_path}")

            vad_result = self.vad_model.generate(
                input=str(audio_path),
                batch_size_s=300
            )

            speech_segments = []
            for item in vad_result:
                if isinstance(item, dict) and 'value' in item:
                    value = item['value']
                    if isinstance(value, list):
                        for segment in value:
                            if isinstance(segment, list) and len(segment) >= 2:
                                start = segment[0] / 1000.0
                                end = segment[1] / 1000.0
                                duration = end - start
                                if duration >= self.min_segment_duration:
                                    speech_segments.append((start, end))

            speech_segments = self._merge_segments(speech_segments, self.gap_threshold)

            total_speech_duration = sum(end - start for start, end in speech_segments)
            logger.info(
                f"[VAD] [OK] 检测完成: {len(speech_segments)}个语音片段，"
                f"总时长{total_speech_duration:.1f}秒"
            )

            return speech_segments

        except Exception as e:
            logger.error(f"[VAD] [FAIL] VAD检测失败: {e}，将跳过VAD预处理")
            return [(0.0, float('inf'))]

    def _merge_segments(
        self,
        segments: List[Tuple[float, float]],
        gap_threshold: float = 0.5
    ) -> List[Tuple[float, float]]:
        """
        合并相近的语音片段

        Args:
            segments: 语音片段列表
            gap_threshold: 合并阈值（秒）

        Returns:
            合并后的片段列表
        """
        if not segments:
            return []

        segments.sort(key=lambda x: x[0])

        merged = [segments[0]]

        for current in segments[1:]:
            prev = merged[-1]
            gap = current[0] - prev[1]

            if gap <= gap_threshold:
                merged[-1] = (prev[0], current[1])
            else:
                merged.append(current)

        return merged

    def extract_speech_segments(
        self,
        audio_path: Path,
        speech_segments: List[Tuple[float, float]],
        output_dir: Path
    ) -> List[Path]:
        """
        提取语音片段

        Args:
            audio_path: 原始音频路径
            speech_segments: 语音区间列表
            output_dir: 输出目录

        Returns:
            提取的音频片段路径列表
        """
        if not speech_segments or speech_segments == [(0.0, float('inf'))]:
            return [audio_path]

        output_dir.mkdir(parents=True, exist_ok=True)
        segment_paths = []

        for i, (start, end) in enumerate(speech_segments):
            segment_path = output_dir / f"segment_{i:03d}.wav"

            cmd = [
                'ffmpeg',
                '-i', str(audio_path),
                '-ss', str(start),
                '-t', str(end - start),
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                '-y',
                str(segment_path)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')

            if result.returncode == 0:
                segment_paths.append(segment_path)
            else:
                logger.warning(f"[VAD] 片段提取失败: {segment_path}, error: {result.stderr}")

        logger.info(f"[VAD] 提取了{len(segment_paths)}个语音片段")
        return segment_paths

    def get_audio_duration(self, audio_path: Path) -> float:
        """
        获取音频时长

        Args:
            audio_path: 音频文件路径

        Returns:
            时长（秒）
        """
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            str(audio_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')

        if result.returncode == 0:
            try:
                return float(result.stdout.strip())
            except ValueError:
                return 0.0
        else:
            return 0.0

    def calculate_skip_ratio(
        self,
        audio_path: Path,
        speech_segments: List[Tuple[float, float]]
    ) -> float:
        """
        计算静音跳过比例

        Args:
            audio_path: 音频文件路径
            speech_segments: 语音区间列表

        Returns:
            跳过比例（0.0 - 1.0）
        """
        total_duration = self.get_audio_duration(audio_path)
        if total_duration <= 0:
            return 0.0

        speech_duration = sum(end - start for start, end in speech_segments)
        skip_ratio = (total_duration - speech_duration) / total_duration

        return skip_ratio


def get_vad_preprocessor() -> VADPreprocessor:
    """获取VAD预处理器单例"""
    global _vad_preprocessor_instance
    if _vad_preprocessor_instance is None:
        _vad_preprocessor_instance = VADPreprocessor()
    return _vad_preprocessor_instance


_vad_preprocessor_instance: Optional[VADPreprocessor] = None
