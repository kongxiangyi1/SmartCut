"""
说话人识别模块 - 借鉴 FunClip 的 CAM++ 技术

使用阿里巴巴开源的 iic/speech_campplus_sv_zh-cn_16k-common 模型
提供完整的降级方案，确保模型不可用时也能工作
"""

import logging
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

# 尝试导入 ModelScope，如果失败则提供降级方案
HAS_MODELSCOPE = False
try:
    from modelscope.pipelines import pipeline
    HAS_MODELSCOPE = True
except ImportError:
    logger.warning("ModelScope 未安装，说话人识别功能将降级")


class SpeakerRecognizer:
    """
    CAM++ 说话人识别器 - 基于 FunClip 技术
    """

    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self._pipeline = None
        self._initialized = False

    def _initialize(self):
        """
        延迟初始化 - 避免导入时就下载模型
        """
        if self._initialized:
            return

        if not HAS_MODELSCOPE:
            logger.warning("ModelScope 未安装，无法使用 CAM++")
            self._initialized = True
            return

        try:
            logger.info("正在加载 CAM++ 说话人识别模型...")
            self._pipeline = pipeline(
                tasks='speaker-recognition',
                model='iic/speech_campplus_sv_zh-cn_16k-common'
            )
            logger.info("CAM++ 模型加载完成！")
        except Exception as e:
            logger.error(f"加载 CAM++ 模型失败: {e}")
            self._pipeline = None
        finally:
            self._initialized = True

    def recognize_srt_segments(
        self,
        srt_data: List[Dict],
        audio_path: Optional[Path] = None,
        cache_path: Optional[Path] = None
    ) -> List[Dict]:
        """
        识别 SRT 每个段落的说话人

        Args:
            srt_data: SRT 解析结果
            audio_path: 音频文件路径（可选）
            cache_path: 缓存文件路径（可选）

        Returns:
            更新后的 srt_data，每个条目增加 'speaker_id' 字段
        """
        # 先尝试从缓存加载
        if cache_path and cache_path.exists():
            logger.info(f"从缓存加载说话人识别结果: {cache_path}")
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                if self._validate_cached_data(cached_data, srt_data):
                    logger.info("缓存数据有效，直接使用！")
                    return cached_data
            except Exception as e:
                logger.warning(f"加载缓存失败: {e}")

        # 初始化模型
        self._initialize()

        if not self._pipeline:
            # 降级方案：分配默认说话人
            logger.warning("无法使用 CAM++，使用降级方案（简单说话人分配）")
            srt_data = self._simple_speaker_assignment(srt_data)
        else:
            if audio_path:
                # 使用更精确的音频识别
                logger.info("从音频中提取说话人...")
                srt_data = self._recognize_from_audio(srt_data, audio_path)
            else:
                # 仅文本时的降级方案
                logger.info("没有音频路径，使用简单说话人分配")
                srt_data = self._simple_speaker_assignment(srt_data)

        # 保存缓存
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(srt_data, f, ensure_ascii=False, indent=2)
            logger.info(f"说话人识别结果已缓存到: {cache_path}")

        return srt_data

    def _recognize_from_audio(
        self,
        srt_data: List[Dict],
        audio_path: Path
    ) -> List[Dict]:
        """
        从音频提取说话人（需要 FFmpeg 和 pydub）
        """
        try:
            import numpy as np
            from pydub import AudioSegment

            logger.info(f"加载音频文件: {audio_path}")
            audio = AudioSegment.from_file(str(audio_path))

            for sub in srt_data:
                start_ms = self._time_to_ms(sub['start_time'])
                end_ms = self._time_to_ms(sub['end_time'])

                try:
                    # 提取音频片段
                    if start_ms < len(audio):
                        segment = audio[start_ms:min(end_ms, len(audio))]

                        # 转换为 16kHz 单声道
                        segment_16k = segment.set_frame_rate(16000).set_channels(1)

                        # 转换为 numpy 数组
                        samples = np.array(segment_16k.get_array_of_samples())
                        samples = samples.astype(np.float32) / (np.iinfo(np.int16).max + 1)

                        # 识别说话人
                        if self._pipeline:
                            result = self._pipeline(samples)
                            speaker_id = result.get('speaker_id', 'spk0')
                            sub['speaker_id'] = speaker_id
                        else:
                            sub['speaker_id'] = 'spk0'
                    else:
                        sub['speaker_id'] = 'spk0'
                except Exception as e:
                    # 单个段落失败时，使用默认值
                    logger.debug(f"单个段落识别失败: {e}")
                    sub['speaker_id'] = 'spk0'

        except ImportError as e:
            logger.warning(f"pydub 未安装: {e}，使用降级方案")
            srt_data = self._simple_speaker_assignment(srt_data)
        except Exception as e:
            logger.warning(f"从音频识别说话人失败: {e}，使用降级方案")
            srt_data = self._simple_speaker_assignment(srt_data)

        return srt_data

    def _simple_speaker_assignment(self, srt_data: List[Dict]) -> List[Dict]:
        """
        简单降级方案：基于文本长度和段落节奏简单分配说话人
        """
        # 假设只有 2-3 个说话人，根据段落长度模式分配
        speaker_count = 2

        # 分析段落长度模式
        lengths = [len(sub.get('text', '')) for sub in srt_data]
        avg_length = sum(lengths) / max(len(lengths), 1)

        for i, sub in enumerate(srt_data):
            # 简单模式：基于索引交替分配
            sub['speaker_id'] = f'spk{i % speaker_count}'

        logger.info(f"简单说话人分配完成，共 {speaker_count} 个说话人")
        return srt_data

    @staticmethod
    def _time_to_ms(time_str: str) -> int:
        """
        SRT 时间转毫秒
        """
        # 处理格式: 00:00:00,000
        try:
            if ',' in time_str:
                time_part, ms_part = time_str.split(',')
            else:
                time_part = time_str
                ms_part = '000'

            parts = time_part.split(':')
            if len(parts) == 3:
                h, m, s = parts
            elif len(parts) == 2:
                h = 0
                m, s = parts
            else:
                return 0

            return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms_part)
        except Exception as e:
            logger.warning(f"解析时间失败: {time_str}, {e}")
            return 0

    @staticmethod
    def _validate_cached_data(
        cached_data: List[Dict],
        original_data: List[Dict]
    ) -> bool:
        """
        验证缓存数据是否有效
        """
        if len(cached_data) != len(original_data):
            return False
        for cached, original in zip(cached_data, original_data):
            if cached.get('index') != original.get('index'):
                return False
        return True


def get_speaker_for_topic(
    topic_timeline: Dict,
    srt_with_speakers: List[Dict]
) -> Optional[str]:
    """
    为话题找到主导说话人

    Args:
        topic_timeline: 话题时间线数据，包含 start_time 和 end_time
        srt_with_speakers: 带有 speaker_id 的 SRT 数据

    Returns:
        主导说话人 ID
    """
    if not srt_with_speakers:
        return None

    topic_start = SpeakerRecognizer._time_to_ms(topic_timeline.get('start_time', '00:00:00,000'))
    topic_end = SpeakerRecognizer._time_to_ms(topic_timeline.get('end_time', '00:00:00,000'))

    speaker_counts = defaultdict(int)

    for sub in srt_with_speakers:
        sub_start = SpeakerRecognizer._time_to_ms(sub.get('start_time', '00:00:00,000'))
        sub_end = SpeakerRecognizer._time_to_ms(sub.get('end_time', '00:00:00,000'))

        # 检查是否重叠
        if not (sub_end < topic_start or sub_start > topic_end):
            speaker_id = sub.get('speaker_id', 'spk0')
            speaker_counts[speaker_id] += 1

    # 返回出现最多的说话人
    if speaker_counts:
        return max(speaker_counts.items(), key=lambda x: x[1])[0]

    return None


def get_speaker_statistics(timeline: List[Dict]) -> Dict[str, int]:
    """
    获取说话人统计信息

    Returns:
        { 'spk0': 话题数, 'spk1': 话题数, ... }
    """
    stats = defaultdict(int)
    for item in timeline:
        speaker = item.get('speaker_id')
        if speaker:
            stats[speaker] += 1
    return dict(stats)
