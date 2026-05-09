"""
上下文边界精化器
基于上下文信息对边界位置进行微调，确保话题完整性
"""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ContextAwareBoundaryRefiner:
    """上下文边界精化器"""
    
    def __init__(self):
        # 话题完整性检查参数
        self.min_topic_length = 3  # 最小话题长度（句子数）
        self.max_topic_length = 20  # 最大话题长度（句子数）
        self.coherence_threshold = 0.5  # 连贯性阈值
    
    def refine(self, 
              boundaries: List[Dict],
              srt_data: List[Dict],
              max_adjustment: float = 2.0) -> List[Dict]:
        """
        精化边界位置，确保话题完整性
        
        Args:
            boundaries: 原始边界列表
            srt_data: 字幕数据
            max_adjustment: 最大调整时间（秒）
            
        Returns:
            精化后的边界列表
        """
        logger.info("开始上下文边界精化")
        
        if not boundaries or not srt_data:
            return boundaries
        
        # 按时间排序边界
        sorted_boundaries = sorted(boundaries, key=lambda x: x['time'])
        
        # 逐个检查边界
        refined_boundaries = []
        for i, boundary in enumerate(sorted_boundaries):
            refined = self._check_and_adjust(boundary, i, sorted_boundaries, srt_data)
            refined_boundaries.append(refined)
        
        # 进一步优化：检查话题完整性
        refined_boundaries = self._ensure_topic_completeness(refined_boundaries, srt_data)
        
        logger.info(f"边界精化完成，处理了 {len(refined_boundaries)} 个边界")
        return refined_boundaries
    
    def _check_and_adjust(self, 
                         boundary: Dict,
                         index: int,
                         all_boundaries: List[Dict],
                         srt_data: List[Dict]) -> Dict:
        """
        检查并调整单个边界位置
        
        Args:
            boundary: 当前边界
            index: 边界索引
            all_boundaries: 所有边界
            srt_data: 字幕数据
            
        Returns:
            调整后的边界
        """
        boundary_time = boundary['time']
        
        # 找到最近的字幕片段
        nearest_segment = self._find_nearest_segment(boundary_time, srt_data)
        
        if nearest_segment:
            # 检查边界是否在合理位置
            segment_end = self._parse_time(nearest_segment.get('end_time', '00:00:00.000'))
            segment_start = self._parse_time(nearest_segment.get('start_time', '00:00:00.000'))
            
            # 如果边界不在片段末尾附近，调整到合适位置
            distance_to_end = abs(boundary_time - segment_end)
            distance_to_start = abs(boundary_time - segment_start)
            
            if distance_to_end < distance_to_start:
                # 更接近结束时间，调整到片段结束
                new_time = segment_end
            else:
                # 更接近开始时间，调整到前一个片段结束（如果存在）
                new_time = self._find_prev_segment_end(index, nearest_segment, srt_data)
            
            # 检查调整幅度
            if abs(new_time - boundary_time) <= 2.0:  # 最大调整 2 秒
                boundary['time'] = new_time
                boundary['adjusted'] = True
                boundary['adjustment_reason'] = 'alignment'
        
        return boundary
    
    def _find_nearest_segment(self, time: float, srt_data: List[Dict]) -> Optional[Dict]:
        """找到最接近指定时间的字幕片段"""
        min_distance = float('inf')
        nearest = None
        
        for segment in srt_data:
            start = self._parse_time(segment.get('start_time', '00:00:00.000'))
            end = self._parse_time(segment.get('end_time', '00:00:00.000'))
            
            # 检查时间是否在片段范围内
            if start <= time <= end:
                return segment
            
            # 计算距离
            distance = min(abs(time - start), abs(time - end))
            if distance < min_distance:
                min_distance = distance
                nearest = segment
        
        return nearest
    
    def _find_prev_segment_end(self, 
                              boundary_index: int,
                              current_segment: Dict,
                              srt_data: List[Dict]) -> float:
        """找到前一个片段的结束时间"""
        # 查找当前片段在 srt_data 中的位置
        for i, segment in enumerate(srt_data):
            if segment == current_segment and i > 0:
                return self._parse_time(srt_data[i-1].get('end_time', '00:00:00.000'))
        
        return self._parse_time(current_segment.get('start_time', '00:00:00.000'))
    
    def _parse_time(self, time_str: str) -> float:
        """解析时间字符串为秒数"""
        try:
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
    
    def _ensure_topic_completeness(self, 
                                  boundaries: List[Dict],
                                  srt_data: List[Dict]) -> List[Dict]:
        """
        确保话题完整性，避免边界切断完整话题
        
        Args:
            boundaries: 边界列表
            srt_data: 字幕数据
            
        Returns:
            优化后的边界列表
        """
        if len(boundaries) < 2:
            return boundaries
        
        # 计算每个边界之间的片段数量
        result = []
        prev_time = 0.0
        
        for boundary in boundaries:
            current_time = boundary['time']
            
            # 计算两个边界之间的片段数量
            segment_count = self._count_segments_between(prev_time, current_time, srt_data)
            
            # 如果片段数量太少，可能需要合并边界
            if segment_count < self.min_topic_length and result:
                # 与前一个边界合并
                result[-1]['time'] = (result[-1]['time'] + current_time) / 2
                result[-1]['merged'] = True
            else:
                result.append(boundary)
            
            prev_time = current_time
        
        return result
    
    def _count_segments_between(self, 
                               start_time: float,
                               end_time: float,
                               srt_data: List[Dict]) -> int:
        """计算两个时间之间的字幕片段数量"""
        count = 0
        
        for segment in srt_data:
            segment_start = self._parse_time(segment.get('start_time', '00:00:00.000'))
            segment_end = self._parse_time(segment.get('end_time', '00:00:00.000'))
            
            # 检查片段是否在时间范围内
            if segment_start >= start_time and segment_end <= end_time:
                count += 1
        
        return count
    
    def _check_coherence(self, segments: List[Dict]) -> float:
        """
        检查一组片段的连贯性
        
        Args:
            segments: 字幕片段列表
            
        Returns:
            连贯度分数（0-1）
        """
        if len(segments) < 2:
            return 1.0
        
        total_similarity = 0.0
        count = 0
        
        for i in range(len(segments) - 1):
            text1 = segments[i].get('text', '')
            text2 = segments[i+1].get('text', '')
            
            similarity = self._calculate_similarity(text1, text2)
            total_similarity += similarity
            count += 1
        
        return total_similarity / count if count > 0 else 0.0
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两段文本的相似度"""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.strip().split())
        words2 = set(text2.strip().split())
        
        if not words1 and not words2:
            return 1.0
        
        intersection = words1 & words2
        union = words1 | words2
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
