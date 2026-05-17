"""
本地评分算法模块
不依赖LLM，基于字幕文本特征和音频能量进行基础评分
仅用于演示预览模式，明确标注"非AI智能识别"
"""

import logging
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass, field
import math

from backend.models.enums import ProcessMode
from backend.pipeline.strategies import PipelineStrategy, PipelineContext, PipelineResult

logger = logging.getLogger(__name__)


@dataclass
class ScoredClip:
    """评分后的片段"""
    id: int
    start_time: str
    end_time: str
    content: str
    final_score: float
    scoring_method: str = "local_preview"
    quality_note: str = "[WARN] 仅供预览，非AI智能识别"
    features: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "content": self.content,
            "final_score": self.final_score,
            "scoring_method": self.scoring_method,
            "quality_note": self.quality_note,
            "features": self.features
        }


class LocalScorer:
    """
    本地评分器
    
    核心原则：
    1. 不声称是"精彩片段识别"，而是"字幕片段预览"
    2. 评分逻辑透明，用户可理解
    3. 所有切片都保留，不做筛选
    """
    
    def __init__(
        self,
        audio_path: Optional[Path] = None,
        audio_energy_cache: Optional[Dict[int, float]] = None
    ):
        self.audio_path = audio_path
        self._audio_energy_cache = audio_energy_cache or {}
        
        # 评分参数配置
        self.config = {
            # 字幕长度评分
            "length_optimal_min": 20,
            "length_optimal_max": 80,
            "length_good_min": 10,
            "length_good_max": 120,
            "length_weight": 0.25,
            
            # 音频能量评分
            "energy_optimal_min": 0.3,
            "energy_optimal_max": 0.7,
            "energy_weight": 0.25,
            
            # 词汇多样性评分
            "diversity_weight": 0.25,
            
            # 术语检测评分
            "keyword_weight": 0.25,
            "keyword_boost_per_term": 0.05,
            "keyword_max_boost": 0.25
        }
        
        # 专业术语关键词库
        self._keyword_patterns = self._init_keyword_patterns()
    
    def _init_keyword_patterns(self) -> List[re.Pattern]:
        """初始化关键词正则模式"""
        keywords = [
            # 数字+名词组合（通常是重要信息）
            r'\d+%', r'\d+倍', r'\d+年', r'\d+个',
            
            # 强调词
            r'重要', r'关键', r'核心', r'必须', r'应该', r'建议', r'一定', r'绝对',
            
            # 分析词
            r'分析', r'研究', r'发现', r'结论', r'观点', r'看法',
            
            # 方法词
            r'方法', r'技巧', r'策略', r'步骤', r'流程', r'过程',
            
            # 转折后的内容
            r'但是', r'然而', r'不过'
        ]
        return [re.compile(kw, re.IGNORECASE) for kw in keywords]
    
    def score_clips(
        self,
        srt_data: List[Dict[str, Any]],
        audio_path: Optional[Path] = None
    ) -> List[ScoredClip]:
        """对字幕片段进行评分"""
        if not srt_data:
            logger.warning("字幕数据为空，无法评分")
            return []
        
        # 如果提供了音频路径，加载能量数据
        if audio_path and not self._audio_energy_cache:
            self._audio_energy_cache = self._calculate_audio_energies(
                audio_path, srt_data
            )
        
        scored_clips = []
        
        for i, segment in enumerate(srt_data):
            # 提取片段信息
            content = segment.get('content', '') or segment.get('text', '')
            start_time = segment.get('start_time', segment.get('start', '00:00:00'))
            end_time = segment.get('end_time', segment.get('end', '00:00:00'))
            
            # 计算各维度得分
            length_score = self._score_text_length(content)
            energy_score = self._score_audio_energy(i)
            diversity_score = self._score_vocabulary_diversity(content)
            keyword_score = self._score_keywords(content)
            
            # 如果内容太少，给一个基础分避免0分
            if not content or len(content.strip()) < 5:
                length_score = 0.6
                diversity_score = 0.5
                keyword_score = 0.4
            
            # 综合评分（加权平均）
            final_score = (
                length_score * self.config["length_weight"] +
                energy_score * self.config["energy_weight"] +
                diversity_score * self.config["diversity_weight"] +
                keyword_score * self.config["keyword_weight"]
            )
            
            # 确保分数在 0-1 之间，且不会太低
            final_score = max(0.3, min(1.0, final_score))
            
            # 创建评分片段
            scored = ScoredClip(
                id=i,
                start_time=start_time,
                end_time=end_time,
                content=content if content else f"片段{i+1}内容",
                final_score=round(final_score, 3),
                scoring_method="local_preview",
                quality_note="[WARN] 仅供预览，非AI智能识别",
                features={
                    "length_score": round(length_score, 3),
                    "energy_score": round(energy_score, 3),
                    "diversity_score": round(diversity_score, 3),
                    "keyword_score": round(keyword_score, 3)
                }
            )
            
            scored_clips.append(scored)
        
        logger.info(f"本地评分完成，共 {len(scored_clips)} 个片段")
        logger.info(f"分数范围: {min(c.final_score for c in scored_clips):.3f} - {max(c.final_score for c in scored_clips):.3f}")
        
        return scored_clips
    
    def _score_text_length(self, text: str) -> float:
        """字幕长度评分（倒U型）"""
        actual_length = len(text.replace(' ', '').replace('\n', ''))
        
        optimal_min = self.config["length_optimal_min"]
        optimal_max = self.config["length_optimal_max"]
        good_min = self.config["length_good_min"]
        good_max = self.config["length_good_max"]
        
        if optimal_min <= actual_length <= optimal_max:
            return 1.0
        elif good_min <= actual_length < optimal_min:
            ratio = (actual_length - good_min) / (optimal_min - good_min)
            return 0.7 + 0.3 * ratio
        elif optimal_max < actual_length <= good_max:
            ratio = (good_max - actual_length) / (good_max - optimal_max)
            return 0.7 + 0.3 * ratio
        elif good_min <= actual_length <= good_max:
            return 0.5
        else:
            if actual_length < good_min:
                return max(0.2, actual_length / good_min * 0.5)
            else:
                return max(0.2, (good_max / actual_length) * 0.5)
    
    def _score_audio_energy(self, segment_index: int) -> float:
        """音频能量评分"""
        if not self._audio_energy_cache:
            return 0.5
        
        energy = self._audio_energy_cache.get(segment_index, 0.5)
        
        optimal_min = self.config["energy_optimal_min"]
        optimal_max = self.config["energy_optimal_max"]
        
        if optimal_min <= energy <= optimal_max:
            return 1.0
        elif energy < optimal_min:
            return max(0.2, energy / optimal_min * 0.7)
        else:
            ratio = (1.0 - energy) / (1.0 - optimal_max) if optimal_max < 1.0 else 0.5
            return max(0.2, ratio * 0.7)
    
    def _score_vocabulary_diversity(self, text: str) -> float:
        """词汇多样性评分"""
        if not text:
            return 0.0
        
        clean_text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text)
        if len(clean_text) == 0:
            return 0.0
        
        unique_chars = len(set(clean_text))
        total_chars = len(clean_text)
        diversity_ratio = unique_chars / total_chars if total_chars > 0 else 0
        
        score = (diversity_ratio - 0.3) / 0.4 if diversity_ratio >= 0.3 else diversity_ratio / 0.3 * 0.3
        return max(0.0, min(1.0, score))
    
    def _score_keywords(self, text: str) -> float:
        """关键词检测评分"""
        keyword_count = 0
        for pattern in self._keyword_patterns:
            matches = pattern.findall(text)
            keyword_count += len(matches)
        
        boost = min(
            keyword_count * self.config["keyword_boost_per_term"],
            self.config["keyword_max_boost"]
        )
        return 0.3 + boost
    
    def _calculate_audio_energies(
        self,
        audio_path: Path,
        srt_data: List[Dict[str, Any]]
    ) -> Dict[int, float]:
        """计算音频能量数据（兼容各种库不可用的情况）"""
        energies = {}
        
        try:
            # 优先使用 librosa
            import librosa
            import numpy as np
            
            y, sr = librosa.load(audio_path, sr=16000)
            frame_length = 2048
            hop_length = 512
            
            rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
            rms = rms / (np.max(rms) + 1e-10)
            
            for i, segment in enumerate(srt_data):
                start_time = self._parse_time_to_seconds(segment.get('start_time', segment.get('start', '0')))
                end_time = self._parse_time_to_seconds(segment.get('end_time', segment.get('end', '0')))
                
                start_frame = int(start_time * sr / hop_length)
                end_frame = int(end_time * sr / hop_length)
                
                start_frame = max(0, start_frame)
                end_frame = min(len(rms), end_frame)
                
                if start_frame < end_frame:
                    segment_energy = np.mean(rms[start_frame:end_frame])
                else:
                    segment_energy = 0.5
                
                energies[i] = float(segment_energy)
            
            logger.info(f"使用librosa计算音频能量: {len(energies)} 个片段")
            
        except ImportError:
            try:
                # fallback 到 scipy
                from scipy.io import wavfile
                import numpy as np
                
                sr, y = wavfile.read(audio_path)
                if len(y.shape) > 1:
                    y = np.mean(y, axis=1)
                
                frame_length = int(sr * 0.025)
                hop_length = int(sr * 0.01)
                
                energies_list = []
                for i in range(0, len(y) - frame_length, hop_length):
                    frame = y[i:i + frame_length]
                    energy = np.sqrt(np.mean(frame.astype(float) ** 2))
                    energies_list.append(energy)
                
                energies_array = np.array(energies_list)
                energies_array = energies_array / (np.max(energies_array) + 1e-10)
                
                for i, segment in enumerate(srt_data):
                    start_time = self._parse_time_to_seconds(segment.get('start_time', segment.get('start', '0')))
                    end_time = self._parse_time_to_seconds(segment.get('end_time', segment.get('end', '0')))
                    
                    start_idx = int(start_time * sr / hop_length)
                    end_idx = int(end_time * sr / hop_length)
                    
                    start_idx = max(0, start_idx)
                    end_idx = min(len(energies_array), end_idx)
                    
                    if start_idx < end_idx:
                        segment_energy = np.mean(energies_array[start_idx:end_idx])
                    else:
                        segment_energy = 0.5
                    
                    energies[i] = float(segment_energy)
                
                logger.info(f"使用scipy计算音频能量: {len(energies)} 个片段")
                
            except ImportError:
                logger.warning("无音频处理库，使用默认能量值")
                for i in range(len(srt_data)):
                    energies[i] = 0.5
        
        return energies
    
    @staticmethod
    def _parse_time_to_seconds(time_str: str) -> float:
        """解析时间字符串为秒数"""
        try:
            time_str = time_str.replace(',', '.')
            if ':' in time_str:
                parts = time_str.split(':')
                if len(parts) == 3:
                    h, m, s = parts
                    return float(h) * 3600 + float(m) * 60 + float(s)
                elif len(parts) == 2:
                    m, s = parts
                    return float(m) * 60 + float(s)
            else:
                return float(time_str)
        except:
            return 0.0


# 便捷函数
def local_score_clips(
    srt_data: List[Dict[str, Any]],
    audio_path: Optional[Path] = None
) -> List[Dict[str, Any]]:
    """便捷函数：对字幕片段进行本地评分"""
    scorer = LocalScorer(audio_path=audio_path)
    scored = scorer.score_clips(srt_data, audio_path)
    return [s.to_dict() for s in scored]

