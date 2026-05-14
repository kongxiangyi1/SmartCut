# 静音处理方案

## 1. 概述

### 1.1 问题背景

视频切片中存在长静音问题，影响用户观看体验。当前代码中的静音处理逻辑存在缺陷，需要优化。

### 1.2 现有问题

当前 `silence_processor.py` 中的 `adjust_clip_for_silence` 方法存在以下问题：

```python
# 当前错误逻辑 (L221-228)
if len(filtered_segments) == 1:
    # 只有1个区间，使用它
    ...
else:
    # 如果有多个区间，只保留最长的 ⚠️ 问题所在
    longest_segment = max(filtered_segments, key=lambda x: x['duration'])
    adjusted_start = max(longest_segment['start'] - buffer_duration, clip_start)
    adjusted_end = min(longest_segment['end'] + buffer_duration, clip_end)
```

**问题**：当切片内有多个语音区间时，代码只保留最长的那个，把其他语音内容直接丢弃。

### 1.3 目标

- 精确去除静音，保留所有语音内容
- 处理开头静音、中间静音、结尾静音
- 保留合理的短静音（让视频更自然）
- 提供可配置的参数

---

## 2. 技术方案

### 2.1 方案对比

| 方案 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| 方案一 | Python代码拼接 | 逻辑清晰 | 无法真正拼接非连续片段 |
| 方案二 | FFmpeg指定时间段拼接 | 精确控制 | 依赖VAD检测结果 |
| 方案三 | FFmpeg silenceremove | 自动处理 | 无法精确控制保留哪些语音 |

### 2.2 推荐方案：方案二+方案三结合

结合两种方案的优势：

```
┌─────────────────────────────────────────────────────────────┐
│                      原始视频切片                             │
│  |---语音A---| 静音3秒 |---语音B---| 静音1秒 |---语音C---|   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: silenceremove 快速去除超长静音（>3秒）              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  |---语音A---| 静音1秒 |---语音B---| 静音1秒 |---语音C---|  │
│                    ↓                                        │
│  Step 2: VAD检测 + FFmpeg拼接 精确保留所有语音区间            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  |---语音A---|---语音B---|---语音C---|                      │
│                      最终输出（无长静音）                     │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 概要设计

### 3.1 模块结构

```
backend/utils/
├── silence_processor.py      # 现有VAD检测模块（保留）
├── silence_concat.py          # 新增：静音拼接模块 ⭐
└── video_processor.py        # 修改：集成静音拼接
```

### 3.2 核心类设计

#### 3.2.1 SpeechSegment 数据类

```python
@dataclass
class SpeechSegment:
    """语音区间"""
    start: float  # 秒
    end: float    # 秒
```

#### 3.2.2 SilenceConcat 类

```python
class SilenceConcat:
    """静音处理与语音拼接器"""

    def __init__(self,
                 long_silence_threshold: float = 3.0,
                 short_silence_keep: float = 1.0,
                 buffer_duration: float = 0.2):
        """
        Args:
            long_silence_threshold: 超过此秒数的静音将被去除（秒）
            short_silence_keep: 保留的短静音阈值（秒）
            buffer_duration: 语音区间前后的缓冲时间（秒）
        """

    def detect_speech_segments(self, audio_path: Path) -> List[SpeechSegment]
    """使用VAD检测语音区间"""

    def merge_segments(self, segments: List[SpeechSegment],
                      max_gap: float = None) -> List[SpeechSegment]
    """合并相邻的语音区间"""

    def process_clip(self, input_video: Path, output_video: Path,
                    clip_start: float, clip_end: float,
                    clip_id: str = None) -> bool
    """完整的静音处理流程"""
```

### 3.3 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `long_silence_threshold` | 3.0秒 | 超过此秒数的静音将被去除 |
| `short_silence_keep` | 1.0秒 | 保留此范围内的短静音 |
| `buffer_duration` | 0.2秒 | 语音区间前后的缓冲时间 |

---

## 4. 详细设计

### 4.1 处理流程

```
输入视频切片 (clip_start ~ clip_end)
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 0: 提取音频 (WAV格式)                                   │
│   - ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000    │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: VAD检测语音区间                                      │
│   - FunASR fsmn-vad 模型                                    │
│   - 备用：能量检测                                           │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: 过滤切片范围内区间                                    │
│   - 只保留 end > clip_start 且 start < clip_end 的区间      │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: 合并短间隔                                            │
│   - 间隔 ≤ short_silence_keep → 合并                       │
│   - 间隔 > short_silence_keep → 新区间                      │
└─────────────────────────────────────────────────────────────┘
     │
     ├─── 只有1个区间? ───→ 直接简单切割
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: FFmpeg切割每个区间                                    │
│   - 每个区间前后 + buffer_duration 缓冲                      │
│   - 保存为临时片段 temp_clip_N.mp4                          │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 5: FFmpeg concat拼接                                    │
│   - 合并所有临时片段                                         │
│   - 输出最终视频                                              │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
清理临时文件 → 完成
```

### 4.2 关键算法

#### 4.2.1 语音区间合并算法

```python
def merge_segments(self, segments: List[SpeechSegment],
                  max_gap: float = None) -> List[SpeechSegment]:
    """合并相邻的语音区间"""
    if max_gap is None:
        max_gap = self.short_silence_keep

    # 按开始时间排序
    sorted_segs = sorted(segments, key=lambda x: x.start)

    merged = [sorted_segs[0]]

    for seg in sorted_segs[1:]:
        gap = seg.start - merged[-1].end

        if gap <= max_gap:
            # 合并：扩展前一个区间的结束时间
            merged[-1].end = max(merged[-1].end, seg.end)
        else:
            # 间隔太大，作为新区间
            merged.append(seg)

    return merged
```

#### 4.2.2 FFmpeg拼接命令

```python
# 方案A：使用 concat filter
filter_complex = (
    "[0:a]atrim=start=0.200:duration=14.800,asetpts=PTS-STARTPTS[v0];"
    "[0:a]atrim=start=30.200:duration=15.600,asetpts=PTS-STARTPTS[v1];"
    "[v0][v1]concat=n=2:v=0:a=1[outa]"
)

cmd = [
    'ffmpeg', '-i', 'input.mp4',
    '-filter_complex', filter_complex,
    '-map', '0:v', '-map', '[outa]',
    '-c:v', 'copy', '-c:a', 'aac',
    'output.mp4'
]

# 方案B：使用 concat demuxer（更简单）
with open('concat_list.txt', 'w') as f:
    f.write("file 'clip_0.mp4'\n")
    f.write("file 'clip_1.mp4'\n")
    f.write("file 'clip_2.mp4'\n")

cmd = [
    'ffmpeg', '-y', '-f', 'concat', '-safe', '0',
    '-i', 'concat_list.txt',
    '-c', 'copy',
    'output.mp4'
]
```

### 4.3 VAD检测实现

```python
def detect_speech_segments(self, audio_path: Path) -> List[SpeechSegment]:
    """使用VAD检测语音区间"""
    try:
        from funasr import AutoModel
        vad_model = AutoModel(model="fsmn-vad", device="cpu")

        vad_result = vad_model.generate(
            input=str(audio_path),
            batch_size_s=300
        )

        segments = []
        for item in vad_result:
            if isinstance(item, dict) and 'value' in item:
                value = item['value']
                if isinstance(value, list):
                    for seg in value:
                        if isinstance(seg, list) and len(seg) >= 2:
                            start = seg[0] / 1000.0  # 毫秒转秒
                            end = seg[1] / 1000.0
                            if end - start >= 0.3:  # 过滤噪音
                                segments.append(SpeechSegment(start, end))

        logger.info(f"VAD检测到 {len(segments)} 个语音区间")
        return segments

    except ImportError:
        logger.warning("FunASR未安装，使用能量检测替代")
        return self._energy_based_detection(audio_path)
    except Exception as e:
        logger.error(f"VAD检测失败: {e}")
        return []
```

### 4.4 能量检测备用方案

```python
def _energy_based_detection(self, audio_path: Path) -> List[SpeechSegment]:
    """基于能量的语音检测（备用方案）"""
    import numpy as np
    import wave

    with wave.open(str(audio_path), 'rb') as wf:
        frames = wf.readframes(wf.getnframes())
        sample_rate = wf.getframerate()

    audio_data = np.frombuffer(frames, dtype=np.int16)

    # 计算能量（10ms窗口）
    window_size = int(sample_rate * 0.1)
    energy = []
    for i in range(0, len(audio_data) - window_size, window_size):
        window = audio_data[i:i+window_size]
        energy.append(np.sqrt(np.mean(window.astype(float)**2)))

    threshold = np.mean(energy) * 0.5
    is_speech = np.array(energy) > threshold

    segments = []
    in_speech = False
    start_idx = 0

    for i, has_speech in enumerate(is_speech):
        if has_speech and not in_speech:
            start_idx = i
            in_speech = True
        elif not has_speech and in_speech:
            segments.append(SpeechSegment(
                start=start_idx * 0.1,
                end=i * 0.1
            ))
            in_speech = False

    return segments
```

---

## 5. 集成设计

### 5.1 与 video_processor.py 集成

```python
# video_processor.py 修改

# 导入新模块
try:
    from .silence_concat import SilenceConcat
    silence_concat_available = True
except ImportError:
    silence_concat_available = False

def batch_extract_clips(self, input_video: Path, clips_data: List[Dict],
                       apply_silence_processing: bool = True) -> List[Path]:
    # ...
    if apply_silence_processing and silence_concat_available:
        # 使用新的静音拼接器
        concat_processor = SilenceConcat(
            long_silence_threshold=3.0,
            short_silence_keep=1.0,
            buffer_duration=0.2
        )

        for clip_data in clips_data:
            # ...
            success = concat_processor.process_clip(
                input_video=input_video,
                output_video=output_path,
                clip_start=start_seconds,
                clip_end=end_seconds,
                clip_id=clip_id
            )
    else:
        # 回退到原有的简单切割
        # ...
```

### 5.2 配置项

在 `backend/core/shared_config.py` 中添加：

```python
# 静音处理配置
SILENCE_CONFIG = {
    "enabled": True,                    # 是否启用静音处理
    "long_silence_threshold": 3.0,      # 长静音阈值（秒）
    "short_silence_keep": 1.0,          # 保留的短静音（秒）
    "buffer_duration": 0.2,             # 语音缓冲时间（秒）
    "use_vad": True,                    # 是否使用VAD检测
    "fallback_to_simple_cut": True,     # VAD失败时回退到简单切割
}
```

---

## 6. 错误处理

### 6.1 异常场景

| 场景 | 处理方式 |
|------|---------|
| FunASR未安装 | 使用能量检测备用方案 |
| 能量检测也失败 | 回退到简单切割 |
| FFmpeg拼接失败 | 回退到简单切割 |
| VAD检测无结果 | 使用原始时间切割 |
| 临时文件创建失败 | 清理并返回错误 |

### 6.2 日志记录

```python
logger.info(f"[{clip_id}] VAD检测到 {len(segments)} 个语音区间")
logger.info(f"[{clip_id}] 原始{len(raw)}段 -> 合并后{len(merged)}段")
logger.warning(f"[{clip_id}] VAD检测失败，使用简单切割")
logger.error(f"[{clip_id}] FFmpeg拼接失败: {error}")
```

---

## 7. 测试计划

### 7.1 单元测试

- [ ] `SpeechSegment` 数据类测试
- [ ] `merge_segments` 合并算法测试
- [ ] 边界条件测试（空区间、重叠区间）

### 7.2 集成测试

- [ ] 完整流程测试（提取音频 → VAD检测 → 合并 → 拼接）
- [ ] 不同类型视频测试（带货、访谈、演讲）
- [ ] 参数配置测试

### 7.3 性能测试

- [ ] VAD检测耗时
- [ ] FFmpeg拼接耗时
- [ ] 内存占用监控

---

## 8. 实施计划

### 8.1 阶段一：文档与设计（P0）

- [x] 问题分析与方案设计
- [x] 编写概要设计文档
- [x] 编写详细设计文档

### 8.2 阶段二：编码实现（P0）

- [ ] 创建 `silence_concat.py` 模块
- [ ] 实现 `SpeechSegment` 数据类
- [ ] 实现 `SilenceConcat` 类
- [ ] 实现 VAD 检测与能量检测
- [ ] 实现 FFmpeg 拼接逻辑
- [ ] 实现错误处理与回退机制

### 8.3 阶段三：集成测试（P1）

- [ ] 集成到 `video_processor.py`
- [ ] 添加配置项
- [ ] 单元测试
- [ ] 集成测试

### 8.4 阶段四：上线与优化（P2）

- [ ] 性能优化
- [ ] 参数调优
- [ ] 监控告警

---

## 9. 附录

### 9.1 参考资料

- [FFmpeg concat filter](https://ffmpeg.org/ffmpeg-filters.html#concat)
- [FFmpeg silenceremove](https://ffmpeg.org/ffmpeg-filters.html#silenceremove)
- [FunASR VAD模型](https://github.com/modelscope/FunASR)

### 9.2 相关文件

| 文件路径 | 说明 |
|---------|------|
| `backend/utils/silence_processor.py` | 现有VAD检测模块 |
| `backend/utils/silence_concat.py` | 新增静音拼接模块 |
| `backend/utils/video_processor.py` | 视频处理器（需修改） |
| `backend/core/shared_config.py` | 配置文件（需添加配置） |
