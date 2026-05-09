"""
语音停顿分析器
检测音频中的语音停顿区间，用于辅助边界检测
"""
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class SpeechPauseAnalyzer:
    """语音停顿分析器"""
    
    def __init__(self):
        self.vad_available = False
        self._init_vad()
    
    def _init_vad(self):
        """初始化语音活动检测"""
        try:
            from funasr import AutoModel
            self.vad_model = AutoModel(model="fsmn-vad", device="cpu")
            self.vad_available = True
            logger.info("✅ FunASR VAD 模型加载成功")
        except ImportError:
            logger.warning("FunASR 未安装，VAD 功能不可用")
            self.vad_available = False
        except Exception as e:
            logger.warning(f"VAD 模型初始化失败: {e}")
            self.vad_available = False
    
    def analyze(self, audio_path: Path) -> List[Dict]:
        """
        分析语音停顿特征
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            停顿区间列表，每个元素包含：
            - start: 开始时间（秒）
            - end: 结束时间（秒）
            - duration: 持续时间（秒）
            - type: 停顿类型（short/medium/long）
            - confidence: 置信度
        """
        if not self.vad_available:
            logger.warning("VAD 不可用，返回空结果")
            return []
        
        try:
            logger.info(f"开始分析语音停顿: {audio_path}")
            
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
            
            # 提取停顿区间（语音区间之间的间隔）
            pauses = []
            for i in range(len(speech_segments) - 1):
                current_end = speech_segments[i]['end']
                next_start = speech_segments[i+1]['start']
                
                pause_duration = next_start - current_end
                
                # 过滤有效停顿（>200ms 且 <10s）
                if 0.2 < pause_duration < 10:
                    pause_type = self._classify_pause(pause_duration)
                    confidence = self._calculate_confidence(pause_duration)
                    
                    pauses.append({
                        'start': current_end,
                        'end': next_start,
                        'duration': pause_duration,
                        'type': pause_type,
                        'confidence': confidence
                    })
            
            logger.info(f"分析完成，找到 {len(pauses)} 个停顿区间")
            return pauses
            
        except Exception as e:
            logger.error(f"语音停顿分析失败: {e}")
            return []
    
    def _classify_pause(self, duration: float) -> str:
        """
        分类停顿类型
        
        Args:
            duration: 停顿持续时间（秒）
            
        Returns:
            停顿类型: short/medium/long
        """
        if duration < 0.5:
            return "short"      # 短停顿（语句内部）
        elif duration < 2.0:
            return "medium"     # 中等停顿（语句之间）
        else:
            return "long"       # 长停顿（话题转换）
    
    def _calculate_confidence(self, duration: float) -> float:
        """
        计算停顿置信度
        
        Args:
            duration: 停顿持续时间（秒）
            
        Returns:
            置信度（0-1）
        """
        # 基于停顿时长的置信度计算
        if duration < 0.3:
            return min(duration / 0.3, 1.0)
        elif duration < 2.0:
            return 0.8 + (duration - 0.3) * 0.1
        else:
            return min(0.95 + (duration - 2.0) * 0.02, 1.0)
    
    def find_boundary_candidates(self, audio_path: Path, threshold: float = 0.7) -> List[Dict]:
        """
        寻找潜在的边界候选点
        
        Args:
            audio_path: 音频文件路径
            threshold: 置信度阈值
            
        Returns:
            边界候选点列表，包含时间和置信度
        """
        pauses = self.analyze(audio_path)
        
        # 筛选高置信度的长停顿作为边界候选
        candidates = []
        for pause in pauses:
            if pause['type'] == 'long' and pause['confidence'] >= threshold:
                candidates.append({
                    'time': (pause['start'] + pause['end']) / 2,  # 取中间时间
                    'confidence': pause['confidence'],
                    'duration': pause['duration'],
                    'source': 'speech_pause'
                })
        
        return candidates
