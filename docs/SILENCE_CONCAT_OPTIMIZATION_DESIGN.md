# SilenceConcat 性能优化设计文档

## 1. 概述

### 1.1 目标

消除 `SilenceConcat.process_clip()` 中的冗余编码步骤，将多段 ffmpeg 调用合并为单次 filter_complex 调用，减少约 50% 处理耗时并降低画质损耗。

### 1.2 范围

只修改 **`backend/utils/silence_concat.py`** 一个文件。所有外部接口不变，调用方（`funclip_style.py`、`video_processor.py`）无需任何改动。

---

## 2. 现状分析

### 2.1 当前调用链

以一个含中间静音的切片（3 段语音）为例：

```
process_clip(clip.mp4)
  ├── _get_media_duration()          ffprobe ①    获取时长
  ├── _extract_audio()               ffmpeg ②    解码视频 → 写入 audio.wav
  ├── _detect_silence_ffmpeg()       ffmpeg ③    读取 audio.wav → 静音检测
  ├── (Python 逻辑)                              静音→语音反转、合并短间隔
  ├── _split_video()                 ffmpeg ④⑤⑥  3 次编码 → seg_0,1,2.mp4
  └── _concat_videos()               ffmpeg ⑦    1 次编码 → final.mp4
```

**合计**: 7 次 ffmpeg 调用，5 次编码，3 个临时文件

### 2.2 冗余分析

| 冗余点 | 说明 | 浪费 |
|--------|------|------|
| 音频提取 | 先写 WAV 再检测；silencedetect 可直接读视频 | 1 次编解码 + 文件 I/O |
| 分步 split+concat | 每段单独编码再拼接；filter_complex 可一次完成 | (N-1) 次编码 |
| 临时文件 | seg_0.mp4 等写入磁盘再读取 | N 次文件 I/O |

### 2.3 耗时估算

| 阶段 | 耗时 | 占比 |
|------|:----:|:----:|
| 音频提取 + 检测 | ~20s | 31% |
| 分割 (3 段) | ~30s | 46% |
| 拼接 | ~15s | 23% |
| **合计** | **~65s** | **100%** |

---

## 3. 优化设计

### 3.1 优化策略

**策略一：跳过音频提取环节**

`ffmpeg` 的 `silencedetect` 滤镜可以直接读取视频文件的音频流，无需预先提取 WAV 文件。

```
改动前: clip.mp4 → ffmpeg -vn -acodec pcm_s16le audio.wav → ffmpeg -i audio.wav -af silencedetect
改动后: clip.mp4 → ffmpeg -i clip.mp4 -af silencedetect                                  ✓
```

仅需删除 `_extract_audio()` 调用，`_detect_silence_ffmpeg()` 的入参改为直接传视频路径，内部逻辑无变化。

**策略二：filter_complex 合并 split+concat 为单次调用**

利用 `ffmpeg` 的 filter_complex，将"多段 trim + concat"合成一个滤镜图，单次调用完成全部操作，只编码 1 次。

```
改动前: ffmpeg -ss t1 -i clip.mp4 -t d1 seg_0.mp4          (编码①)
        ffmpeg -ss t2 -i clip.mp4 -t d2 seg_1.mp4          (编码②)
        ffmpeg -f concat -i list.txt -c:v libx264 final.mp4 (编码③)

改动后: ffmpeg -i clip.mp4 -filter_complex "
          [0:v]trim=start=t1:end=t2,setpts=PTS-STARTPTS[v0];
          [0:a]atrim=start=t1:end=t2,asetpts=PTS-STARTPTS[a0];
          [0:v]trim=start=t3:end=t4,setpts=PTS-STARTPTS[v1];    ← 一次 split
          [0:a]atrim=start=t3:end=t4,asetpts=PTS-STARTPTS[a1];
          [v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa]
        " -map [outv] -map [outa] -c:v libx264 final.mp4       ← 编码①
```

**策略三：保留现有方法（不改接口）**

- `_get_media_duration()`：保留，仍用于时长获取
- `_fallback_copy()`：保留，回退逻辑
- `_concat_videos()`：保留，兼容接口 `process_and_concat()`/`concat_videos()` 仍使用
- `_split_video()`：**删除**，不再调用
- `_extract_audio()`：**删除**，不再需要

---

## 4. 详细变更

### 4.1 文件修改清单

**文件**: `backend/utils/silence_concat.py`

#### 变更 1：删除倒计时引入

```
- import shutil               ← 保留（_fallback_copy 仍使用）
  无其他导入变更
```

#### 变更 2：`process_clip()` — 简化音频处理 (第 64~72 行)

```python
# 改动前
audio_dir = output_video.parent / f".silence_temp_{clip_id}" if clip_id else \
    output_video.parent / ".silence_temp"
audio_dir.mkdir(parents=True, exist_ok=True)
audio_path = audio_dir / "audio.wav"
if not self._extract_audio(input_video, audio_path):
    logger.warning(f"{clip_tag} 音频提取失败，跳过静音处理")
    return self._fallback_copy(input_video, output_video)
silence_ranges = self._detect_silence_ffmpeg(audio_path)

# 改动后
silence_ranges = self._detect_silence_ffmpeg(input_video)
```

#### 变更 3：`process_clip()` — 多段路径替换 (第 138~145 行)

```python
# 改动前
segment_paths = self._split_video(input_video, merged, audio_dir, clip_id)
if not segment_paths:
    logger.warning(f"{clip_tag} 分割失败，跳过静音处理")
    return self._fallback_copy(input_video, output_video)
success = self._concat_videos(segment_paths, output_video)

# 改动后
success = self._filter_complex_trim_concat(input_video, output_video, merged)
```

#### 变更 4：`process_clip()` — 清理逻辑简化 (第 150~152 行)

```python
# 改动前
self._cleanup(audio_dir)
# 改动后
# (无临时文件需要清理)
```

#### 变更 5：新增 `_filter_complex_trim_concat()` 方法

```python
def _filter_complex_trim_concat(self, input_video: Path, output_video: Path,
                                 segments: List[Tuple[float, float]]) -> bool:
    """
    单次 ffmpeg filter_complex 调用完成多段 trim + concat。

    原理：
      [0:v]split → trim(段0), trim(段1), ... → concat → 输出
      [0:a]asplit → atrim(段0), atrim(段1), ... → concat → 输出

    Args:
        input_video:  输入视频文件
        output_video: 输出视频文件
        segments:     [(start, end), ...] 语音区间列表

    Returns:
        是否成功
    """
    # 1) 应用 buffer 并过滤过短段
    buffered = self._apply_buffer_non_overlap(segments)
    valid = [(s, e) for s, e in buffered if e - s > 0.3]
    n = len(valid)

    if n == 0:
        logger.warning("filter_complex trim+concat: 无有效段")
        return False

    if n == 1:
        # 单段 → 简单 trim（无需 concat）
        s, e = valid[0]
        dur = e - s
        try:
            cmd = [
                'ffmpeg', '-ss', f'{s:.3f}',
                '-i', str(input_video),
                '-t', f'{dur:.3f}',
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-c:a', 'aac', '-b:a', '192k',
                '-y', str(output_video)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    encoding='utf-8', errors='ignore', timeout=300)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"filter_complex trim (单段) 异常: {e}")
            return False

    # 2) 构建 filter_complex 字符串
    parts = []
    for i, (s, e) in enumerate(valid):
        parts.append(
            f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}];"
            f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}];"
        )
    concat_inputs = ''.join(f'[v{i}][a{i}]' for i in range(n))
    parts.append(f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]")
    filter_complex = ''.join(parts)

    # 3) 单次 ffmpeg 调用
    try:
        cmd = [
            'ffmpeg',
            '-i', str(input_video),
            '-filter_complex', filter_complex,
            '-map', '[outv]',
            '-map', '[outa]',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '192k',
            '-y', str(output_video)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True,
                                encoding='utf-8', errors='ignore', timeout=600)
        if result.returncode == 0:
            logger.info(f"filter_complex trim+concat 完成: {n}段 -> {output_video.name}")
            return True
        else:
            logger.error(f"filter_complex 失败: {result.stderr[:300]}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("filter_complex trim+concat 超时")
        return False
    except Exception as e:
        logger.error(f"filter_complex trim+concat 异常: {e}")
        return False
```

#### 变更 6：删除 `_split_video()` 方法

整个方法体删除，不再被任何代码调用。

#### 变更 7：删除 `_extract_audio()` 方法

整个静态方法删除。

### 4.2 保留不变的方法

| 方法 | 说明 |
|------|------|
| `__init__()` | 配置参数不变 |
| `process_clip()` | 接口不变，内部逻辑简化为 3 处改动 |
| `_get_media_duration()` | 保持不变 |
| `_detect_silence_ffmpeg()` | 接口不变，输入从 audio 变为 video |
| `_silence_to_speech()` | 无变更 |
| `_merge_segments()` | 无变更 |
| `_apply_buffer_non_overlap()` | 无变更 |
| `_concat_videos()` | 保留，兼容旧接口 |
| `_cleanup()` | 保留，兼容旧接口 |
| `_fallback_copy()` | 保留，多处回退使用 |
| `process_and_concat()` | 保留，兼容旧接口 |
| `extract_speech_segments()` | 保留，兼容旧接口 |
| `concat_videos()` | 保留，兼容旧接口 |

---

## 5. 优化后调用链

### 5.2 多输入 concat 方案（最终方案）

#### 原理

利用 ffmpeg 的多输入能力，每个语音段作为独立输入（`-ss` 快速定位），filter_complex 只做 `concat`，无需 `trim`：

```
ffmpeg -ss s1 -t d1 -i clip.mp4 \     ← 输入 0：只解码段0（input seeking）
       -ss s2 -t d2 -i clip.mp4 \     ← 输入 1：只解码段1（input seeking）
       -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]"
       -map [outv] -map [outa] -c:v libx264 output.mp4
```

**为什么快**：每个 `-ss -i` 只解码对应的语音段（input seeking 到关键帧），这是最快的解码方式。filter_complex 仅做 concat，复杂度极低。

#### 方案对比

| 方案 | 解码量 | 编码次数 | 临时文件 | ffmpeg 调用 |
|------|:-----:|:-------:|:-------:|:----------:|
| 旧 split+concat | 语音段长 × 2 | 2 | N 个 | N+1 |
| filter_complex (错误) | 全长 × N | 1 | 0 | 1 |
| **多输入 concat (最终)** | **语音段长** | **1** | **0** | **1** |

#### 代码实现

```python
def _filter_complex_trim_concat(self, input_video, output_video, segments):
    valid = self._apply_buffer_non_overlap(segments)
    # ...
    # 多输入命令
    cmd = ['ffmpeg']
    for s, e in valid:
        dur = e - s
        cmd.extend(['-ss', f'{s:.3f}', '-t', f'{dur:.3f}', '-i', str(input_video)])
    
    # concat filter
    concat_inputs = ''.join(f'[{i}:v][{i}:a]' for i in range(n))
    fc = f'{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]'
    cmd.extend(['-filter_complex', fc, '-map', '[outv]', '-map', '[outa]',
                '-c:v', 'libx264', '-c:a', 'aac', '-y', str(output_video)])
    # 执行...
```

---

## 6. 验证方案

### 6.1 正确性验证

| # | 测试 | 预期 | 通过标准 |
|:-:|------|------|---------|
| 1 | `test_silence_processing.py` (6 场景) | 全部 PASS | 无回归 |
| 2 | `test_integration_silence.py` (4 场景) | 全部 PASS | 无回归 |
| 3 | 输出时长一致性 | 新旧方案差值 < 0.5s | 精度无损 |

### 6.2 性能验证

| # | 测试 | 预期 | 通过标准 |
|:-:|------|------|---------|
| 4 | 相同输入，新旧方案耗时对比 | 新方案 ≤ 旧方案 60% | 优化有效 |

---

## 7. 回退策略

任何环节失败时，`process_clip()` 保持现有行为不变：

```python
# 外层 try-except 包裹
try:
    success = self._filter_complex_trim_concat(input_video, output_video, merged)
    if not success:
        return self._fallback_copy(input_video, output_video)
except Exception:
    return self._fallback_copy(input_video, output_video)
```

优化只改实现不改接口，不会对 `funclip_style.py` 和 `video_processor.py` 产生任何影响。