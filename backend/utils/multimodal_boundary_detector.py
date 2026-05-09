"""
多模态边界检测器
融合文本语义、语音停顿、视频场景等多种特征进行边界检测
"""
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class MultimodalBoundaryDetector:
    """多模态边界检测器"""
    
    def __init__(self):
        # 各模态权重（可配置）
        self.weights = {
            "text_semantic": 0.4,      # 文本语义相似度
            "speech_pause": 0.3,       # 语音停顿特征
            "video_scene": 0.2,        # 视频场景切换
            "audio_energy": 0.1        # 音频能量变化
        }
        
        # 懒加载组件
        self._speech_pause_analyzer = None
        self._video_scene_detector = None
    
    def _get_speech_pause_analyzer(self):
        """获取语音停顿分析器"""
        if self._speech_pause_analyzer is None:
            try:
                from .speech_pause_analyzer import SpeechPauseAnalyzer
                self._speech_pause_analyzer = SpeechPauseAnalyzer()
            except Exception as e:
                logger.warning(f"语音停顿分析器加载失败: {e}")
        return self._speech_pause_analyzer
    
    def _get_video_scene_detector(self):
        """获取视频场景检测器"""
        if self._video_scene_detector is None:
            try:
                from .video_scene_detector import VideoSceneDetector
                self._video_scene_detector = VideoSceneDetector()
            except Exception as e:
                logger.warning(f"视频场景检测器加载失败: {e}")
        return self._video_scene_detector
    
    def detect_boundaries(self, 
                        srt_data: List[Dict],
                        audio_path: Optional[Path] = None,
                        video_path: Optional[Path] = None) -> List[Dict]:
        """
        多模态边界检测
        
        Args:
            srt_data: 字幕数据列表
            audio_path: 音频文件路径（可选）
            video_path: 视频文件路径（可选）
            
        Returns:
            边界列表，每个元素包含：
            - time: 边界时间（秒）
            - confidence: 综合置信度
            - sources: 各模态贡献
        """
        logger.info("开始多模态边界检测")
        
        # 收集各模态的边界候选
        candidates = []
        
        # 1. 文本语义边界检测
        text_boundaries = self._detect_text_boundaries(srt_data)
        candidates.extend(text_boundaries)
        
        # 2. 语音停顿边界检测
        if audio_path:
            speech_pause_analyzer = self._get_speech_pause_analyzer()
            if speech_pause_analyzer:
                speech_boundaries = speech_pause_analyzer.find_boundary_candidates(audio_path)
                candidates.extend(speech_boundaries)
        
        # 3. 视频场景边界检测
        if video_path:
            video_scene_detector = self._get_video_scene_detector()
            if video_scene_detector:
                video_boundaries = video_scene_detector.find_boundary_candidates(video_path)
                candidates.extend(video_boundaries)
        
        # 4. 加权融合
        final_boundaries = self._fuse_boundaries(candidates)
        
        logger.info(f"多模态边界检测完成，找到 {len(final_boundaries)} 个边界")
        return final_boundaries
    
    def _detect_text_boundaries(self, srt_data: List[Dict]) -> List[Dict]:
        """
        基于文本语义的边界检测
        
        Args:
            srt_data: 字幕数据列表
            
        Returns:
            边界候选点列表
        """
        boundaries = []
        
        if len(srt_data) < 2:
            return boundaries
        
        # 计算相邻字幕片段的语义相似度
        for i in range(len(srt_data) - 1):
            current_text = srt_data[i].get('text', '')
            next_text = srt_data[i+1].get('text', '')
            
            # 简化的语义相似度计算（基于文本长度和重叠）
            similarity = self._calculate_similarity(current_text, next_text)
            
            # 如果相似度低于阈值，认为是边界
            if similarity < 0.3:
                # 计算边界时间（取两个片段之间的时间点）
                current_end = self._parse_time(srt_data[i].get('end_time', '00:00:00.000'))
                next_start = self._parse_time(srt_data[i+1].get('start_time', '00:00:00.000'))
                
                boundary_time = (current_end + next_start) / 2
                
                boundaries.append({
                    'time': boundary_time,
                    'confidence': 1 - similarity,
                    'source': 'text_semantic'
                })
        
        return boundaries
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两段文本的相似度（简化实现）
        
        Args:
            text1: 第一段文本
            text2: 第二段文本
            
        Returns:
            相似度（0-1）
        """
        if not text1 or not text2:
            return 0.0
        
        # 基于共同词汇的相似度
        words1 = set(text1.strip().split())
        words2 = set(text2.strip().split())
        
        if not words1 and not words2:
            return 1.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    def _parse_time(self, time_str: str) -> float:
        """解析时间字符串为秒数"""
        try:
            # 处理 SRT 时间格式：00:00:00,000 或 00:00:00.000
            time_str = time_str.replace(',', '.')
            parts = time_str.split(':')
            if len(parts) == 3:
                hours = float(parts[0])
                minutes = float(parts[1])
                seconds = float(parts[2])
                return hours * 3600 + minutes * 60 + seconds
        except Exception as e:
            logger.warning(f"时间解析失败: {time_str}, {e}")
        
        return 0.0
    
    def _fuse_boundaries(self, candidates: List[Dict]) -> List[Dict]:
        """
        加权融合多模态边界候选
        
        Args:
            candidates: 各模态的边界候选列表
            
        Returns:
            融合后的边界列表
        """
        if not candidates:
            return []
        
        # 按时间分组，合并相近的边界
        merged = {}
        
        for candidate in candidates:
            time = candidate['time']
            source = candidate['source']
            confidence = candidate['confidence']
            
            # 找到相近的边界（±1秒）
            found = False
            for existing_time in list(merged.keys()):
                if abs(time - existing_time) < 1.0:
                    # 合并到现有边界
                    merged[existing_time]['sources'].append({
                        'source': source,
                        'confidence': confidence
                    })
                    found = True
                    break
            
            if not found:
                merged[time] = {
                    'time': time,
                    'confidence': 0.0,
                    'sources': [{
                        'source': source,
                        'confidence': confidence
                    }]
                }
        
        # 计算综合置信度
        final_boundaries = []
        for time, data in merged.items():
            total_weight = 0.0
            weighted_confidence = 0.0
            
            for source_info in data['sources']:
                source = source_info['source']
                confidence = source_info['confidence']
                weight = self.weights.get(source, 0.25)  # 默认权重
                
                total_weight += weight
                weighted_confidence += weight * confidence
            
            if total_weight > 0:
                overall_confidence = weighted_confidence / total_weight
            else:
                overall_confidence = 0.0
            
            final_boundaries.append({
                'time': time,
                'confidence': overall_confidence,
                'sources': data['sources']
            })
        
        # 按时间排序
        final_boundaries.sort(key=lambda x: x['time'])
        
        return final_boundaries
    
    def set_weights(self, weights: Dict[str, float]):
        """
        设置各模态权重
        
        Args:
            weights: 权重字典
        """
        self.weights.update(weights)
        logger.info(f"更新多模态权重: {self.weights}")
