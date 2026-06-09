"""
基于FunClip风格的单步LLM处理方案
"""
import logging
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
from backend.pipeline.prompt_loader import get_funclip_prompt
from backend.pipeline.step6_video import VideoGenerator
from backend.pipeline.topic_postprocess import (
    analyze_srt_text,
    parse_srt_timeline as _parse_srt_timeline,
    postprocess_funclip_topics,
    resolve_funclip_sub_mode,
    seconds_to_srt_time as _seconds_to_srt_time,
    srt_time_to_seconds as _srt_time_to_seconds,
    validate_segments_with_srt as _validate_segments_with_srt,
    get_topic_duration_limits,
)
from backend.utils.text_corrector import TextCorrector, SemanticPreprocessor, _clean_filler_words

logger = logging.getLogger(__name__)

FUNCLIP_CLIP_ONLY_PROMPT = get_funclip_prompt('clip_only')
FUNCLIP_TITLE_PROMPT = get_funclip_prompt('title')
FUNCLIP_STEP1_BOUNDARY_PROMPT = get_funclip_prompt('step1_boundary')
FUNCLIP_STEP1_5_GAPFILL_PROMPT = get_funclip_prompt('step1_5_gapfill')
FUNCLIP_STEP2_BATCH_SCORE_PROMPT = get_funclip_prompt('step2_batch_score')
FUNCLIP_STEP3_BATCH_TITLE_PROMPT = get_funclip_prompt('step3_batch_title')
FUNCLIP_MERGED_PROMPT = get_funclip_prompt('merged')


def _deduplicate_clip_segments(merged_clips: List[Dict]) -> List[Dict]:
    """
    跨clip去重：不同clip的segments如果有时间重叠，从segments更多的clip中剔除整个重叠段
    
    策略：segments少的clip（更专注）优先保留重叠部分，从segments多的clip中剔除
    """
    if len(merged_clips) < 2:
        return merged_clips

    # 基于 segment-level confidence + IoU 的去重策略
    # 1) 为每个 segment 计算可信度：优先使用 seg['confidence']，否则基于字幕密度估算
    # 2) 对任意两个跨clip的 segment，如果 IoU > IOU_THRESHOLD，则保留置信度更高的那一端
    IOU_THRESHOLD = 0.5

    def _seg_conf(seg):
        try:
            if 'confidence' in seg:
                return float(seg.get('confidence') or 0.0)
        except Exception:
            pass
        # 备选估算：字幕条目密度（简化）
        try:
            s = _srt_time_to_seconds(seg['start'])
            e = _srt_time_to_seconds(seg['end'])
            dur = max(0.001, e - s)
            # count SRT entries by scanning pre-saved index? 这里采用粗估：短时段优先
            density_score = min(1.0, (len(seg.get('srt_entries', [])) / dur) if seg.get('srt_entries') else 0.0)
            return density_score
        except Exception:
            return 0.0

    def _iou(seg_a, seg_b):
        a_s = _srt_time_to_seconds(seg_a['start'])
        a_e = _srt_time_to_seconds(seg_a['end'])
        b_s = _srt_time_to_seconds(seg_b['start'])
        b_e = _srt_time_to_seconds(seg_b['end'])
        inter_s = max(a_s, b_s)
        inter_e = min(a_e, b_e)
        if inter_e <= inter_s:
            return 0.0
        inter = inter_e - inter_s
        union = (a_e - a_s) + (b_e - b_s) - inter
        return inter / union if union > 0 else 0.0

    # 收集所有 segments 并按置信度降序处理，先保留高置信段
    all_segs = []  # tuples (clip_idx, seg_idx, seg)
    for ci, clip in enumerate(merged_clips):
        for si, seg in enumerate(clip.get('segments', [])):
            all_segs.append((ci, si, seg))

    # sort by confidence desc, longer duration tie-breaker smaller first
    all_segs.sort(key=lambda x: (-_seg_conf(x[2]), _srt_time_to_seconds(x[2]['end']) - _srt_time_to_seconds(x[2]['start'])))

    kept_ranges = []  # list of (start,end)
    removed_map = {}  # clip_idx -> list of removed segment indices

    for ci, si, seg in all_segs:
        s = _srt_time_to_seconds(seg['start'])
        e = _srt_time_to_seconds(seg['end'])
        conflicted = False
        for kr_s, kr_e, kr_seg in kept_ranges:
            # 计算 IoU
            inter_s = max(s, kr_s)
            inter_e = min(e, kr_e)
            if inter_e <= inter_s:
                continue
            inter = inter_e - inter_s
            union = (e - s) + (kr_e - kr_s) - inter
            iou = inter / union if union > 0 else 0.0
            if iou > IOU_THRESHOLD:
                # 比较置信度
                if _seg_conf(seg) <= _seg_conf(kr_seg):
                    conflicted = True
                    break
                else:
                    # 当前 seg 更强，移除已保留的 kr_seg（标记为 removed）
                    for idx, (a, b, ks) in enumerate(kept_ranges):
                        if ks is kr_seg:
                            kept_ranges.pop(idx)
                            removed_map.setdefault(a, []).append(ks)
                            break
        if not conflicted:
            kept_ranges.append((s, e, seg))

    # 根据 kept_ranges 回写每个 clip 的 segments
    new_clips = []
    for ci, clip in enumerate(merged_clips):
        kept = []
        for s, e, seg in kept_ranges:
            # 如果 seg 属于当前 clip (通过对象相等判断)
            if seg in clip.get('segments', []):
                kept.append(seg)
        if kept:
            clip['segments'] = sorted(kept, key=lambda x: _srt_time_to_seconds(x['start']))
            new_clips.append(clip)
        else:
            # clip 没有被保留任何 segment，则降级为移除
            logger.info(f"跨clip去重: 移除了 clip {clip.get('id','?')} 因与更高置信片段冲突")

    return new_clips

    # 移除没有segments的clip
    result = [c for c in merged_clips if c.get('segments')]

    if len(result) < len(merged_clips):
        logger.info(f"跨clip去重: 移除了{len(merged_clips) - len(result)}个重叠片段")

    return result


def _apply_silence_processing(processor, output_path: Path, clip_id: str) -> None:
    """
    对已提取的切片视频应用静音移除后处理。
    使用临时文件方案：处理成功则替换原文件，失败时保留原文件不变。
    """
    import shutil
    temp_path = output_path.with_suffix('.silence_clean.mp4')
    try:
        ok = processor.process_clip(
            input_video=output_path,
            output_video=temp_path,
            clip_id=str(clip_id)
        )
        if ok and temp_path.exists():
            # 用处理后的文件替换原文件
            temp_path.replace(output_path)
            logger.info(f"  切片 {clip_id} 静音移除完成")
        else:
            if ok:
                logger.info(f"  切片 {clip_id} 静音处理无变化，保留原文件")
            else:
                logger.warning(f"  切片 {clip_id} 静音处理失败，保留原文件")
            if temp_path.exists():
                temp_path.unlink()
    except Exception as e:
        logger.warning(f"  切片 {clip_id} 静音处理异常: {e}，保留原文件")
        if temp_path.exists():
            temp_path.unlink()


def _load_vad_silence_ranges(metadata_dir: Path) -> Optional[List[tuple[float, float]]]:
    """
    从VAD结果加载静音段列表（speech_segments反转）。
    依次查找 raw/vad.json, raw/vad_results.json, metadata/vad.json。
    返回 [(start_sec, end_sec), ...] 或 None（无VAD文件时）。
    """
    import json

    vad_candidates = [
        metadata_dir.parent / "raw" / "vad.json",
        metadata_dir.parent / "raw" / "vad_results.json",
        metadata_dir / "vad.json",
    ]
    for vad_path in vad_candidates:
        if not vad_path.exists():
            continue
        try:
            data = json.loads(vad_path.read_text(encoding='utf-8'))
            speech = data.get('speech_segments') or data.get('segments') or []
            if not speech:
                continue

            # 获取音频总时长
            last_end = speech[-1].get('end', speech[-1].get('end_sec', 0))
            audio_dur = data.get('audio_duration') or last_end or 0

            # 反转：语音段 → 静音段
            silences: list[tuple[float, float]] = []
            prev_end = 0.0
            for seg in speech:
                s = seg.get('start', seg.get('start_sec', 0))
                e = seg.get('end', seg.get('end_sec', 0))
                if s - prev_end > 0.5:
                    silences.append((prev_end, s))
                prev_end = e
            # 末尾静音
            if audio_dur - prev_end > 0.5:
                silences.append((prev_end, audio_dur))

            logger.info(f"从VAD加载 {len(silences)} 个静音段 (总时长{audio_dur:.1f}s)")
            return silences
        except Exception as e:
            logger.warning(f"解析VAD文件失败 {vad_path.name}: {e}")
    return None


def _ffmpeg_detect_segment_silences(
    video_path: Path, seg_start: float, seg_end: float,
    temp_audio_path: Path, min_silence: float = 0.5,
    silence_db: float = -30.0
) -> list[tuple[float, float]]:
    """
    对源视频在 [seg_start, seg_end] 范围内用FFmpeg silencedetect检测静音。
    返回 [(source_start_sec, source_end_sec), ...]。
    """
    import subprocess

    duration = seg_end - seg_start
    if duration <= 0:
        return []

    # 确保临时目录存在
    temp_audio_path.parent.mkdir(parents=True, exist_ok=True)

    # 提取音频
    cmd_extract = [
        'ffmpeg', '-y',
        '-ss', f'{seg_start:.3f}',
        '-i', str(video_path),
        '-t', f'{duration:.3f}',
        '-vn', '-acodec', 'pcm_s16le',
        '-ar', '16000', '-ac', '1',
        str(temp_audio_path)
    ]
    r1 = subprocess.run(cmd_extract, capture_output=True)
    if r1.returncode != 0:
        logger.warning(f"提取音频失败: {r1.stderr.decode(errors='ignore')[:200]}")
        return []

    # 静音检测
    cmd_detect = [
        'ffmpeg', '-i', str(temp_audio_path),
        '-af', f'silencedetect=n={silence_db}dB:d={min_silence}',
        '-f', 'null', '-'
    ]
    r2 = subprocess.run(cmd_detect, capture_output=True, text=True)
    stderr = r2.stderr

    # 解析输出: silence_start / silence_end
    pattern_start = re.compile(r'silence_start:\s*([\d.]+)')
    pattern_end = re.compile(r'silence_end:\s*([\d.]+)')

    starts = [float(m.group(1)) for m in pattern_start.finditer(stderr)]
    ends = [float(m.group(1)) for m in pattern_end.finditer(stderr)]

    # 对齐起止，转换回源视频时间
    silences: list[tuple[float, float]] = []
    for i in range(min(len(starts), len(ends))):
        s = seg_start + starts[i]
        e = seg_start + ends[i]
        if e - s >= min_silence:
            silences.append((s, e))

    # 处理最后一条start缺少对应end的情况（音频末尾静音）
    if len(starts) > len(ends):
        s = seg_start + starts[-1]
        e = seg_start + duration
        if e - s >= min_silence:
            silences.append((s, e))

    return silences


def _merge_removed_ranges(
    ranges: list[tuple[float, float]], gap_threshold: float = 0.3
) -> list[tuple[float, float]]:
    """合并相邻/重叠的时间段"""
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda x: x[0])
    merged: list[tuple[float, float]] = [sorted_ranges[0]]
    for s, e in sorted_ranges[1:]:
        last_s, last_e = merged[-1]
        if s - last_e <= gap_threshold:
            merged[-1] = (last_s, max(last_e, e))
        else:
            merged.append((s, e))
    return merged


def _prepopulate_removed_sections(
    clips: list[dict], video_path: Path,
    metadata_dir: Path, temp_dir: Path
) -> None:
    """
    在切割前为每个clip预生成_removed_sections（追加模式）。
    优先使用VAD数据（如果存在），否则回退到FFmpeg silencedetect。
    新增静音段会追加到已有段后，统一合并去重。
    """
    # 尝试加载VAD静音数据
    vad_silences = _load_vad_silence_ranges(metadata_dir)

    for clip in clips:
        segments = clip.get('_segments', [])
        if not segments:
            continue

        new_removed: list[tuple[float, float]] = []

        for seg in segments:
            seg_start = _srt_time_to_seconds(seg['start'])
            seg_end = _srt_time_to_seconds(seg['end'])

            if vad_silences:
                # VAD路线：从全局静音列表取交集
                for vs, ve in vad_silences:
                    overlap_s = max(seg_start, vs)
                    overlap_e = min(seg_end, ve)
                    if overlap_e - overlap_s >= 0.5:
                        new_removed.append((overlap_s, overlap_e))
            else:
                # FFmpeg路线：对segment范围检测
                temp_audio = temp_dir / f'presilence_{clip["id"]}.wav'
                seg_silences = _ffmpeg_detect_segment_silences(
                    video_path, seg_start, seg_end, temp_audio
                )
                new_removed.extend(seg_silences)
                # 清理临时文件
                if temp_audio.exists():
                    temp_audio.unlink()

        if not new_removed:
            continue

        merged = _merge_removed_ranges(new_removed)

        # 追加模式：读取已有段，合并后统一去重
        existing = clip.get('_removed_sections', [])
        existing_sec = [
            (_srt_time_to_seconds(r['start']),
             _srt_time_to_seconds(r['end']))
            for r in existing
        ]
        all_sections = existing_sec + merged
        all_merged = _merge_removed_ranges(all_sections)

        clip['_removed_sections'] = [
            {
                'start': _seconds_to_srt_time(s),
                'end': _seconds_to_srt_time(e),
                'reason': f'VAD检测静音({e - s:.1f}秒)' if vad_silences
                          else f'FFmpeg检测静音({e - s:.1f}秒)'
            }
            for s, e in all_merged
        ]
        logger.info(
            f"Clip {clip['id']}: 原有 {len(existing)} 个静音段 + "
            f"新增 {len(merged)} 个 = 共 {len(all_merged)} 个"
        )


def _compute_effective_segments(segments: List[Dict], removed_sections: List[Dict],
                                 buffer: float = 0.2) -> List[Dict]:
    """
    计算有效段列表：从segments中减去removed_sections的时间范围
    
    对每段的有效内容两侧添加buffer秒缓冲，防止切割时裁剪掉语音首尾。
    各缓冲段之间不重叠（间隙过小时合并），不超出原始segment边界。
    """
    if not removed_sections:
        return segments

    # 将removed_sections转为秒数并排序
    removed = []
    for rs in removed_sections:
        rs_start = _srt_time_to_seconds(rs['start'])
        rs_end = _srt_time_to_seconds(rs['end'])
        if rs_end > rs_start:
            removed.append((rs_start, rs_end))
    removed.sort()

    # 合并重叠的removed区间
    merged_removed = []
    for start, end in removed:
        if merged_removed and start <= merged_removed[-1][1]:
            merged_removed[-1] = (merged_removed[-1][0], max(merged_removed[-1][1], end))
        else:
            merged_removed.append([start, end])

    # 对每个segment减去removed区间，再加缓冲
    effective = []
    for seg in segments:
        seg_start = _srt_time_to_seconds(seg['start'])
        seg_end = _srt_time_to_seconds(seg['end'])

        cuts = [(seg_start, seg_end)]
        for rm_start, rm_end in merged_removed:
            new_cuts = []
            for cs, ce in cuts:
                if rm_start >= ce or rm_end <= cs:
                    new_cuts.append((cs, ce))
                else:
                    if cs < rm_start:
                        new_cuts.append((cs, rm_start))
                    if ce > rm_end:
                        new_cuts.append((rm_end, ce))
            cuts = new_cuts

        # 对每段有效内容加缓冲，但不超出原始segment边界，且不重叠
        buffered = []
        for cs, ce in cuts:
            bs = max(seg_start, cs - buffer)
            be = min(seg_end, ce + buffer)
            if buffered and bs <= buffered[-1][1]:
                buffered[-1] = (buffered[-1][0], max(buffered[-1][1], be))
            else:
                buffered.append((bs, be))

        for bs, be in buffered:
            if be - bs > 0.5:
                effective.append({
                    'start': _seconds_to_srt_time(bs),
                    'end': _seconds_to_srt_time(be)
                })

    return effective


def _log_topic_details(merged_clips: List[Dict], srt_text: str):
    """详细日志：输出每个话题包含的segments、字幕内容及归类原因"""
    entries = _parse_srt_timeline(srt_text)
    if not entries:
        return

    logger.info("")
    logger.info("=" * 60)
    logger.info("话题分组详情")
    logger.info("=" * 60)

    for clip in merged_clips:
        clip_id = clip.get('id', '?')
        title = clip.get('title', clip.get('outline', '未命名话题'))
        outline = clip.get('outline', '')
        reason = clip.get('recommend_reason', '')

        logger.info(f"")
        logger.info(f"--- 话题 {clip_id}: {title} ---")
        logger.info(f"概述: {outline}")
        if reason:
            logger.info(f"归类原因: {reason}")

        segments = clip.get('segments', [])
        logger.info(f"包含 {len(segments)} 个时间段:")

        for si, seg in enumerate(segments):
            seg_start = _srt_time_to_seconds(seg['start'])
            seg_end = _srt_time_to_seconds(seg['end'])

            contained = [e for e in entries if e['start'] >= seg_start and e['end'] <= seg_end]

            logger.info(f"  时间段{si+1}: {seg['start']} -> {seg['end']} ({len(contained)}条字幕)")
            for entry in contained:
                logger.info(f"    [{entry['start_str']} -> {entry['end_str']}] {entry['text']}")

        removed = clip.get('removed_sections', [])
        if removed:
            logger.info(f"  剔除 {len(removed)} 段无关/静音内容:")
            for rs in removed:
                logger.info(f"    {rs['start']} -> {rs['end']}: {rs.get('reason', '')}")

    logger.info("=" * 60)


def _merge_srt_segments(srt_path: Path, merged_clips: List[Dict]) -> List[Dict]:
    """
    将合并方案的输出（含多段segments）转换为标准格式
    每个多段clip被拆分为多个独立clip（后续由视频拼接实现合并）
    """
    video_clips = []
    for i, clip in enumerate(merged_clips):
        segments = clip.get('segments', [])
        if not segments:
            continue
        global_start = segments[0]['start']
        global_end = segments[0]['end']
        for seg in segments[1:]:
            if seg['start'] < global_start:
                global_start = seg['start']
            if seg['end'] > global_end:
                global_end = seg['end']
        video_clips.append({
            'id': clip.get('id', str(i + 1)),
            'outline': clip.get('outline', ''),
            'generated_title': clip.get('title', f"片段_{i+1}"),
            'start_time': global_start,
            'end_time': global_end,
            'final_score': clip.get('final_score', 0.5),
            'recommend_reason': clip.get('recommend_reason', ''),
            'content': [],
            '_segments': segments,
            '_removed_sections': clip.get('removed_sections', [])
        })
    return video_clips


def _filter_vad_silence_by_segments(vad_silence: List[tuple],
                                     segments: List[Dict],
                                     min_silence_duration: float = 0.5) -> List[Dict]:
    """
    将 VAD 检测到的全音频静音区间，筛选为只落在指定 segments 范围内的静音段

    Args:
        vad_silence: VAD输出的全音频静音区间 [(start_sec, end_sec), ...]
        segments: 时间段列表 [{'start': 'hh:mm:ss,fff', 'end': 'hh:mm:ss,fff'}]
        min_silence_duration: 最短静音时长

    Returns:
        格式化的静音段列表，可直接追加到 removed_sections
    """
    seg_ranges = []
    for seg in segments:
        s = _srt_time_to_seconds(seg['start'])
        e = _srt_time_to_seconds(seg['end'])
        seg_ranges.append((s, e))

    result = []
    for silence_start, silence_end in vad_silence:
        for seg_start, seg_end in seg_ranges:
            overlap_start = max(silence_start, seg_start)
            overlap_end = min(silence_end, seg_end)
            if overlap_end - overlap_start >= min_silence_duration:
                result.append({
                    'start': _seconds_to_srt_time(overlap_start),
                    'end': _seconds_to_srt_time(overlap_end),
                    'reason': f"VAD检测静音({overlap_end-overlap_start:.1f}秒)"
                })

    return result


def _safe_parse_json(text: str):
    import json, re
    txt = (text or '').strip()
    try:
        return json.loads(txt)
    except Exception:
        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", txt)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                return None
        return None


def _weighted_segment_conf(segments: List[Dict]) -> float:
    total = 0.0
    total_dur = 0.0
    for seg in segments:
        try:
            conf = float(seg.get('confidence') or 0.0)
        except Exception:
            conf = 0.0
        try:
            s = _srt_time_to_seconds(seg['start'])
            e = _srt_time_to_seconds(seg['end'])
            dur = max(0.001, e - s)
        except Exception:
            dur = 1.0
        total += conf * dur
        total_dur += dur
    return (total / total_dur) if total_dur > 0 else 0.0


def _get_context_snippets(srt_text: str, seg: Dict, window: int = 3) -> str:
    entries = _parse_srt_timeline(srt_text)
    if not entries:
        return ''
    try:
        seg_start = _srt_time_to_seconds(seg['start'])
        seg_end = _srt_time_to_seconds(seg['end'])
    except Exception:
        return ''

    # 仅返回严格属于该 segment 范围内的字幕（start >= seg_start 且 end <= seg_end）
    contained = [e for e in entries if e['start'] >= seg_start and e['end'] <= seg_end]
    if not contained:
        return ''
    return '\n'.join([f"{e['start_str']} --> {e['end_str']}  {e['text']}" for e in contained])


def _apply_short_segment_policy(self, merged_clips: List[Dict], srt_text: str) -> List[Dict]:
    """只保留高置信短片段；对置信处于边界值的短片段，调用二次LLM确认。"""
    HIGH_KEEP_CONF = 0.60
    BORDERLINE_LOW = 0.40
    MIN_SECONDS = get_topic_duration_limits()['min_seconds']
    kept = []
    for clip in merged_clips:
        segments = clip.get('segments', [])
        duration = sum((_srt_time_to_seconds(s['end']) - _srt_time_to_seconds(s['start'])) for s in segments) if segments else 0.0
        wconf = _weighted_segment_conf(segments)
        llm_score = float(clip.get('final_score') or clip.get('score') or 0.0)

        if duration >= MIN_SECONDS:
            kept.append(clip)
            continue

        # 高置信短片段直接保留
        if wconf >= HIGH_KEEP_CONF or llm_score >= 0.65:
            clip['duration_warning'] = 'too_short_but_kept'
            kept.append(clip)
            continue

        # 边界置信：调用二次LLM确认是否保留
        if wconf >= BORDERLINE_LOW:
            try:
                prompt = (
                    "请判断：下列话题是否应以当前划定时间作为独立精彩片段保留。\n"
                    "返回严格JSON: {\"keep\": true|false, \"reason\": \"...\"}。\n"
                    f"话题outline: {clip.get('outline','')}\n"
                    f"final_score: {llm_score:.3f}, weighted_seg_conf: {wconf:.3f}, duration: {duration:.1f}s\n"
                )
                if segments:
                    prompt += "segments:\n"
                    for seg in segments:
                        prompt += f" - {seg.get('start')} -> {seg.get('end')}, conf={seg.get('confidence',0.0)}\n"
                    prompt += "上下文字幕（前后3条）:\n"
                    prompt += _get_context_snippets(srt_text, segments[0], window=3)

                resp = self.llm_manager.current_provider.call(
                    FUNCLIP_MERGED_PROMPT,  # use same provider; prompt as instruction
                    prompt,
                    max_tokens=256,
                    temperature=0,
                )
                parsed = _safe_parse_json(resp.content or '')
                if isinstance(parsed, dict) and parsed.get('keep'):
                    clip['duration_warning'] = 'too_short_kept_after_llm'
                    kept.append(clip)
                    continue
                else:
                    logger.info(f"二次LLM判定不保留短片段: {clip.get('outline')} -> {parsed}")
                    clip['needs_review'] = True
                    continue
            except Exception as e:
                logger.warning(f"二次LLM验证失败，按不保留处理: {e}")
                clip['needs_review'] = True
                continue

        # 默认：太短且低置信 -> 标注为 needs_review（不保留）
        clip['needs_review'] = True

    return kept



def parse_funclip_timestamps(input_text):
    """解析FunClip风格的时间戳提取"""
    timestamps = re.findall(r'\[(\d{2}:\d{2}:\d{2},?\d{0,3})\s*-\s*(\d{2}:\d{2}:\d{2},?\d{0,3})\]', input_text)
    times_list = []
    
    for start_time, end_time in timestamps:
        start_millis = _convert_time_to_millis(start_time)
        end_millis = _convert_time_to_millis(end_time)
        times_list.append([start_millis, end_millis])
    
    return times_list

def _convert_time_to_millis(time_str):
    """将时间字符串转换为毫秒"""
    try:
        hours, minutes, seconds, milliseconds = map(int, re.split('[:,]', time_str))
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds
    except Exception as e:
        logger.warning(f"时间转换失败: {time_str}, 使用默认值: {e}")
        return 0


# ============================================================
# B2: Step2 智能截取工具
# ============================================================

def _find_boundary_line_indices(lines: List[str], segments: List[Dict]) -> List[int]:
    boundary_idxs = set()
    for seg in segments:
        seg_start = _srt_time_to_seconds(seg['start'])
        seg_end = _srt_time_to_seconds(seg['end'])
        for i, line in enumerate(lines):
            m = re.match(r'(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->', line)
            if m:
                t = _srt_time_to_seconds(m.group(1))
                if abs(t - seg_start) < 5 or abs(t - seg_end) < 5:
                    boundary_idxs.add(i)
    return sorted(boundary_idxs)


def _smart_truncate_srt_for_scoring(
    srt_text: str,
    segments: List[Dict],
    *,
    max_chars: int = 3000,
    head_lines: int = 40,
    tail_lines: int = 30,
    boundary_window: int = 20,
) -> str:
    lines = srt_text.split('\n')
    if len(srt_text) <= max_chars:
        return srt_text

    boundary_line_idxs = _find_boundary_line_indices(lines, segments)

    selected = set(range(min(head_lines, len(lines))))
    selected.update(range(max(0, len(lines) - tail_lines), len(lines)))
    for bi in boundary_line_idxs:
        selected.update(range(max(0, bi - boundary_window), min(len(lines), bi + boundary_window)))

    ordered = sorted(selected)
    result = []
    prev = -2
    for idx in ordered:
        if idx > prev + 1:
            result.append('...(省略)...')
        result.append(lines[idx])
        prev = idx
    return '\n'.join(result)


# ============================================================
# B2: boundary_suggestion 工具 — _handle_add_segment
# ============================================================

def _handle_add_segment(
    suggestion: str,
    topic: Dict,
    segments: List[Dict],
    srt_entries: List[Dict]
):
    time_pairs = re.findall(
        r'(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*[-~到至]\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})',
        suggestion,
    )
    added = 0
    for start_str, end_str in time_pairs:
        start = _align_to_srt_start(
            _srt_time_to_seconds(start_str.replace('.', ',')), srt_entries
        )
        end = _align_to_srt_end(
            _srt_time_to_seconds(end_str.replace('.', ',')), srt_entries
        )
        if start is not None and end is not None and end > start:
            segments.append({'start': _seconds_to_srt_time(start), 'end': _seconds_to_srt_time(end)})
            added += 1
    if added:
        segments.sort(key=lambda s: _srt_time_to_seconds(s['start']))
        topic['segments'] = _merge_overlapping_segments(segments)
        logger.info(f"boundary_suggestion add_segment 应用完成: 话题{topic['id']} 新增{added}个segment")


def _get_max_boundary_shift() -> float:
    try:
        from backend.core.shared_config import config_manager
        return float(getattr(config_manager.settings, 'max_boundary_shift_seconds', 180.0))
    except Exception:
        return 180.0


# ============================================================
# 三步方案工具函数：boundary_suggestion 处理（P0修复3）
# ============================================================

def _apply_boundary_suggestions(
    topics: List[Dict],
    scores: List[Dict],
    srt_entries: List[Dict]
) -> List[Dict]:
    """
    处理 Step 2 返回的 boundary_suggestion，验证并应用合理的建议。

    建议应用规则：
    1. 扩展开头：新起点必须对齐某条SRT的首时间戳
    2. 收缩结尾：新终点必须对齐某条SRT的尾时间戳
    3. 前移/后移：同扩展/收缩
    4. 移除内部段：只有当移除后话题仍有 ≥ 1 个 segment 时才执行
    5. 激进建议（移动 > 60 秒）→ 忽略（可能是 LLM 幻觉）
    """
    applied_count = 0
    max_suggestions_per_topic = 2
    max_shift = _get_max_boundary_shift()

    for score_item in scores:
        suggestion = score_item.get('boundary_suggestion')
        if not suggestion or suggestion == 'null' or suggestion == 'None':
            continue

        topic_id = score_item.get('id')
        topic = next((t for t in topics if t.get('id') == topic_id), None)
        if not topic:
            continue

        segments = topic.get('segments', [])
        if not segments:
            continue

        suggestion_lower = suggestion.lower()
        handled = False

        if '扩展' in suggestion and ('开头' in suggestion or '向前' in suggestion):
            _handle_extend_start(suggestion, topic, segments, srt_entries)

        elif '扩展' in suggestion and ('结尾' in suggestion or '向后' in suggestion):
            _handle_extend_end(suggestion, topic, segments, srt_entries)

        elif '收缩' in suggestion and '结尾' in suggestion:
            _handle_shrink_end(suggestion, topic, segments, srt_entries)

        elif '收缩' in suggestion and '开头' in suggestion:
            _handle_shrink_start(suggestion, topic, segments, srt_entries)

        elif '移除' in suggestion and ('内部' in suggestion or 'segment' in suggestion_lower):
            _handle_remove_segment(suggestion, topic, segments)

        elif '前移' in suggestion:
            _handle_extend_start(suggestion, topic, segments, srt_entries)

        elif '后移' in suggestion:
            _handle_shrink_start(suggestion, topic, segments, srt_entries)

        elif '补 segment' in suggestion_lower or '新增 segment' in suggestion_lower or '添加 segment' in suggestion_lower:
            _handle_add_segment(suggestion, topic, segments, srt_entries)

        else:
            logger.info(f"boundary_suggestion 格式无法解析，跳过: {suggestion[:100]}")

    return topics


def _handle_extend_start(suggestion: str, topic: Dict, segments: List[Dict],
                          srt_entries: List[Dict]):
    time_match = re.search(r'(\d+)\s*秒', suggestion)
    extend_seconds = int(time_match.group(1)) if time_match else 10

    max_shift = _get_max_boundary_shift()
    if extend_seconds > max_shift:
        logger.warning(f"扩展建议偏移量过大({extend_seconds}秒)，可能是LLM幻觉，跳过")
        return

    first_seg_start = _srt_time_to_seconds(segments[0]['start'])
    new_start_sec = max(0, first_seg_start - extend_seconds)

    aligned_start = _align_to_srt_start(new_start_sec, srt_entries)

    if aligned_start is not None and aligned_start < first_seg_start:
        segments[0]['start'] = _seconds_to_srt_time(aligned_start)
        logger.info(
            f"boundary_suggestion 已应用: 话题{topic['id']} 开头前移 "
            f"{first_seg_start - aligned_start:.1f}秒 → {_seconds_to_srt_time(aligned_start)}"
        )


def _handle_shrink_end(suggestion: str, topic: Dict, segments: List[Dict],
                        srt_entries: List[Dict]):
    time_match = re.search(r'(\d+)\s*秒', suggestion)
    shrink_seconds = int(time_match.group(1)) if time_match else 10

    if shrink_seconds > 60:
        logger.warning(f"收缩建议偏移量过大({shrink_seconds}秒)，可能是LLM幻觉，跳过")
        return

    last_seg_end = _srt_time_to_seconds(segments[-1]['end'])
    new_end_sec = last_seg_end - shrink_seconds

    aligned_end = _align_to_srt_end(new_end_sec, srt_entries)

    if aligned_end is not None and aligned_end < last_seg_end:
        segments[-1]['end'] = _seconds_to_srt_time(aligned_end)
        logger.info(
            f"boundary_suggestion 已应用: 话题{topic['id']} 结尾收缩 "
            f"{last_seg_end - aligned_end:.1f}秒 → {_seconds_to_srt_time(aligned_end)}"
        )


def _handle_shrink_start(suggestion: str, topic: Dict, segments: List[Dict],
                          srt_entries: List[Dict]):
    time_match = re.search(r'(\d+)\s*秒', suggestion)
    shrink_seconds = int(time_match.group(1)) if time_match else 10

    if shrink_seconds > 60:
        return

    first_seg_start = _srt_time_to_seconds(segments[0]['start'])
    new_start_sec = first_seg_start + shrink_seconds

    aligned_start = _align_to_srt_start(new_start_sec, srt_entries)

    if aligned_start is not None and aligned_start > first_seg_start:
        segments[0]['start'] = _seconds_to_srt_time(aligned_start)
        logger.info(
            f"boundary_suggestion 已应用: 话题{topic['id']} 开头后移 "
            f"{aligned_start - first_seg_start:.1f}秒 → {_seconds_to_srt_time(aligned_start)}"
        )


def _handle_extend_end(suggestion: str, topic: Dict, segments: List[Dict],
                        srt_entries: List[Dict]):
    time_match = re.search(r'(\d+)\s*秒', suggestion)
    extend_seconds = int(time_match.group(1)) if time_match else 10

    if extend_seconds > 60:
        return

    last_seg_end = _srt_time_to_seconds(segments[-1]['end'])
    new_end_sec = last_seg_end + extend_seconds

    aligned_end = _align_to_srt_end(new_end_sec, srt_entries)

    if aligned_end is not None and aligned_end > last_seg_end:
        segments[-1]['end'] = _seconds_to_srt_time(aligned_end)
        logger.info(
            f"boundary_suggestion 已应用: 话题{topic['id']} 结尾后移 "
            f"{aligned_end - last_seg_end:.1f}秒 → {_seconds_to_srt_time(aligned_end)}"
        )


def _handle_remove_segment(suggestion: str, topic: Dict, segments: List[Dict]):
    seg_match = re.search(r'segment\s*#?\s*(\d+)', suggestion, re.IGNORECASE)
    if not seg_match:
        return
    seg_idx = int(seg_match.group(1)) - 1

    if seg_idx < 0 or seg_idx >= len(segments):
        return

    if len(segments) <= 1:
        logger.warning(f"boundary_suggestion 拒绝: 话题{topic['id']} 只有1个segment，不能移除")
        return

    removed_seg = segments.pop(seg_idx)
    logger.info(
        f"boundary_suggestion 已应用: 移除话题{topic['id']}的segment#{seg_idx+1} "
        f"({removed_seg['start']} -> {removed_seg['end']})"
    )


def _align_to_srt_start(target_sec: float, srt_entries: List[Dict]) -> Optional[float]:
    best = None
    for entry in srt_entries:
        if entry['start'] <= target_sec:
            if best is None or entry['start'] > best:
                best = entry['start']
    return best


def _align_to_srt_end(target_sec: float, srt_entries: List[Dict]) -> Optional[float]:
    best = None
    for entry in srt_entries:
        if entry['end'] >= target_sec:
            if best is None or entry['end'] < best:
                best = entry['end']
    return best


# ============================================================
# 三步方案工具函数：token 预估与自动分批（P0修复4）
# ============================================================

ZH_CHAR_TO_TOKEN_RATIO = 2.0
DEFAULT_MAX_TOKENS = 8192
TOKEN_SAFETY_MARGIN = 0.8
RESERVED_OUTPUT_TOKENS = 2048


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * ZH_CHAR_TO_TOKEN_RATIO + other_chars * 0.3)


def _should_batch_step2(topics_with_srt: List[Dict], max_tokens: int = None) -> bool:
    if max_tokens is None:
        max_tokens = DEFAULT_MAX_TOKENS

    prompt_tokens = _estimate_tokens(FUNCLIP_STEP2_BATCH_SCORE_PROMPT)
    total_input_tokens = prompt_tokens

    for topic in topics_with_srt:
        total_input_tokens += _estimate_tokens(topic.get('srt_text', ''))
        total_input_tokens += _estimate_tokens(json.dumps({
            'id': topic.get('id'),
            'outline': topic.get('outline'),
            'topic_type': topic.get('topic_type'),
            'total_duration_seconds': topic.get('total_duration_seconds')
        }, ensure_ascii=False))

    effective_limit = int(max_tokens * TOKEN_SAFETY_MARGIN) - RESERVED_OUTPUT_TOKENS
    return total_input_tokens > effective_limit


def _split_topics_by_priority(topics_with_srt: List[Dict]) -> tuple:
    TYPE_PRIORITY = {'highlight': 1, 'knowledge': 1, 'product': 2, 'fun': 2, 'daily': 2}
    batch1 = [t for t in topics_with_srt if TYPE_PRIORITY.get(t.get('topic_type'), 2) == 1]
    batch2 = [t for t in topics_with_srt if TYPE_PRIORITY.get(t.get('topic_type'), 2) == 2]
    return batch1, batch2


# ============================================================
# 三步方案工具函数：话题选择（A4 — 替代硬编码 Top-6）
# ============================================================

def _get_topic_selection_config() -> Dict[str, float]:
    try:
        from backend.core.shared_config import config_manager
        s = config_manager.settings
        return {
            'min_score': float(getattr(s, 'topic_selection_min_score', 0.5)),
            'max_topics': int(getattr(s, 'topic_selection_hard_cap', 8)),
        }
    except Exception:
        return {'min_score': 0.5, 'max_topics': 8}


def _select_final_topics(
    topics: List[Dict],
    *,
    min_score: float = None,
    max_topics: int = None,
) -> List[Dict]:
    cfg = _get_topic_selection_config()
    min_score = min_score if min_score is not None else cfg['min_score']
    max_topics = max_topics if max_topics is not None else cfg['max_topics']

    scored = sorted(topics, key=lambda t: t.get('final_score', 0), reverse=True)

    kept = [t for t in scored if t.get('final_score', 0) >= min_score]

    if not kept and scored:
        kept = [scored[0]]

    if len(kept) > max_topics:
        kept = kept[:max_topics]

    kept.sort(key=lambda t: _srt_time_to_seconds(t['segments'][0]['start']))
    for i, t in enumerate(kept):
        t['id'] = str(i + 1)
    return kept


# ============================================================
# B1: Step1.5 Gap Fill 工具函数
# ============================================================

def _get_step1_5_config() -> dict:
    try:
        from backend.core.shared_config import config_manager
        s = config_manager.settings
        return {
            'enabled': bool(getattr(s, 'step1_5_enabled', True)),
            'coverage_threshold': float(getattr(s, 'step1_5_coverage_threshold', 0.92)),
            'confidence_threshold': float(getattr(s, 'step1_5_confidence_threshold', 0.75)),
        }
    except Exception:
        return {'enabled': True, 'coverage_threshold': 0.92, 'confidence_threshold': 0.75}


def _compute_topic_coverage_simple(
    topics: List[Dict], srt_entries: List[Dict]
) -> tuple:
    if not topics or not srt_entries:
        return 1.0, [], []

    covered = set()
    for topic in topics:
        for seg in topic.get('segments', []):
            seg_start = _srt_time_to_seconds(seg['start'])
            seg_end = _srt_time_to_seconds(seg['end'])
            for i, e in enumerate(srt_entries):
                if e['start'] < seg_end and e['end'] > seg_start:
                    covered.add(i)

    orphans = [e for i, e in enumerate(srt_entries) if i not in covered]
    ratio = len(covered) / len(srt_entries) if srt_entries else 1.0

    gaps = []
    if orphans:
        orphans.sort(key=lambda e: e['start'])
        g_start = orphans[0]['start']
        g_end = orphans[0]['end']
        g_list = [orphans[0]]
        for e in orphans[1:]:
            if e['start'] - g_end <= 2.0:
                g_end = max(g_end, e['end'])
                g_list.append(e)
            else:
                gaps.append({'start': g_start, 'end': g_end, 'entries': g_list})
                g_start, g_end, g_list = e['start'], e['end'], [e]
        gaps.append({'start': g_start, 'end': g_end, 'entries': g_list})

    return ratio, orphans, gaps


def _extract_gap_srt(
    gap_start: float, gap_end: float, srt_entries: List[Dict]
) -> str:
    lines = []
    for e in srt_entries:
        if e['start'] >= gap_start and e['end'] <= gap_end:
            start_str = e.get('start_str', _seconds_to_srt_time(e['start']))
            end_str = e.get('end_str', _seconds_to_srt_time(e['end']))
            text = e.get('text', '').strip()
            if text:
                lines.append(f"{start_str} --> {end_str}\n{text}")
        elif e['start'] < gap_end and e['end'] > gap_start:
            start_str = e.get('start_str', _seconds_to_srt_time(e['start']))
            end_str = e.get('end_str', _seconds_to_srt_time(e['end']))
            text = e.get('text', '').strip()
            if text:
                lines.append(f"{start_str} --> {end_str}\n{text}")
    return '\n\n'.join(lines)


def _merge_new_topics(
    topics: List[Dict], actions: List[Dict], srt_entries: List[Dict]
) -> List[Dict]:
    for action in actions:
        act = action.get('action', 'ignore')
        if act == 'ignore':
            continue
        if act == 'create':
            new_topic = action.get('new_topic', {})
            if new_topic.get('outline'):
                seg_start = _seconds_to_srt_time(_srt_time_to_seconds(new_topic.get('start', '0')))
                seg_end = _seconds_to_srt_time(_srt_time_to_seconds(new_topic.get('end', '0')))
                if seg_start and seg_end and seg_start != seg_end:
                    next_id = str(len(topics) + 1)
                    topics.append({
                        'id': next_id,
                        'outline': new_topic['outline'],
                        'topic_type': new_topic.get('topic_type', 'daily'),
                        'segments': [{'start': seg_start, 'end': seg_end}],
                    })
        elif act == 'merge_to':
            target_id = action.get('target_topic_id')
            gap_start = _srt_time_to_seconds(action.get('gap_start', '0').replace(',', '.'))
            gap_end = _srt_time_to_seconds(action.get('gap_end', '0').replace(',', '.'))
            for topic in topics:
                if topic.get('id') == target_id:
                    topic['segments'].append({
                        'start': _seconds_to_srt_time(gap_start),
                        'end': _seconds_to_srt_time(gap_end),
                    })
                    topic['segments'].sort(key=lambda s: _srt_time_to_seconds(s['start']))
                    break

    topics.sort(key=lambda t: _srt_time_to_seconds(t['segments'][0]['start']))
    for i, t in enumerate(topics):
        t['id'] = str(i + 1)
    return topics


# ============================================================
# 三步方案工具函数：检查点持久化（P0修复5）
# ============================================================

CHECKPOINT_DIR_NAME = "pipeline_checkpoints"


class PipelineCheckpoint:
    """三步流水线检查点管理器"""

    def __init__(self, metadata_dir: Path):
        self.checkpoint_dir = metadata_dir / CHECKPOINT_DIR_NAME
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file = self.checkpoint_dir / "three_step_state.json"
        self._state = self._load()

    def _load(self) -> Dict:
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            'version': 1,
            'created_at': time.time(),
            'steps': {}
        }

    def _save(self):
        self._state['updated_at'] = time.time()
        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    def has_step(self, step_name: str) -> bool:
        return step_name in self._state.get('steps', {})

    def get_step_output(self, step_name: str) -> Optional[Any]:
        step = self._state.get('steps', {}).get(step_name)
        if step and step.get('status') == 'success':
            return step.get('output')
        return None

    def save_step_output(self, step_name: str, output: Any, metadata: Dict = None):
        self._state.setdefault('steps', {})[step_name] = {
            'status': 'success',
            'output': output,
            'timestamp': time.time(),
            'retry_count': self._state['steps'].get(step_name, {}).get('retry_count', 0),
            'metadata': metadata or {}
        }
        self._save()

    def mark_step_failed(self, step_name: str, error: str):
        step = self._state.setdefault('steps', {}).setdefault(step_name, {})
        step['status'] = 'failed'
        step['error'] = str(error)[:500]
        step['retry_count'] = step.get('retry_count', 0) + 1
        step['timestamp'] = time.time()
        self._save()

    def should_retry(self, step_name: str, max_retries: int = 2) -> bool:
        step = self._state.get('steps', {}).get(step_name, {})
        return step.get('retry_count', 0) < max_retries

    def clear(self):
        self._state = {
            'version': 1,
            'created_at': time.time(),
            'steps': {}
        }
        self._save()


# ============================================================
# 三步方案辅助函数：数据转换（P0修复3-5共享）
# ============================================================

VULGAR_WORD_MAP = {
    '装逼': '犀利点评',
    '傻逼': '令人费解',
    '他妈的': '真性情',
    '逼味': '独特风格',
    '傻X': '争议观点',
    '脑残': '出人意料',
    '弱智': '令人困惑',
}


def _validate_step1_segments(topics: List[Dict], srt_text: str) -> List[Dict]:
    for topic in topics:
        topic.setdefault('removed_sections', [])
    return postprocess_funclip_topics(topics, srt_text)


def _merge_scores_to_topics(topics: List[Dict], scores: List[Dict]) -> List[Dict]:
    score_map = {s.get('id'): s for s in scores}
    for topic in topics:
        tid = topic.get('id', '')
        score_data = score_map.get(tid, {})
        topic['final_score'] = score_data.get('final_score', 0.5)
        topic['sub_scores'] = score_data.get('sub_scores', {})
        topic['recommend_reason'] = score_data.get('recommend_reason',
                                                    topic.get('outline', '')[:20])
    return topics


def _merge_titles_to_topics(topics: List[Dict], titles: List[Dict]) -> List[Dict]:
    title_map = {t.get('id'): t.get('title', '') for t in titles}
    for topic in topics:
        tid = topic.get('id', '')
        title = title_map.get(tid, '')
        if title:
            title = _postprocess_title(title, topic)
            topic['title'] = title
        else:
            topic['title'] = topic.get('outline', '未命名片段')[:20]
    return topics


def _postprocess_title(title: str, topic: Dict) -> str:
    for vulgar, replacement in VULGAR_WORD_MAP.items():
        title = title.replace(vulgar, replacement)

    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', title))
    if chinese_chars < 8:
        outline = topic.get('outline', '')
        title = title + '：' + outline[:15]
    elif chinese_chars > 20:
        chinese_positions = [i for i, c in enumerate(title) if '\u4e00' <= c <= '\u9fff']
        if len(chinese_positions) > 20:
            cut_pos = chinese_positions[19] + 1
            for punct in '，。！？…~':
                punct_pos = title[:cut_pos].rfind(punct)
                if punct_pos > 0:
                    cut_pos = punct_pos + 1
                    break
            title = title[:cut_pos]
    return title


def _convert_topics_to_clips(topics: List[Dict]) -> List[Dict]:
    clips = []
    for topic in topics:
        segments = topic.get('segments', [])
        if not segments:
            continue
        clip = {
            'id': topic.get('id', ''),
            'outline': topic.get('outline', ''),
            'generated_title': topic.get('title', topic.get('outline', '')),
            'start_time': segments[0]['start'],
            'end_time': segments[-1]['end'],
            'final_score': topic.get('final_score', 0.5),
            'recommend_reason': topic.get('recommend_reason', ''),
            'content': [],
            '_segments': segments,
            '_removed_sections': topic.get('removed_sections', [])
        }
        clips.append(clip)
    return clips


class FunClipStyleProcessor:
    """基于FunClip风格的单步LLM处理方案"""
    
    def __init__(self, metadata_dir: Path = None):
        from backend.core.llm_manager import LLMManager
        self.llm_manager = LLMManager()
        self.metadata_dir = metadata_dir or Path('.')
        self.chunks_dir = self.metadata_dir / "funclip_chunks"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
    
    def process(self, srt_path: Path, processing_mode: str = "two_stage", vad_path: Path = None, asr_path: Path = None):
        """完整的单步处理流程

        Args:
            srt_path: SRT文件路径
            processing_mode: 处理模式
                - "two_stage": 两阶段方案（默认，先识别边界再生成标题）
                - "merged": 合并方案（单次LLM调用完成所有任务）
                - "three_step": 三步方案（边界识别→评分→标题，含检查点与降级）
        """
        processing_mode = resolve_funclip_sub_mode(srt_path, processing_mode)
        logger.info("="*60)
        logger.info(f"使用FunClip风格处理开始 [模式: {processing_mode}]")
        logger.info("="*60)
        
        # 1. 读取和解析SRT
        srt_text = self._read_srt(srt_path)
        
        # 2. 单步LLM处理（根据模式选择）
        clips, collections = self._single_step_llm_process(srt_text, processing_mode, vad_path=vad_path, asr_path=asr_path)
        
        # 3. 保存结果
        self._save_results(clips, collections)
        
        return clips, collections
    
    def _read_srt(self, srt_path: Path):
        """读取SRT文件"""
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"读取SRT失败: {e}")
            return ""
    
    def _single_step_llm_process(self, srt_text: str, processing_mode: str = "two_stage", vad_path: Path = None, asr_path: Path = None):
        """单步LLM处理，根据模式选择不同方案"""
        if not self.llm_manager.current_provider:
            logger.warning("没有可用的LLM提供商，使用降级方案")
            return self._fallback_process(srt_text)
        
        if processing_mode == "merged":
            return self._llm_process_merged(srt_text, vad_path=vad_path, asr_path=asr_path)
        elif processing_mode == "three_step":
            return self._llm_process_three_step(srt_text)
        else:
            return self._llm_process_with_llm(srt_text)
    
    def _llm_process_with_llm(self, srt_text: str):
        """两阶段LLM处理：1.识别片段 2.每段独立生成标题"""
        try:
            # ===== 预处理：剔除填充词 + 语义断句 + 纠错 =====
            logger.info("开始预处理SRT文本（剔除填充词 + 语义断句 + 纠错）...")
            original_len = len(srt_text)
            try:
                enhanced_text = self._prepare_enhanced_text(srt_text)
                logger.info(f"预处理完成: {original_len} -> {len(enhanced_text)} 字符")
            except Exception as e:
                logger.warning(f"预处理失败，回退到填充词清理后的文本: {e}")
                enhanced_text = _clean_filler_words(srt_text)

            # ===== 第一阶段：仅识别片段边界 =====
            logger.info("开始第一阶段LLM调用（识别片段边界）...")
            enhanced_text = self._truncate_srt_for_local_model(enhanced_text)
            logger.info(f"输入SRT文本长度: {len(enhanced_text)} 字符")

            response = self.llm_manager.current_provider.call(
                FUNCLIP_CLIP_ONLY_PROMPT,
                "这是待裁剪的视频srt字幕：\n" + enhanced_text,
                max_tokens=16384,
                temperature=0,
                seed=42
            )
            
            if not response or not response.content:
                logger.warning("第一阶段LLM返回空响应，使用降级方案")
                return self._fallback_process(srt_text)
            
            logger.info(f"第一阶段LLM响应成功，长度: {len(response.content)} 字符")
            
            clips = self._parse_clips_only(response.content)

            # 对两阶段识别结果做确定性后处理（包括短产品片段合并）
            try:
                from backend.pipeline.topic_postprocess import postprocess_funclip_topics
                clips = postprocess_funclip_topics(clips, srt_text)
            except Exception:
                pass
            
            if not clips:
                logger.warning("第一阶段未能解析出片段，使用降级方案")
                return self._fallback_process(srt_text)
            
            logger.info(f"第一阶段识别到 {len(clips)} 个片段")
            for clip in clips:
                logger.info(f"  片段{clip.get('id')}: {clip.get('outline', 'N/A')}, "
                          f"时间: {clip.get('start', 'N/A')} -> {clip.get('end', 'N/A')}, "
                          f"评分: {clip.get('final_score', 0)}")
            
            # ===== 第二阶段：为每个片段独立生成标题 =====
            logger.info("=" * 40)
            logger.info("开始第二阶段：为每个片段独立生成标题")
            logger.info("=" * 40)
            
            for clip in clips:
                clip_id = clip.get('id', '')
                start_time = clip.get('start', '')
                end_time = clip.get('end', '')
                outline = clip.get('outline', '')
                recommend_reason = clip.get('recommend_reason', '')
                
                # 提取该片段自己的SRT文本
                clip_srt = self._extract_srt_segment(srt_text, start_time, end_time)
                
                if not clip_srt:
                    logger.warning(f"片段{clip_id}无法提取字幕文本，使用outline作为标题")
                    clip['generated_title'] = outline
                    continue
                
                logger.info(f"为片段{clip_id}生成标题，SRT长度: {len(clip_srt)} 字符")
                logger.debug(f"片段{clip_id}的SRT文本: {clip_srt[:200]}...")
                
                title_response = self.llm_manager.current_provider.call(
                    FUNCLIP_TITLE_PROMPT.format(
                        outline=outline,
                        recommend_reason=recommend_reason,
                        clip_srt_text=clip_srt
                    ),
                    None
                )
                
                if title_response and title_response.content:
                    title = title_response.content.strip()
                    # 清理可能的引号和多余字符
                    title = title.strip('"').strip("'").strip()
                    clip['generated_title'] = title
                    logger.info(f"  片段{clip_id}标题: {title}")
                else:
                    logger.warning(f"片段{clip_id}标题生成失败，使用outline")
                    clip['generated_title'] = outline
            
            # 生成合集
            collections = self._generate_collections(clips)
            
            logger.info(f"两阶段处理完成，共 {len(clips)} 个片段")
            return clips, collections
            
        except Exception as e:
            logger.warning(f"LLM处理失败: {e}，使用降级方案")
            return self._fallback_process(srt_text)
    
    def _llm_process_merged(self, srt_text: str, vad_path: Path = None, asr_path: Path = None):
        """合并方案：单次LLM调用完成话题切分 + 多段合并 + 标题生成 + 静音剔除"""
        try:
            # ===== 预处理：剔除填充词 + 语义断句 + 纠错 =====
            logger.info("开始预处理SRT文本（剔除填充词 + 语义断句 + 纠错）...")
            original_len = len(srt_text)
            try:
                enhanced_text = self._prepare_enhanced_text(srt_text)
                logger.info(f"预处理完成: {original_len} -> {len(enhanced_text)} 字符")
            except Exception as e:
                logger.warning(f"Step1 预处理失败，回退到原始SRT文本: {e}")
                enhanced_text = _clean_filler_words(srt_text)

            logger.info("开始合并方案LLM调用（话题切分 + 标题生成 + 静音剔除）...")
            enhanced_text = self._truncate_srt_for_local_model(enhanced_text)
            logger.info(f"输入SRT文本长度: {len(enhanced_text)} 字符")

            response = self.llm_manager.current_provider.call(
                FUNCLIP_MERGED_PROMPT,
                "这是待分析剪辑的直播srt字幕：\n" + enhanced_text,
                max_tokens=16384,
                temperature=0,  # temperature=0 固定输出，确保同输入同结果
                seed=42  # 固定随机种子，配合temperature=0保证完全确定性
            )

            if not response or not response.content:
                logger.warning("合并方案LLM返回空响应，使用降级方案")
                return self._fallback_process(srt_text)

            logger.info(f"合并方案LLM响应成功，长度: {len(response.content)} 字符")
            logger.info(f"合并方案LLM响应内容: {response.content[:500]}")

            # 保存原始响应到文件（用于调试）
            try:
                debug_path = self.metadata_dir / "funclip_raw_response.txt"
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(response.content)
                logger.info(f"原始LLM响应已保存到: {debug_path}")
            except Exception as e:
                logger.warning(f"保存原始LLM响应失败: {e}")

            merged_clips = self._parse_merged_response(response.content)

            if not merged_clips:
                logger.warning("合并方案未能解析出片段，使用降级方案")
                return self._fallback_process(srt_text)

            # 检查 LLM 是否返回置信度信息（boundary_confidence / segments[].confidence）
            # 若缺失或平均 boundary_confidence 过低，则认为 merged 不可靠，降级为 three_step
            try:
                # 计算每个 clip 的 boundary_confidence：优先使用顶层 boundary_confidence，
                # 否则用 segments[].confidence 的时长加权平均作为备选值。
                total_bc = 0.0
                bc_count = 0
                any_seg_conf_found = False
                for c in merged_clips:
                    # 默认使用顶层 boundary_confidence（若存在且非空）
                    bc_val = None
                    if 'boundary_confidence' in c and c.get('boundary_confidence') is not None:
                        try:
                            bc_val = float(c.get('boundary_confidence') or 0.0)
                        except Exception:
                            bc_val = None

                    # 如果顶层缺失，则尝试用 segments[].confidence 的时长加权平均作为备用
                    if bc_val is None:
                        segs = c.get('segments', []) or []
                        weighted_sum = 0.0
                        total_dur = 0.0
                        seg_conf_found = False
                        for seg in segs:
                            if 'confidence' in seg:
                                try:
                                    conf = float(seg.get('confidence') or 0.0)
                                except Exception:
                                    conf = 0.0
                                s = _srt_time_to_seconds(seg['start'])
                                e = _srt_time_to_seconds(seg['end'])
                                dur = max(0.001, e - s)
                                weighted_sum += conf * dur
                                total_dur += dur
                                seg_conf_found = True
                        if seg_conf_found and total_dur > 0:
                            bc_val = weighted_sum / total_dur
                            any_seg_conf_found = True
                    else:
                        # 顶层存在则认为该 clip 有置信度信息
                        any_seg_conf_found = True

                    # 最终归一化为 0.0~1.0 范围数值
                    bc = float(bc_val or 0.0)
                    total_bc += bc
                    bc_count += 1

                avg_bc = (total_bc / bc_count) if bc_count else 0.0
                MIN_AVG_BOUNDARY_CONFIDENCE = 0.35

                # 只在所有 clip 都没有任何置信度信息时视为缺失（需要回退）；
                # 否则用计算出的 avg_bc 判断是否回退
                if (not any_seg_conf_found) or (avg_bc < MIN_AVG_BOUNDARY_CONFIDENCE):
                    logger.warning(
                        "合并方案输出缺少置信度字段或平均 boundary_confidence=%.3f < %.3f，退回 three_step",
                        avg_bc,
                        MIN_AVG_BOUNDARY_CONFIDENCE,
                    )
                    return self._llm_process_three_step(srt_text)
            except Exception as e:
                logger.warning(f"检测合并方案置信度信息失败: {e}，退回 three_step")
                return self._llm_process_three_step(srt_text)

            # 校验recommend_reason是否所有片段相同（照抄示例的典型表现）
            if len(merged_clips) >= 2:
                reasons = [c.get('recommend_reason', '') for c in merged_clips]
                if len(set(reasons)) == 1:
                    logger.warning(f"所有片段的recommend_reason完全相同: '{reasons[0]}'，可能是照抄了示例")
                elif len(merged_clips) >= 3 and len(set(reasons)) <= 2:
                    logger.warning(f"多数片段的recommend_reason重复，仅{len(set(reasons))}种不同值")

            # 跨clip去重：确保不同clip的segments不重叠（先于gap-filling执行）
            logger.info("开始跨clip去重...")
            merged_clips = _deduplicate_clip_segments(merged_clips)
            logger.info(f"去重后保留 {len(merged_clips)} 个片段")
            # SRT时间戳验证：修正边界 + 填充间隙 + 标记内部静音
            logger.info("开始SRT时间戳验证（修正LLM边界 + 填充间隙 + 剔除静音）...")

            # 解析 VAD/ASR 输入（如果提供）
            vad_silences = None
            asr_conf_map = None
            try:
                if vad_path and vad_path.exists():
                    vad_text = vad_path.read_text(encoding='utf-8')
                    vad_entries = _parse_srt_timeline(vad_text)
                    vad_silences = []
                    for i in range(len(vad_entries)-1):
                        gap = vad_entries[i+1]['start'] - vad_entries[i]['end']
                        if gap > 0:
                            vad_silences.append((vad_entries[i]['end'], vad_entries[i+1]['start']))
                if asr_path and asr_path.exists():
                    # 目前ASR SRT不包含置信度，保留接口以便未来解析
                    asr_conf_map = {}
            except Exception as e:
                logger.warning(f"解析 VAD/ASR 输入失败: {e}")

            merged_clips = postprocess_funclip_topics(merged_clips, srt_text, vad_silences=vad_silences, asr_conf_map=asr_conf_map)
            logger.info(f"SRT验证与时长校验完成")

            # 对短片段应用保留策略：仅保留高置信短片段；对置信处于边界的短片段，调用二次LLM确认
            try:
                merged_clips = _apply_short_segment_policy(self, merged_clips, srt_text)
            except Exception as e:
                logger.warning(f"短片段保留策略执行失败: {e}")

            # 输出详细分组日志：每个话题的segments、字幕内容、归类原因
            _log_topic_details(merged_clips, srt_text)

            logger.info(f"合并方案识别到 {len(merged_clips)} 个片段")
            for clip in merged_clips:
                seg_count = len(clip.get('segments', []))
                removed_count = len(clip.get('removed_sections', []))
                logger.info(
                    f"  片段{clip.get('id')}: {clip.get('title', 'N/A')}, "
                    f"{seg_count}个时间段, "
                    f"评分: {clip.get('final_score', 0)}, "
                    f"剔除{removed_count}段无关内容"
                )

            # 转换格式以匹配下游视频生成
            clips = _merge_srt_segments(None, merged_clips)
            collections = self._generate_collections(clips)

            logger.info(f"合并方案处理完成，共 {len(clips)} 个片段")
            return clips, collections

        except Exception as e:
            logger.warning(f"合并方案LLM处理失败: {e}，使用降级方案")
            return self._fallback_process(srt_text)

    def _prepare_enhanced_text(self, srt_text: str) -> str:
        cleaned_srt = _clean_filler_words(srt_text)
        try:
            srt_entries = SemanticPreprocessor.parse_srt_text(cleaned_srt)
            if not srt_entries:
                return cleaned_srt

            preprocessor = SemanticPreprocessor()
            chunks = preprocessor.generate_semantic_chunks(srt_entries)
            text_corrector = TextCorrector()
            enhanced_chunks = []
            meta_records = []
            for chunk in chunks:
                corrected_text, corrections, confidence = text_corrector.correct_text(chunk['text'])
                enhanced_chunks.append(
                    f"[{chunk['start_str']} --> {chunk['end_str']}]\n{corrected_text}"
                )

                meta_records.append({
                    'start_str': chunk.get('start_str'),
                    'end_str': chunk.get('end_str'),
                    'original_text': chunk.get('text'),
                    'corrected_text': corrected_text,
                    'corrections': corrections,
                    'confidence': confidence
                })

            enhanced_text = "\n\n".join(enhanced_chunks)
            try:
                debug_path = self.metadata_dir / "step1_preprocessed_text.txt"
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(enhanced_text)
                logger.info(f"预处理结果已保存到: {debug_path}")
            except Exception as e:
                logger.warning(f"保存 Step1 预处理文本失败: {e}")

            # 写入纠错元数据文件（可用于回溯和分析）
            try:
                meta_path = self.metadata_dir / "step1_preprocessed_meta.json"
                with open(meta_path, 'w', encoding='utf-8') as mf:
                    json.dump(meta_records, mf, ensure_ascii=False, indent=2)
                logger.info(f"预处理纠错元数据已保存到: {meta_path}")
            except Exception as e:
                logger.warning(f"保存 Step1 预处理元数据失败: {e}")

            # 尝试注入预聚类报告（C2），非必需：失败不影响主流程
            try:
                from backend.core.shared_config import config_manager
                settings = config_manager.settings
                inject_precluster = bool(getattr(settings, 'precluster_step1_inject', True)) and bool(getattr(settings, 'precluster_enabled', True))
            except Exception:
                inject_precluster = True

            if inject_precluster:
                try:
                    from backend.pipeline.topic_precluster import TopicPreCluster
                    pre = TopicPreCluster()
                    report = pre.process(srt_text)
                    cov = 0.0
                    try:
                        cov = float(report.stats.get('coverage_ratio', 0.0))
                    except Exception:
                        cov = 0.0

                    if cov >= 0.5 and getattr(report, 'clusters', None):
                        try:
                            block = self._format_precluster_block(report)
                            enhanced_text = f"{block}\n\n---\n\n{enhanced_text}"
                            # 写入 precluster 报告辅助文件以便回溯
                            try:
                                pc_path = self.metadata_dir / "step1_precluster_report.txt"
                                with open(pc_path, 'w', encoding='utf-8') as pf:
                                    pf.write(report.enhanced_text or '')
                            except Exception:
                                pass
                        except Exception as e:
                            logger.warning(f"格式化预聚类报告失败: {e}")
                except Exception as e:
                    logger.warning(f"预聚类注入失败（不影响主流程）: {e}")

            return enhanced_text
        except Exception as e:
            logger.warning(f"Step1 语义预处理失败，回退到填充词清理后的文本: {e}")
        return cleaned_srt

    def _format_precluster_block(self, report) -> str:
        """格式化预聚类报告文本，供 Step1 prompt 注入使用。"""
        try:
            from backend.pipeline.topic_postprocess import seconds_to_srt_time as to_srt
        except Exception:
            def to_srt(x):
                # fallback: approximate formatter
                h = int(x // 3600)
                m = int((x % 3600) // 60)
                s = x % 60
                return f"{h:02d}:{m:02d}:{s:06.3f}".replace('.', ',')

        lines = ["## 预聚类参考（辅助边界判断，非最终答案）"]
        cov = report.stats.get('coverage_ratio', 0.0) if getattr(report, 'stats', None) else 0.0
        lines.append(f"SRT条目覆盖率: {cov:.0%}")
        lines.append("")
        clusters = getattr(report, 'clusters', []) or []
        for i, cluster in enumerate(clusters[:6]):
            tr = cluster.time_ranges[0] if cluster.time_ranges else None
            if tr:
                start_str = to_srt(tr.start_seconds)
                end_str = to_srt(tr.end_seconds)
            else:
                start_str, end_str = "??", "??"
            keywords = ", ".join(cluster.topic_keywords[:4]) if getattr(cluster, 'topic_keywords', None) else ""
            lines.append(f"簇{i+1}: {start_str}-{end_str}" + (f" 关键词={keywords}" if keywords else ""))
            if getattr(cluster, 'is_multi_segment', False):
                lines.append(f"  [多段] 在{len(cluster.time_ranges)}个时间段出现")
            lines.append("")

        lines.extend([
            "",
            "注意：预聚类基于n-gram相似度，可能过度合并。请结合语义判断。",
            "若覆盖率 < 90%，请确保输出话题覆盖主要语段。",
        ])
        return "\n".join(lines)

    def _extract_srt_for_topic(self, segments: List[Dict], srt_entries: List[Dict]) -> str:
        if not segments or not srt_entries:
            return ""
        seg_start = _srt_time_to_seconds(segments[0]['start'])
        seg_end = _srt_time_to_seconds(segments[-1]['end'])
        relevant = [e for e in srt_entries if e['end'] >= seg_start and e['start'] <= seg_end]
        lines = []
        for i, entry in enumerate(relevant):
            lines.append(f"{entry['start_str']} --> {entry['end_str']}")
            lines.append(entry['text'])
            if i < len(relevant) - 1:
                lines.append("")
        return '\n'.join(lines)

    def _prepare_step2_input(self, topics: List[Dict], srt_entries: List[Dict]) -> List[Dict]:
        topics_with_srt = []
        use_full_context = self._is_long_context_provider()
        for topic in topics:
            segments = topic.get('segments', [])
            if not segments:
                continue
            srt_text = self._extract_srt_for_topic(segments, srt_entries)
            if not use_full_context:
                srt_text = _smart_truncate_srt_for_scoring(srt_text, segments)

            total_duration = sum(
                _srt_time_to_seconds(seg['end']) - _srt_time_to_seconds(seg['start'])
                for seg in segments
            )

            topics_with_srt.append({
                'id': topic.get('id', ''),
                'outline': topic.get('outline', ''),
                'topic_type': topic.get('topic_type', 'daily'),
                'total_duration_seconds': round(total_duration, 1),
                'srt_text': srt_text
            })

        return topics_with_srt

    def _is_long_context_provider(self) -> bool:
        """当前provider是否支持长上下文（≥100K tokens则无需截断）"""
        try:
            return self.llm_manager.supports_long_context(100_000)
        except Exception:
            return False

    def _is_local_provider(self) -> bool:
        """当前是否为本地模型提供商（Ollama / LM Studio），需要上下文限制"""
        try:
            provider_type = self.llm_manager.settings.get("llm_provider", "")
            return provider_type in ("ollama", "lmstudio")
        except Exception:
            return False

    def _truncate_srt_for_local_model(self, srt_text: str, max_chars: int = 8000) -> str:
        """本地模型上下文有限，截断SRT文本到安全长度"""
        if not self._is_local_provider() or len(srt_text) <= max_chars:
            return srt_text
        lines = srt_text.split('\n')
        head_lines = 60
        tail_lines = 40
        if len(lines) <= head_lines + tail_lines:
            return srt_text
        result = '\n'.join(lines[:head_lines])
        result += '\n...（中间省略）...\n'
        result += '\n'.join(lines[-tail_lines:])
        logger.info(
            f"本地模型SRT已截断: {len(srt_text)} -> {len(result)} 字符 "
            f"(保留前后共{head_lines + tail_lines}行)"
        )
        return result

    def _prepare_step3_input(self, topics: List[Dict], srt_entries: List[Dict]) -> List[Dict]:
        topics_data = []
        for topic in topics:
            segments = topic.get('segments', [])
            srt_text = ""
            if segments and srt_entries:
                srt_text = self._extract_srt_for_topic(segments, srt_entries)
                if len(srt_text) > 2000:
                    srt_lines = srt_text.split('\n')
                    head_lines = srt_lines[:80]
                    tail_lines = srt_lines[-30:]
                    srt_text = (
                        '\n'.join(head_lines)
                        + '\n...(中间省略)...\n'
                        + '\n'.join(tail_lines)
                    )
                    logger.info(
                        f"话题{topic.get('id', '')} Step3 SRT过长({len(srt_lines)}条)，"
                        f"截取首{len(head_lines)}+尾{len(tail_lines)}条"
                    )

            topics_data.append({
                'id': topic.get('id', ''),
                'outline': topic.get('outline', ''),
                'topic_type': topic.get('topic_type', 'daily'),
                'recommend_reason': topic.get('recommend_reason', ''),
                'srt_text': srt_text
            })
        return topics_data

    def _call_step1_boundary(self, srt_text: str) -> Optional[List[Dict]]:
        try:
            response = self.llm_manager.current_provider.call(
                FUNCLIP_STEP1_BOUNDARY_PROMPT,
                "这是待分析的直播srt字幕：\n" + srt_text,
                max_tokens=4096,
                temperature=0.1
            )

            if not response or not response.content:
                return None

            debug_path = self.metadata_dir / "step1_raw_response.txt"
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(response.content)

            return self._parse_step1_response(response.content)

        except Exception as e:
            logger.error(f"Step 1 调用异常: {e}")
            return None

    def _parse_step1_response(self, response_text: str) -> Optional[List[Dict]]:
        def _try_parse(json_str):
            try:
                data = json.loads(re.sub(r',\s*([\]}])', r'\1', json_str))
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and 'topics' in data:
                    return data['topics']
            except json.JSONDecodeError:
                pass
            return None

        result = _try_parse(response_text)
        if result is not None:
            return result

        for block in re.findall(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text):
            result = _try_parse(block)
            if result is not None:
                return result

        match = re.search(r'\[[\s\S]*"segments"[\s\S]*\]', response_text)
        if match:
            result = _try_parse(match.group())
            if result is not None:
                return result

        logger.warning(f"无法解析 Step 1 响应: {response_text[:300]}")
        return None

    def _do_step1_with_retry(self, srt_text: str, srt_entries: List[Dict],
                              checkpoint: 'PipelineCheckpoint') -> Optional[List[Dict]]:
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                enhanced_text = self._prepare_enhanced_text(srt_text)
                step1_topics = self._call_step1_boundary(enhanced_text)
                if step1_topics is not None:
                    return step1_topics
                logger.warning(f"Step 1 第{attempt+1}次调用解析失败")
                checkpoint.mark_step_failed('step1_boundary', 'JSON解析失败')
            except Exception as e:
                logger.error(f"Step 1 第{attempt+1}次调用异常: {e}")
                checkpoint.mark_step_failed('step1_boundary', str(e))
            if attempt < max_retries:
                logger.info(f"Step 1 重试 ({attempt+1}/{max_retries})...")
        return None

    def _call_step2_batch_score(self, topics_with_srt: List[Dict]) -> List[Dict]:
        if not topics_with_srt:
            return []

        if _should_batch_step2(topics_with_srt):
            logger.info(
                f"Step 2 输入 token 超阈值，启动分批评分 "
                f"(共 {len(topics_with_srt)} 个话题)"
            )
            batch1, batch2 = _split_topics_by_priority(topics_with_srt)
            logger.info(f"  批次1(高优先): {len(batch1)} 个话题")
            logger.info(f"  批次2(低优先): {len(batch2)} 个话题")
            all_scores = []
            if batch1:
                scores1 = self._do_step2_call(batch1, batch_label="批次1")
                all_scores.extend(scores1)
            if batch2:
                scores2 = self._do_step2_call(batch2, batch_label="批次2")
                all_scores.extend(scores2)
            logger.info(f"分批评分完成，共 {len(all_scores)} 个分数")
            return all_scores
        else:
            return self._do_step2_call(topics_with_srt, batch_label="单批")

    def _do_step2_call(self, topics_with_srt: List[Dict], batch_label: str = "") -> List[Dict]:
        try:
            input_json = json.dumps(topics_with_srt, ensure_ascii=False, indent=2)
            logger.info(f"Step 2 [{batch_label}] LLM调用: {len(topics_with_srt)} 个话题, "
                        f"输入长度 {len(input_json)} 字符, 预估 {_estimate_tokens(input_json)} tokens")

            response = self.llm_manager.current_provider.call(
                FUNCLIP_STEP2_BATCH_SCORE_PROMPT,
                "以下是待评分的话题数据：\n" + input_json,
                max_tokens=2048,
                temperature=0.2
            )

            if not response or not response.content:
                logger.warning(f"Step 2 [{batch_label}] 返回空响应")
                return []

            result = self._parse_step2_response(response.content)
            logger.info(f"Step 2 [{batch_label}] 解析成功: {len(result)} 个分数")
            return result

        except Exception as e:
            logger.error(f"Step 2 [{batch_label}] 调用失败: {e}")
            return []

    def _parse_step2_response(self, response_text: str) -> List[Dict]:
        def _try_parse(json_str):
            try:
                data = json.loads(re.sub(r',\s*([\]}])', r'\1', json_str))
                if isinstance(data, dict) and 'scores' in data:
                    return data['scores']
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
            return None

        result = _try_parse(response_text)
        if result is not None:
            return result

        for block in re.findall(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text):
            result = _try_parse(block)
            if result is not None:
                return result

        for pattern in [r'\{[\s\S]*"scores"[\s\S]*\}', r'\[[\s\S]*"final_score"[\s\S]*\]']:
            match = re.search(pattern, response_text)
            if match:
                result = _try_parse(match.group())
                if result is not None:
                    return result

        logger.warning(f"无法解析 Step 2 响应: {response_text[:300]}")
        return []

    def _call_step3_batch_title(self, topics_data: List[Dict]) -> List[Dict]:
        try:
            input_json = json.dumps(topics_data, ensure_ascii=False, indent=2)
            response = self.llm_manager.current_provider.call(
                FUNCLIP_STEP3_BATCH_TITLE_PROMPT,
                "以下是待生成标题的话题列表：\n" + input_json,
                max_tokens=2048,
                temperature=0.3
            )

            if not response or not response.content:
                return []

            return self._parse_step3_response(response.content)

        except Exception as e:
            logger.error(f"Step 3 调用异常: {e}")
            return []

    def _parse_step3_response(self, response_text: str) -> List[Dict]:
        def _try_parse(json_str):
            try:
                data = json.loads(re.sub(r',\s*([\]}])', r'\1', json_str))
                if isinstance(data, dict) and 'titles' in data:
                    return data['titles']
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
            return None

        result = _try_parse(response_text)
        if result is not None:
            return result

        for block in re.findall(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text):
            result = _try_parse(block)
            if result is not None:
                return result

        match = re.search(r'\{[\s\S]*"titles"[\s\S]*\}', response_text)
        if match:
            result = _try_parse(match.group())
            if result is not None:
                return result

        logger.warning(f"无法解析 Step 3 响应: {response_text[:300]}")
        return []

    def _step1_5_gapfill(self, step1_topics: List[Dict], srt_entries: List[Dict], srt_text: str) -> List[Dict]:
        """Step 1.5 Gap Fill：覆盖率检查，调用LLM补洞"""
        cfg = _get_step1_5_config()
        if not cfg['enabled']:
            return step1_topics

        coverage_ratio, orphans, gaps = _compute_topic_coverage_simple(step1_topics, srt_entries)
        logger.info(f"Step 1.5: 当前覆盖率 {coverage_ratio:.2%}, 未覆盖条目 {len(orphans)}, 空白区间 {len(gaps)}")

        if coverage_ratio >= cfg['coverage_threshold'] or not gaps:
            logger.info(f"Step 1.5: 覆盖率达标({coverage_ratio:.2%} >= {cfg['coverage_threshold']:.2%})，跳过补洞")
            return step1_topics

        logger.info(f"Step 1.5: 覆盖率不足({coverage_ratio:.2%} < {cfg['coverage_threshold']:.2%})，启动LLM补洞")

        for gap in gaps:
            gap_duration = gap['end'] - gap['start']
            if gap_duration < 10.0:
                logger.debug(f"Step 1.5: 空白区间过短({gap_duration:.1f}s < 10s)，跳过")
                continue

            gap_srt = _extract_gap_srt(gap['start'], gap['end'], gap['entries'])
            if not gap_srt.strip():
                continue

            existing_topics_text = []
            for t in step1_topics:
                outline = t.get('outline', '').strip()
                if outline:
                    existing_topics_text.append(f"- {outline}")
            existing_text = '\n'.join(existing_topics_text)

            gap_info = (
                f"\n## 当前待处理的空白区间\n"
                f"空白区间: {gap['start']:.2f}s - {gap['end']:.2f}s\n"
                f"空白区间SRT字幕:\n{gap_srt}\n\n"
                f"已有话题概览:\n{existing_text}\n"
            )
            prompt = FUNCLIP_STEP1_5_GAPFILL_PROMPT + gap_info

            try:
                response = self.llm_manager.call(prompt, temperature=0.3)
                parsed = None
                for block in re.findall(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response):
                    try:
                        parsed = json.loads(block.strip())
                        break
                    except:
                        continue
                if parsed is None:
                    match = re.search(r'\[[\s\S]*\]', response)
                    if match:
                        try:
                            parsed = json.loads(match.group().strip())
                        except:
                            pass

                if parsed and isinstance(parsed, list):
                    step1_topics = _merge_new_topics(step1_topics, parsed, srt_entries)
                    logger.info(f"Step 1.5: 空白区间合并后话题数: {len(step1_topics)}")
                else:
                    logger.debug(f"Step 1.5: LLM返回无法解析，跳过: {response[:200]}")

            except Exception as e:
                logger.warning(f"Step 1.5: LLM调用失败: {e}，跳过此区间")
                continue

        return step1_topics

    def _llm_process_three_step(self, srt_text: str):
        """三步流水线处理：边界识别 → 批量评分 → 批量标题（带检查点与降级）"""
        try:
            checkpoint = PipelineCheckpoint(self.metadata_dir)

            # ==========================================
            # Step 1: 边界识别（带检查点 + 空输出降级）
            # ==========================================
            step1_topics = checkpoint.get_step_output('step1_boundary')

            if step1_topics is None:
                logger.info("Step 1 检查点未命中，开始执行...")
                srt_entries = _parse_srt_timeline(srt_text)
                step1_topics = self._do_step1_with_retry(srt_text, srt_entries, checkpoint)

                if step1_topics is None:
                    logger.warning("Step 1 重试耗尽，降级到 _fallback_process")
                    checkpoint.clear()
                    return self._fallback_process(srt_text)

            if not step1_topics:
                logger.warning("Step 1 输出为空数组（LLM判断无独立话题），降级")
                checkpoint.clear()
                srt_entries = _parse_srt_timeline(srt_text)
                if srt_entries:
                    step1_topics = [{
                        'id': '1',
                        'outline': '完整内容',
                        'segments': [{
                            'start': srt_entries[0]['start_str'],
                            'end': srt_entries[-1]['end_str']
                        }],
                        'topic_type': 'daily'
                    }]
                    logger.info("已构造默认单话题")
                else:
                    return self._fallback_process(srt_text)

            step1_topics = _validate_step1_segments(step1_topics, srt_text)
            checkpoint.save_step_output('step1_boundary', step1_topics,
                                         {'topic_count': len(step1_topics)})

            srt_entries = _parse_srt_timeline(srt_text)

            # ==========================================
            # Step 1.5: Gap Fill Pass（B1：LLM补洞）
            # ==========================================
            step1_topics = self._step1_5_gapfill(step1_topics, srt_entries, srt_text)

            # ==========================================
            # Step 2: 批量评分（带检查点 + boundary_suggestion）
            # ==========================================
            step2_scores = checkpoint.get_step_output('step2_scores')
            if step2_scores is None:
                logger.info("Step 2 检查点未命中，开始执行...")
                step2_input = self._prepare_step2_input(step1_topics, srt_entries)
                step2_scores = self._call_step2_batch_score(step2_input)

                if step2_scores:
                    step1_topics = _apply_boundary_suggestions(
                        step1_topics, step2_scores, srt_entries
                    )
                    checkpoint.save_step_output('step2_scores', step2_scores,
                                                 {'score_count': len(step2_scores)})
                else:
                    checkpoint.mark_step_failed('step2_scores', 'Step 2 返回空')
                    logger.warning("Step 2 评分失败，将使用默认评分继续")

            step1_topics = _merge_scores_to_topics(step1_topics, step2_scores or [])

            # ==========================================
            # Step 3: 批量标题（带检查点）
            # ==========================================
            step3_titles = checkpoint.get_step_output('step3_titles')
            if step3_titles is None:
                logger.info("Step 3 检查点未命中，开始执行...")
                step3_input = self._prepare_step3_input(step1_topics, srt_entries)
                step3_titles = self._call_step3_batch_title(step3_input)

                if step3_titles:
                    checkpoint.save_step_output('step3_titles', step3_titles,
                                                 {'title_count': len(step3_titles)})

            step1_topics = _merge_titles_to_topics(step1_topics, step3_titles or [])

            # ==========================================
            # 最终后处理：智能选择 → 按时间升序（A4）
            # ==========================================
            step1_topics = _select_final_topics(step1_topics)

            clips = _convert_topics_to_clips(step1_topics)
            collections = self._generate_collections(clips)

            # ---- C3: 计算完整性指标并写入 metadata （非阻塞） ----
            try:
                from backend.pipeline.topic_completeness import compute_all_completeness
                try:
                    from backend.core.shared_config import config_manager
                    completeness_enabled = getattr(config_manager.settings, 'completeness_enabled', True)
                except Exception:
                    completeness_enabled = True

                if completeness_enabled:
                    try:
                        srt_entries = _parse_srt_timeline(srt_text)
                        clips = compute_all_completeness(clips, srt_entries)
                        # write summary metadata
                        try:
                            out_path = self.metadata_dir / 'topic_completeness.json'
                            with open(out_path, 'w', encoding='utf-8') as f:
                                json.dump({'clips': [
                                    {'id': c.get('id'), 'completeness': c.get('completeness')}
                                    for c in clips
                                ]}, f, ensure_ascii=False, indent=2)
                        except Exception as e:
                            logger.warning(f"写入完整性 metadata 失败: {e}")
                    except Exception as e:
                        logger.warning(f"计算完整性指标失败: {e}")
            except Exception:
                # 如果模块不可用则跳过，不影响主流程
                pass

            checkpoint.clear()

            logger.info(f"三步流水线完成: {len(clips)} 个片段")
            return clips, collections

        except Exception as e:
            logger.warning(f"三步流水线处理失败: {e}，使用降级方案")
            return self._fallback_process(srt_text)

    def _parse_merged_response(self, response_text: str) -> List[Dict]:
        """解析合并方案LLM返回的数据"""
        merged_clips = []

        def _clean_trailing_commas(json_str: str) -> str:
            """移除JSON中数组/对象末尾的逗号（LLM常见错误）"""
            return re.sub(r',\s*([\]}])', r'\1', json_str)

        def _filter_valid_segments(segments: List[Dict]) -> List[Dict]:
            """过滤掉零时长和重复的segments，保留有效段"""
            if not segments:
                return []
            seen = set()
            valid = []
            for seg in segments:
                start = seg.get('start', '')
                end = seg.get('end', '')
                if start and end and start != end:
                    key = (start, end)
                    if key not in seen:
                        seen.add(key)
                        valid.append(seg)
            return valid

        def _try_parse(json_str: str) -> Optional[List[Dict]]:
            """尝试解析JSON，包含尾部逗号修复和零时长segment过滤"""
            if not json_str:
                return None
            try:
                data = json.loads(_clean_trailing_commas(json_str))
                if isinstance(data, list):
                    result = []
                    for i, item in enumerate(data):
                        if 'segments' in item and isinstance(item['segments'], list):
                            valid_segs = _filter_valid_segments(item['segments'])
                            if valid_segs:
                                item['segments'] = valid_segs
                                item['id'] = str(item.get('id', i + 1))
                                result.append(item)
                    if result:
                        return result
            except json.JSONDecodeError:
                pass
            return None

        def _try_fix_and_parse(extracted: str) -> Optional[List[Dict]]:
            """尝试修复截断的JSON并解析"""
            # 先尝试直接解析
            result = _try_parse(extracted)
            if result:
                return result
            # 去掉代码块标记
            cleaned = re.sub(r'```(?:json)?\s*\n?', '', extracted).strip()
            if cleaned != extracted:
                result = _try_parse(cleaned)
                if result:
                    return result
                extracted = cleaned
            # 如果是截断的JSON，找到最后一个完整的对象/数组，截断并补齐括号
            for trim_char in ['}', ']']:
                last_complete = extracted.rfind(trim_char)
                if last_complete >= 0:
                    trimmed = extracted[:last_complete + 1]
                    if extracted.count('[') > trimmed.count(']'):
                        open_count = extracted.count('[') - trimmed.count(']')
                        for _ in range(open_count):
                            trimmed += ']'
                    if extracted.count('{') > trimmed.count('}'):
                        open_count = extracted.count('{') - trimmed.count('}')
                        for _ in range(open_count):
                            trimmed += '}'
                    result = _try_parse(trimmed)
                    if result:
                        logger.info(f"通过截断并补齐括号修复截断JSON成功，共 {len(result)} 个片段")
                        return result
            return None

        # 1. 直接解析（纯JSON，无多余文字）
        result = _try_fix_and_parse(response_text)
        if result:
            logger.info(f"JSON解析成功，共 {len(result)} 个片段")
            return result

        # 2. 从代码块中提取（```json ... ```）
        for block in re.findall(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text):
            start = block.find('[')
            end = block.rfind(']')
            extract = block[start:] if start >= 0 else block
            if end > start:
                extract = block[start:end + 1]
            result = _try_fix_and_parse(extract)
            if result:
                logger.info(f"从代码块解析JSON成功，共 {len(result)} 个片段")
                return result

        # 3. 从文本中直接查找JSON数组（忽略前后文字）
        start_idx = response_text.find('[')
        if start_idx >= 0:
            extract = response_text[start_idx:]
            result = _try_fix_and_parse(extract)
            if result:
                logger.info(f"从文本提取JSON成功，共 {len(result)} 个片段")
                return result

        # 4. 兜底：逐行找可能的JSON片段
        lines = response_text.split('\n')
        json_candidates = []
        in_block = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('```'):
                in_block = not in_block
                continue
            if in_block or stripped.startswith('{') or stripped.startswith('[') or stripped.startswith('"'):
                json_candidates.append(line)
        if json_candidates:
            candidate_text = '\n'.join(json_candidates)
            start_idx = candidate_text.find('[')
            if start_idx >= 0:
                extract = candidate_text[start_idx:]
                result = _try_fix_and_parse(extract)
                if result:
                    logger.info(f"从逐行提取解析JSON成功，共 {len(result)} 个片段")
                    return result

        logger.warning(f"无法解析合并方案响应，原始响应长度: {len(response_text)}")
        logger.warning(f"响应内容(前1000): {response_text[:1000]}")
        logger.warning(f"响应内容(最后200): {response_text[-200:]}")
        has_code_block = '```' in response_text
        has_segments = '"segments"' in response_text
        logger.warning(f"解析诊断: 代码块={has_code_block}, segments字段={has_segments}")
        return merged_clips
    
    def _parse_clips_only(self, response: str) -> List[Dict]:
        """解析第一阶段LLM返回的片段数据（不含标题）"""
        clips = []

        def _clean_trailing_commas(json_str: str) -> str:
            return re.sub(r',\s*([\]}])', r'\1', json_str)

        # 直接解析JSON
        try:
            data = json.loads(_clean_trailing_commas(response))
            if isinstance(data, list):
                clips = data
                for i, clip in enumerate(clips):
                    if 'id' not in clip or not clip['id']:
                        clip['id'] = str(i + 1)
                logger.info(f"JSON解析成功，共 {len(clips)} 个片段")
                return clips
        except json.JSONDecodeError:
            pass

        # 从代码块中提取
        for block in re.findall(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response):
            start = block.find('[')
            end = block.rfind(']')
            if start >= 0 and end > start:
                try:
                    data = json.loads(_clean_trailing_commas(block[start:end + 1]))
                    if isinstance(data, list):
                        clips = data
                        for i, clip in enumerate(clips):
                            if 'id' not in clip or not clip['id']:
                                clip['id'] = str(i + 1)
                        logger.info(f"从代码块解析JSON成功，共 {len(clips)} 个片段")
                        return clips
                except json.JSONDecodeError:
                    pass

        # 从文本中提取
        start_idx = response.find('[')
        end_idx = response.rfind(']')
        if start_idx >= 0 and end_idx > start_idx:
            try:
                data = json.loads(_clean_trailing_commas(response[start_idx:end_idx + 1]))
                if isinstance(data, list):
                    clips = data
                    for i, clip in enumerate(clips):
                        if 'id' not in clip or not clip['id']:
                            clip['id'] = str(i + 1)
                    logger.info(f"从文本提取JSON成功，共 {len(clips)} 个片段")
                    return clips
            except json.JSONDecodeError:
                pass

        clips = self._extract_clips_from_text(response)
        return clips
    
    def _extract_srt_segment(self, full_srt: str, start_time: str, end_time: str) -> str:
        """从完整SRT中提取指定时间范围内的字幕文本"""
        lines = []
        in_range = False
        
        for line in full_srt.split('\n'):
            # 匹配时间行: 00:00:00,000 --> 00:00:05,000
            time_match = re.match(
                r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})',
                line
            )
            if time_match:
                seg_start = time_match.group(1)
                seg_end = time_match.group(2)
                # 检查是否与目标时间范围有重叠
                if (self._time_to_seconds(seg_start) <= self._time_to_seconds(end_time) and
                    self._time_to_seconds(seg_end) >= self._time_to_seconds(start_time)):
                    in_range = True
                else:
                    in_range = False
            
            if in_range:
                lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def _time_to_seconds(time_str: str) -> float:
        """将SRT时间格式转换为秒数"""
        try:
            time_str = time_str.replace(',', '.')
            parts = time_str.split(':')
            h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
            return h * 3600 + m * 60 + s
        except Exception:
            return 0
    
    def _extract_clips_from_text(self, text: str):
        """从LLM响应中提取片段"""
        clips = []
        
        # 清理文本
        text = text.strip()
        
        # 尝试多种正则表达式模式
        patterns = [
            # 模式1: JSON格式中的outline字段
            r'\{\s*"outline"\s*:\s*"([^"]+)"[^}]*"start"\s*:\s*"([^"]+)"[^}]*"end"\s*:\s*"([^"]+)"[^}]*\}',
            # 模式2: Markdown格式
            r'\d+\.\s*\[(\d{2}:\d{2}:\d{2},?\d{0,3})\s*-\s*(\d{2}:\d{2}:\d{2},?\d{0,3})\]\s*([^\n]+)',
            # 模式3: 纯时间戳格式
            r'\[(\d{2}:\d{2}:\d{2},?\d{0,3})\s*-\s*(\d{2}:\d{2}:\d{2},?\d{0,3})\]\s*([^\n\[\]]+)',
        ]
        
        for i, pattern in enumerate(patterns):
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                logger.info(f"使用模式{i+1}成功匹配到 {len(matches)} 个片段")
                for j, match in enumerate(matches[:6]):  # 最多6个片段
                    if len(match) >= 3:
                        start_time, end_time, content = match[0], match[1], match[2]
                        clip = {
                            'id': str(j + 1),
                            'outline': content.strip(),
                            'start': start_time,
                            'end': end_time,
                            'content': [content.strip()],
                            'final_score': 0.7 + (j * 0.05),
                            'recommend_reason': '精彩片段',
                            'generated_title': f'精彩片段{str(j+1)}'
                        }
                        clips.append(clip)
                break
        
        return clips
    
    def _generate_collections(self, clips):
        """基于clips生成简单的合集"""
        if not clips:
            return []
        
        collections = [{
            'id': '1',
            'collection_title': '全部内容',
            'collection_summary': f'包含{len(clips)}个片段',
            'clip_ids': [clip['id'] for clip in clips]
        }]
                
        return collections
    
    def _fallback_process(self, srt_text: str):
        """降级方案，无LLM时使用简单处理"""
        logger.info("使用降级方案：按时间分段")
        clips = []
        
        # 解析SRT获取实际时长
        srt_entries = self._parse_srt_simple(srt_text)
        if srt_entries:
            # 根据实际内容分段
            total_duration = srt_entries[-1].get('end_seconds', 1200) if srt_entries else 1200
            interval = min(total_duration / 4, 300)  # 最多5分钟一段
        else:
            interval = 300
        
        time_intervals = []
        current_time = 0
        while current_time < (srt_entries[-1].get('end_seconds', 1200) if srt_entries else 1200):
            end_time = min(current_time + interval, 
                         (srt_entries[-1].get('end_seconds', 1200) if srt_entries else 1200))
            time_intervals.append((
                self._seconds_to_srt_time(current_time),
                self._seconds_to_srt_time(end_time)
            ))
            current_time = end_time
            if len(time_intervals) >= 4:
                break
        
        for i, (start, end) in enumerate(time_intervals):
            clips.append({
                'id': str(i + 1),
                'outline': f'片段{i+1}',
                'start': start,
                'end': end,
                'final_score': 0.5,
                'recommend_reason': '自动分段',
                'generated_title': f'精彩片段{i+1}'
            })
        
        collections = [{
            'id': '1',
            'collection_title': '自动合集',
            'collection_summary': '全部内容',
            'clip_ids': [clip['id'] for clip in clips]
        }]
            
        return clips, collections
    
    def _parse_srt_simple(self, srt_text: str) -> List[Dict]:
        """解析SRT文本获取时间信息"""
        entries = []
        pattern = r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})'
        matches = re.findall(pattern, srt_text)
        
        for match in matches:
            start_seconds = int(match[0])*3600 + int(match[1])*60 + int(match[2]) + int(match[3])/1000
            end_seconds = int(match[4])*3600 + int(match[5])*60 + int(match[6]) + int(match[7])/1000
            entries.append({
                'start_seconds': start_seconds,
                'end_seconds': end_seconds
            })
        
        return entries
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """将秒数转换为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def _save_results(self, clips: List[Dict], collections: List[Dict]):
        """保存处理结果"""
        try:
            clips_path = self.metadata_dir / "funclip_clips.json"
            with open(clips_path, 'w', encoding='utf-8') as f:
                json.dump(clips, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存 {len(clips)} 个切片到 {clips_path}")
            
            collections_path = self.metadata_dir / "funclip_collections.json"
            with open(collections_path, 'w', encoding='utf-8') as f:
                json.dump(collections, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存 {len(collections)} 个合集到 {collections_path}")
        except Exception as e:
            logger.warning(f"保存结果失败: {e}")


def _extract_multi_segment_clip(input_video: Path, output_path: Path,
                                 segments: List[Dict], temp_dir: Path) -> bool:
    """
    单次FFmpeg调用，使用 filter_complex concat filter 实现多段精确拼接

    Args:
        input_video: 输入视频路径
        output_path: 输出视频路径
        segments: 时间段列表，每个元素含 start 和 end
        temp_dir: 临时文件目录（保留参数仅用于兼容，不再使用）

    Returns:
        是否成功
    """
    import subprocess

    filter_parts = []
    label_idx = 0
    for seg in segments:
        start = seg.get('start', '00:00:00,000')
        end = seg.get('end', '00:00:00,000')
        start_sec = _srt_time_to_seconds(start)
        end_sec = _srt_time_to_seconds(end)
        if end_sec - start_sec <= 0.5:
            continue
        filter_parts.append(
            f"[0:v]trim=start={start_sec}:end={end_sec},setpts=PTS-STARTPTS[v{label_idx}];"
            f"[0:a]atrim=start={start_sec}:end={end_sec},asetpts=PTS-STARTPTS[a{label_idx}];"
        )
        label_idx += 1

    if label_idx == 0:
        logger.error("多段提取：无有效段")
        return False

    concat_inputs = ''.join(f'[v{i}][a{i}]' for i in range(label_idx))
    filter_parts.append(f"{concat_inputs}concat=n={label_idx}:v=1:a=1[outv][outa]")
    filter_complex = ''.join(filter_parts)

    cmd = [
        'ffmpeg',
        '-i', str(input_video),
        '-filter_complex', filter_complex,
        '-map', '[outv]',
        '-map', '[outa]',
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-y',
        str(output_path)
    ]

    try:
        # 视频编码耗时无法预估，不使用固定 timeout（避免 subprocess 因
        # timeout 被错误计算为负数而立即超时）。
        # timeout=None 表示无限等待，ffmpeg 完成后自然返回。
        result = subprocess.run(cmd, capture_output=True,
                                encoding='utf-8', errors='ignore', timeout=None)
        if result.returncode == 0:
            logger.info(f"多段拼接成功: {label_idx}段 -> {output_path}")
            return True
        else:
            logger.error(f"多段拼接失败: {result.stderr}")
            return False
    except subprocess.TimeoutExpired as e:
        logger.error(f"多段提取超时: {e} (timeout={e.timeout})")
        return False
    except Exception as e:
        logger.error(f"多段提取异常: {e}")
        return False


def run_funclip_pipeline(srt_path: Path,
                         video_path: Path,
                         metadata_dir: Path,
                         clips_output_dir: Path,
                         collections_output_dir: Path,
                         processing_mode: str = "two_stage"):
    """运行FunClip风格的完整流水线

    Args:
        srt_path: SRT字幕文件路径
        video_path: 输入视频路径
        metadata_dir: 元数据目录
        clips_output_dir: 切片输出目录
        collections_output_dir: 合集输出目录
        processing_mode: 处理模式
            - "two_stage": 两阶段方案（默认）
            - "merged": 合并方案（单次LLM调用）
    """
    processor = FunClipStyleProcessor(metadata_dir)
    processing_mode = resolve_funclip_sub_mode(srt_path, processing_mode)
    clips, collections = processor.process(srt_path, processing_mode)

    logger.info("=" * 60)
    logger.info(f"处理完成，共生成 {len(clips)} 个切片 [模式: {processing_mode}]")
    for i, clip in enumerate(clips):
        has_multi = " [多段]" if clip.get('_segments') and len(clip['_segments']) > 1 else ""
        logger.info(f"  切片{clip.get('id', i+1)}: {clip.get('generated_title', 'N/A')}{has_multi}")
        logger.info(f"    时间: {clip.get('start_time', 'N/A')} -> {clip.get('end_time', 'N/A')}")
        logger.info(f"    评分: {clip.get('final_score', 0)}")
    logger.info("=" * 60)

    # 复用 FunASR 的 fsmn-vad 结果检测静音（无需独立运行 Silero VAD）
    MIN_SILENCE_DURATION = 0.5
    vad_silence_all = []
    try:
        if srt_path and srt_path.exists():
            vad_path = Path(str(srt_path).replace('.srt', '.vad.json'))
            if vad_path.exists():
                import json
                speech_segs = json.load(open(vad_path, encoding='utf-8'))
                logger.info(f"复用 FunASR VAD 数据: {len(speech_segs)} 段语音")
                duration = speech_segs[-1]['end'] if speech_segs else 0.0
                prev_end = 0.0
                for seg in speech_segs:
                    if seg['start'] - prev_end >= MIN_SILENCE_DURATION:
                        vad_silence_all.append((prev_end, seg['start']))
                    prev_end = seg['end']
                if duration - prev_end >= MIN_SILENCE_DURATION:
                    vad_silence_all.append((prev_end, duration))
                logger.info(f"从 VAD 数据推导出 {len(vad_silence_all)} 段静音(>={MIN_SILENCE_DURATION}s)")

            # VAD 数据无效（0 或 1 段语音）时，回退到 FFmpeg silencedetect
            if not vad_silence_all:
                from backend.utils.silence_processor import SilenceProcessor
                # 按优先级查找音频源：ASR 生成的音频 → 硬编码名 → 原视频文件
                audio_candidates = [
                    srt_path.parent / f"{video_path.stem}_audio.wav",  # ASR 实际生成的文件名
                    srt_path.parent / "input_audio.wav",               # 部分旧逻辑硬编码
                ]
                audio_path = None
                for candidate in audio_candidates:
                    if candidate.exists():
                        audio_path = candidate
                        break
                # 所有 wav 都不存在时，直接用视频文件（FFmpeg 会自动读取音频流）
                if audio_path is None:
                    audio_path = video_path
                    logger.info(f"未找到预先提取的音频，直接使用视频源: {audio_path}")

                logger.info(f"VAD 数据无效，回退到 FFmpeg silencedetect: {audio_path}")
                # 使用 -30dB 阈值，最小静音长度 0.5 秒
                raw_silences = SilenceProcessor.process_silence(
                    audio_path, threshold=-35.0, min_silence_duration=MIN_SILENCE_DURATION
                )
                if raw_silences:
                    vad_silence_all = raw_silences
                    logger.info(f"FFmpeg silencedetect 检测到 {len(vad_silence_all)} 段静音")

            if vad_silence_all:
                vad_count = 0
                for clip in clips:
                    segments = clip.get('_segments', [])
                    if not segments:
                        # fallback: 用 start_time/end_time 构造单段确保 VAD 静音可被追加
                        s = clip.get('start_time') or clip.get('start')
                        e = clip.get('end_time') or clip.get('end')
                        if s and e:
                            segments = [{'start': s, 'end': e}]
                        else:
                            continue
                    clip_vad = _filter_vad_silence_by_segments(
                        vad_silence_all, segments
                    )
                    if clip_vad:
                        existing = clip.setdefault('_removed_sections', [])
                        existing.extend(clip_vad)
                        vad_count += len(clip_vad)
                logger.info(f"VAD静音检测完成: 共添加 {vad_count} 段音频级静音到各片段")
        else:
            logger.info("SRT 文件不存在，跳过静音检测")
    except Exception as e:
        logger.warning(f"静音检测跳过: {e}")

    # 转换格式以匹配 video_generator 的期望
    clips_for_video = []
    for clip in clips:
        # 兼容两种字段名：merged模式用start_time/end_time，two_stage模式用start/end
        start_time = clip.get('start_time') or clip.get('start') or '00:00:00,000'
        end_time = clip.get('end_time') or clip.get('end') or '00:05:00,000'
        video_clip = {
            'id': clip.get('id', ''),
            'outline': clip.get('outline', ''),
            'generated_title': clip.get('generated_title', f"片段_{clip.get('id', '')}"),
            'start_time': start_time,
            'end_time': end_time,
            'final_score': clip.get('final_score', 0.5),
            'recommend_reason': clip.get('recommend_reason', ''),
            'content': clip.get('content', [])
        }
        # 合并模式：使用LLM返回的多段segments
        if clip.get('_segments'):
            video_clip['_segments'] = clip['_segments']
        # 两阶段模式：用start_time/end_time构造单段segments
        elif start_time != '00:00:00,000' or end_time != '00:05:00,000':
            video_clip['_segments'] = [{'start': start_time, 'end': end_time}]
        if clip.get('_removed_sections'):
            video_clip['_removed_sections'] = clip['_removed_sections']
        clips_for_video.append(video_clip)

    from backend.utils.video_processor import VideoProcessor as VP
    from backend.utils.silence_concat import SilenceConcat
    # 视频生成
    video_generator = VideoGenerator(
        clips_dir=clips_output_dir,
        collections_dir=collections_output_dir,
        metadata_dir=metadata_dir
    )

    # 初始化静音处理器（用于后续对每个切片做静音移除后处理）
    try:
        silence_processor = SilenceConcat(
            long_silence_threshold=0.5,
            short_silence_keep=0.5,
            buffer_duration=0.15,
            silence_threshold_db=-28.0
        )
        logger.info("静音处理器初始化成功，将应用于每个切片的视频提取")
    except Exception as e:
        logger.warning(f"静音处理器初始化失败，跳过静音处理: {e}")
        silence_processor = None

    # 处理多段不连续切片
    temp_dir = metadata_dir / "temp_segments"
    successful_clips = []
    processed_clips_data = []

    # ── 预生成 _removed_sections ──
    temp_dir.mkdir(parents=True, exist_ok=True)
    _prepopulate_removed_sections(clips_for_video, video_path, metadata_dir, temp_dir)
    # ──────────────────────────────

    # ── 视频切割并行化（ThreadPoolExecutor，max_workers=2） ──
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading
    _results_lock = threading.Lock()

    def _process_single_clip(video_clip: dict) -> List[Any]:
        """处理单个切片提取，返回 [successful_path or None, processed_data or None]"""
        segments = video_clip.get('_segments', None)
        removed = video_clip.get('_removed_sections', [])
        clip_id = video_clip['id']
        title = video_clip.get('generated_title', f"片段_{clip_id}")

        safe_title = VP.sanitize_filename(title)
        output_path = clips_output_dir / f"{clip_id}_{safe_title}.mp4"

        # 计算有效段（跳过removed_sections中的静音/无关内容）
        effective_segments = _compute_effective_segments(segments, removed) if (segments and removed) else segments

        # 防御：segments为空时跳过该切片（LLM可能返回None）
        if not effective_segments:
            logger.warning(f"切片 {video_clip['id']} 无有效段（_segments为空），跳过")
            return [None, None]

        if len(effective_segments) > 1:
            # 多段不连续：提取每段再拼接
            logger.info(f"多段切片 {clip_id}: {len(effective_segments)} 个有效时间段，正在提取拼接...")
            success = _extract_multi_segment_clip(
                video_path, output_path, effective_segments, temp_dir
            )
            if success:
                # 计算实际总时长（各段时长之和，不含间隙）
                total_duration = sum(
                    _srt_time_to_seconds(s['end']) - _srt_time_to_seconds(s['start'])
                    for s in effective_segments
                )
                start_sec = _srt_time_to_seconds(effective_segments[0]['start'])
                actual_end_sec = start_sec + total_duration
                data = {
                    'id': clip_id,
                    'title': title,
                    'start_time': _seconds_to_srt_time(start_sec),
                    'end_time': _seconds_to_srt_time(actual_end_sec),
                    'output_path': str(output_path),
                    'keyframe_aligned': False,
                    'multi_segment': True,
                    'segment_count': len(effective_segments)
                }
                logger.info(f"  多段切片 {clip_id} 提取成功 ({len(effective_segments)}段合并)")
                # ---- 静音后处理 ----
                if silence_processor is not None:
                    _apply_silence_processing(silence_processor, output_path, clip_id)
                # ----
                return [output_path, data]
            else:
                logger.error(f"  多段切片 {clip_id} 提取失败")
                return [None, None]
        else:
            # 单段：使用原有方式
            logger.info(f"单段切片 {clip_id}: 常规切割...")
            start_time = effective_segments[0].get('start', video_clip.get('start_time', '00:00:00,000'))
            end_time = effective_segments[0].get('end', video_clip.get('end_time', '00:05:00,000'))

            if VP.extract_clip(video_path, output_path, start_time, end_time):
                data = {
                    'id': clip_id,
                    'title': title,
                    'start_time': start_time,
                    'end_time': end_time,
                    'output_path': str(output_path),
                    'keyframe_aligned': False,
                    'multi_segment': False
                }
                logger.info(f"  单段切片 {clip_id} 提取成功")
                # ---- 静音后处理 ----
                if silence_processor is not None:
                    _apply_silence_processing(silence_processor, output_path, clip_id)
                # ----
                return [output_path, data]
            else:
                logger.error(f"  单段切片 {clip_id} 提取失败")
                return [None, None]

    # 并行执行视频切割
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_to_clip = {
            executor.submit(_process_single_clip, video_clip): video_clip
            for video_clip in clips_for_video
        }
        for future in as_completed(future_to_clip):
            try:
                path, data = future.result()
                with _results_lock:
                    if path is not None:
                        successful_clips.append(path)
                    if data is not None:
                        processed_clips_data.append(data)
            except Exception as e:
                logger.error(f"切片处理异常: {e}")

    # 按 clip id 排序 processed_clips_data 以保持确定性顺序
    processed_clips_data.sort(key=lambda x: str(x.get('id', '')))

    # 生成合集
    successful_collections = video_generator.generate_collections(collections)

    # 更新元数据
    for clip in clips_for_video:
        for processed in processed_clips_data:
            if processed['id'] == clip['id']:
                clip['start_time'] = processed.get('start_time', clip['start_time'])
                clip['end_time'] = processed.get('end_time', clip['end_time'])
                break

    # 保存元数据
    video_generator.save_clip_metadata(clips_for_video, metadata_dir / "clips_metadata.json")
    video_generator.save_collection_metadata(collections, metadata_dir / "collections_metadata.json")

    # 同时保存到项目根目录
    project_dir = metadata_dir.parent
    try:
        video_generator.save_clip_metadata(clips_for_video, project_dir / "clips_metadata.json")
        video_generator.save_collection_metadata(collections, project_dir / "collections_metadata.json")
        logger.info(f"元数据已保存到项目根目录: {project_dir}")
    except Exception as e:
        logger.warning(f"保存备用元数据失败: {e}")

    logger.info(f"FunClip方案处理完成 [模式: {processing_mode}]")
    logger.info(f"  成功: {len(successful_clips)}/{len(clips_for_video)} 个切片")
    logger.info(f"  合集: {len(successful_collections)} 个")

    return clips, collections
