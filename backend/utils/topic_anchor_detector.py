"""
话题锚点检测器
用于在滑动窗口分块中识别完整的话题边界
"""
import logging
from typing import List, Dict, Any, Optional, Set
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class TopicAnchorDetector:
    def __init__(
        self,
        anchor_window_size: int = 30,
        similarity_threshold: float = 0.6,
        completeness_threshold: float = 0.8
    ):
        self.anchor_window_size = anchor_window_size
        self.similarity_threshold = similarity_threshold
        self.completeness_threshold = completeness_threshold

    def detect_anchors(
        self,
        chunks: List[Dict],
        timeline_data: List[Dict]
    ) -> List[Dict]:
        if not chunks or not timeline_data:
            return timeline_data

        logger.info(f"开始话题锚点检测: {len(timeline_data)} 个话题, {len(chunks)} 个分块")

        timeline_with_coverage = self._analyze_topic_coverage(chunks, timeline_data)
        deduplicated = self._deduplicate_timeline(timeline_with_coverage)
        anchors = self._identify_anchors(deduplicated)

        logger.info(f"话题锚点检测完成: {len(anchors)}/{len(timeline_data)} 个有效话题")
        return anchors

    def _analyze_topic_coverage(
        self,
        chunks: List[Dict],
        timeline_data: List[Dict]
    ) -> List[Dict]:
        for topic in timeline_data:
            topic['coverage'] = self._calculate_coverage(topic, chunks)
            topic['is_complete'] = topic['coverage'] >= self.completeness_threshold
        return timeline_data

    def _calculate_coverage(
        self,
        topic: Dict,
        chunks: List[Dict]
    ) -> float:
        topic_start = self._time_to_seconds(topic.get('start_time', '0'))
        topic_end = self._time_to_seconds(topic.get('end_time', '0'))
        topic_duration = topic_end - topic_start

        if topic_duration <= 0:
            return 0.0

        covered_time = 0.0
        for chunk in chunks:
            chunk_start = chunk.get('start_seconds', 0)
            chunk_end = chunk.get('end_seconds', 0)

            overlap_start = max(topic_start, chunk_start)
            overlap_end = min(topic_end, chunk_end)
            if overlap_end > overlap_start:
                covered_time += overlap_end - overlap_start

        return covered_time / topic_duration

    def _deduplicate_timeline(
        self,
        timeline_data: List[Dict]
    ) -> List[Dict]:
        if len(timeline_data) <= 1:
            return timeline_data

        timeline_data.sort(key=lambda x: self._time_to_seconds(x.get('start_time', '0')))

        deduplicated = []
        for topic in timeline_data:
            is_duplicate = False
            for existing in deduplicated:
                if self._topics_are_similar(topic, existing):
                    if topic.get('coverage', 0) > existing.get('coverage', 0):
                        deduplicated.remove(existing)
                        deduplicated.append(topic)
                        logger.debug(f"替换重复话题: {existing['outline']} -> {topic['outline']}")
                    else:
                        logger.debug(f"跳过重复话题: {topic['outline']}")
                    is_duplicate = True
                    break
            if not is_duplicate:
                deduplicated.append(topic)

        return deduplicated

    def _topics_are_similar(
        self,
        topic1: Dict,
        topic2: Dict
    ) -> bool:
        outline1 = topic1.get('outline', '').lower()
        outline2 = topic2.get('outline', '').lower()

        if outline1 == outline2:
            return True

        similarity = SequenceMatcher(None, outline1, outline2).ratio()
        if similarity >= self.similarity_threshold:
            return True

        time1_start = self._time_to_seconds(topic1.get('start_time', '0'))
        time1_end = self._time_to_seconds(topic1.get('end_time', '0'))
        time2_start = self._time_to_seconds(topic2.get('start_time', '0'))
        time2_end = self._time_to_seconds(topic2.get('end_time', '0'))

        overlap_start = max(time1_start, time2_start)
        overlap_end = min(time1_end, time2_end)
        overlap = max(0, overlap_end - overlap_start)

        shorter_duration = min(time1_end - time1_start, time2_end - time2_start)
        if shorter_duration > 0:
            overlap_ratio = overlap / shorter_duration
            if overlap_ratio >= 0.5:
                return True

        return False

    def _identify_anchors(
        self,
        timeline_data: List[Dict]
    ) -> List[Dict]:
        anchors = []
        for topic in timeline_data:
            if topic.get('is_complete', False) or topic.get('coverage', 0) >= 0.5:
                anchors.append(topic)
            else:
                logger.warning(f"跳过不完整话题: {topic.get('outline')} (完整度: {topic.get('coverage', 0):.2%})")
        return anchors

    @staticmethod
    def _time_to_seconds(time_str: str) -> float:
        time_str = time_str.replace(',', '.')
        parts = time_str.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
        elif len(parts) == 2:
            minutes, seconds = parts
            return float(minutes) * 60 + float(seconds)
        return 0.0
