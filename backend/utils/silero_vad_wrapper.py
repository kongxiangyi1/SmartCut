"""
Silero VAD 轻量封装
使用 ONNX 模式，无需 PyTorch 环境即可运行
"""
import logging
from pathlib import Path
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class SileroVADWrapper:
    """
    Silero VAD 轻量封装

    用法:
        vad = SileroVADWrapper()
        segments = vad.detect_speech("audio.wav")
        # 返回: [(0.0, 12.5), (14.0, 30.2), ...]
    """

    def __init__(self, onnx: bool = True, threshold: float = 0.5,
                 min_speech_duration_ms: int = 300,
                 min_silence_duration_ms: int = 500):
        self.onnx = onnx
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms
        self._model = None

    def _load_model(self):
        """延迟加载模型（首次调用 detect_speech 时加载）"""
        if self._model is not None:
            return
        try:
            from silero_vad import load_silero_vad
            logger.info(f"[SileroVAD] 加载模型 (ONNX={self.onnx})...")
            self._model = load_silero_vad(onnx=self.onnx)
            logger.info("[SileroVAD] 模型加载成功")
        except ImportError as e:
            raise RuntimeError(
                "Silero VAD 未安装，请执行: pip install silero-vad"
            ) from e

    def detect_speech(self, audio_path: Path) -> List[Tuple[float, float]]:
        """
        对音频文件进行 VAD 检测

        Args:
            audio_path: 16kHz 单声道 WAV 文件路径

        Returns:
            语音区间列表 [(start_sec, end_sec), ...]
        """
        self._load_model()

        try:
            from silero_vad import read_audio, get_speech_timestamps

            wav = read_audio(str(audio_path))
            timestamps = get_speech_timestamps(
                wav,
                self._model,
                threshold=self.threshold,
                min_speech_duration_ms=self.min_speech_duration_ms,
                min_silence_duration_ms=self.min_silence_duration_ms,
                return_seconds=True,
            )
            result = [(t['start'], t['end']) for t in timestamps]
            logger.info(
                f"[SileroVAD] 检测完成: {len(result)} 段语音, "
                f"音频长度 {len(wav) / 16000:.1f}s"
            )
            return result

        except Exception as e:
            logger.error(f"[SileroVAD] 检测失败: {e}")
            raise

    def detect_silence(
        self, audio_path: Path, total_duration: float
    ) -> List[Tuple[float, float]]:
        """
        从语音区间反推静音区间

        Args:
            audio_path: 音频文件路径
            total_duration: 音频总时长（秒）

        Returns:
            静音区间列表 [(start_sec, end_sec), ...]
        """
        speech = self.detect_speech(audio_path)
        return self._speech_to_silence(speech, total_duration)

    @staticmethod
    def _speech_to_silence(
        speech_segments: List[Tuple[float, float]],
        total_duration: float,
    ) -> List[Tuple[float, float]]:
        """语音区间 → 静音区间（反转）"""
        if not speech_segments:
            return [(0.0, total_duration)]

        silence = []
        # 开头静音
        if speech_segments[0][0] > 0:
            silence.append((0.0, speech_segments[0][0]))
        # 中间静音
        for i in range(len(speech_segments) - 1):
            gap_start = speech_segments[i][1]
            gap_end = speech_segments[i + 1][0]
            if gap_end > gap_start:
                silence.append((gap_start, gap_end))
        # 结尾静音
        if speech_segments[-1][1] < total_duration:
            silence.append((speech_segments[-1][1], total_duration))

        return silence

    @staticmethod
    def map_to_clip(
        full_speech_segments: List[Tuple[float, float]],
        clip_start: float,
        clip_end: float,
    ) -> List[Tuple[float, float]]:
        """
        将全音频 VAD 结果映射到 clip 的局部坐标

        Args:
            full_speech_segments: 全音频语音区间 [(s,e), ...]（全局坐标）
            clip_start: clip 在全音频中的开始时间（秒）
            clip_end: clip 在全音频中的结束时间（秒）

        Returns:
            clip 局部坐标的语音区间 [(s,e), ...]
        """
        local_speech = []
        for seg_start, seg_end in full_speech_segments:
            # 跳过完全不在 clip 范围内的段
            if seg_end <= clip_start or seg_start >= clip_end:
                continue
            # 取交集并映射到局部坐标
            local_s = max(seg_start, clip_start) - clip_start
            local_e = min(seg_end, clip_end) - clip_start
            if local_e - local_s > 0.3:  # 过滤过短段
                local_speech.append((local_s, local_e))
        return local_speech

    @staticmethod
    def save_vad_json(
        speech_segments: List[Tuple[float, float]],
        output_path: Path,
    ):
        """将 VAD 结果保存为标准 .vad.json 格式"""
        import json
        data = [
            {"start": round(s, 3), "end": round(e, 3)}
            for s, e in speech_segments
        ]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def load_vad_json(vad_path: Path) -> List[Tuple[float, float]]:
        """从 .vad.json 加载 VAD 结果"""
        import json
        with open(vad_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return [(item['start'], item['end']) for item in data]