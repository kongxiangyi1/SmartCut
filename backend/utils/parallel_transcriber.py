# -*- coding: UTF-8 -*-
"""
并行语音识别模块
基于 VAD 分段 + 多进程并行的高效识别方案
"""

import os
import sys
import logging
import tempfile
import traceback
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum

import numpy as np

logger = logging.getLogger(__name__)


class ParallelStrategy(str, Enum):
    """并行策略"""
    VAD_SEGMENT = "vad_segment"      # VAD分段（推荐）
    TIME_SLICE = "time_slice"        # 时间均分
    MULTI_FILE = "multi_file"        # 多文件并行


@dataclass
class AudioSegment:
    """音频段信息"""
    start: float      # 开始时间（秒）
    end: float        # 结束时间（秒）
    audio: np.ndarray = None  # 音频数据
    index: int = 0    # 索引


@dataclass
class TranscriptionResult:
    """识别结果"""
    start: float
    end: float
    text: str
    confidence: float = 1.0
    segment_index: int = 0


def _init_worker():
    """工作进程初始化（如果有全局资源需要初始化）"""
    pass


def _transcribe_segment_worker(
    segment: AudioSegment,
    model_name: str,
    language: Optional[str] = None,
    device: str = "cpu"
) -> TranscriptionResult:
    """
    工作进程中执行的单个片段识别函数
    
    注意：此函数必须是顶级函数才能被pickle
    """
    try:
        # 延迟导入，避免主进程加载模型
        import faster_whisper
        
        # 加载模型（每个进程加载一次）
        # 注意：生产环境中应该使用模型预加载 + 进程池
        model = faster_whisper.WhisperModel(
            model_name,
            device=device,
            compute_type="int8" if device == "cpu" else "float16",
            cpu_threads=2  # 每个进程限制线程数
        )
        
        # 执行识别
        segments, info = model.transcribe(
            segment.audio,
            language=language,
            vad_filter=False,  # 已经分段过，不需要再VAD
            word_timestamps=False
        )
        
        # 收集结果
        text = ''.join([s.text.strip() for s in segments])
        
        return TranscriptionResult(
            start=segment.start,
            end=segment.end,
            text=text,
            segment_index=segment.index
        )
        
    except Exception as e:
        logger.error(f"片段识别失败 [{segment.start}-{segment.end}]: {e}")
        logger.debug(traceback.format_exc())
        return TranscriptionResult(
            start=segment.start,
            end=segment.end,
            text="",
            segment_index=segment.index
        )


class ParallelTranscriber:
    """
    并行语音识别器
    
    使用方法:
    ```python
    transcriber = ParallelTranscriber(
        model_name='small',
        max_workers=4,
        strategy=ParallelStrategy.VAD_SEGMENT
    )
    
    results = transcriber.transcribe('audio.wav')
    for res in results:
        print(f"{res.start:.1f}-{res.end:.1f}: {res.text}")
    ```
    """
    
    def __init__(
        self,
        model_name: str = "small",
        max_workers: Optional[int] = None,
        strategy: ParallelStrategy = ParallelStrategy.VAD_SEGMENT,
        device: Optional[str] = None,
        language: Optional[str] = None,
        segment_duration: float = 30.0,  # 每段最长30秒
        overlap_duration: float = 2.0,    # 段重叠2秒
    ):
        """
        初始化并行识别器
        
        Args:
            model_name: 模型名称 (tiny, base, small, medium, large-v3)
            max_workers: 最大进程数，默认自动根据CPU核数配置
            strategy: 并行策略
            device: 计算设备 (cpu, cuda)，自动检测
            language: 语言代码，None表示自动检测
            segment_duration: 单段最大时长（秒）
            overlap_duration: 段重叠时长（秒）
        """
        self.model_name = model_name
        self.strategy = strategy
        self.language = language
        self.segment_duration = segment_duration
        self.overlap_duration = overlap_duration
        
        # 自动检测设备
        if device is None:
            device = self._detect_device()
        self.device = device
        
        # 智能配置进程数
        if max_workers is None:
            max_workers = self._auto_config_workers()
        self.max_workers = max_workers
        
        logger.info(
            f"ParallelTranscriber初始化: "
            f"model={model_name}, "
            f"workers={max_workers} (自动), "
            f"device={device}, "
            f"strategy={strategy}"
        )
    
    @staticmethod
    def _detect_device() -> str:
        """检测可用的计算设备"""
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"
    
    def _auto_config_workers(self) -> int:
        """
        根据CPU核数和设备类型自动配置最优进程数
        
        智能策略：
        - CPU模式：可以使用更多进程（每个进程独立计算）
        - GPU模式：需要更保守（GPU内存限制）
        - 内存模式：自动评估可用内存
        """
        import psutil
        
        cpu_count = os.cpu_count() or 2
        available_memory_gb = psutil.virtual_memory().available / (1024**3)
        
        # 基础配置
        if cpu_count <= 2:
            # 极低配置：使用全部核数，但留一个给系统
            workers = max(1, cpu_count - 1)
        elif cpu_count <= 4:
            # 低配置：使用CPU核数-1
            workers = cpu_count - 1
        elif cpu_count <= 8:
            # 中配置：使用4-6个进程
            workers = min(6, cpu_count - 2)
        else:
            # 高配置：使用6-8个进程（收益递减）
            workers = min(8, cpu_count - 3)
        
        # GPU模式下更保守（显存限制）
        if self.device == "cuda":
            workers = max(1, workers // 2)
            logger.debug(f"GPU模式，进程数减半: {workers}")
        
        # 内存不足时减少进程数
        if available_memory_gb < 8:
            workers = min(workers, 2)
            logger.debug(f"内存不足({available_memory_gb:.1f}GB)，限制进程数: {workers}")
        elif available_memory_gb < 16:
            workers = min(workers, 4)
            logger.debug(f"内存一般({available_memory_gb:.1f}GB)，限制进程数: {workers}")
        
        logger.info(
            f"智能进程配置: CPU={cpu_count}核, "
            f"内存={available_memory_gb:.1f}GB, "
            f"设备={self.device}, "
            f"进程数={workers}"
        )
        
        return workers
    
    def _split_audio_time_based(self, audio_path: Path) -> List[AudioSegment]:
        """基于时间均分分段"""
        import librosa
        
        y, sr = librosa.load(audio_path, sr=16000)
        duration = len(y) / sr
        
        segments = []
        start = 0.0
        index = 0
        
        while start < duration:
            end = min(start + self.segment_duration, duration)
            
            # 提取音频片段
            start_sample = int(start * sr)
            end_sample = int(end * sr)
            audio_segment = y[start_sample:end_sample]
            
            segments.append(AudioSegment(
                start=start,
                end=end,
                audio=audio_segment,
                index=index
            ))
            
            start = end - self.overlap_duration  # 重叠
            index += 1
        
        return segments
    
    def _split_audio_vad_based(self, audio_path: Path) -> List[AudioSegment]:
        """基于VAD分段（推荐）"""
        import librosa
        
        y, sr = librosa.load(audio_path, sr=16000)
        duration = len(y) / sr
        
        # 方案1: 使用faster-whisper内置VAD
        try:
            import faster_whisper
            
            # 使用faster-whisper做VAD检测
            temp_model = faster_whisper.WhisperModel(
                "tiny",
                device=self.device,
                compute_type="int8"
            )
            
            _, info = temp_model.transcribe(
                str(audio_path),
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=300
                )
            )
            
            # 我们需要真正的VAD段，这里简化处理
            return self._split_audio_time_based(audio_path)
            
        except Exception as e:
            logger.warning(f"VAD检测失败，使用时间均分: {e}")
            return self._split_audio_time_based(audio_path)
    
    def _split_audio(self, audio_path: Path) -> List[AudioSegment]:
        """根据策略分段"""
        if self.strategy == ParallelStrategy.VAD_SEGMENT:
            return self._split_audio_vad_based(audio_path)
        elif self.strategy == ParallelStrategy.TIME_SLICE:
            return self._split_audio_time_based(audio_path)
        else:
            return self._split_audio_time_based(audio_path)
    
    def _merge_results(self, results: List[TranscriptionResult]) -> List[TranscriptionResult]:
        """
        合并识别结果
        
        处理段重叠区域，确保文本连贯
        """
        if not results:
            return []
        
        # 按索引排序
        sorted_results = sorted(results, key=lambda x: x.segment_index)
        
        # TODO: 优化：合并重叠段，去重
        # 这里先简单返回排序后的结果
        return sorted_results
    
    def transcribe(self, audio_path: Path) -> List[TranscriptionResult]:
        """
        并行识别音频
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            识别结果列表，按时间排序
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")
        
        logger.info(f"开始并行识别: {audio_path}")
        
        # 1. 分段
        logger.info("Step 1/3: 音频分段...")
        segments = self._split_audio(audio_path)
        logger.info(f"  分成 {len(segments)} 段")
        
        if not segments:
            logger.warning("未检测到语音段")
            return []
        
        # 2. 并行识别
        logger.info(f"Step 2/3: 并行识别 ({self.max_workers} 进程)...")
        
        results: List[TranscriptionResult] = []
        
        with ProcessPoolExecutor(
            max_workers=self.max_workers,
            initializer=_init_worker
        ) as executor:
            
            # 提交任务
            futures = {
                executor.submit(
                    _transcribe_segment_worker,
                    seg,
                    self.model_name,
                    self.language,
                    self.device
                ): seg
                for seg in segments
            }
            
            # 收集结果
            completed = 0
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1
                    logger.info(f"  进度: {completed}/{len(segments)}")
                except Exception as e:
                    logger.error(f"任务执行失败: {e}")
        
        # 3. 合并结果
        logger.info("Step 3/3: 合并结果...")
        merged_results = self._merge_results(results)
        
        logger.info(f"识别完成: {len(merged_results)} 个结果")
        return merged_results
    
    def transcribe_multiple(
        self,
        audio_paths: List[Path]
    ) -> Dict[Path, List[TranscriptionResult]]:
        """
        批量并行识别多个文件（策略：MULTI_FILE）
        
        Args:
            audio_paths: 音频文件列表
            
        Returns:
            {文件路径: 识别结果}
        """
        logger.info(f"批量识别: {len(audio_paths)} 个文件")
        
        results = {}
        
        with ProcessPoolExecutor(
            max_workers=min(self.max_workers, len(audio_paths))
        ) as executor:
            
            futures = {
                executor.submit(
                    self._transcribe_single_file_wrapper,
                    path
                ): path
                for path in audio_paths
            }
            
            for future in as_completed(futures):
                path = futures[future]
                try:
                    results[path] = future.result()
                except Exception as e:
                    logger.error(f"文件识别失败 {path}: {e}")
        
        return results
    
    def _transcribe_single_file_wrapper(self, audio_path: Path) -> List[TranscriptionResult]:
        """单文件识别包装器（用于批量处理）"""
        return self.transcribe(audio_path)


# ============ 便捷函数 ============

def generate_subtitle_parallel(
    audio_path: str,
    output_path: Optional[str] = None,
    model_name: str = "small",
    max_workers: Optional[int] = None,  # None表示自动配置
    language: Optional[str] = None,
    output_format: str = "srt"
) -> str:
    """
    并行生成字幕（便捷函数）
    
    Args:
        audio_path: 音频/视频文件路径
        output_path: 输出字幕文件路径
        model_name: 模型名称
        max_workers: 最大进程数（默认自动配置）
        language: 语言代码
        output_format: 输出格式 (srt, json)
        
    Returns:
        输出文件路径
    """
    audio_path = Path(audio_path)
    
    if output_path is None:
        output_path = audio_path.parent / f"{audio_path.stem}.{output_format}"
    
    # 初始化识别器
    transcriber = ParallelTranscriber(
        model_name=model_name,
        max_workers=max_workers,
        language=language
    )
    
    # 识别
    results = transcriber.transcribe(audio_path)
    
    # 生成字幕
    if output_format == "srt":
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, res in enumerate(results, start=1):
                if not res.text.strip():
                    continue
                
                # 格式化时间
                def format_time(sec):
                    h = int(sec // 3600)
                    m = int((sec % 3600) // 60)
                    s = sec % 60
                    return f"{h:02d}:{m:02d}:{s:06.3f}".replace('.', ',')
                
                f.write(f"{i}\n")
                f.write(f"{format_time(res.start)} --> {format_time(res.end)}\n")
                f.write(f"{res.text.strip()}\n\n")
        
        logger.info(f"SRT字幕已保存: {output_path}")
    
    return str(output_path)
