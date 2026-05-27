# FFmpeg视频提取修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复视频提取过程中音画不同步、重复卡顿、静音未剔除三大问题

**Architecture:** 通过修改两个FFmpeg调用点解决问题：(1) `VideoProcessor.extract_clip` 将 `-ss before -i` fast seek 改为 `-ss after -i` frame-accurate seek，放弃 stream copy 改用重编码以获得帧级精确度；(2) `_extract_multi_segment_clip` 放弃"分段提取+concat协议拼接"两阶段方案，改用单次FFmpeg调用的 `filter_complex concat` filter，消除PTS时间戳紊乱。

**Tech Stack:** FFmpeg, Python subprocess, filter_complex

---

### Task 1: 修复 `VideoProcessor.extract_clip` — 单段视频提取

**Files:**
- Modify: `backend/utils/video_processor.py:129-183`

- [ ] **Step 1: 确认当前代码**

Read the current `extract_clip` method at `backend/utils/video_processor.py:129-183` to confirm the code matches the expected state.

- [ ] **Step 2: 修改FFmpeg命令 — 改为 `-ss after -i` + `-to` + 重编码**

将 L159-L169 的FFmpeg命令从：
```python
# 构建优化的FFmpeg命令
# 使用 -ss 在输入前进行精确定位，使用 -t 指定持续时间
cmd = [
    'ffmpeg',
    '-ss', ffmpeg_start_time,  # 在输入前定位，更精确
    '-i', str(input_video),
    '-t', str(duration),  # 使用持续时间而不是绝对结束时间
    '-c:v', 'copy',  # 复制视频流
    '-c:a', 'copy',  # 复制音频流
    '-avoid_negative_ts', 'make_zero',
    '-y',  # 覆盖输出文件
    str(output_path)
]
```

修改为：

```python
cmd = [
    'ffmpeg',
    '-i', str(input_video),
    '-ss', ffmpeg_start_time,
    '-to', ffmpeg_end_time,
    '-c:v', 'libx264',
    '-preset', 'fast',
    '-crf', '23',
    '-c:a', 'aac',
    '-b:a', '128k',
    '-y',
    str(output_path)
]
```

改动说明：
1. `-ss ffmpeg_start_time` 从 `-i` 前面移到后面 → fast seek → frame-accurate seek，解码到精确帧位置
2. `-t str(duration)` → `-to ffmpeg_end_time` → 从相对时长改为绝对结束时间，解决结尾被截断问题
3. `-c:v copy` → `-c:v libx264 -preset fast -crf 23` → 流复制→重编码，帧精确的前提（stream copy只能从关键帧开始）
4. `-c:a copy` → `-c:a aac -b:a 128k` → 音频重编码
5. 删除 `-avoid_negative_ts make_zero` → 此参数仅在 stream copy 时需要，重编码下无关

- [ ] **Step 3: 删除不再需要的 `duration` 计算代码**

L153-L155 中计算 `duration` 的代码在 `-t` 被移除后不再需要，但保留 `start_seconds` 和 `end_seconds` 用于日志。修改为只保留日志中用到的变量：

```python
# 转换时间格式：从SRT格式转换为FFmpeg格式
ffmpeg_start_time = VideoProcessor.convert_srt_time_to_ffmpeg_time(start_time)
ffmpeg_end_time = VideoProcessor.convert_srt_time_to_ffmpeg_time(end_time)

# 构建精确帧定位的FFmpeg命令
# -ss 在 -i 之后：帧精确定位
# -to 指定绝对结束时间
# -c:v libx264 重编码：帧精确的前提
cmd = [
    ...
]
```

可删除 `start_seconds = ...`、`end_seconds = ...`、`duration = ...` 这三行，日志中改为直接使用 `ffmpeg_start_time` 和 `ffmpeg_end_time` 输出：

```python
if result.returncode == 0:
    # 从ffmpeg时间字符串计算时长用于日志
    start_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(ffmpeg_start_time)
    end_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(ffmpeg_end_time)
    duration = end_sec - start_sec
    logger.info(f"成功提取视频片段: {output_path} ({ffmpeg_start_time} -> {ffmpeg_end_time}, 时长: {duration:.2f}秒)")
    return True
```

- [ ] **Step 4: 验证修改后的完整函数**

最终 `extract_clip` 方法应如下：

```python
@staticmethod
def extract_clip(input_video: Path, output_path: Path,
                start_time: str, end_time: str) -> bool:
    """
    从视频中提取指定时间段的片段（帧精确模式）

    Args:
        input_video: 输入视频路径
        output_path: 输出视频路径
        start_time: 开始时间 (格式: "00:01:25,140")
        end_time: 结束时间 (格式: "00:02:53,500")

    Returns:
        是否成功
    """
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 转换时间格式：从SRT格式转换为FFmpeg格式
        ffmpeg_start_time = VideoProcessor.convert_srt_time_to_ffmpeg_time(start_time)
        ffmpeg_end_time = VideoProcessor.convert_srt_time_to_ffmpeg_time(end_time)

        # 构建精确帧定位的FFmpeg命令
        cmd = [
            'ffmpeg',
            '-i', str(input_video),
            '-ss', ffmpeg_start_time,
            '-to', ffmpeg_end_time,
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-y',
            str(output_path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')

        if result.returncode == 0:
            start_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(ffmpeg_start_time)
            end_sec = VideoProcessor.convert_ffmpeg_time_to_seconds(ffmpeg_end_time)
            duration = end_sec - start_sec
            logger.info(f"成功提取视频片段: {output_path} ({ffmpeg_start_time} -> {ffmpeg_end_time}, 时长: {duration:.2f}秒)")
            return True
        else:
            logger.error(f"提取视频片段失败: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"视频处理异常: {str(e)}")
        return False
```

---

### Task 2: 修复 `_extract_multi_segment_clip` — 多段拼接提取

**Files:**
- Modify: `backend/pipeline/funclip_style.py:991-1077`

- [ ] **Step 1: 确认当前代码**

Read the current `_extract_multi_segment_clip` function at `backend/pipeline/funclip_style.py:991-1077` to confirm it matches the expected state.

- [ ] **Step 2: 重写完整函数 — 单次 filter_complex concat 调用**

将 `_extract_multi_segment_clip` 函数体完全替换为以下代码：

```python
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
            f"[0:a]atrim=start={start_sec}:end={end_sec},asetpts=PTS-STARTPTS[a{label_idx}]"
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
        result = subprocess.run(cmd, capture_output=True,
                                encoding='utf-8', errors='ignore', timeout=600)
        if result.returncode == 0:
            logger.info(f"多段拼接成功: {label_idx}段 -> {output_path}")
            return True
        else:
            logger.error(f"多段拼接失败: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"多段提取异常: {e}")
        return False
```

关键设计要点：
1. **filter 构建**：每段生成一对 `trim + setpts`（视频）和 `atrim + asetpts`（音频）filter
2. **PTS归零**：`setpts=PTS-STARTPTS` 和 `asetpts=PTS-STARTPTS` 确保每个段的PTS从0开始，concat filter要求所有子流PTS连续
3. **concat 拼接**：`concat=n=N:v=1:a=1` 将N段音视频精确拼接，输出标签 `[outv][outa]`
4. **无需临时文件**：所有处理在内存中完成，删除temp_file清理代码
5. **参数兼容**：`temp_dir` 参数保留但不使用，保持函数签名不变

- [ ] **Step 3: 验证filter_complex输出**

对于一个包含2个段的segments列表：
```python
segments = [
    {'start': '00:02:01,904', 'end': '00:02:34,576'},
    {'start': '00:02:52,860', 'end': '00:03:58,803'}
]
```

生成的 filter_complex 字符串应为：
```
[0:v]trim=start=121.904:end=154.576,setpts=PTS-STARTPTS[v0];
[0:a]atrim=start=121.904:end=154.576,asetpts=PTS-STARTPTS[a0];
[0:v]trim=start=172.86:end=238.803,setpts=PTS-STARTPTS[v1];
[0:a]atrim=start=172.86:end=238.803,asetpts=PTS-STARTPTS[a1];
[v0][a0][v1][a1]concat=n=2:v=1:a=1[outv][outa]
```

concat filter将：
1. [v0] PTS范围 0~32.672 + [v1] PTS范围 0~65.943
2. 按 [v0][a0]→[v1][a1] 顺序拼接 → 输出PTS 0~98.615
3. 音视频精确对齐，无gap无重叠

---

### Task 3: 验证构建无语法错误

**Files:**
- No file changes

- [ ] **Step 1: 检查 Python 语法**

```bash
python -m py_compile backend/utils/video_processor.py
python -m py_compile backend/pipeline/funclip_style.py
```

Expected: No SyntaxError

- [ ] **Step 2: 检查导入和符号引用**

确保 `funclip_style.py` 顶部保留 `import subprocess`，同时确认 `_srt_time_to_seconds` 函数在文件中存在（L387）。

确保 `video_processor.py` 顶部保留 `import subprocess`，且 `convert_ffmpeg_time_to_seconds` 方法存在。

---

### Task 4: 端到端功能测试

**Files:**
- Test: 使用现有测试脚本或手动执行pipeline

- [ ] **Step 1: 准备测试输入**

准备一个短视频（~1分钟）及其对应的SRT字幕文件，包含：
- 至少3个非连续话题段（触发多段拼接）
- 段间有超过2秒的静音间隙（触发静音剔除）

- [ ] **Step 2: 执行 funclip pipeline**

```bash
cd backend
python -c "
from backend.pipeline.funclip_style import run_funclip_pipeline
from pathlib import Path

srt_path = Path('pipeline/test_srt_simple.srt')
video_path = Path('path/to/test_video.mp4')
metadata_dir = Path('../data/test_metadata')
clips_dir = Path('../data/test_clips')
collections_dir = Path('../data/test_collections')

clips, collections = run_funclip_pipeline(
    srt_path, video_path, metadata_dir,
    clips_dir, collections_dir,
    processing_mode='merged'
)
print(f'Generated {len(clips)} clips')
"
```

- [ ] **Step 3: 验证输出视频**

使用FFmpeg验证每个输出视频：
```bash
# 检查时长是否与预期一致
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 output_clip.mp4

# 检查是否有编码错误
ffmpeg -v error -i output_clip.mp4 -f null -
```

- [ ] **Step 4: 验证音画同步**

使用 `ffprobe` 检查音视频流的时间基是否一致：
```bash
ffprobe -v error -select_streams v:0 -show_entries stream=time_base,start_time,duration -of default=noprint_wrappers=1:nokey=1 output_clip.mp4
ffprobe -v error -select_streams a:0 -show_entries stream=time_base,start_time,duration -of default=noprint_wrappers=1:nokey=1 output_clip.mp4
```

- [ ] **Step 5: 清理测试数据**

```bash
rm -rf ../data/test_metadata ../data/test_clips ../data/test_collections
```