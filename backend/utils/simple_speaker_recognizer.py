"""
简化版说话人识别 - 方案A
基于文本特征的轻量级说话人识别（不依赖 ModelScope）

借鉴 FunClip 的思路，但实现更简单：
1. 分析段落文本特征
2. 使用 K-means 聚类分配说话人
3. 零额外依赖

作者：AutoClip 团队
"""

import logging
import json
import random
import math
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class SimpleSpeakerRecognizer:
    """
    基于文本特征的轻量级说话人识别器
    """

    def __init__(self, n_clusters: int = 2):
        self.n_clusters = n_clusters
        self.use_cache = True

    def recognize_srt_segments(
        self,
        srt_data: List[Dict],
        audio_path: Optional[Path] = None,
        cache_path: Optional[Path] = None
    ) -> List[Dict]:
        """
        识别 SRT 每个段落的说话人（简化版）

        Args:
            srt_data: SRT 解析结果
            audio_path: 音频文件路径（兼容旧接口，不使用）
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

        logger.info("开始基于文本特征的说话人识别（简化版）...")

        # 步骤1：提取特征
        features = self._extract_features(srt_data)

        # 步骤2：聚类
        labels = self._simple_cluster(features, self.n_clusters)

        # 步骤3：分配说话人ID
        for i, sub in enumerate(srt_data):
            sub['speaker_id'] = f'spk{labels[i]}'

        logger.info(f"说话人识别完成！共识别到 {len(set(labels))} 个说话人")

        # 保存缓存
        if cache_path:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(srt_data, f, ensure_ascii=False, indent=2)
            logger.info(f"说话人识别结果已缓存到: {cache_path}")

        return srt_data

    def _extract_features(self, srt_data: List[Dict]) -> List[List[float]]:
        """
        提取每个段落的文本特征

        特征维度：
        1. 文本长度
        2. 标点符号数量（逗号 + 句号）
        3. 平均词长
        4. 数字出现次数
        5. 感叹词出现次数（啊、呀、哦等）
        """
        features = []
        exclamations = {'啊', '呀', '哦', '嗯', '呢', '吧', '吗', '啦', '哇'}

        for sub in srt_data:
            text = sub.get('text', '')

            # 特征1：文本长度
            len_feat = len(text)

            # 特征2：标点数量
            punc_feat = text.count('，') + text.count('。') + text.count('？') + text.count('！')

            # 特征3：平均词长（简单按字符分割）
            words = [c for c in text if c.strip()]
            avg_word_len = len(text) / max(len(words), 1)

            # 特征4：数字出现次数
            digits = sum(1 for c in text if c.isdigit())

            # 特征5：感叹词
            exclam_feat = sum(1 for c in text if c in exclamations)

            features.append([
                len_feat * 0.1,  # 归一化
                punc_feat * 0.5,
                avg_word_len,
                digits * 0.3,
                exclam_feat * 0.8
            ])

        return features

    def _simple_cluster(self, features: List[List[float]], n_clusters: int) -> List[int]:
        """
        简单的 K-means 聚类实现（纯 Python）

        简化版：
        1. 随机初始化中心点
        2. 迭代 50 次
        """
        if not features:
            return []

        # 数据点太少
        if len(features) <= n_clusters:
            return list(range(len(features)))

        # 随机初始化中心点
        random.seed(42)  # 固定种子保证可复现性
        centroids_idx = random.sample(range(len(features)), n_clusters)
        centroids = [features[i] for i in centroids_idx]

        labels = [0] * len(features)

        # 迭代 20 次
        for _ in range(20):
            # 分配：每个点到最近的中心点
            new_labels = []
            for point in features:
                distances = [
                    self._distance(point, centroid)
                    for centroid in centroids
                ]
                new_label = distances.index(min(distances))
                new_labels.append(new_label)

            # 如果没有变化，提前退出
            if new_labels == labels:
                break
            labels = new_labels

            # 更新中心点
            clusters = defaultdict(list)
            for i, label in enumerate(labels):
                clusters[label].append(features[i])

            for i in range(n_clusters):
                if i in clusters and clusters[i]:
                    centroids[i] = self._average(clusters[i])

        return labels

    def _distance(self, a: List[float], b: List[float]) -> float:
        """欧几里得距离"""
        squared_sum = 0.0
        for ai, bi in zip(a, b):
            squared_sum += (ai - bi) ** 2
        return math.sqrt(squared_sum)

    def _average(self, points: List[List[float]]) -> List[float]:
        """计算多个点的平均中心"""
        if not points:
            return []

        avg = [0.0 for _ in points[0]]
        for point in points:
            for i, val in enumerate(point):
                avg[i] += val

        return [val / len(points) for val in avg]

    @staticmethod
    def _validate_cached_data(cached_data: List[Dict], original_data: List[Dict]) -> bool:
        """验证缓存数据是否有效"""
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
    为话题找到主导说话人（重用）

    保持与原函数相同的接口
    """
    if not srt_with_speakers:
        return None

    topic_start = _time_to_seconds(topic_timeline.get('start_time', '00:00:00,000'))
    topic_end = _time_to_seconds(topic_timeline.get('end_time', '00:00:00,000'))

    speaker_counts = defaultdict(int)

    for sub in srt_with_speakers:
        sub_start = _time_to_seconds(sub.get('start_time', '00:00:00,000'))
        sub_end = _time_to_seconds(sub.get('end_time', '00:00:00,000'))

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
    获取说话人统计（重用）

    保持与原函数相同的接口
    """
    stats = defaultdict(int)
    for item in timeline:
        speaker = item.get('speaker_id')
        if speaker:
            stats[speaker] += 1
    return dict(stats)


def _time_to_seconds(time_str: str) -> float:
    """
    SRT 时间转秒（重用）
    """
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

        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms_part) / 1000
    except Exception as e:
        logger.warning(f"解析时间失败: {time_str}, {e}")
        return 0
