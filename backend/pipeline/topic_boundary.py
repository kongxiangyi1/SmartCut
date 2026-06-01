"""
话题边界扩展模块（阶段 A3）

确定性规则（无 LLM）：
- 反向追溯：对以指代词开头的话题，回溯扩展首 segment 起点
- 收尾延伸：对未完整收尾的话题，向后扩展末 segment 终点
- occupied_ranges 防冲突
"""

import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

FORWARD_DEPENDENCY_MARKERS = (
    '这', '那', '他', '她', '它', '这个', '那个', '这些', '那些',
    '为什么', '所以', '因此', '因为', '于是',
    '刚才', '刚刚', '说到', '提到', '那你说', '然后呢',
)
TOPIC_SWITCH_MARKERS = (
    '换个话题', '接下来说说', '再聊一个', '下一个', '另外说',
)


def _get_boundary_config() -> dict:
    try:
        from backend.core.shared_config import config_manager
        s = config_manager.settings
        return {
            'max_backtrack_seconds': float(getattr(s, 'max_backtrack_seconds', 300.0)),
            'max_forward_extend_entries': int(getattr(s, 'max_forward_extend_entries', 5)),
        }
    except Exception:
        return {'max_backtrack_seconds': 300.0, 'max_forward_extend_entries': 5}


def _srt_time_to_seconds(time_str: str) -> float:
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def _seconds_to_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace('.', ',')


def _starts_with_continuation(text: str) -> bool:
    t = (text or '').strip()
    markers = (
        '因为', '所以', '然后', '接着', '并且', '而且', '那你', '那就',
        '刚才', '刚刚', '接下来', '另外', '继续', '还有', '就是说',
    )
    return any(t.startswith(m) for m in markers)


def _ends_sentence(text: str) -> bool:
    t = (text or '').strip()
    return bool(t and t[-1] in ('。', '！', '？', '!', '?', '…'))


def _has_forward_dependency(text: str) -> bool:
    t = (text or '').strip()
    return any(t.startswith(m) for m in FORWARD_DEPENDENCY_MARKERS)


def _is_topic_switch(text: str) -> bool:
    t = (text or '').strip()
    return any(m in t for m in TOPIC_SWITCH_MARKERS)


def _first_entry_in_segment(
    entries: List[Dict], seg_start: float, seg_end: float
) -> Optional[Dict]:
    matched = [e for e in entries if e['start'] >= seg_start and e['end'] <= seg_end]
    if matched:
        return matched[0]
    overlapping = [e for e in entries if e['start'] < seg_end and e['end'] > seg_start]
    return overlapping[0] if overlapping else None


def _last_entry_in_segment(
    entries: List[Dict], seg_start: float, seg_end: float
) -> Optional[Dict]:
    matched = [e for e in entries if e['start'] >= seg_start and e['end'] <= seg_end]
    if matched:
        return matched[-1]
    overlapping = [e for e in entries if e['start'] < seg_end and e['end'] > seg_start]
    return overlapping[-1] if overlapping else None


def _build_occupied_ranges(
    topics: List[Dict], exclude_topic_id: Optional[str] = None
) -> List[Tuple[float, float]]:
    ranges = []
    for t in topics:
        if exclude_topic_id is not None and t.get('id') == exclude_topic_id:
            continue
        for seg in t.get('segments', []):
            ranges.append((
                _srt_time_to_seconds(seg['start']),
                _srt_time_to_seconds(seg['end']),
            ))
    return sorted(ranges)


def _conflicts_with_occupied(
    start: float, end: float, occupied: List[Tuple[float, float]], *, margin: float = 0.5
) -> bool:
    for os, oe in occupied:
        if start < oe - margin and end > os + margin:
            return True
    return False


def backfill_topic_boundaries(
    topics: List[Dict],
    srt_entries: List[Dict],
) -> List[Dict]:
    entries = sorted(srt_entries, key=lambda e: e['start'])
    config = _get_boundary_config()
    max_backtrack = config['max_backtrack_seconds']
    max_forward = config['max_forward_extend_entries']

    for topic in topics:
        segments = topic.get('segments', [])
        if not segments:
            continue

        occupied = _build_occupied_ranges(topics, exclude_topic_id=topic.get('id'))
        changes = []

        # ---- 反向追溯：扩展首 segment 起点 ----
        first = segments[0]
        seg_start = _srt_time_to_seconds(first['start'])
        seg_end = _srt_time_to_seconds(first['end'])
        first_entry = _first_entry_in_segment(entries, seg_start, seg_end)

        if first_entry and _has_forward_dependency(first_entry['text']):
            idx = entries.index(first_entry) if first_entry in entries else -1
            if idx > 0:
                min_start = max(0, seg_start - max_backtrack)
                new_start_idx = idx

                while new_start_idx > 0:
                    prev = entries[new_start_idx - 1]
                    if prev['start'] < min_start:
                        break
                    if _is_topic_switch(entries[new_start_idx]['text']):
                        break
                    if (_ends_sentence(prev['text'])
                            and not _has_forward_dependency(entries[new_start_idx]['text'])):
                        break
                    new_start_idx -= 1

                new_start = entries[new_start_idx]['start']
                if new_start < seg_start:
                    if not _conflicts_with_occupied(new_start, seg_start, occupied):
                        first['start'] = _seconds_to_srt_time(new_start)
                        changes.append(f"intro_backfill:{seg_start - new_start:.1f}s")
                    else:
                        logger.info("话题 %s 反向追溯被 occupied_ranges 阻止",
                                    topic.get('id'))

        # ---- 收尾延伸：扩展末 segment 终点 ----
        last = segments[-1]
        seg_end = _srt_time_to_seconds(last['end'])
        last_entry = _last_entry_in_segment(entries, _srt_time_to_seconds(last['start']), seg_end)

        if last_entry is not None:
            idx = entries.index(last_entry) if last_entry in entries else -1
            extended = 0
            while idx >= 0 and idx + 1 < len(entries) and extended < max_forward:
                cur = entries[idx]
                nxt = entries[idx + 1]
                if _ends_sentence(cur['text']) and not _starts_with_continuation(nxt['text']):
                    break
                if _is_topic_switch(nxt['text']):
                    break
                nxt_end = nxt['end']
                if _conflicts_with_occupied(seg_end, nxt_end, occupied):
                    break
                last['end'] = _seconds_to_srt_time(nxt_end)
                idx += 1
                extended += 1
            if extended:
                changes.append(f"outro_extend:{extended}_entries")

        if changes:
            topic['boundary_adjustments'] = changes
            logger.info("话题 %s 边界调整: %s", topic.get('id'), changes)

    return topics