# 阶段C：架构优化 — 整理与优化实施方案（v2，已修正缺陷）

> **版本说明**：v2版本基于v1的全面缺陷审查进行了11项修正，详见文末"缺陷修正清单"。

## 概述

阶段C建立在阶段A（确定性修复）和阶段B（LLM增强）的基础上，聚焦长视频规模化处理、预聚类集成和可观测性建设。

**已完成的A/B阶段基础**：A1语义合并 → A2覆盖率审计 → A3边界扩展 → A4智能话题选择 → B1 Step1.5补洞 → B2 Step2评分增强 → B3默认三步流

**阶段C总依赖**：C1依赖B1+B2，C2可独立部署，C3依赖A2+A3

---

## C1. 滑动窗口 + 全局话题合并（核心模块）

### 目标
长视频（>30min / >400条SRT条目）的分窗处理，避免LLM上下文溢出；跨窗口话题合并消除重复。

### 核心约束（重要）
窗口化**仅应用于Step1**（边界识别），Step2/Step3继续使用**全量SRT**。原因：
- Step2需要全局视角判断"话题完整度"，分窗SRT会丢失边界上下文
- Step2的 `_smart_truncate_srt_for_scoring` 已能处理长SRT
- Step3标题生成也依赖全量上下文

### 与现有资产的关系

| 现有资源 | 状态 | C1处理方式 |
|---------|------|-----------|
| `SLIDING_WINDOW` dict配置 | ✅ 已存在（shared_config.py L148-155） | 迁移到`Settings`类，保留dict兼容映射 |
| `docs/SLIDING_WINDOW_PLAN.md` | ✅ 已有设计 | 采纳分块策略，但移除TopicAnchorDetector |
| `shared_config.py Settings` | ✅ 已有A/B阶段配置 | 新增C1配置项 |
| `_llm_process_three_step` | ✅ 已有 | 新增`_windowed`变体，Step2/Step3复用 |

### 新增文件

#### 文件：`backend/pipeline/sliding_window_chunker.py`

```python
"""
滑动窗口分块器 — 将长SRT字幕分块以供Step1逐块处理。

设计要点：
1. 以SRT条目边界对齐，不切割单条字幕
2. chunk.srt_text使用原始SRT时间戳（全局时间），无需偏移校正
3. chunk_entries使用"有交集即包含"策略，相邻窗口边界条目可能重复
"""
from dataclasses import dataclass
from typing import List, Dict


@dataclass
class SrtChunk:
    chunk_index: int
    start_sec: float
    end_sec: float
    srt_text: str            # 全局时间戳，可直接传递给LLM
    entry_count: int
    start_entry_idx: int     # 在全局entries中的起始索引
    overlap_prev_sec: float = 0.0


class SlidingWindowChunker:

    def __init__(
        self,
        chunk_size_sec: float = 300.0,
        overlap_sec: float = 60.0,
        min_chunk_sec: float = 90.0,
    ):
        self.chunk_size_sec = chunk_size_sec
        self.overlap_sec = overlap_sec
        self.min_chunk_sec = min_chunk_sec

    def chunk_entries(self, entries: List[Dict]) -> List[SrtChunk]:
        """核心方法：将SRT条目列表分割为带重叠的窗口。"""
        if not entries:
            return []

        total_end = max(e.get('end', 0) for e in entries)
        cursor = min(e.get('start', 0) for e in entries)
        chunks = []

        idx = 0
        while cursor < total_end - self.min_chunk_sec:
            win_end = min(cursor + self.chunk_size_sec, total_end)

            chunk_entries = [
                e for e in entries
                if e.get('start', 0) < win_end and e.get('end', 0) > cursor
            ]
            if not chunk_entries:
                cursor += self.chunk_size_sec
                continue

            first_idx = next(
                (i for i, e in enumerate(entries) if e is chunk_entries[0]), 0
            )
            srt_text = self._entries_to_srt(chunk_entries)
            chunks.append(SrtChunk(
                chunk_index=idx,
                start_sec=cursor,
                end_sec=win_end,
                srt_text=srt_text,
                entry_count=len(chunk_entries),
                start_entry_idx=first_idx,
                overlap_prev_sec=self.overlap_sec if idx > 0 else 0.0,
            ))

            idx += 1
            cursor = win_end - self.overlap_sec
            if win_end >= total_end:
                break

        return chunks

    def _entries_to_srt(self, entries: List[Dict]) -> str:
        """使用原始SRT时间戳（全局时间），无需偏移校正。"""
        lines = []
        for i, e in enumerate(entries):
            start = e.get('start_str', '00:00:00,000')
            end = e.get('end_str', '00:00:00,000')
            text = e.get('text', '').strip()
            if text:
                lines.append(f"{i+1}")
                lines.append(f"{start} --> {end}")
                lines.append(text)
                lines.append("")
        return "\n".join(lines)
```

### 修改现有文件

#### shared_config.py — 新增Settings字段 + 兼容映射

```python
# C1: 滑动窗口配置
sliding_window_enabled: bool = True
sliding_window_chunk_size_sec: float = 300.0
sliding_window_overlap_sec: float = 60.0
sliding_window_min_chunk_sec: float = 90.0
sliding_window_threshold_entries: int = 400
sliding_window_threshold_duration: float = 1800.0  # 30分钟

# ConfigManager中增加兼容映射：
def _get_sliding_window_config(self) -> dict:
    """读取滑动窗口配置，兼容旧的 SLIDING_WINDOW dict 格式。"""
    s = self.settings
    # 从Settings类读取为主
    return {
        'enabled': s.sliding_window_enabled,
        'chunk_size_sec': s.sliding_window_chunk_size_sec,
        'overlap_sec': s.sliding_window_overlap_sec,
        'min_chunk_sec': s.sliding_window_min_chunk_sec,
        'threshold_entries': s.sliding_window_threshold_entries,
        'threshold_duration': s.sliding_window_threshold_duration,
    }
```

#### topic_postprocess.py — 新增跨窗口合并（含语义约束）

```python
def merge_cross_window_topics(
    topics: List[Dict],
    srt_entries: List[Dict],
    *,
    time_gap_max: float = 30.0,
    title_sim_threshold: float = 0.45,
) -> List[Dict]:
    """
    合并跨窗口的重复话题。

    合并条件（**必须同时满足时间+语义**，防止误合并）：
    1. 相邻chunk的topic，时间gap < time_gap_max
       **且** outline标题相似度 > title_sim_threshold
    2. 两topic的segments时间IoU > 0.5
       **且** topic A末条与topic B首条存在前向依赖
    """
    sorted_topics = sorted(
        topics,
        key=lambda t: (
            t.get('chunk_index', 0),
            _srt_time_to_seconds(t['segments'][0]['start']),
        ),
    )
    merged = []
    i = 0
    while i < len(sorted_topics):
        cur = sorted_topics[i]
        if i + 1 < len(sorted_topics):
            nxt = sorted_topics[i + 1]
            if _should_merge_cross_window(cur, nxt, srt_entries, time_gap_max, title_sim_threshold):
                cur = _merge_two_topics(cur, nxt)
                i += 2
                merged.append(cur)
                continue
        merged.append(cur)
        i += 1
    return merged


def _should_merge_cross_window(
    a, b, entries, time_gap_max=30.0, title_sim_threshold=0.45
) -> bool:
    """跨窗口合并判定（时间 + 语义双重约束）。"""
    from difflib import SequenceMatcher

    a_start = _srt_time_to_seconds(a['segments'][0]['start'])
    b_end = _srt_time_to_seconds(b['segments'][-1]['end'])
    a_end = _srt_time_to_seconds(a['segments'][-1]['end'])
    b_start = _srt_time_to_seconds(b['segments'][0]['start'])

    # 条件1: 相邻chunk + 时间gap小 + 标题相似
    a_outline = a.get('outline', '')
    b_outline = b.get('outline', '')
    title_sim = SequenceMatcher(None, a_outline, b_outline).ratio()
    time_gap = b_start - a_end

    if time_gap < time_gap_max and title_sim > title_sim_threshold:
        return True

    # 条件2: 时间IoU大 + 存在前向依赖
    iou = _calc_time_iou(a, b)
    if iou > 0.5 and _cross_window_forward_dep(a, b, entries):
        return True

    return False


def _calc_time_iou(a, b) -> float:
    """计算两个topic的时间IoU。"""
    a_s = _srt_time_to_seconds(a['segments'][0]['start'])
    a_e = _srt_time_to_seconds(a['segments'][-1]['end'])
    b_s = _srt_time_to_seconds(b['segments'][0]['start'])
    b_e = _srt_time_to_seconds(b['segments'][-1]['end'])
    inter = max(0, min(a_e, b_e) - max(a_s, b_s))
    union = max(a_e, b_e) - min(a_s, b_s)
    return inter / union if union > 0 else 0.0


def _cross_window_forward_dep(a, b, entries) -> bool:
    """topic A末条与topic B首条是否存在前向依赖。"""
    a_last_text = _get_last_entry_text(a, entries)
    b_first_text = _get_first_entry_text(b, entries)
    from backend.pipeline.topic_boundary import _has_forward_dependency
    return bool(a_last_text and b_first_text and _has_forward_dependency(b_first_text))
```

#### funclip_style.py — 新增窗口化三步流

```python
# ============================================================
# C1: 窗口化三步流
# ============================================================

def _should_use_windowed_step1(self, srt_entries: List[Dict]) -> bool:
    """判断是否需要分窗执行Step1。"""
    cfg = self._get_sliding_window_config()
    if not cfg['enabled']:
        return False
    duration = srt_entries[-1]['end'] - srt_entries[0]['start']
    return (
        len(srt_entries) > cfg['threshold_entries']
        or duration > cfg['threshold_duration']
    )


def _llm_process_three_step_windowed(self, srt_text: str):
    """分窗Step1 → 全局合并 → 标准Step2/Step3。

    LLM调用次数 = 窗口数(Step1) + 1(Step2) + 1(Step3)
    例：45min视频 ≈ 11+1+1 = 13次（非窗口化=3次）
    """
    srt_entries = _parse_srt_timeline(srt_text)
    cfg = self._get_sliding_window_config()

    from backend.pipeline.sliding_window_chunker import SlidingWindowChunker
    chunker = SlidingWindowChunker(
        chunk_size_sec=cfg['chunk_size_sec'],
        overlap_sec=cfg['overlap_sec'],
    )
    chunks = chunker.chunk_entries(srt_entries)
    logger.info(
        "窗口化Step1: %d个窗口(%.0fs/窗口, %.0fs重叠)",
        len(chunks), cfg['chunk_size_sec'], cfg['overlap_sec'],
    )

    # ---- 逐窗口执行Step1 ----
    all_topics = []
    failed_windows = 0
    for chunk in chunks:
        try:
            local_topics = self._do_step1_with_retry(
                chunk.srt_text, srt_entries, None
            )
            if local_topics:
                for t in local_topics:
                    t['chunk_index'] = chunk.chunk_index
                all_topics.extend(local_topics)
        except Exception as e:
            logger.warning("窗口%d Step1失败: %s", chunk.chunk_index, e)
            failed_windows += 1

    # 降级判断：失败窗口 >= 50% → 放弃窗口化
    if failed_windows >= len(chunks) * 0.5:
        logger.warning("窗口化Step1失败率过高(%d/%d)，降级到非窗口化", failed_windows, len(chunks))
        return self._llm_process_three_step(srt_text)

    # ---- 跨窗口合并 ----
    from backend.pipeline.topic_postprocess import merge_cross_window_topics
    all_topics = merge_cross_window_topics(all_topics, srt_entries)

    # ---- 复用标准Step2/Step3（使用全量SRT） ----
    step2_scores = self._call_step2_batch_score(
        self._prepare_step2_input(all_topics, srt_entries)
    )
    if step2_scores:
        all_topics = _apply_boundary_suggestions(all_topics, step2_scores, srt_entries)
    all_topics = _merge_scores_to_topics(all_topics, step2_scores or [])

    step3_titles = self._call_step3_batch_title(
        self._prepare_step3_input(all_topics, srt_entries)
    )
    all_topics = _merge_titles_to_topics(all_topics, step3_titles or [])

    # ---- 最终后处理 ----
    all_topics = _select_final_topics(all_topics)
    clips = _convert_topics_to_clips(all_topics)
    collections = self._generate_collections(clips)

    logger.info(
        "窗口化三步流完成: %d clips, %d windows(%d failed)",
        len(clips), len(chunks), failed_windows,
    )
    return clips, collections


#### 并发控制（可选优化）

窗口化可并行执行以缩短总处理时间。LLM调用是I/O密集型，适合轻量并发：

```python
def _llm_process_three_step_windowed(self, srt_text: str):
    """分窗Step1（支持并发）→ 全局合并 → 标准Step2/Step3"""
    srt_entries = _parse_srt_timeline(srt_text)
    cfg = self._get_sliding_window_config()
    max_concurrency = cfg.get('max_concurrency', 0)

    from backend.pipeline.sliding_window_chunker import SlidingWindowChunker
    chunker = SlidingWindowChunker(...)
    chunks = chunker.chunk_entries(srt_entries)

    # ---- 逐窗口/并发执行Step1 ----
    all_topics = []
    failed_windows = 0

    if max_concurrency > 1 and len(chunks) >= max_concurrency:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
            futures = {
                pool.submit(self._do_step1_with_retry, c.srt_text, srt_entries, None): c
                for c in chunks
            }
            for future in as_completed(futures):
                chunk = futures[future]
                try:
                    local_topics = future.result()
                    if local_topics:
                        for t in local_topics:
                            t['chunk_index'] = chunk.chunk_index
                        all_topics.extend(local_topics)
                except Exception as e:
                    logger.warning("窗口%d Step1失败: %s", chunk.chunk_index, e)
                    failed_windows += 1
    else:
        # 串行执行（默认）
        for chunk in chunks:
            try:
                local_topics = self._do_step1_with_retry(
                    chunk.srt_text, srt_entries, None
                )
                if local_topics:
                    for t in local_topics:
                        t['chunk_index'] = chunk.chunk_index
                    all_topics.extend(local_topics)
            except Exception as e:
                logger.warning("窗口%d Step1失败: %s", chunk.chunk_index, e)
                failed_windows += 1

    # 后续降级判断 + 合并 + Step2/Step3 同前
    ...
```

**注意**：并发数不宜过大（建议2-4），避免触发LLM服务的速率限制。`max_concurrency=0` 或 `=1` 时回退到串行模式。

在 `_single_step_llm_process` 中增加窗口化判断：

```python
if processing_mode == "three_step":
    srt_entries = _parse_srt_timeline(srt_text)
    if self._should_use_windowed_step1(srt_entries):
        logger.info(f"长视频({len(srt_entries)} entries)触发窗口化Step1")
        return self._llm_process_three_step_windowed(srt_text)
    return self._llm_process_three_step(srt_text)
```

### 配置项汇总

| 配置项 | 默认值 | 说明 |
|-------|--------|------|
| `sliding_window_enabled` | True | 是否启用滑动窗口 |
| `sliding_window_chunk_size_sec` | 300.0 | 窗口大小（秒） |
| `sliding_window_overlap_sec` | 60.0 | 重叠时长（秒） |
| `sliding_window_min_chunk_sec` | 90.0 | 最小分块（秒） |
| `sliding_window_threshold_entries` | 400 | 触发窗口化的SRT条目阈值 |
| `sliding_window_threshold_duration` | 1800.0 | 触发窗口化的时长阈值（秒） |
| `sliding_window_max_concurrency` | 0 | 并发窗口数（0或1=串行，2-4=并发） |
| `sliding_window_degrade_threshold` | 0.5 | 失败窗口比例超过此值时降级到非窗口化 |

#### 降级策略（精细化）

窗口化Step1的降级分两级：

```python
class WindowedStep1Result:
    def __init__(self):
        self.all_topics = []
        self.failed_windows = 0
        self.total_windows = 0
        self.retried_windows = 0

    def has_degrade(self, threshold=0.5) -> bool:
        """失败窗口 >= threshold * total_windows 时降级。"""
        return self.total_windows > 0 and self.failed_windows >= self.total_windows * threshold


def _execute_windowed_step1(self, chunks, srt_entries, max_concurrency=0) -> WindowedStep1Result:
    """执行窗口化Step1，含单窗口重试+失败统计。"""
    result = WindowedStep1Result()
    result.total_windows = len(chunks)

    def _process_one(chunk):
        """单窗口处理（内部含1次重试）。"""
        try:
            # _do_step1_with_retry 内部已有重试逻辑
            topics = self._do_step1_with_retry(chunk.srt_text, srt_entries, None)
            if topics:
                for t in topics:
                    t['chunk_index'] = chunk.chunk_index
                return topics
        except Exception as e:
            logger.warning("窗口%d Step1失败（已耗尽重试）: %s", chunk.chunk_index, e)
        return None

    if max_concurrency > 1 and len(chunks) >= max_concurrency:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
            futures = {pool.submit(_process_one, c): c for c in chunks}
            for future in as_completed(futures):
                topics = future.result()
                if topics:
                    result.all_topics.extend(topics)
                else:
                    result.failed_windows += 1
    else:
        for chunk in chunks:
            topics = _process_one(chunk)
            if topics:
                result.all_topics.extend(topics)
            else:
                result.failed_windows += 1

    return result


# 在 _llm_process_three_step_windowed 中使用：
step1_result = self._execute_windowed_step1(chunks, srt_entries, max_concurrency)
if step1_result.has_degrade(cfg['degrade_threshold']):
    logger.warning("窗口化降级（%d/%d失败），回退到非窗口化", step1_result.failed_windows, step1_result.total_windows)
    return self._llm_process_three_step(srt_text)
```

**关键说明**：
- `_do_step1_with_retry` 内部已有最多 `max_retries`（默认3次）的重试，因此单窗口层面无需额外重试循环
- 降级阈值 `sliding_window_degrade_threshold` 默认为0.5，可通过配置调整
- 局部失败（未触发降级）的窗口不产出topic，这部分区间在后续Step2/Step3中不会被覆盖，**但Step1.5的覆盖审计会发现空白区间并触发补洞**，形成兜底成本影响
| 视频时长 | 窗口数 | LLM调用次数(窗口化) | LLM调用次数(非窗口化) | 成本增幅 |
|---------|-------|-------------------|-------------------|---------|
| 30min | 7 | 7+1+1=9次 | 1+1+1=3次 | 3x |
| 45min | 11 | 11+1+1=13次 | 3次 | 4.3x |
| 60min | 14 | 14+1+1=16次 | 3次 | 5.3x |
| 90min | 21 | 21+1+1=23次 | 3次 | 7.7x |

**注意**：窗口化启用后LLM调用次数随视频时长线性增长。可通过增大 `chunk_size_sec`（如600s）或提高 `threshold_duration`（如3600s）控制成本。

### 验收标准

- 45min视频，chunk_size=300s, overlap=60s → 窗口数 = ceil((2700-300)/240) + 1 ≈ 11
- 跨窗口合并后，无时间重叠 > 5s 的重复topic
- 语义无关但时间重叠的topic不被合并（双重约束保证）
- 窗口失败率 ≥ 50% 时自动降级到非窗口化

---

## C2. 预聚类报告注入 Step1

### 目标
利用已有`TopicPreCluster`模块的聚类信息为Step1提供辅助参考，减少LLM遗漏。`TopicPreCluster`已稳定运行，直接复用。

### 与现有资产的关系

| 现有资源 | 状态 | C2处理方式 |
|---------|------|-----------|
| `TopicPreCluster`类 | ✅ 已有（topic_precluster.py L542-657） | 直接复用，不重新实现 |
| `_prepare_enhanced_text()` | ✅ 已有（funclip_style.py L1443） | 在其调用结果前注入预聚类报告 |
| `_seconds_to_srt_time` | ✅ 已从topic_postprocess导入 | 用于时间格式化，勿用不存在的`_sec_to_srt` |

### 集成方式

**位置**：`backend/pipeline/funclip_style.py`，在 `_prepare_enhanced_text` 调用前注入

**避免重复SRT解析**：`_build_step1_input` 接收可选的 `srt_entries` 参数，若主流程已解析过则传入，否则内部解析。

```python
def _build_step1_input(self, srt_text: str, srt_entries: List[Dict] = None) -> str:
    """构建Step1输入：增强文本 + 可选预聚类报告（注入失败不影响主流程）。"""
    enhanced = self._prepare_enhanced_text(srt_text)

    if not self.settings.precluster_enabled:
        return enhanced

    try:
        from backend.pipeline.topic_precluster import TopicPreCluster
        precluster = TopicPreCluster()
        report = precluster.process(srt_text)

        # 低覆盖率时跳过注入（聚类本身不可靠）
        cov = report.stats.get('coverage_ratio', 0)
        if cov < 0.5:
            logger.debug("预聚类覆盖率%.0f%%过低，跳过注入", cov * 100)
            return enhanced

        if report.clusters:
            block = self._format_precluster_block(report)
            enhanced = f"{block}\n\n---\n\n{enhanced}"
    except Exception as e:
        logger.warning("预聚类注入失败（不影响主流程）: %s", e)

    return enhanced


def _format_precluster_block(self, report) -> str:
    """格式化预聚类报告文本（用 _seconds_to_srt_time 而非不存在的 _sec_to_srt）。"""
    from backend.pipeline.topic_postprocess import seconds_to_srt_time as to_srt

    lines = [
        "## 预聚类参考（辅助边界判断，非最终答案）",
        f"SRT条目覆盖率: {report.stats.get('coverage_ratio', 0):.0%}",
        "",
    ]
    for i, cluster in enumerate(report.clusters[:6]):
        time_ranges = cluster.time_ranges
        if time_ranges:
            start_str = to_srt(time_ranges[0].start_seconds)
            end_str = to_srt(time_ranges[0].end_seconds)
        else:
            start_str, end_str = "??", "??"
        keywords = ", ".join(cluster.topic_keywords[:4]) if cluster.topic_keywords else ""
        lines.append(
            f"簇{i+1}: {start_str}-{end_str}"
            + (f" 关键词={keywords}" if keywords else "")
        )
        if cluster.is_multi_segment:
            lines.append(f"  [多段] 在{len(cluster.time_ranges)}个时间段出现")

    lines.extend([
        "",
        "注意：预聚类基于n-gram相似度，可能过度合并。请结合语义判断。",
        "若覆盖率 < 90%，请确保输出话题覆盖主要语段。",
    ])
    return "\n".join(lines)
```

### Step1 Prompt补充

在 `funclip_step1_boundary.txt` 末尾追加（注：`_format_precluster_block` 已包含此说明，prompt文件中的这句是兜底，当预聚类被禁用时由LLM自行判断）：

```
若预聚类报告显示覆盖率 < 90%，请确保输出话题覆盖主要语段，避免大段时间轴空白。
```

### 配置项

| 配置项 | 默认值 | 说明 |
|-------|--------|------|
| `precluster_enabled` | True | 已有配置，控制预聚类开关 |
| `precluster_step1_inject` | True | **新增**：是否将预聚类报告注入Step1 |

### 验收标准

- 预聚类coverage ≥ 50% 时正常注入，< 50% 跳过
- 注入失败时主流程不受影响（try/except保护）
- 报告中时间格式使用SRT标准 `hh:mm:ss,mmm`

---

## C3. 完整性指标入库与前端展示

### 目标
为每个clip生成完整性元数据，暴露给API，支持前端展示。**复用已有函数，不重复定义**。

### 新增文件

#### 文件：`backend/pipeline/topic_completeness.py`

```python
"""
话题完整性指标计算模块。
复用：topic_boundary._has_forward_dependency, topic_postprocess._ends_sentence
"""
from typing import List, Dict, Optional

from backend.pipeline.topic_boundary import _has_forward_dependency
from backend.pipeline.topic_postprocess import _ends_sentence


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
    返回字典包含：
    - coverage_ratio: clip覆盖条目 / 全局总条目
    - intro_complete: 首条是否为完整句首（无前向依赖）
    - outro_complete: 末条是否为句号结尾
    - segment_count: segment数量
    - gap_fill_applied: 是否经B1补洞
    - boundary_adjustments: A3边界调整记录
    - warnings: 警告列表
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

    intro = not _has_forward_dependency(first_entry['text']) if first_entry else False
    outro = _ends_sentence(last_entry['text']) if last_entry else False
    cov = _get_coverage_ratio(clip, srt_entries)

    warnings = []
    if not intro:
        warnings.append("intro_incomplete")
    if not outro:
        warnings.append("outro_incomplete")
    if clip.get('gap_fill_applied'):
        warnings.append("has_gap_fill")

    return {
        "coverage_ratio": cov,
        "intro_complete": intro,
        "outro_complete": outro,
        "segment_count": len(segments),
        "gap_fill_applied": bool(clip.get('gap_fill_applied')),
        "boundary_adjustments": clip.get('boundary_adjustments', []),
        "warnings": warnings,
    }


def compute_all_completeness(
    clips: List[Dict],
    srt_entries: List[Dict],
) -> List[Dict]:
    """为所有clips批量计算完整性指标（在后处理时调用）。"""
    for clip in clips:
        clip['completeness'] = compute_clip_completeness(clip, srt_entries)
    return clips
```

### 存储策略

完整性指标**不在API调用时实时计算**，而是在后处理中一次性计算并写入文件：

```
metadata_dir/topic_completeness.json → {"clips": [{id, completeness}, ...]}
```

**集成点**：在 `_convert_topics_to_clips` 或 `postprocess_funclip_topics` 中调用 `compute_all_completeness(clips, srt_entries)`，随后写入metadata文件。

**API读取**：`GET /api/projects/{id}/clips` 从metadata文件读取completeness字段返回，不存在时忽略。

### API扩展（最小改动）

```json
// GET /api/projects/{id}/clips 返回每个clip附带completeness
{
    "id": "1",
    "title": "...",
    "segments": [...],
    "completeness": {
        "coverage_ratio": 0.1234,
        "intro_complete": true,
        "outro_complete": false,
        "segment_count": 3,
        "warnings": ["outro_incomplete"],
        "needs_review": true
    }
}
```
前端可忽略 `completeness` 字段（旧版本兼容）。

#### 人工审核标记

当clip的完整性指标显示任何问题时，标记 `needs_review` 供前端提示人工审查。判断逻辑：

```python
# 在 compute_clip_completeness 返回前增加：
needs_review = len(warnings) > 0

return {
    ...
    "warnings": warnings,
    "needs_review": needs_review,  # 任意warning触发审查标记
}
```

- `needs_review = True` → 前端显示黄色警告图标，提示"需要人工复核"
- `needs_review = False` → 前端不显示额外标记
- 后端暂不实现反馈API（`POST /api/projects/{id}/clips/{clip_id}/boundary_feedback` 列为可选后续）

### 配置项

| 配置项 | 默认值 | 说明 |
|-------|--------|------|
| `completeness_enabled` | True | **新增**：是否启用完整性指标 |

### 验收标准

- 每个clip的 `completeness` 字段在metadata中可查到
- warnings非空时指示具体问题类型
- 旧前端不受新字段影响

---

## 实施顺序

```
C2 (预聚类注入) ─── 可独立上线，无依赖，风险最低
      │
      ▼
C1 (滑动窗口) ───── 核心改造，依赖A/B阶段
      │
      ▼
C3 (指标+API) ──── 依赖A2+A3，但可后置
```

**推荐实施顺序**：**C2 → C1 → C3**

| 步骤 | 内容 | 工作量估计 |
|------|------|-----------|
| C2 | 预聚类注入（~60行） | 0.5天 |
| C1 | 滑动窗口分块器+合并+流水线集成（~300行） | 2天 |
| C3 | 完整性指标+metadata存储（~120行） | 1天 |
| 测试 | 单元测试+集成测试 | 1天 |
| **合计** | | **4.5天** |

---

## 关键风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 窗口化Step1 LLM成本线性增长（45min 13次） | 成本增加4x | 可调整chunk_size(600s)和threshold_duration(3600s)控制; 文档已量化 |
| 跨窗口合并误合并语义无关topic | 切片质量下降 | 双重约束（时间+语义），不单纯依靠IoU |
| 预聚类低质量误导LLM | 边界错误 | coverage < 50%跳过注入；注入文本含免责说明 |
| 窗口化Step1失败率高 | 处理中断 | 失败窗口≥50%自动降级到非窗口化 |
| 完整性指标重复计算 | 性能浪费 | 后处理一次性计算 + metadata缓存 |

---

## 可观测性与审计日志

### 目标
为每次窗口化处理输出结构化审计记录，支持成本核算、故障回溯和质量评估。

### 审计记录结构

```python
@dataclass
class PipelineAuditRecord:
    project_id: str
    video_duration_sec: float
    srt_entry_count: int
    processing_mode: str                         # 'windowed' | 'standard' | 'degraded'
    # 窗口统计
    total_windows: int
    failed_windows: int
    degraded: bool                               # 是否触发降级
    merged_cross_window: int                     # 跨窗口合并事件数
    merge_skipped: int                           # 判定不合并的事件数
    # LLM调用
    llm_step1_calls: int                         # Step1 LLM调用次数（=窗口数）
    llm_step2_calls: int                         # 0或1
    llm_step3_calls: int                         # 0或1
    llm_total_calls: int
    estimated_cost_cny: float                    # 估算成本（元）
    # 预聚类
    precluster_injected: bool
    precluster_coverage: float
    # 完整性
    clips_total: int
    clips_needing_review: int                    # needs_review=True的clip数
    # 时间
    start_timestamp: str
    duration_sec: float                          # 处理耗时
```

### 输出位置

```
metadata_dir/pipeline_audit.json
```

### 集成点

在 `_llm_process_three_step_windowed` 和 `_llm_process_three_step` 返回前构建并写入：

```python
def _write_pipeline_audit(self, audit: PipelineAuditRecord):
    path = self.metadata_dir / "pipeline_audit.json"
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(dataclasses.asdict(audit), f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning("写入审计日志失败: %s", e)
```

### 关键监控指标

| 指标 | 计算方式 | 正常范围 | 告警阈值 |
|------|---------|---------|---------|
| 窗口失败率 | failed_windows / total_windows | 0% | ≥10% |
| LLM调用成本 | total_calls × 单次均价 | 视视频时长 | 超出预估50% |
| 合并率 | merged_cross_window / total_windows | 5-30% | >50%（可能过度合并） |
| 审查比例 | clips_needing_review / clips_total | <40% | >60% |
| 处理耗时增幅 | windowed_duration / standard_duration基准 | <窗口数×1.2 | >窗口数×2 |

这些指标可在 `pipeline_audit.json` 中积累后由外部监控系统收集展示。

---

## 可替代方案

### 方案A：两级窗口（推荐替代）

先用大窗口粗筛，再对有内容的窗口精细切分。

```
阶段1（粗筛）：chunk_size=600s, overlap=0
  → 每个窗口只问LLM："此窗口内是否有独立话题？"（二分类，token消耗极小）
  → 过滤掉约50%的无话题窗口

阶段2（精细）：chunk_size=300s, overlap=60s
  → 只对有话题的窗口执行标准Step1
  → LLM调用次数：粗筛(窗口数) + 有话题窗口数
```

**收益**：45min视频从11次Step1降低到约6-8次（粗筛5次+精细3-5次）。适用于成本敏感场景。

**代价**：增加一次粗筛LLM调用模式，增加了架构复杂度。

### 方案B：本地小模型预筛

用本地小模型（如Qwen2.5-7B-Q4）做Step1边界检测，仅将Step2/Step3交由云端大模型。

**前提条件**：
- `llm_manager` 需要支持多provider路由（当前不支持，需改造）
- 本地模型推理需要GPU或足够CPU+RAM

**当前评估**：C阶段暂不实施，列为后续优化方向。原因：
1. 当前 `llm_manager` 只支持单provider
2. 本地小模型的边界识别质量与 `qwen-plus` 的差距缺乏测试数据支撑
3. 引入本地推理增加部署复杂度

### 方案C：语义缓存去重

对高频重复内容（如直播中的固定开场/结尾）建立缓存索引，相同或高度相似的SRT片段跳过重复LLM调用。

**适用于**：同一主播/栏目的批量处理，当前单视频场景收益有限，暂不实施。

---

## 验收条件

### C1 滑动窗口

| # | 条件 | 验证方法 |
|---|------|---------|
| 1 | 45min视频窗口数计算正确（chunk_size=300s, overlap=60s ≈ 11个） | 单元测试覆盖 |
| 2 | 跨窗口合并后无时间重叠 >5s 的重复topic | 在至少5个长视频上人工抽样检查 |
| 3 | 语义无关但时间重叠的topic不被合并 | 构造2个时间重叠但outline不同的topic，验证合并逻辑拒绝 |
| 4 | 窗口失败率≥50%时自动降级到非窗口化 | 模拟全部窗口失败，验证降级调用 |
| 5 | 单窗口失败（<50%）时其他窗口不受影响，局部失败区间由Step1.5兜底 | 模拟单窗口失败，验证Step1.5补洞触发 |
| 6 | 并发模式（max_concurrency=2）产出与串行模式一致 | 同一视频在两种模式下运行，比较输出topic列表 |

### C2 预聚类注入

| # | 条件 | 验证方法 |
|---|------|---------|
| 7 | coverage ≥ 50% 时正常注入，< 50% 跳过 | 构造高低两种覆盖率的SRT，验证注入行为 |
| 8 | 注入失败不影响主流程 | mock `TopicPreCluster.process` 抛异常，验证仍返回enhanced_text |

### C3 完整性指标

| # | 条件 | 验证方法 |
|---|------|---------|
| 9 | 每个clip的completeness字段非空 | 处理完成后检查metadata文件 |
| 10 | warnings非空时needs_review=True | 构造intro_incomplete场景验证 |
| 11 | API返回不因completeness字段报错 | 调用GET /projects/{id}/clips验证响应正常 |

### 验收前提

- 需至少 **5个>30min的长视频** 作为C1测试样本（当前项目是否满足？如不满足需先准备）
- 验收前先运行一次非窗口化流程建立"基准结果"，窗口化后的结果应与基准在主要话题上一致（允许边界微调但不应遗漏核心话题）

---

## 缺陷修正清单（v1 → v3）

| # | 缺陷 | 类型 | 修正方式 |
|---|------|------|---------|
| 1 | `_offset_topics_to_global` 不必要（SRT时间戳全局） | 设计过度 | 移除；chunk直接使用原始SRT时间戳 |
| 2 | Step2/Step3使用全量还是分窗SRT未明确 | 设计模糊 | 明确：Step2/Step3使用全量SRT |
| 3 | LLM成本未量化 | 遗漏 | 增加成本影响表格 |
| 4 | IoU合并缺少语义约束 | 逻辑缺陷 | 增加outline相似度和前向依赖双重约束 |
| 5 | `TopicPreCluster.process()` 重复解析SRT | 性能浪费 | `_build_step1_input` 接受可选srt_entries |
| 6 | `_sec_to_srt` 方法不存在 | 语法错误 | 改用已导入的 `_seconds_to_srt_time` |
| 7 | 预聚类低覆盖率时仍注入 | 质量风险 | coverage < 50%跳过注入 |
| 8 | C3 `_is_forward_dependent` 重复定义 | 代码复用 | 从 `topic_boundary` 导入 `_has_forward_dependency` |
| 9 | C3 `completeness` 无存储策略 | 设计模糊 | 后处理一次性计算 + metadata文件缓存 |
| 10 | 窗口化无降级链 | 健壮性 | 失败窗口≥50%降级到非窗口化 |
| 11 | SLIDING_WINDOW新旧配置无兼容映射 | 兼容性 | `_get_sliding_window_config` 兼容映射 |
| 12 | **并行度管理缺失**（本次补充） | 设计遗漏 | 新增 `max_concurrency` 配置 + ThreadPoolExecutor |
| 13 | **结构化审计日志缺失**（本次补充） | 设计遗漏 | 新增 `PipelineAuditRecord` + `pipeline_audit.json` |
| 14 | **降级精度粗糙**（本次补充） | 健壮性 | 封装 `_execute_windowed_step1` + `WindowedStep1Result` |
| 15 | **人工审核路径缺失**（本次补充） | 功能缺失 | `completeness` 中增加 `needs_review` 字段 |
| 16 | **可替代方案未记录**（本次补充） | 文档遗漏 | 新增两级窗口/本地小模型/语义缓存三种方案 |
| 17 | **验收条件不系统**（本次补充） | 文档遗漏 | 新增11项验收条件+验收前提 |

---

## 设计决策记录

1. **优先复用已有`TopicPreCluster`**而非重新实现：已稳定运行，process()方法直接返回可用report
2. **滑动窗口只覆盖three_step的Step1**：merged模式已有全量SRT输入，分窗无意义
3. **窗口化Step2/Step3使用全量SRT**：Step2需要全局视角判断完好度
4. **不使用TopicAnchorDetector**：过于复杂，跨窗口合并用时间+语义双重约束即可
5. **completeness不单独建表**：metadata文件存储，减少DB变更
6. **C2注入失败不阻塞**：try/except保护，日志警告即可
7. **新旧配置兼容**：ConfigManager提供统一读取接口，迁移过程透明