"""
话题划分共享后处理模块

供 Legacy 与 FunClip 流水线共用的确定性校验逻辑：
- SRT 边界对齐
- 时间重叠修复
- 跨块话题合并
- 话题时长校验
- 长视频处理模式选择
"""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

LONG_VIDEO_SRT_ENTRY_THRESHOLD = 600
LONG_VIDEO_DURATION_SECONDS = 7200  # 2 小时


def srt_time_to_seconds(time_str: str) -> float:
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    if len(parts) != 3:
        return 0.0
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def seconds_to_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace('.', ',')


def parse_srt_timeline(srt_text: str) -> List[Dict]:
    entries = []
    blocks = re.split(r'\n\s*\n', srt_text.strip())
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        time_line = lines[1]
        time_match = re.match(
            r'(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})',
            time_line,
        )
        if not time_match:
            continue

        start = srt_time_to_seconds(time_match.group(1))
        end = srt_time_to_seconds(time_match.group(2))
        text = ' '.join(lines[2:]).strip()

        entries.append({
            'start': start,
            'end': end,
            'start_str': time_match.group(1).replace('.', ','),
            'end_str': time_match.group(2).replace('.', ','),
            'text': text,
            'duration': end - start,
        })

    entries.sort(key=lambda e: e['start'])
    return entries


def analyze_srt_text(srt_text: str) -> Dict[str, float]:
    entries = parse_srt_timeline(srt_text)
    if not entries:
        return {'entry_count': 0, 'duration_seconds': 0.0}
    return {
        'entry_count': len(entries),
        'duration_seconds': entries[-1]['end'] - entries[0]['start'],
    }


def analyze_srt_file(srt_path: Path) -> Dict[str, float]:
    try:
        srt_text = srt_path.read_text(encoding='utf-8')
    except Exception as exc:
        logger.warning(f"读取 SRT 失败，无法分析长视频特征: {exc}")
        return {'entry_count': 0, 'duration_seconds': 0.0}
    return analyze_srt_text(srt_text)


def resolve_funclip_sub_mode(srt_path: Optional[Path], configured_mode: str) -> str:
    """长视频自动从 merged 切换到 three_step。"""
    if configured_mode != 'merged' or not srt_path or not srt_path.exists():
        return configured_mode

    stats = analyze_srt_file(srt_path)
    if (
        stats['entry_count'] > LONG_VIDEO_SRT_ENTRY_THRESHOLD
        or stats['duration_seconds'] > LONG_VIDEO_DURATION_SECONDS
    ):
        logger.info(
            "长视频检测(entry=%s, duration=%.0fs)，自动切换 merged -> three_step",
            stats['entry_count'],
            stats['duration_seconds'],
        )
        return 'three_step'
    return configured_mode


def get_topic_duration_limits() -> Dict[str, float]:
    try:
        from backend.core.shared_config import config_manager

        settings = config_manager.settings
        min_seconds = settings.min_topic_duration_minutes * 60
        max_seconds = settings.max_topic_duration_minutes * 60
    except Exception:
        from backend.core.shared_config import (
            MAX_TOPIC_DURATION_MINUTES,
            MIN_TOPIC_DURATION_MINUTES,
        )

        min_seconds = MIN_TOPIC_DURATION_MINUTES * 60
        max_seconds = MAX_TOPIC_DURATION_MINUTES * 60

    return {'min_seconds': min_seconds, 'max_seconds': max_seconds}


def get_max_topics_per_chunk() -> int:
    try:
        from backend.core.shared_config import config_manager

        return config_manager.settings.max_topics_per_chunk
    except Exception:
        from backend.core.shared_config import MAX_TOPICS_PER_CHUNK

        return MAX_TOPICS_PER_CHUNK


GENERIC_TITLE_KEYWORDS = {
    '介绍', '概述', '讲解', '分析', '讨论', '内容', '部分', '总结',
}


def score_outline_quality(outline: Dict) -> float:
    """Step1 阶段无时间信息时，基于标题与子话题估算质量分。"""
    title = outline.get('title') or outline.get('outline') or ''
    score = 0.5

    if outline.get('has_signature'):
        score += 0.25

    subtopics = outline.get('subtopics') or []
    score += min(len(subtopics) * 0.08, 0.24)

    title_len = len(title)
    if 6 <= title_len <= 20:
        score += 0.15
    elif title_len < 4:
        score -= 0.2

    if any(keyword in title for keyword in GENERIC_TITLE_KEYWORDS):
        score -= 0.25

    if len(set(title)) >= 4:
        score += 0.05

    return max(0.0, min(1.0, score))


def score_topic_with_duration(
    topic: Dict,
    limits: Optional[Dict[str, float]] = None,
) -> float:
    """有时长/LLM 评分时的综合质量分。"""
    limits = limits or get_topic_duration_limits()
    target = (limits['min_seconds'] + limits['max_seconds']) / 2

    if topic.get('segments'):
        duration = compute_segments_duration_seconds(topic.get('segments', []))
    else:
        duration = compute_timeline_duration_seconds(topic)

    quality = score_outline_quality({
        'title': topic.get('outline') or topic.get('title', ''),
        'subtopics': topic.get('subtopics', []),
        'has_signature': topic.get('has_signature', False),
    })

    if duration <= 0:
        duration_score = 0.0
    elif duration < limits['min_seconds']:
        duration_score = (duration / limits['min_seconds']) * 0.4
    elif duration > limits['max_seconds']:
        duration_score = 0.6
    else:
        span = max(limits['max_seconds'] - limits['min_seconds'], 1.0)
        duration_score = 0.5 + 0.5 * (1 - abs(duration - target) / span)

    llm_score = float(topic.get('final_score') or topic.get('score') or 0.0)
    if llm_score > 0:
        combined = quality * 0.25 + duration_score * 0.45 + llm_score * 0.30
    else:
        combined = quality * 0.35 + duration_score * 0.65

    return max(0.0, min(1.0, combined))


def _topic_sort_key(topic: Dict) -> float:
    if topic.get('segments'):
        return srt_time_to_seconds(topic['segments'][0].get('start', '00:00:00,000'))
    if topic.get('start_time'):
        return srt_time_to_seconds(topic.get('start_time', '00:00:00,000'))
    return float(topic.get('chunk_index', 0))


def rank_and_truncate_topics(
    topics: List[Dict],
    max_count: int,
    score_fn=None,
    preserve_time_order: bool = True,
) -> List[Dict]:
    """按质量/时长排序后截断，保留高分话题。"""
    if len(topics) <= max_count:
        return topics

    score_fn = score_fn or score_topic_with_duration
    scored = [(score_fn(topic), index, topic) for index, topic in enumerate(topics)]
    scored.sort(key=lambda item: (-item[0], item[1]))

    kept = [topic for _, _, topic in scored[:max_count]]
    dropped = [topic for _, _, topic in scored[max_count:]]

    for topic in dropped:
        label = topic.get('outline') or topic.get('title') or topic.get('id', '未知')
        logger.info("话题 '%s' 综合分较低，截断时被移除", label)

    if preserve_time_order:
        kept.sort(key=_topic_sort_key)

    logger.warning(
        "话题数 %s 超过上限 %s，按质量/时长排序后保留 %s 个",
        len(topics),
        max_count,
        len(kept),
    )
    return kept


def compute_segments_duration_seconds(segments: List[Dict]) -> float:
    total = 0.0
    for seg in segments:
        start = srt_time_to_seconds(seg.get('start', '00:00:00,000'))
        end = srt_time_to_seconds(seg.get('end', '00:00:00,000'))
        total += max(0.0, end - start)
    return total


def compute_timeline_duration_seconds(item: Dict) -> float:
    start = srt_time_to_seconds(item.get('start_time', '00:00:00,000'))
    end = srt_time_to_seconds(item.get('end_time', '00:00:00,000'))
    return max(0.0, end - start)


def _extract_keywords(text: str) -> List[str]:
    text = re.sub(r'[^\w\s]', '', text)
    separators = [' ', '，', '、', ',', '；', ';', '。', '.', '：', ':']
    words = []
    current_word = ''

    for char in text:
        if char in separators:
            if current_word:
                words.append(current_word)
                current_word = ''
        else:
            current_word += char

    if current_word:
        words.append(current_word)

    stopwords = {
        '的', '是', '在', '了', '和', '与', '或', '以及', '等', '之', '于',
        '这', '那', '有', '我', '你', '他', '我们', '你们', '他们',
    }
    keywords = [w for w in words if len(w) >= 2 and w not in stopwords]

    if not keywords and len(text) >= 2:
        for i in range(len(text) - 1):
            keywords.append(text[i:i + 2])

    return keywords


def _calculate_char_overlap(text1: str, text2: str) -> float:
    if not text1 or not text2:
        return 0.0

    max_common_len = 0
    min_len = min(3, len(text1), len(text2))
    for check_len in range(min_len, 0, -1):
        for i in range(len(text1) - check_len + 1):
            substr = text1[i:i + check_len]
            if substr in text2:
                max_common_len = check_len
                break
        if max_common_len > 0:
            break

    if max_common_len == 0:
        return 0.0
    return min(1.0, max_common_len / 3.0)


def calculate_title_similarity(title1: str, title2: str) -> float:
    title1 = str(title1 or '').lower().strip()
    title2 = str(title2 or '').lower().strip()
    if not title1 or not title2:
        return 0.0
    if title1 == title2:
        return 1.0
    if title1 in title2 or title2 in title1:
        return 0.85

    keywords1 = set(_extract_keywords(title1))
    keywords2 = set(_extract_keywords(title2))
    if not keywords1 or not keywords2:
        return 0.0

    intersection = len(keywords1 & keywords2)
    union = len(keywords1 | keywords2)
    if union == 0:
        return 0.0

    jaccard = intersection / union
    len_ratio = min(len(title1), len(title2)) / max(len(title1), len(title2))
    char_overlap = _calculate_char_overlap(title1, title2)
    return jaccard * 0.5 + len_ratio * 0.2 + char_overlap * 0.3


def validate_segments_with_srt(
    merged_clips: List[Dict],
    srt_text: str,
    silence_threshold: float = 2.0,
    vad_silences: Optional[List[Tuple[float, float]]] = None,
    asr_conf_map: Optional[Dict[int, float]] = None,
) -> List[Dict]:
    entries = parse_srt_timeline(srt_text)
    if not entries:
        logger.warning("无法解析SRT时间线，跳过验证")
        return merged_clips

    logger.info(f"SRT时间线解析完成: {len(entries)} 条字幕条目")

    for clip in merged_clips:
        segments = clip.get('segments', [])
        if not segments:
            continue

        validated_segments = []
        all_removed = clip.get('removed_sections', [])

        # 当段落没有显式置信度时，基于SRT密度估算一个段置信度：每秒字幕条目数映射到[0,1]
        def _estimate_seg_conf(seg_start, seg_end):
            dur = max(0.001, seg_end - seg_start)
            cnt = sum(1 for e in entries if e['start'] >= seg_start and e['end'] <= seg_end)
            density = cnt / dur  # 条/秒
            # map density 0~0.5+ to 0~1（经验值）
            conf = min(1.0, density * 1.0)
            return conf

        for seg in segments:

            seg_start = srt_time_to_seconds(seg.get('start', '00:00:00,000'))
            seg_end = srt_time_to_seconds(seg.get('end', '00:00:00,000'))
            contained = [e for e in entries if e['start'] >= seg_start and e['end'] <= seg_end]

            if not contained:
                # 没有完全包含的SRT条目，尝试寻找部分重叠条目
                overlapping = [
                    e for e in entries if e['start'] < seg_end and e['end'] > seg_start
                ]
                if overlapping:
                    first = overlapping[0]
                    last = overlapping[-1]
                    seg_start = min(seg_start, first['start'])
                    seg_end = max(seg_end, last['end'])
                    contained = overlapping
                else:
                    # 没有任何字幕覆盖。若VAD存在并在该区间检测到语音，则保留并标记为低置信
                    has_voice = False
                    if vad_silences is not None:
                        # 若VAD静音段与该区间无覆盖，说明有语音
                        overlap_with_silence = any(
                            not (seg_end <= s_start or seg_start >= s_end)
                            for s_start, s_end in vad_silences
                        )
                        has_voice = not overlap_with_silence

                    # ASR置信度判断（按所在chunk id或近似映射）
                    asr_conf = None
                    try:
                        asr_conf = asr_conf_map.get(int(seg.get('id'))) if asr_conf_map else None
                    except Exception:
                        asr_conf = None

                    est_conf = asr_conf if asr_conf is not None else _estimate_seg_conf(seg_start, seg_end)

                    if has_voice or est_conf >= 0.5:
                        # 保留段，但标注为低置信并记录原因
                        clip.setdefault('removed_sections', [])
                        clip.setdefault('low_confidence_segments', []).append({
                            'start': seg.get('start'),
                            'end': seg.get('end'),
                            'reason': '无SRT但VAD/ASR或密度支持'
                        })
                        validated_start = seg_start
                        validated_end = seg_end
                    else:
                        all_removed.append({
                            'start': seg['start'],
                            'end': seg['end'],
                            'reason': '该时间范围内无字幕（纯静音）',
                        })
                        continue

            validated_start = contained[0]['start']
            validated_end = contained[-1]['end']

            for i in range(len(contained) - 1):
                gap = contained[i + 1]['start'] - contained[i]['end']
                # silence_threshold 可来自参数或全局配置
                use_threshold = silence_threshold
                try:
                    from backend.core.shared_config import config_manager
                    use_threshold = getattr(config_manager.settings, 'silence_threshold', silence_threshold)
                except Exception:
                    pass

                if gap > use_threshold:
                    all_removed.append({
                        'start': seconds_to_srt_time(contained[i]['end']),
                        'end': seconds_to_srt_time(contained[i + 1]['start']),
                        'reason': f"SRT时间戳间隙{gap:.1f}秒（静音）",
                    })

            validated_segments.append({
                'start': seconds_to_srt_time(validated_start),
                'end': seconds_to_srt_time(validated_end),
            })

        if len(validated_segments) >= 2:
            i = 0
            while i < len(validated_segments) - 1:
                curr_end_sec = srt_time_to_seconds(validated_segments[i]['end'])
                next_start_sec = srt_time_to_seconds(validated_segments[i + 1]['start'])

                if curr_end_sec >= next_start_sec:
                    validated_segments[i]['end'] = validated_segments[i + 1]['end']
                    del validated_segments[i + 1]
                    continue

                gap_srts = [
                    e for e in entries
                    if e['start'] >= curr_end_sec and e['end'] <= next_start_sec
                    and e.get('text', '').strip()
                ]

                if gap_srts:
                    validated_segments[i]['end'] = validated_segments[i + 1]['end']
                    del validated_segments[i + 1]
                else:
                    i += 1

        # 额外启发式：避免在句子/语义未完结时切分（如下一条字幕为承接词/因果/承前），
        # 将紧接的短承接性字幕合并到当前 segment 中，直到不再满足承接条件。
        if entries:
            cont_markers = (
                '因为','所以','然后','接着','并且','而且','那你','那就','刚才','刚刚',
                '接下来','另外','继续','还有','并说','就是说','而','但','不过','如果','可是','就','还'
            )
            def _starts_with_marker(text: str) -> bool:
                t = (text or '').strip()
                for m in cont_markers:
                    if t.startswith(m):
                        return True
                return False

            # for each validated segment, try to extend to include immediate following entries if they are continuation
            for vi, vseg in enumerate(validated_segments):
                v_start = srt_time_to_seconds(vseg['start'])
                v_end = srt_time_to_seconds(vseg['end'])
                # find last fully contained entry index
                last_idx = None
                for idx, e in enumerate(entries):
                    if e['start'] >= v_start and e['end'] <= v_end:
                        last_idx = idx
                if last_idx is None:
                    # find first overlapping
                    for idx, e in enumerate(entries):
                        if e['start'] < v_end and e['end'] > v_start:
                            last_idx = idx
                            break
                # try to extend
                while last_idx is not None and last_idx + 1 < len(entries):
                    nxt = entries[last_idx + 1]
                    # short continuation candidate: very short or starts with marker
                    nxt_text = nxt.get('text', '').strip()
                    nxt_dur = nxt['end'] - nxt['start']
                    # 如果下一条以承接词开头或很短（可能是衔接/残句）则合并；
                    # 或者上一条字幕未以句号/问号/感叹号结尾，可能是未完结句子，也合并
                    prev_text = entries[last_idx].get('text', '') if last_idx is not None else ''
                    prev_ends_sentence = bool(prev_text.strip() and prev_text.strip()[-1] in ('。', '！', '？', '!','?'))
                    if _starts_with_marker(nxt_text) or nxt_dur <= 3.0 or (not prev_ends_sentence):
                        # extend
                        vseg['end'] = seconds_to_srt_time(nxt['end'])
                        last_idx += 1
                    else:
                        break

        clip['segments'] = validated_segments if validated_segments else segments

        existing_starts = {(r['start'], r['end']) for r in clip.get('removed_sections', [])}
        for removed in all_removed:
            key = (removed['start'], removed['end'])
            if key not in existing_starts:
                clip.setdefault('removed_sections', []).append(removed)
                existing_starts.add(key)

    return merged_clips


def fix_overlapping_timeline(timeline_data: List[Dict]) -> List[Dict]:
    if not timeline_data:
        return []

    limits = get_topic_duration_limits()
    min_seconds = limits['min_seconds']
    fixed_data = []

    for timeline_item in timeline_data:
        start_time = timeline_item.get('start_time', '')
        end_time = timeline_item.get('end_time', '')
        if not start_time or not end_time:
            continue

        start_sec = srt_time_to_seconds(start_time)
        end_sec = srt_time_to_seconds(end_time)
        if start_sec >= end_sec:
            continue

        duration_sec = end_sec - start_sec
        outline_lower = str(timeline_item.get('outline', '')).lower()
        # 如果该话题类型在免时长限制列表中，跳过最小时长限制
        try:
            from backend.core.shared_config import NO_DURATION_LIMIT_TYPES
            topic_type = str(timeline_item.get('topic_type', '')).lower()
        except Exception:
            NO_DURATION_LIMIT_TYPES = ['product', 'topic']
            topic_type = str(timeline_item.get('topic_type', '')).lower()

        product_like = any(k in outline_lower for k in ('产品', '销售', '介绍', '优惠'))
        exempt_type = topic_type in NO_DURATION_LIMIT_TYPES
        # 如果是免限制类型或明显的产品介绍，则不强制最小时长
        if exempt_type or product_like:
            min_required = 0
        else:
            min_required = min(min_seconds, 30)

        if duration_sec < min_required:
            logger.warning(
                "话题 '%s' 时长 %.1fs 小于阈值 %.1fs，跳过",
                timeline_item.get('outline', '未知'),
                duration_sec,
                min_required,
            )
            continue

        fixed_data.append(timeline_item)

    if not fixed_data:
        return []

    for i in range(len(fixed_data) - 1):
        current = fixed_data[i]
        next_item = fixed_data[i + 1]
        current_end_sec = srt_time_to_seconds(current['end_time'])
        next_start_sec = srt_time_to_seconds(next_item['start_time'])

        if next_start_sec < current_end_sec:
            mid_point = (current_end_sec + next_start_sec) / 2
            current['end_time'] = seconds_to_srt_time(mid_point - 0.1)
            next_item['start_time'] = seconds_to_srt_time(mid_point + 0.1)

    return fixed_data


def merge_cross_boundary_topics(timeline_data: List[Dict]) -> List[Dict]:
    if len(timeline_data) < 2:
        return timeline_data

    sorted_data = sorted(
        timeline_data,
        key=lambda x: (
            x.get('chunk_index', 0),
            srt_time_to_seconds(x.get('start_time', '00:00:00,000')),
        ),
    )

    merged = []
    i = 0
    while i < len(sorted_data):
        current = sorted_data[i]
        if i + 1 < len(sorted_data):
            next_item = sorted_data[i + 1]
            current_chunk = current.get('chunk_index', 0)
            next_chunk = next_item.get('chunk_index', 0)
            current_end = srt_time_to_seconds(current.get('end_time', '00:00:00,000'))
            next_start = srt_time_to_seconds(next_item.get('start_time', '00:00:00,000'))
            current_title = str(current.get('outline', '')).lower().strip()
            next_title = str(next_item.get('outline', '')).lower().strip()
            titles_similar = calculate_title_similarity(current_title, next_title)
            time_gap = next_start - current_end
            should_merge = False

            if current_chunk != next_chunk and -2 <= time_gap < 60:
                # loosen合并阈值：增加关键词重叠判定与更宽的时间窗口
                if titles_similar > 0.45:
                    should_merge = True
                elif titles_similar > 0.3 and time_gap < 20:
                    should_merge = True
                elif current_title in next_title or next_title in current_title:
                    should_merge = True
                elif time_gap < 5:
                    should_merge = True
                else:
                    # 关键词重叠检查（补充判定）
                    cur_keys = set(_extract_keywords(current.get('outline', '')))
                    next_keys = set(_extract_keywords(next_item.get('outline', '')))
                    if cur_keys and next_keys:
                        inter = len(cur_keys & next_keys)
                        union = len(cur_keys | next_keys)
                        if union > 0 and (inter / union) > 0.25 and time_gap < 120:
                            should_merge = True

            if should_merge:
                merged_topic = current.copy()
                merged_topic['start_time'] = current['start_time']
                merged_topic['end_time'] = next_item['end_time']
                merged_topic['merged'] = True
                if len(next_title) > len(current_title):
                    merged_topic['outline'] = next_item.get('outline')
                merged.append(merged_topic)
                i += 2
                continue

        merged.append(current)
        i += 1

    if len(merged) != len(timeline_data):
        logger.info("跨边界话题合并: %s -> %s", len(timeline_data), len(merged))
    return merged


def validate_funclip_topic_durations(topics: List[Dict]) -> List[Dict]:
    limits = get_topic_duration_limits()
    min_seconds = limits['min_seconds']
    max_seconds = limits['max_seconds']
    max_topics = get_max_topics_per_chunk()
    validated = []

    for topic in topics:
        duration = compute_segments_duration_seconds(topic.get('segments', []))
        label = topic.get('outline') or topic.get('title') or topic.get('id', '未知')

        # 若被标记为 product，但经检索其实际文本内容不含产品相关关键词，则去掉 product 标记
        try:
            entries = []
            # 收集该topic的字幕文本用于关键词检测
            from backend.pipeline.topic_postprocess import parse_srt_timeline as _ppt_parse
        except Exception:
            entries = []
        product_keywords = ('产品', '购买', '下单', '链接', '价格', '优惠', '折扣', '包邮', '买', '促销', '手表', '牛肉丸', '鸡肉丸')
        topic_text = str(topic.get('outline', '')) + ' ' + ' '.join(
            [s.get('text', '') for s in topic.get('segments', []) if isinstance(s, dict)]
        )
        product_like_actual = any(k in topic_text for k in product_keywords)
        if str(topic.get('topic_type', '')).lower() == 'product' and not product_like_actual:
            logger.info("话题 '%s' 标记为 product 但内容不含产品关键词，移除 product 标注", label)
            topic['topic_type'] = ''

        # 判断是否需要跳过时长限制（产品或特定话题类型无需时长限制）
        try:
            from backend.core.shared_config import NO_DURATION_LIMIT_TYPES
            topic_type = str(topic.get('topic_type', '')).lower()
        except Exception:
            NO_DURATION_LIMIT_TYPES = ['product', 'topic']
            topic_type = str(topic.get('topic_type', '')).lower()

        outline_lower = str(topic.get('outline', '')).lower()
        product_like = any(k in outline_lower for k in ('产品', '介绍', '营销', '销售', '优惠'))
        exempt_type = topic_type in NO_DURATION_LIMIT_TYPES

        if not (exempt_type or product_like):
            # 非免限类型：不再因时长过短而直接过滤，改为记录警告并按内容保留。
            if duration < min_seconds:
                topic['duration_warning'] = 'too_short'
                logger.info(
                    "FunClip 话题 '%s' 时长 %.1fs 低于最小值 %.1fs，但按话题内容保留",
                    label,
                    duration,
                    min_seconds,
                )

            if duration > max_seconds:
                topic['duration_warning'] = 'too_long'
                logger.warning(
                    "FunClip 话题 '%s' 时长 %.1fs 超过最大值 %.1fs，保留并标记",
                    label,
                    duration,
                    max_seconds,
                )
        else:
            logger.info(f"话题 '{label}' 属于免时长限制类型(topic_type={topic_type}), 跳过时长过滤")

        validated.append(topic)

    if len(validated) > max_topics:
        validated = rank_and_truncate_topics(
            validated,
            max_topics,
            score_fn=lambda topic: score_topic_with_duration(topic, limits),
        )

    return validated


def validate_timeline_durations(timeline_data: List[Dict]) -> List[Dict]:
    limits = get_topic_duration_limits()
    max_seconds = limits['max_seconds']
    max_topics = get_max_topics_per_chunk()
    validated = []

    for item in timeline_data:
        duration = compute_timeline_duration_seconds(item)
        label = item.get('outline', '未知')

        if duration > max_seconds:
            item['duration_warning'] = 'too_long'
            logger.warning(
                "Legacy 话题 '%s' 时长 %.1fs 超过最大值 %.1fs，保留并标记",
                label,
                duration,
                max_seconds,
            )

        validated.append(item)

    if len(validated) > max_topics:
        validated = rank_and_truncate_topics(
            validated,
            max_topics,
            score_fn=lambda topic: score_topic_with_duration(topic, limits),
        )

    return validated


def postprocess_funclip_topics(
    topics: List[Dict],
    srt_text: str,
    vad_silences: Optional[List[Tuple[float, float]]] = None,
    asr_conf_map: Optional[Dict[int, float]] = None,
) -> List[Dict]:
    topics = validate_segments_with_srt(topics, srt_text, vad_silences=vad_silences, asr_conf_map=asr_conf_map)
    return validate_funclip_topic_durations(topics)


def postprocess_timeline(timeline_data: List[Dict]) -> List[Dict]:
    timeline_data = fix_overlapping_timeline(timeline_data)
    timeline_data = merge_cross_boundary_topics(timeline_data)
    return validate_timeline_durations(timeline_data)


def extract_precluster_report_text(enhanced_text: str) -> str:
    marker = '完整的SRT字幕：'
    if marker in enhanced_text:
        return enhanced_text.split(marker)[0].strip()
    return enhanced_text.strip()
