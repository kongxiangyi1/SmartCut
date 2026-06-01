"""
话题覆盖率审计模块（阶段 A2）

量化「哪些 SRT 条目未被任何 topic 覆盖」，触发日志告警，
为阶段 B 的补洞提供输入。
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.pipeline.topic_postprocess import (
    seconds_to_srt_time,
    srt_time_to_seconds,
)

logger = logging.getLogger(__name__)


@dataclass
class CoverageGap:
    start_sec: float
    end_sec: float
    start_str: str
    end_str: str
    entry_count: int
    sample_texts: List[str] = field(default_factory=list)


@dataclass
class CoverageReport:
    total_entries: int
    covered_entries: int
    coverage_ratio: float
    gaps: List[CoverageGap]
    orphan_entries: List[Dict]

    @property
    def has_significant_gaps(self) -> bool:
        return (1.0 - self.coverage_ratio) > 0.05


def _entry_index(entries: List[Dict]) -> List[Dict]:
    return [{**e, 'idx': i} for i, e in enumerate(entries)]


def _entries_in_segment(
    entries: List[Dict], start: float, end: float
) -> List[Dict]:
    return [
        e for e in entries
        if e['start'] < end and e['end'] > start
    ]


def _make_gap(
    gap_start: float,
    gap_end: float,
    gap_entries_list: List[Dict],
    max_sample_texts: int = 3,
) -> CoverageGap:
    samples = []
    for e in gap_entries_list[:max_sample_texts]:
        txt = (e.get('text') or '').strip()
        if txt:
            samples.append(txt[:40])
    return CoverageGap(
        start_sec=gap_start,
        end_sec=gap_end,
        start_str=seconds_to_srt_time(gap_start),
        end_str=seconds_to_srt_time(gap_end),
        entry_count=len(gap_entries_list),
        sample_texts=samples,
    )


def audit_topic_coverage(
    topics: List[Dict],
    srt_entries: List[Dict],
    *,
    min_gap_duration: float = 5.0,
    max_sample_texts: int = 3,
) -> CoverageReport:
    entries = _entry_index(srt_entries)
    covered_indices: set = set()

    for topic in topics:
        for seg in topic.get('segments', []):
            seg_start = srt_time_to_seconds(seg['start'])
            seg_end = srt_time_to_seconds(seg['end'])
            for e in _entries_in_segment(entries, seg_start, seg_end):
                covered_indices.add(e['idx'])

    orphan = [e for e in entries if e['idx'] not in covered_indices]
    total = len(entries)
    covered = len(covered_indices)
    ratio = covered / total if total else 1.0

    gaps: List[CoverageGap] = []
    if orphan:
        orphan.sort(key=lambda e: e['start'])
        gap_start = orphan[0]['start']
        gap_end = orphan[0]['end']
        gap_entries_list = [orphan[0]]
        for e in orphan[1:]:
            if e['start'] - gap_end <= 1.0:
                gap_end = max(gap_end, e['end'])
                gap_entries_list.append(e)
            else:
                if gap_end - gap_start >= min_gap_duration:
                    gaps.append(_make_gap(gap_start, gap_end, gap_entries_list, max_sample_texts))
                gap_start, gap_end, gap_entries_list = e['start'], e['end'], [e]
        if gap_end - gap_start >= min_gap_duration:
            gaps.append(_make_gap(gap_start, gap_end, gap_entries_list, max_sample_texts))

    return CoverageReport(
        total_entries=total,
        covered_entries=covered,
        coverage_ratio=ratio,
        gaps=gaps,
        orphan_entries=orphan,
    )


def compute_topic_coverage_stats(
    topics: List[Dict],
    srt_entries: List[Dict],
) -> List[Dict]:
    report = audit_topic_coverage(topics, srt_entries)
    for topic in topics:
        topic['_coverage'] = {
            'ratio': report.coverage_ratio,
            'gaps_count': len(report.gaps),
        }
    if report.has_significant_gaps:
        logger.warning(
            "话题覆盖率不足: %.1f%% (%d/%d entries), gaps=%d",
            report.coverage_ratio * 100,
            report.covered_entries, report.total_entries,
            len(report.gaps),
        )
        for g in report.gaps[:5]:
            logger.warning(
                "  未覆盖区间: %s -> %s (%d entries) 样例: %s",
                g.start_str, g.end_str, g.entry_count,
                ' | '.join(g.sample_texts),
            )
    return topics