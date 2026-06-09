"""
话题完整性指标计算模块。
复用：topic_boundary._has_forward_dependency, topic_postprocess._ends_sentence
"""
from typing import List, Dict, Optional

from backend.pipeline.topic_boundary import _has_forward_dependency
from backend.pipeline.topic_postprocess import _ends_sentence, srt_time_to_seconds


def _find_first_entry(clip: Dict, entries: List[Dict]) -> Optional[Dict]:
    segments = clip.get('segments', [])
    if not segments:
        return None
    start_sec = _to_seconds(segments[0]['start'])
    end_sec = _to_seconds(segments[0]['end'])
    matched = [e for e in entries if e['start'] < end_sec and e['end'] > start_sec]
    matched.sort(key=lambda e: e['start'])
    return matched[0] if matched else None


def _find_last_entry(clip: Dict, entries: List[Dict]) -> Optional[Dict]:
    segments = clip.get('segments', [])
    if not segments:
        return None
    start_sec = _to_seconds(segments[-1]['start'])
    end_sec = _to_seconds(segments[-1]['end'])
    matched = [e for e in entries if e['start'] < end_sec and e['end'] > start_sec]
    matched.sort(key=lambda e: e['end'], reverse=True)
    return matched[0] if matched else None


def _get_coverage_ratio(clip: Dict, entries: List[Dict]) -> float:
    """clip覆盖的条目数 / 全局总条目数"""
    if not entries:
        return 0.0
    segments = clip.get('segments', [])
    covered = set()
    for seg in segments:
        seg_s = _to_seconds(seg['start'])
        seg_e = _to_seconds(seg['end'])
        for i, e in enumerate(entries):
            if e['start'] < seg_e and e['end'] > seg_s:
                covered.add(i)
    return round(len(covered) / len(entries), 4)


def _to_seconds(t: str) -> float:
    t = t.replace(',', '.')
    parts = t.split(':')
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def compute_clip_completeness(
    clip: Dict,
    srt_entries: List[Dict],
) -> Dict:
    """
    计算单个clip的完整性指标（复用 topic_boundary 和 topic_postprocess 函数）。
    返回字典包含 coverage_ratio, intro_complete, outro_complete, segment_count, gap_fill_applied, boundary_adjustments, warnings, needs_review
    """
    segments = clip.get('segments', [])
    if not segments:
        return {
            "coverage_ratio": 0.0,
            "intro_complete": False,
            "outro_complete": False,
            "segment_count": 0,
            "gap_fill_applied": False,
            "boundary_adjustments": [],
            "warnings": ["no_segments"],
            "needs_review": True,
        }

    first_entry = _find_first_entry(clip, srt_entries)
    last_entry = _find_last_entry(clip, srt_entries)

    intro = False
    try:
        intro = not _has_forward_dependency(first_entry['text']) if first_entry else False
    except Exception:
        intro = False

    outro = False
    try:
        outro = _ends_sentence(last_entry['text']) if last_entry else False
    except Exception:
        outro = False

    cov = _get_coverage_ratio(clip, srt_entries)

    warnings = []
    if not intro:
        warnings.append("intro_incomplete")
    if not outro:
        warnings.append("outro_incomplete")
    if clip.get('gap_fill_applied'):
        warnings.append("has_gap_fill")

    needs_review = len(warnings) > 0

    return {
        "coverage_ratio": cov,
        "intro_complete": intro,
        "outro_complete": outro,
        "segment_count": len(segments),
        "gap_fill_applied": bool(clip.get('gap_fill_applied')),
        "boundary_adjustments": clip.get('boundary_adjustments', []),
        "warnings": warnings,
        "needs_review": needs_review,
    }


def compute_all_completeness(
    clips: List[Dict],
    srt_entries: List[Dict],
) -> List[Dict]:
    """为所有clips批量计算完整性指标（在后处理时调用）。"""
    for clip in clips:
        try:
            clip['completeness'] = compute_clip_completeness(clip, srt_entries)
        except Exception:
            clip['completeness'] = {
                "coverage_ratio": 0.0,
                "intro_complete": False,
                "outro_complete": False,
                "segment_count": len(clip.get('segments', [])),
                "gap_fill_applied": bool(clip.get('gap_fill_applied')),
                "boundary_adjustments": clip.get('boundary_adjustments', []),
                "warnings": ["compute_error"],
                "needs_review": True,
            }
    return clips
