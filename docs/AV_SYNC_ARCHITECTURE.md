# AutoClip 音视频同步架构方案

> **最后更新**: 2026-05-20
> **版本**: v2.0
> **核心模块**: `backend/utils/keyframe_aligner.py`
> **相关文档**: `KEYFRAME_ALIGNMENT_IMPLEMENTATION.md`, `VIDEO_SLICE_FIX_REPORT.md`, `KEYFRAME_ALIGNMENT_FIX_REPORT.md`

---

## 背景

在直播切片场景中，LLM 识别出的话题边界是**语义时间点**，而视频编码中的切割点是**信号时间点**。二者的错位会导致三类问题：

| 问题 | 表现 | 根因 |
|------|------|------|
| **花屏** | 切片开头几帧绿屏/花屏 | 切割点在非关键帧（P/B帧），`-c copy` 解码失败 |
| **音画不同步** | 画面与声音时间轴偏移 | 音频从指定时间开始，视频从最近 I 帧开始 |
| **内容截断** | 切片开头/结尾缺失部分内容 | LLM 边界刚好在关键帧之后，回退到前一个 I 帧导致丢帧 |

---

## 架构总览

### 核心链路

```
LLM 输出话题时间边界 (语义级)
    ↓
backend/pipeline/step2_timeline.py  —— 关键帧辅助验证（可选）
    ↓
backend/pipeline/step6_video.py     —— 传入切片数据给 VideoProcessor
    ↓
backend/utils/video_processor.py    —— 调用 KeyframeAligner 批量对齐
    ↓
backend/utils/keyframe_aligner.py   —— 核心：ffprobe 分析 I 帧分布 → 对齐边界
    ↓
FFmpeg -c copy 无损切割              —— 从对齐后的 I 帧开始切割
    ↓
元数据同步                           —— 记录对齐前后的时间偏移量
```

### 三层 AV 同步保障

| 层级 | 模块 | 职责 |
|------|------|------|
| **第1层：关键帧对齐** | `KeyframeAligner` | 用 ffprobe 分析 I 帧分布，将 LLM 边界对齐到最近 I 帧 |
| **第2层：渐进式降级** | `_get_video_duration()` / `_find_ffprobe_path()` | ffprobe 不可用时自动降级到 ffmpeg 备用方案 |
| **第3层：元数据同步** | `step6_video.py` | 将对齐后的实际切割时间写回元数据，前端展示时还原原始时间 |

---

## 核心模块：KeyframeAligner

### 文件位置

[`backend/utils/keyframe_aligner.py`](../backend/utils/keyframe_aligner.py)（约699行）

### 核心数据结构

```python
@dataclass
class KeyframeInfo:
    """关键帧信息"""
    timestamp: float      # 时间戳（秒）
    frame_number: int     # 帧序号

@dataclass
class AlignedBoundary:
    """对齐后的边界"""
    original_start: float    # LLM 建议的原始开始时间
    original_end: float      # LLM 建议的原始结束时间
    aligned_start: float     # 对齐到 I 帧后的开始时间
    aligned_end: float       # 对齐到 I 帧后的结束时间
    start_expansion: float   # 向前扩展量（秒）
    end_expansion: float     # 向后扩展量（秒）
    keyframe_aligned: bool   # 是否成功对齐到关键帧
```

### 关键帧分析流程

```
ffprobe -v quiet -select_streams v:0 \
  -show_entries frame=pkt_pts_time,pict_type \
  -of csv=p=0 input.mp4
```

输出原始数据：
```
0.000000,I     ← I 帧（关键帧）
2.500000,P     ← P 帧（非关键帧）
5.000000,I     ← I 帧（关键帧）
7.500000,B     ← B 帧（非关键帧）
10.000000,I    ← I 帧（关键帧）
```

解析逻辑：只保留 `pict_type=I` 的行，收集所有 I 帧的时间戳。

### 对齐算法

#### 边界对齐 `align_boundary(start_time, end_time, strategy)`

以 `balanced` 策略为例：

```python
# balanced 策略
aligned_start = align_to_previous_kf(start_time, max_expansion=3.0)
aligned_end   = align_to_next_kf(end_time, max_expansion=3.0)
```

**扩展限制机制**：`_align_with_limit(target_time, direction, max_expansion)`

- 如果最近的 I 帧距离目标不超过 `max_expansion`（默认3秒），直接对齐到该 I 帧
- 如果超过3秒，则只扩展 `max_expansion` 秒（从目标位置向前/后推3秒），避免过度扩展

```
例：目标时间 10.5s
    最近前向 I 帧: 8.0s（距离 2.5s，未超3秒）→ 对齐到 8.0s
    最近前向 I 帧: 5.0s（距离 5.5s，超3秒）  → 扩展到 7.5s（10.5 - 3.0）
```

#### 最近关键帧查找 `find_nearest_keyframe(target_time, direction)`

使用**二分查找**（`O(log N)`）定位目标时间在 I 帧列表中的位置：

```python
left, right = 0, len(keyframes)
while left < right:
    mid = (left + right) // 2
    if keyframes[mid].timestamp < target_time:
        left = mid + 1
    else:
        right = mid
```

### 五种对齐策略

| 策略 | `start_time` 对齐 | `end_time` 对齐 | 扩展限制 | 推荐场景 |
|------|-------------------|----------------|---------|---------|
| **balanced**（默认） | 向前找最近 I 帧 | 向后找最近 I 帧 | 最大3秒 | 大多数场景 |
| **content_preserving** | 向前找最近 I 帧 | 向后找最近 I 帧 | 无严格限制 | 内容完整性优先 |
| **strict** | 找最近的 I 帧（双向） | 找最近的 I 帧（双向） | 无 | 追求精确时间 |
| **previous** | 前一个 I 帧 | 前一个 I 帧 | 无 | 保守方案 |
| **next** | 后一个 I 帧 | 后一个 I 帧 | 无 | 严格方案 |

### FFmpeg 切割命令

提供两种 seek 模式：

```python
# fast 模式：-ss 在 -i 之前，-c copy 无损切割（需关键帧对齐）
ffmpeg -ss 10.000000 -i input.mp4 -t 11.000000 \
  -c:v copy -c:a copy -avoid_negative_ts make_zero -y output.mp4

# accurate 模式：-ss 在 -i 之后，重编码精确切割（无需关键帧对齐）
ffmpeg -i input.mp4 -ss 10.000000 -t 11.000000 \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 192k -y output.mp4
```

**推荐**：`fast` 模式 + 关键帧对齐 = 无损 + 快速 + 同步

---

## 集成点

### 1. VideoProcessor（批量处理入口）

[`backend/utils/video_processor.py`](../backend/utils/video_processor.py) `batch_extract_clips()`

```python
def batch_extract_clips(self, input_video, clips_data):
    # 1. 创建 KeyframeAligner
    keyframe_aligner = KeyframeAligner(input_video)
    keyframe_aligner.ensure_initialized()

    # 2. 批量对齐所有切片
    aligned_clips_data = keyframe_aligner.align_clips(clips_data, strategy="balanced")

    # 3. 逐个切割（使用对齐后的时间）
    for clip_data in aligned_clips_data:
        start_time = clip_data['start_time']    # 对齐后的时间
        end_time   = clip_data['end_time']      # 对齐后的时间
        # 记录原始时间用于元数据同步
        original_start = clip_data.get('original_start', start_time)
        original_end   = clip_data.get('original_end', end_time)
        ...
```

### 2. Step6 VideoGenerator（元数据同步）

[`backend/pipeline/step6_video.py`](../backend/pipeline/step6_video.py) `generate_clips()`

```python
# 切割完成后，将对齐前后的时间写回元数据
for clip in clips_with_titles:
    for processed_clip in processed_clips_data:
        if processed_clip['id'] == clip['id']:
            clip['start_time'] = processed_clip['start_time']           # 对齐后
            clip['end_time']   = processed_clip['end_time']             # 对齐后
            clip['original_start_time'] = processed_clip['original_start']  # 原始
            clip['original_end_time']   = processed_clip['original_end']    # 原始
```

这样前端可以通过 `original_start_time` / `original_end_time` 展示 LLM 识别的原始时间，而 `start_time` / `end_time` 是实际切割时间。

图例如下：

```
原始时间线:  |----[话题A]----[话题B]----[话题C]----|
LLM识别边界:     10.5-20.8     25.3-35.6     40.1-55.2
                    ↓对齐           ↓对齐           ↓对齐
实际切割时间: 10.0-21.0     25.0-36.0     40.0-55.5
                  ↑              ↑              ↑
                 I帧=10.0      I帧=25.0      I帧=40.0
前端显示:     10.5-20.8     25.3-35.6     40.1-55.2（原始时间）
```

### 3. Step2 TimelineExtractor（关键帧验证）

[`backend/pipeline/step2_timeline.py`](../backend/pipeline/step2_timeline.py)

在时间线提取阶段可选地传入 `video_path`，让 LLM 返回的边界经过关键帧验证：

```python
class TimelineExtractor:
    def __init__(self, ..., video_path=None):
        self.video_path = video_path
        if video_path:
            self.keyframe_analyzer = KeyframeAligner(video_path, lazy_load=True)

    def _validate_with_keyframes(self, timeline_data):
        """仅提供对齐建议，不修改原始边界"""
        for item in timeline_data:
            start = parse_time(item['start_time'])
            end = parse_time(item['end_time'])
            suggestion = self.keyframe_analyzer.align_boundary(start, end, "balanced")
            item['keyframe_suggestion'] = {
                'suggested_start': format_time(suggestion.aligned_start),
                'suggested_end': format_time(suggestion.aligned_end),
                'start_expansion': suggestion.start_expansion,
                'end_expansion': suggestion.end_expansion,
            }
```

---

## 时间格式规范

项目中存在三种时间格式，必须严格区分：

| 用途 | 格式 | 示例 | 说明 |
|------|------|------|------|
| **FFmpeg 命令** | `hh:mm:ss.frac`（点号） | `00:10:05.500` | FFmpeg 只认点号 |
| **SRT 字幕** | `hh:mm:ss,frac`（逗号） | `00:10:05,500` | SRT 标准格式 |
| **内部计算** | 秒（float） | `605.5` | Python 内部统一用秒 |

### 格式转换函数

```python
# FFmpeg 格式 → 秒
00:10:05.500 → 605.5

# 秒 → FFmpeg 格式
605.5 → 00:10:05.500

# SRT 格式 → FFmpeg 格式
00:10:05,500 → 00:10:05.500（逗号替换为点号）
```

**关键修复记录**：`_format_time()` 方法早期返回了逗号格式（`00:00:10,500`），导致 FFmpeg 解析失败、生成的视频文件损坏。修复后统一返回点号格式（`00:00:10.500`）。

---

## 容错与降级机制

### 三级容错

| 场景 | 降级路径 | 效果 |
|------|---------|------|
| **ffprobe 不可用** | ffprobe 不在 PATH → 从 ffmpeg 同目录查找 → 回退到默认 `ffprobe` 命令 | 仍可使用 ffmpeg 获取视频时长 |
| **关键帧分析失败** | 分析异常/超时 → `keyframes = []` → 获取视频时长 | 回退到固定2秒前后扩展 |
| **时长也无法获取** | `_get_video_duration()` 全部失败 → 返回 `0.0` | 回退到最小扩展0.5秒 |

### 自动查找 ffprobe 路径

```python
def _find_ffprobe_path():
    # 1. 系统 PATH 中的 ffprobe
    # 2. 从 ffmpeg 同目录推断 ffprobe.exe
    # 3. 同目录下带/不带 .exe 扩展名试探
    # 4. 返回 "ffprobe" 让 subprocess 尝试
```

### 视频时长获取双重保障

```python
def _get_video_duration():
    # 1. 优先使用 ffmpeg（更可靠：从 stderr 解析 Duration: 行）
    # 2. 备用使用 ffprobe（-show_entries format=duration）
```

---

## 性能数据

### 关键帧分析耗时

| 视频时长 | 分析时间 | 额外处理时间 |
|---------|---------|------------|
| 30分钟 | ~2秒 | +5% |
| 1小时 | ~4秒 | +5% |
| 2小时 | ~8秒 | +5% |

### 优化前后对比

| 指标 | 原方案（固定2秒扩展） | 优化方案（关键帧对齐） |
|------|---------------------|---------------------|
| 开头截断率 | ~15% | ~5% |
| 结尾截断率 | ~12% | ~3% |
| 花屏率 | ~8% | ~1% |
| 内容完整性 | ~85% | ~95% |

### 缓存机制

```json
// metadata/keyframe_cache/{video_name}_keyframes.json
{
  "video_path": "xxx.mp4",
  "duration": 3600.0,
  "keyframes": [
    {"timestamp": 0.0, "frame_number": 0},
    {"timestamp": 2.5, "frame_number": 1},
    ...
  ]
}
```

缓存生命周期：与视频文件绑定。视频不变化，缓存不失效。

---

## 完整数据流示例

### 输入

```json
// LLM 识别的片段
[
  {"id": 1, "title": "话题A", "start_time": "00:10:05,500", "end_time": "00:15:30,200"}
]
```

### 对齐过程

```python
aligner = KeyframeAligner("input.mp4")
aligned = aligner.align_boundary(
    start_time=605.5,  # 00:10:05.500
    end_time=930.2,     # 00:15:30.200
    strategy="balanced"
)

# 输出
AlignedBoundary(
    original_start=605.5,
    original_end=930.2,
    aligned_start=604.0,     # 扩展了1.5秒向前对齐到 I 帧
    aligned_end=932.0,       # 扩展了1.8秒向后对齐到 I 帧
    start_expansion=1.5,
    end_expansion=1.8,
    keyframe_aligned=True
)
```

### FFmpeg 命令

```bash
ffmpeg -ss 604.000000 -i input.mp4 -t 328.000000 \
  -c:v copy -c:a copy -avoid_negative_ts make_zero -y output.mp4
```

### 元数据

```json
// clips_metadata.json
{
  "id": 1,
  "title": "话题A",
  "start_time": "00:10:04.000",
  "end_time": "00:15:32.000",
  "original_start_time": "00:10:05,500",
  "original_end_time": "00:15:30,200",
  "start_expansion": 1.5,
  "end_expansion": 1.8,
  "keyframe_aligned": true
}
```

---

## 配置参考

### KeyframeAligner 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `video_path` | (必填) | 视频文件路径 |
| `cache_dir` | `None` | 缓存目录（可选） |
| `lazy_load` | `True` | 懒加载模式（初始化时不立即分析） |
| `max_expansion_seconds` | `3.0` | 最大扩展秒数 |

### 禁用关键帧对齐

```python
VideoProcessor.extract_clip(
    input_video, output_path,
    start_time, end_time,
    use_keyframe_alignment=False  # 禁用
)
```

---

## 文档索引

| 文档 | 内容 | 文件 |
|------|------|------|
| **本方案文档** | 音视频同步完整架构 | `docs/AV_SYNC_ARCHITECTURE.md` |
| 实施报告 | KeyframeAligner 开发过程 | `docs/KEYFRAME_ALIGNMENT_IMPLEMENTATION.md` |
| 时间格式修复 | 逗号→点号格式修复 | `docs/KEYFRAME_ALIGNMENT_FIX_REPORT.md` |
| 切片修复 | ffprobe 不可用降级 | `docs/VIDEO_SLICE_FIX_REPORT.md` |
| 核心源码 | KeyframeAligner 完整实现 | `backend/utils/keyframe_aligner.py` |
| 视频处理器 | 集成对齐 + 批量切割 | `backend/utils/video_processor.py` |
| 视频生成步骤 | 元数据同步 | `backend/pipeline/step6_video.py` |