import re
import math
import time
import random
import logging
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import List, Set, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TimeRange:
    start_seconds: float
    end_seconds: float

    @property
    def duration(self) -> float:
        return self.end_seconds - self.start_seconds

    def to_srt_range(self) -> str:
        def _to_srt(s):
            h = int(s // 3600)
            m = int((s % 3600) // 60)
            sec = s % 60
            return f"{h:02d}:{m:02d}:{sec:06.3f}".replace('.', ',')
        return f"{_to_srt(self.start_seconds)} -> {_to_srt(self.end_seconds)}"


@dataclass
class SrtEntry:
    index: int
    start_seconds: float
    end_seconds: float
    start_str: str
    end_str: str
    raw_text: str
    text: str
    duration: float


_FILLER_WORDS = {
    '嗯', '呃', '哦', '哈', '嘿', '哎', '唉',
    '嗯嗯', '呃呃', '哈哈', '嘿嘿',
    '那个', '那个啥', '这个',
    '就是', '就是说', '也就是说',
    '然后', '然后呢',
    '对吧', '是吧', '对不对', '是不是',
    '所以说', '所以说呢',
    '的话', '的话呢',
    '好的', '好吧', '好呢',
    '一个', '一种',
    '我们可以看到', '大家可以看到',
    '总的来说', '总的来说呢',
}


def _clean_filler_words(text: str) -> str:
    for word in sorted(_FILLER_WORDS, key=len, reverse=True):
        text = re.sub(re.escape(word), '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _srt_time_to_seconds(time_str: str) -> float:
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def _seconds_to_srt_str(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace('.', ',')


class SrtEntryParser:
    def parse(self, srt_text: str) -> List[SrtEntry]:
        if not srt_text or not srt_text.strip():
            return []

        entries = []
        blocks = re.split(r'\n\s*\n', srt_text.strip())

        for block in blocks:
            lines = block.strip().split('\n')
            if len(lines) < 3:
                continue

            time_line = lines[1]
            m = re.match(r'(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})', time_line)
            if not m:
                logger.warning(f"跳过格式损坏的SRT条目: {time_line[:40]}")
                continue

            start_str = m.group(1).replace('.', ',')
            end_str = m.group(2).replace('.', ',')
            start = _srt_time_to_seconds(m.group(1))
            end = _srt_time_to_seconds(m.group(2))

            raw_text = ' '.join(lines[2:]).strip()
            cleaned_text = _clean_filler_words(raw_text)

            entries.append(SrtEntry(
                index=len(entries) + 1,
                start_seconds=start,
                end_seconds=end,
                start_str=start_str,
                end_str=end_str,
                raw_text=raw_text,
                text=cleaned_text,
                duration=end - start
            ))

        entries.sort(key=lambda e: e.start_seconds)
        return entries


@dataclass
class NgramConfig:
    n: int = 0
    filter_stopword_only: bool = True


_STOP_CHARS = frozenset('的了是在我有和就不人都一个上也很到说要去你会着没有看')


class NgramExtractor:
    def extract(self, entries: List[SrtEntry], config: Optional[NgramConfig] = None) -> List[Set[str]]:
        config = config or NgramConfig()
        if config.n == 0:
            n = self._auto_select_n(entries)
        else:
            n = config.n

        results = []
        for entry in entries:
            source = entry.text
            if len(entry.text) < n:
                source = _clean_filler_words(entry.raw_text)
            grams = self._char_ngrams(source, n, config)
            results.append(grams)
        return results

    def _auto_select_n(self, entries: List[SrtEntry]) -> int:
        if not entries:
            return 2
        total_len = sum(len(e.text) for e in entries)
        avg_len = total_len / len(entries)
        return 3 if avg_len > 25 else 2

    def _char_ngrams(self, text: str, n: int, config: Optional[NgramConfig] = None) -> Set[str]:
        if not text:
            return set()
        config = config or NgramConfig()

        text = unicodedata.normalize('NFKC', text)
        text = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\u2064\ufeff]', '', text)
        text = re.sub('[\\s,，。！？、；：""''()\\[\\]【】\\-]', '', text)

        if not text or len(text) < n:
            return set()

        grams = set()
        for i in range(len(text) - n + 1):
            gram = text[i:i + n]
            if config.filter_stopword_only and all(c in _STOP_CHARS for c in gram):
                continue
            grams.add(gram)
        return grams


@dataclass
class SimilarityConfig:
    method: str = "cosine"
    min_intersection: int = 1


class SimilarityCalculator:
    def compute_matrix(self, ngram_sets: List[Set[str]], config: Optional[SimilarityConfig] = None) -> List[List[float]]:
        if not ngram_sets:
            return []
        config = config or SimilarityConfig()
        n = len(ngram_sets)
        matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            matrix[i][i] = 1.0
            for j in range(i + 1, n):
                sim = self._cosine_similarity(ngram_sets[i], ngram_sets[j], config.min_intersection)
                matrix[i][j] = sim
                matrix[j][i] = sim
        return matrix

    def _cosine_similarity(self, set_a: Set[str], set_b: Set[str], min_intersection: int = 1) -> float:
        intersection = len(set_a & set_b)
        if intersection < min_intersection:
            return 0.0
        denominator = math.sqrt(len(set_a) * len(set_b))
        if denominator == 0:
            return 0.0
        return intersection / denominator


@dataclass
class ClusterConfig:
    similarity_threshold: float = 0.15
    min_cluster_size: int = 3
    min_multi_segment_size: int = 2
    internal_sim_threshold: float = 0.08
    time_gap_threshold: float = 30.0


@dataclass
class TopicCluster:
    id: str
    entry_indices: List[int]
    time_ranges: List[TimeRange]
    internal_similarity: float
    topic_keywords: List[str] = field(default_factory=list)
    is_multi_segment: bool = False
    confidence: float = 0.0


class ClusterEngine:
    def __init__(self, config: Optional[ClusterConfig] = None):
        self.config = config or ClusterConfig()

    def cluster(self, matrix: List[List[float]], entries: List[SrtEntry]) -> List[TopicCluster]:
        if not matrix or not entries:
            return []

        components = self._bfs_components(matrix)

        clusters = []
        for comp in components:
            time_ranges = self._extract_time_ranges([entries[i] for i in sorted(comp)])
            is_multi = len(time_ranges) > 1

            internal_sim = self._internal_similarity(comp, matrix)

            min_size = self.config.min_multi_segment_size if is_multi else self.config.min_cluster_size
            if len(comp) < min_size:
                continue

            if internal_sim < self.config.internal_sim_threshold:
                continue

            confidence = self._calculate_confidence(comp, matrix, is_multi)

            cluster = TopicCluster(
                id=f"TC-{len(clusters) + 1}",
                entry_indices=sorted(comp),
                time_ranges=time_ranges,
                internal_similarity=internal_sim,
                is_multi_segment=is_multi,
                confidence=confidence,
            )
            clusters.append(cluster)

        clusters.sort(key=lambda c: c.confidence, reverse=True)
        for i, c in enumerate(clusters):
            c.id = f"TC-{i + 1}"
        return clusters

    def _bfs_components(self, matrix: List[List[float]]) -> List[Set[int]]:
        n = len(matrix)
        visited = [False] * n
        components = []
        for i in range(n):
            if not visited[i]:
                comp = set()
                queue = [i]
                visited[i] = True
                while queue:
                    node = queue.pop(0)
                    comp.add(node)
                    for j in range(n):
                        if not visited[j] and matrix[node][j] > self.config.similarity_threshold:
                            visited[j] = True
                            queue.append(j)
                components.append(comp)
        return components

    def _extract_time_ranges(self, entries: List[SrtEntry]) -> List[TimeRange]:
        if not entries:
            return []
        sorted_entries = sorted(entries, key=lambda e: e.start_seconds)
        ranges = []
        current_start = sorted_entries[0].start_seconds
        current_end = sorted_entries[0].end_seconds
        for i in range(1, len(sorted_entries)):
            gap = sorted_entries[i].start_seconds - sorted_entries[i - 1].end_seconds
            if gap >= self.config.time_gap_threshold:
                ranges.append(TimeRange(current_start, current_end))
                current_start = sorted_entries[i].start_seconds
                current_end = sorted_entries[i].end_seconds
            else:
                current_end = sorted_entries[i].end_seconds
        ranges.append(TimeRange(current_start, current_end))
        return ranges

    def _internal_similarity(self, comp: Set[int], matrix: List[List[float]]) -> float:
        indices = list(comp)
        if len(indices) < 2:
            return 1.0
        total = 0.0
        count = 0
        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                total += matrix[indices[i]][indices[j]]
                count += 1
        return total / count if count > 0 else 0.0

    def _calculate_confidence(self, comp: Set[int], matrix: List[List[float]], is_multi: bool) -> float:
        internal_sim = self._internal_similarity(comp, matrix)
        size_factor = min(len(comp) / 20.0, 1.0)
        return 0.6 * internal_sim + 0.4 * size_factor


@dataclass
class WordExtractConfig:
    top_n: int = 6
    min_phrase_length: int = 5
    max_phrase_length: int = 30


class ClusterWordExtractor:
    def __init__(self, config: Optional[WordExtractConfig] = None):
        self.config = config or WordExtractConfig()

    def extract(self, cluster_indices: List[int], entries: List[SrtEntry], all_ngram_sets: List[Set[str]]) -> List[str]:
        if not cluster_indices:
            return []

        cluster_entries = [entries[i] for i in cluster_indices]
        cluster_ngram_sets = [all_ngram_sets[i] for i in cluster_indices]

        ngram_keywords = self._score_ngram_tfidf(cluster_ngram_sets, all_ngram_sets)
        phrase_keywords = self._extract_time_gap_phrases(cluster_entries)

        combined = ngram_keywords + phrase_keywords
        seen = set()
        deduped = []
        for kw in combined:
            if kw not in seen:
                seen.add(kw)
                deduped.append(kw)

        return deduped[:self.config.top_n]

    def _score_ngram_tfidf(self, cluster_ngram_sets: List[Set[str]], all_ngram_sets: List[Set[str]]) -> List[str]:
        total_docs = len(all_ngram_sets)

        tf: Counter = Counter()
        for gram_set in cluster_ngram_sets:
            for gram in gram_set:
                tf[gram] += 1

        doc_freq: Counter = Counter()
        for gram_set in all_ngram_sets:
            for gram in gram_set:
                doc_freq[gram] += 1

        scored = []
        for gram, freq in tf.items():
            df = doc_freq.get(gram, 0)
            score = freq * (math.log((total_docs + 1) / (df + 1)) + 1)
            scored.append((score, gram))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [gram for _, gram in scored[:3]]

    def _extract_time_gap_phrases(self, entries: List[SrtEntry]) -> List[str]:
        if not entries:
            return []

        sorted_entries = sorted(entries, key=lambda e: e.start_seconds)

        chunks = []
        current_chunk = [sorted_entries[0].text]
        for i in range(1, len(sorted_entries)):
            gap = sorted_entries[i].start_seconds - sorted_entries[i - 1].end_seconds
            if gap >= 5.0:
                chunks.append(current_chunk)
                current_chunk = []
            current_chunk.append(sorted_entries[i].text)
        chunks.append(current_chunk)

        phrases = []
        for chunk in chunks:
            phrase = ''.join(chunk)
            if self.config.min_phrase_length <= len(phrase) <= self.config.max_phrase_length:
                phrases.append(phrase)

        phrase_counts = Counter(phrases)
        most_common = phrase_counts.most_common(3)
        return [phrase for phrase, _ in most_common]


@dataclass
class EnhancedInput:
    full_text: str
    report_text: str
    token_estimate: int
    clusters_count: int


class LlmInputBuilder:
    def build(self, srt_text: str, clusters: List[TopicCluster], entries: List[SrtEntry], max_clusters: int = 8) -> EnhancedInput:
        if not clusters:
            return EnhancedInput(
                full_text=srt_text,
                report_text="",
                token_estimate=len(srt_text) // 2,
                clusters_count=0,
            )

        top_clusters = clusters[:max_clusters]
        report_lines = []
        report_lines.append("【预聚类分析报告】")
        report_lines.append("以下SRT条目可能属于同一个话题:")
        report_lines.append("")

        for cluster in top_clusters:
            keywords_str = ", ".join(cluster.topic_keywords) if cluster.topic_keywords else ""
            report_lines.append(f"[话题] (关键词: {keywords_str})")

            first_range = cluster.time_ranges[0]
            preview = self._get_preview(entries, cluster.entry_indices, first_range)
            time_str = f"  时间: {_seconds_to_srt_str(first_range.start_seconds)} -> {_seconds_to_srt_str(first_range.end_seconds)}  预览: {preview}"
            report_lines.append(time_str)

            if cluster.is_multi_segment:
                report_lines.append(f"  [多段] 该话题在{len(cluster.time_ranges)}个不连续时间段出现")

            report_lines.append("")

        report_lines.append("---")
        report_lines.append("注意：以上为预聚类分析结果，仅供参考。")
        report_lines.append("---")
        report_lines.append("完整的SRT字幕：")

        report_text = "\n".join(report_lines)
        full_text = report_text + "\n" + srt_text

        return EnhancedInput(
            full_text=full_text,
            report_text=report_text,
            token_estimate=len(full_text) // 2,
            clusters_count=len(top_clusters),
        )

    def _get_preview(self, entries: List[SrtEntry], cluster_indices: List[int], time_range: TimeRange) -> str:
        matching = [
            entries[i] for i in cluster_indices
            if time_range.start_seconds <= entries[i].start_seconds <= time_range.end_seconds
        ]
        matching.sort(key=lambda e: e.start_seconds)
        texts = [e.text for e in matching[:4]]
        joined = "".join(texts)
        return joined[:60]


@dataclass
class PreClusterConfig:
    enabled: bool = True
    similarity_threshold: float = 0.15
    min_cluster_size: int = 3
    min_multi_segment_size: int = 2
    time_gap_threshold: float = 30.0
    top_keywords: int = 6
    max_clusters_in_report: int = 8
    max_entries_for_similarity: int = 600


class TopicPreCluster:
    def __init__(self, config: Optional[PreClusterConfig] = None):
        self.config = config or PreClusterConfig()
        self.parser = SrtEntryParser()
        self.ngram_extractor = NgramExtractor()
        self.ngram_config = NgramConfig(n=0, filter_stopword_only=True)
        self.similarity_calculator = SimilarityCalculator()
        self.similarity_config = SimilarityConfig(method="cosine", min_intersection=1)
        self.cluster_config = ClusterConfig(
            similarity_threshold=self.config.similarity_threshold,
            min_cluster_size=self.config.min_cluster_size,
            min_multi_segment_size=self.config.min_multi_segment_size,
            time_gap_threshold=self.config.time_gap_threshold,
        )
        self.cluster_engine = ClusterEngine(self.cluster_config)
        self.word_extractor = ClusterWordExtractor(WordExtractConfig(top_n=self.config.top_keywords))
        self.llm_builder = LlmInputBuilder()

    def process(self, srt_text: str):
        start_time = time.time()

        report = type('Report', (), {})()
        report.enhanced_text = srt_text
        report.clusters = []
        report.entries = []
        report.stats = {}

        if not self.config.enabled:
            report.stats = {
                'total_entries': 0,
                'total_clusters': 0,
                'multi_segment_clusters': 0,
                'coverage_ratio': 0.0,
                'processing_time_ms': 0.0,
                'enabled': False,
            }
            return report

        entries = self.parser.parse(srt_text)
        total_entries = len(entries)
        report.entries = entries

        if total_entries < 5:
            report.stats = {
                'total_entries': total_entries,
                'total_clusters': 0,
                'multi_segment_clusters': 0,
                'coverage_ratio': 0.0,
                'processing_time_ms': (time.time() - start_time) * 1000,
                'skipped': True,
            }
            return report

        try:
            if total_entries > self.config.max_entries_for_similarity:
                sampled_indices = set(random.sample(range(total_entries), self.config.max_entries_for_similarity))
                entries_for_sim = [entries[i] for i in sorted(sampled_indices)]
                sampled = True
            else:
                entries_for_sim = entries
                sampled = False

            ngram_sets = self.ngram_extractor.extract(entries_for_sim, self.ngram_config)

            has_any_ngrams = any(bool(s) for s in ngram_sets)
            if has_any_ngrams:
                matrix = self.similarity_calculator.compute_matrix(ngram_sets, self.similarity_config)
            else:
                matrix = [[0.0] * len(ngram_sets) for _ in range(len(ngram_sets))]

            clusters = self.cluster_engine.cluster(matrix, entries_for_sim)

            for cluster in clusters:
                keywords = self.word_extractor.extract(cluster.entry_indices, entries_for_sim, ngram_sets)
                cluster.topic_keywords = keywords

            enhanced_input = self.llm_builder.build(
                srt_text, clusters, entries_for_sim,
                max_clusters=self.config.max_clusters_in_report,
            )

            report.enhanced_text = enhanced_input.full_text
            report.clusters = clusters

            total_clusters = len(clusters)
            multi_segment_clusters = sum(1 for c in clusters if c.is_multi_segment)
            clustered_indices = set()
            for c in clusters:
                clustered_indices.update(c.entry_indices)
            coverage_ratio = len(clustered_indices) / total_entries if total_entries > 0 else 0.0

            report.stats = {
                'total_entries': total_entries,
                'total_clusters': total_clusters,
                'multi_segment_clusters': multi_segment_clusters,
                'coverage_ratio': coverage_ratio,
                'processing_time_ms': (time.time() - start_time) * 1000,
            }
            if sampled:
                report.stats['sampled'] = True
        except Exception as e:
            logger.warning(f"聚类分析失败: {e}", exc_info=True)
            report.enhanced_text = srt_text
            report.clusters = []
            report.stats = {
                'total_entries': total_entries,
                'total_clusters': 0,
                'multi_segment_clusters': 0,
                'coverage_ratio': 0.0,
                'processing_time_ms': (time.time() - start_time) * 1000,
            }

        return report