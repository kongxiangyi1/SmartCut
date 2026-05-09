"""
静音处理器
用于检测和处理视频中的静音部分
"""
import logging
import subprocess
from typing import List, Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class SilenceProcessor:
    """静音处理器"""
    
    def __init__(self):
        self.vad_available = False
        self._init_vad()
    
    def _init_vad(self):
        """初始化语音活动检测"""
        try:
            from funasr import AutoModel
            self.vad_model = AutoModel(model="fsmn-vad", device="cpu")
            self.vad_available = True
            logger.info("[OK] FunASR VAD 模型加载成功")
        except ImportError:
            logger.warning("FunASR 未安装，VAD 功能不可用")
            self.vad_available = False
        except Exception as e:
            logger.warning(f"VAD 模型初始化失败: {e}")
            self.vad_available = False
    
    def detect_speech_segments(self, audio_path: Path) -> List[Dict]:
        """
        检测语音活动区间
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            语音区间列表，每个元素包含：
            - start: 开始时间（秒）
            - end: 结束时间（秒）
            - duration: 持续时间（秒）
        """
        if not self.vad_available:
            logger.warning("VAD 不可用，返回空结果")
            return []
        
        try:
            logger.info(f"开始检测语音活动: {audio_path}")
            
            # 使用 VAD 检测语音区间
            vad_result = self.vad_model.generate(input=str(audio_path), batch_size_s=300)
            
            # 提取语音区间
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
                                if duration >= 0.1:  # 过滤噪音
                                    speech_segments.append({
                                        'start': start,
                                        'end': end,
                                        'duration': duration
                                    })
            
            logger.info(f"VAD 检测到 {len(speech_segments)} 个语音区间")
            return speech_segments
            
        except Exception as e:
            logger.error(f"语音活动检测失败: {e}")
            return []
    
    def detect_silence_segments(self, audio_path: Path, min_silence_duration: float = 0.5) -> List[Dict]:
        """
        检测静音区间
        
        Args:
            audio_path: 音频文件路径
            min_silence_duration: 最小静音持续时间（秒）
            
        Returns:
            静音区间列表
        """
        speech_segments = self.detect_speech_segments(audio_path)
        
        if not speech_segments:
            return []
        
        # 按开始时间排序
        speech_segments.sort(key=lambda x: x['start'])
        
        silence_segments = []
        
        # 检测开头静音
        first_speech_start = speech_segments[0]['start']
        if first_speech_start > min_silence_duration:
            silence_segments.append({
                'start': 0.0,
                'end': first_speech_start,
                'duration': first_speech_start,
                'type': 'leading'  # 开头静音
            })
        
        # 检测语音之间的静音
        for i in range(len(speech_segments) - 1):
            current_end = speech_segments[i]['end']
            next_start = speech_segments[i+1]['start']
            silence_duration = next_start - current_end
            
            if silence_duration >= min_silence_duration:
                silence_segments.append({
                    'start': current_end,
                    'end': next_start,
                    'duration': silence_duration,
                    'type': 'middle'  # 中间静音
                })
        
        # 检测结尾静音（可选，通常不需要处理）
        
        logger.info(f"检测到 {len(silence_segments)} 个静音区间")
        return silence_segments
    
    def find_first_speech_start(self, audio_path: Path) -> float:
        """
        找到第一个语音开始的时间
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            第一个语音开始时间（秒），如果没有检测到语音返回0
        """
        speech_segments = self.detect_speech_segments(audio_path)
        
        if not speech_segments:
            logger.warning("未检测到语音活动")
            return 0.0
        
        # 返回第一个语音区间的开始时间
        first_segment = min(speech_segments, key=lambda x: x['start'])
        return first_segment['start']
    
    def adjust_clip_for_silence(self, clip_start: float, clip_end: float, 
                                audio_path: Path, 
                                silence_threshold: float = 2.0,
                                buffer_duration: float = 0.3) -> Tuple[float, float]:
        """
        根据静音检测结果调整切片时间
        
        Args:
            clip_start: 原始开始时间（秒）
            clip_end: 原始结束时间（秒）
            audio_path: 音频文件路径
            silence_threshold: 需要去除的静音阈值（秒）
            buffer_duration: 语音前后保留的缓冲时间（秒）
            
        Returns:
            调整后的开始时间和结束时间
        """
        speech_segments = self.detect_speech_segments(audio_path)
        
        if not speech_segments:
            logger.warning("未检测到语音活动，使用原始时间")
            return clip_start, clip_end
        
        # 过滤出在当前切片范围内的语音区间
        relevant_speech = []
        for segment in speech_segments:
            # 检查语音区间是否与切片有重叠
            if segment['end'] > clip_start and segment['start'] < clip_end:
                relevant_speech.append({
                    'start': max(segment['start'], clip_start),
                    'end': min(segment['end'], clip_end),
                    'duration': min(segment['end'], clip_end) - max(segment['start'], clip_start)
                })
        
        if not relevant_speech:
            logger.warning("切片范围内未检测到语音活动")
            return clip_start, clip_end
        
        # 按时间排序
        relevant_speech.sort(key=lambda x: x['start'])
        
        # 找到有效的语音区间（去除过长的静音间隔）
        filtered_segments = [relevant_speech[0]]
        
        for i in range(1, len(relevant_speech)):
            prev_end = filtered_segments[-1]['end']
            curr_start = relevant_speech[i]['start']
            gap = curr_start - prev_end
            
            if gap <= silence_threshold:
                # 静音间隔在阈值内，合并到前一个区间
                filtered_segments[-1]['end'] = relevant_speech[i]['end']
                filtered_segments[-1]['duration'] = filtered_segments[-1]['end'] - filtered_segments[-1]['start']
            else:
                # 静音间隔超过阈值，作为新的区间
                filtered_segments.append(relevant_speech[i])
        
        # 如果只有一个有效区间，使用它
        if len(filtered_segments) == 1:
            adjusted_start = max(filtered_segments[0]['start'] - buffer_duration, clip_start)
            adjusted_end = min(filtered_segments[0]['end'] + buffer_duration, clip_end)
            return adjusted_start, adjusted_end
        
        # 如果有多个区间，选择最长的一个
        longest_segment = max(filtered_segments, key=lambda x: x['duration'])
        adjusted_start = max(longest_segment['start'] - buffer_duration, clip_start)
        adjusted_end = min(longest_segment['end'] + buffer_duration, clip_end)
        
        logger.info(f"静音调整: {clip_start:.2f} -> {clip_end:.2f} => {adjusted_start:.2f} -> {adjusted_end:.2f}")
        return adjusted_start, adjusted_end
    
    def skip_leading_silence(self, audio_path: Path, max_skip: float = 30.0) -> float:
        """
        计算需要跳过的开头静音时间
        
        Args:
            audio_path: 音频文件路径
            max_skip: 最大跳过时间（秒）
            
        Returns:
            应该跳过的时间（秒）
        """
        first_speech_start = self.find_first_speech_start(audio_path)
        return min(first_speech_start, max_skip)
    
    @staticmethod
    def extract_audio_from_video(video_path: Path, output_audio_path: Path) -> bool:
        """
        从视频中提取音频
        
        Args:
            video_path: 视频文件路径
            output_audio_path: 输出音频路径
            
        Returns:
            是否成功
        """
        try:
            output_audio_path.parent.mkdir(parents=True, exist_ok=True)
            
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-vn',  # 不包含视频
                '-acodec', 'pcm_s16le',  # PCM 16位
                '-ar', '16000',  # 采样率
                '-ac', '1',  # 单声道
                '-y',
                str(output_audio_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                logger.info(f"成功提取音频: {output_audio_path}")
                return True
            else:
                logger.error(f"提取音频失败: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"提取音频异常: {str(e)}")
            return False


# 全局实例
silence_processor = SilenceProcessor()