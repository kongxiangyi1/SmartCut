# 字幕生成系统设计文档

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档名称 | SUBTITLE_GENERATION_DESIGN.md |
| 版本 | v2.0 |
| 创建日期 | 2026-05-13 |
| 状态 | 核心文档 |
| 关联模块 | speech_recognizer, simple_pipeline_adapter |

---

## 1. 概述

### 1.1 文档目的

本文档定义AutoClip项目中字幕生成系统的完整架构和实现逻辑，确保：

- 支持多种语音识别引擎（FunASR、Whisper、bcut-asr等）
- 自动选择最优可用方案
- 具备降级策略，保证系统鲁棒性
- 满足内存限制要求（≤2GB）

### 1.2 设计目标

| 目标 | 说明 |
|------|------|
| **高准确率** | 中文识别准确率 ≥ 95% |
| **低内存占用** | 单次推理内存 ≤ 2GB |
| **快速生成** | 实时率 ≥ 10x（1分钟视频 ≤ 6秒处理） |
| **高可用性** | 多级降级，任何方案都能生成字幕 |
| **零配置** | 默认最优方案，开箱即用 |

---

## 2. 技术方案概览

### 2.1 支持的语音识别方案

| 方案 | 枚举值 | 类型 | 中文准确率 | 内存占用 | 速度 | 成本 |
|------|--------|------|------------|----------|------|------|
| **FunASR** | `funasr` | 本地 | 95%+ | ~1GB | 快 | 免费 |
| Whisper Medium | `whisper_local` | 本地 | 90%+ | ~2GB | 中 | 免费 |
| bcut-asr | `bcut_asr` | 本地 | 85%+ | - | 最快 | 免费 |
| OpenAI API | `openai_api` | 云端 | 93%+ | - | 快 | 付费 |
| Azure Speech | `azure_speech` | 云端 | 93%+ | - | 快 | 付费 |
| Google Speech | `google_speech` | 云端 | 93%+ | - | 快 | 付费 |
| 阿里云语音 | `aliyun_speech` | 云端 | 90%+ | - | 快 | 付费 |

### 2.2 默认方案选择

**当前问题**：原降级顺序为 `bcut-asr → Whisper → None`

**优化后降级顺序**：`FunASR → Whisper Small → bcut-asr → 空字幕`

| 优先级 | 方案 | 选择原因 |
|--------|------|----------|
| **1（首选）** | FunASR Paraformer-zh | 中文准确率最高、内存占用最低 |
| **2** | Whisper Small | 多语言支持、内存适中 |
| **3** | bcut-asr | 速度快、备用方案 |
| **4** | 空字幕 | 降级保底 |

### 2.3 内存限制分析

| 模型 | 参数量 | 模型大小 | 推理内存 | 总内存占用 | 是否满足 |
|------|--------|----------|----------|------------|----------|
| Whisper Large | 1550M | ~3GB | ~8GB | ~10GB+ | ❌ 不满足 |
| Whisper Medium | 769M | ~1.5GB | ~4GB | ~5-6GB | ⚠️ 临界 |
| Whisper Small | 244M | ~500MB | ~2GB | ~3GB | ✅ 满足 |
| **FunASR Paraformer** | - | ~200MB | ~500MB | **~1GB** | ✅✅ 最优 |

---

## 3. 架构设计

### 3.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        调用层                                    │
│  simple_pipeline_adapter / track_project / API                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     字幕生成调度层                               │
│              generate_subtitle_for_video()                       │
│              - 参数标准化                                        │
│              - 方法路由                                          │
│              - 异常处理                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      语音识别引擎层                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  FunASR    │  │   Whisper   │  │  bcut-asr  │  ...        │
│  │ (Paraformer)│  │   (Small)   │  │             │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      输出格式层                                  │
│              SRT / VTT / TXT / JSON                             │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 核心组件

| 组件 | 路径 | 职责 |
|------|------|------|
| `SpeechRecognizer` | `backend/utils/speech_recognizer.py` | 语音识别引擎抽象层 |
| `SpeechRecognitionMethod` | 同上 | 识别方法枚举 |
| `SpeechRecognitionConfig` | 同上 | 配置管理 |
| `generate_subtitle_for_video()` | 同上 | 统一入口函数 |
| `_generate_subtitle_automatically()` | `backend/services/simple_pipeline_adapter.py` | 自动生成调度 |

---

## 4. 详细设计

### 4.1 枚举定义

**文件**：`backend/utils/speech_recognizer.py`

```python
class SpeechRecognitionMethod(str, Enum):
    """语音识别方法枚举"""
    BCUT_ASR = "bcut_asr"
    WHISPER_LOCAL = "whisper_local"
    FUNASR = "funasr"
    OPENAI_API = "openai_api"
    AZURE_SPEECH = "azure_speech"
    GOOGLE_SPEECH = "google_speech"
    ALIYUN_SPEECH = "aliyun_speech"


class LanguageCode(str, Enum):
    """支持的语言代码"""
    CHINESE_SIMPLIFIED = "zh"
    CHINESE_TRADITIONAL = "zh-TW"
    ENGLISH = "en"
    ENGLISH_US = "en-US"
    ENGLISH_UK = "en-GB"
    JAPANESE = "ja"
    KOREAN = "ko"
    FRENCH = "fr"
    GERMAN = "de"
    SPANISH = "es"
    RUSSIAN = "ru"
    ARABIC = "ar"
    PORTUGUESE = "pt"
    ITALIAN = "it"
    AUTO = "auto"
```

### 4.2 配置类

**文件**：`backend/utils/speech_recognizer.py`

```python
@dataclass
class SpeechRecognitionConfig:
    """语音识别配置"""
    method: SpeechRecognitionMethod = SpeechRecognitionMethod.FUNASR
    language: LanguageCode = LanguageCode.AUTO
    model: str = "base"  # Whisper模型大小
    timeout: int = 0  # 超时时间（秒），0表示无限制
    output_format: str = "srt"  # 输出格式
    enable_timestamps: bool = True  # 是否启用时间戳
    enable_punctuation: bool = True  # 是否启用标点符号
    enable_speaker_diarization: bool = False  # 是否启用说话人分离
    enable_fallback: bool = True  # 是否启用回退机制
    fallback_method: SpeechRecognitionMethod = SpeechRecognitionMethod.WHISPER_LOCAL
```

### 4.3 统一入口函数

**文件**：`backend/utils/speech_recognizer.py`

```python
def generate_subtitle_for_video(
    video_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    method: str = "auto",
    model: str = "base",
    language: str = "auto",
    **kwargs
) -> Optional[Path]:
    """
    生成字幕文件的统一入口函数

    Args:
        video_path: 视频文件路径
        output_path: 输出字幕文件路径，默认与视频同目录
        method: 识别方法，支持 "auto", "funasr", "whisper_local", "bcut_asr" 等
        model: 模型大小，仅 Whisper 有效
        language: 语言代码，支持 "auto", "zh", "en" 等

    Returns:
        生成的字幕文件路径，失败返回 None
    """
    # 1. 参数标准化
    video_path = Path(video_path)
    if output_path:
        output_path = Path(output_path)
    else:
        output_path = video_path.parent / f"{video_path.stem}.srt"

    # 2. 方法解析
    if method == "auto":
        # 自动选择最优可用方案（FunASR优先）
        method = _select_best_available_method()
        logger.info(f"自动选择识别方法: {method}")
    else:
        method = SpeechRecognitionMethod(method)

    # 3. 配置构建
    config = SpeechRecognitionConfig(
        method=method,
        language=LanguageCode(language),
        model=model,
        output_format=output_path.suffix[1:] if output_path.suffix else "srt"
    )

    # 4. 执行识别
    recognizer = SpeechRecognizer(config)
    try:
        return recognizer.generate_subtitle(video_path, output_path, config)
    except SpeechRecognitionError as e:
        logger.error(f"字幕生成失败: {e}")
        return None


def _select_best_available_method() -> SpeechRecognitionMethod:
    """
    自动选择最优可用识别方法

    优先级：FunASR > Whisper Small > bcut-asr > Whisper Base
    """
    recognizer = SpeechRecognizer()

    # 1. 优先 FunASR（中文最优、内存最低）
    if recognizer.available_methods.get(SpeechRecognitionMethod.FUNASR, False):
        return SpeechRecognitionMethod.FUNASR

    # 2. 其次 Whisper Small（内存友好、多语言）
    if recognizer.available_methods.get(SpeechRecognitionMethod.WHISPER_LOCAL, False):
        return SpeechRecognitionMethod.WHISPER_LOCAL

    # 3. bcut-asr（快速备用）
    if recognizer.available_methods.get(SpeechRecognitionMethod.BCUT_ASR, False):
        return SpeechRecognitionMethod.BCUT_ASR

    # 4. 默认 Whisper Base
    return SpeechRecognitionMethod.WHISPER_LOCAL
```

### 4.4 FunASR 实现

**文件**：`backend/utils/speech_recognizer.py`

```python
def _generate_subtitle_funasr(self, video_path: Path, output_path: Path,
                               config: SpeechRecognitionConfig) -> Path:
    """使用FunASR生成字幕 - 中文最优方案"""

    # 模型缓存
    global _FUNASR_MODEL_CACHE

    if not self.available_methods[SpeechRecognitionMethod.FUNASR]:
        raise SpeechRecognitionError("FunASR不可用，请安装: pip install funasr")

    try:
        logger.info(f"开始使用FunASR生成字幕: {video_path}")

        # 1. 音频提取
        audio_path = self._extract_audio_from_video(video_path, output_path.parent)

        # 2. 模型加载（使用缓存）
        if _FUNASR_MODEL_CACHE is None:
            logger.info("初始化FunASR模型（首次加载）...")
            from funasr import AutoModel
            _FUNASR_MODEL_CACHE = AutoModel(
                model="paraformer-zh",  # 中文最优模型
                vad_model="fsmn-vad",   # VAD模型
                punc_model="ct-punc",   # 标点模型
                device="cpu",           # CPU推理
                disable_update=True     # 禁用更新检查
            )
            logger.info("FunASR模型加载完成")

        model = _FUNASR_MODEL_CACHE

        # 3. 语音识别
        result = model.generate(
            input=str(audio_path),
            return_timestamp=True
        )

        # 4. 生成SRT文件
        def format_time(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hours:02}:{minutes:02}:{secs:06.3f}".replace('.', ',')

        def split_text_by_punctuation(text):
            sentences = []
            current = ""
            for char in text:
                current += char
                if char in '。！？；\n':
                    sentences.append(current.strip())
                    current = ""
            if current.strip():
                sentences.append(current.strip())
            return sentences

        with open(output_path, 'w', encoding='utf-8') as f:
            segment_index = 1
            for segment in result:
                if isinstance(segment, dict):
                    text = segment.get('text', '').strip()
                    timestamps = segment.get('timestamp', [])

                    if text and timestamps:
                        sentences = split_text_by_punctuation(text)
                        for sentence in sentences:
                            if sentence:
                                start_ms = timestamps[0][0]
                                end_ms = timestamps[-1][1] if len(timestamps) > 1 else start_ms + 1000
                                f.write(f"{segment_index}\n")
                                f.write(f"{format_time(start_ms/1000)} --> {format_time(end_ms/1000)}\n")
                                f.write(f"{sentence}\n\n")
                                segment_index += 1

        logger.info(f"✅ FunASR字幕生成成功: {output_path}")
        return output_path

    except Exception as e:
        raise SpeechRecognitionError(f"FunASR生成字幕失败: {e}")
```

### 4.5 Whisper Small 实现

**文件**：`backend/utils/speech_recognizer.py`

```python
def _generate_subtitle_whisper_local(self, video_path: Path, output_path: Path,
                                     config: SpeechRecognitionConfig) -> Path:
    """使用本地Whisper Small生成字幕 - 内存友好方案"""

    if not self.available_methods[SpeechRecognitionMethod.WHISPER_LOCAL]:
        raise SpeechRecognitionError("Whisper不可用，请安装: pip install openai-whisper")

    try:
        logger.info(f"开始使用Whisper {config.model} 生成字幕: {video_path}")

        # 1. 加载模型（Small 内存友好）
        import whisper
        model = whisper.load_model(config.model)

        # 2. 识别参数
        transcribe_kwargs = {"verbose": False}
        if config.language != LanguageCode.AUTO:
            transcribe_kwargs["language"] = config.language.value

        # 3. 执行识别
        result = model.transcribe(str(video_path), **transcribe_kwargs)

        # 4. 生成SRT
        def format_time(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = seconds % 60
            return f"{hours:02}:{minutes:02}:{secs:06.3f}".replace('.', ',')

        with open(output_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(result['segments'], start=1):
                start = segment['start']
                end = segment['end']
                f.write(f"{i}\n")
                f.write(f"{format_time(start)} --> {format_time(end)}\n")
                f.write(f"{segment['text'].strip()}\n\n")

        logger.info(f"✅ Whisper字幕生成成功: {output_path}")
        return output_path

    except Exception as e:
        raise SpeechRecognitionError(f"Whisper生成字幕失败: {e}")
```

### 4.6 bcut-asr 实现

**文件**：`backend/utils/speech_recognizer.py`

```python
def _generate_subtitle_bcut_asr(self, video_path: Path, output_path: Path,
                                config: SpeechRecognitionConfig) -> Path:
    """使用bcut-asr生成字幕 - 快速备用方案"""

    if not self.available_methods[SpeechRecognitionMethod.BCUT_ASR]:
        raise SpeechRecognitionError("bcut-asr不可用")

    try:
        logger.info(f"开始使用bcut-asr生成字幕: {video_path}")

        # 1. 音频提取
        audio_path = self._extract_audio_from_video(video_path, output_path.parent)

        # 2. 创建ASR实例
        asr = BcutASR(str(audio_path))

        # 3. 上传并创建任务
        asr.upload()
        asr.create_task()

        # 4. 轮询等待结果
        max_attempts = 60
        for attempt in range(max_attempts):
            result = asr.result()
            if result.state == ResultStateEnum.COMPLETE:
                break
            elif result.state == ResultStateEnum.FAILED:
                raise SpeechRecognitionError("bcut-asr识别失败")
            time.sleep(5)
        else:
            raise SpeechRecognitionError("bcut-asr识别超时")

        # 5. 解析并保存
        subtitle = result.parse()
        subtitle_content = subtitle.to_srt()

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(subtitle_content)

        logger.info(f"✅ bcut-asr字幕生成成功: {output_path}")
        return output_path

    except Exception as e:
        raise SpeechRecognitionError(f"bcut-asr生成字幕失败: {e}")
```

---

## 5. 自动生成调度逻辑

### 5.1 simple_pipeline_adapter 中的实现

**文件**：`backend/services/simple_pipeline_adapter.py`

```python
async def _generate_subtitle_automatically(self, video_path: str, metadata_dir: Path) -> Optional[Path]:
    """
    自动生成字幕文件 - 优化版本

    降级策略（按准确度和内存综合排序）：
    1. FunASR Paraformer-zh（推荐，最准确、内存最低）
    2. Whisper Small（多语言、内存适中）
    3. bcut-asr（快速备用）
    4. 返回 None（使用空大纲）
    """
    from backend.utils.speech_recognizer import generate_subtitle_for_video

    video_file_path = Path(video_path)
    output_path = metadata_dir / f"{video_file_path.stem}.srt"

    # 方案1: FunASR（最推荐）
    try:
        logger.info("尝试使用 FunASR (Paraformer-zh) 生成字幕...")
        srt_path = generate_subtitle_for_video(
            video_file_path,
            output_path=output_path,
            method="funasr",
            model="paraformer-zh",
            language="zh"
        )
        if srt_path and srt_path.exists():
            logger.info(f"✅ FunASR 字幕生成成功: {srt_path}")
            return srt_path
    except Exception as e:
        logger.warning(f"⚠️ FunASR 生成失败: {e}")

    # 方案2: Whisper Small（内存友好）
    try:
        logger.info("尝试使用 Whisper Small 生成字幕...")
        srt_path = generate_subtitle_for_video(
            video_file_path,
            output_path=output_path,
            method="whisper_local",
            model="small",  # 改为 small，降低内存占用
            language="auto"
        )
        if srt_path and srt_path.exists():
            logger.info(f"✅ Whisper Small 字幕生成成功: {srt_path}")
            return srt_path
    except Exception as e:
        logger.warning(f"⚠️ Whisper Small 生成失败: {e}")

    # 方案3: bcut-asr（备用快速方案）
    try:
        logger.info("尝试使用 bcut-asr 生成字幕...")
        srt_path = generate_subtitle_for_video(
            video_file_path,
            output_path=output_path,
            method="bcut_asr",
            model="base",
            language="auto"
        )
        if srt_path and srt_path.exists():
            logger.info(f"✅ bcut-asr 字幕生成成功: {srt_path}")
            return srt_path
    except Exception as e:
        logger.warning(f"⚠️ bcut-asr 生成失败: {e}")

    # 全部失败
    logger.error("❌ 所有字幕生成方案均失败")
    return None
```

### 5.2 降级流程图

```
┌─────────────────────────────────────────────────────────┐
│                 输入: 视频文件                           │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Step 1: 检查 FunASR 是否可用                            │
│  ✅ 可用 → 使用 FunASR Paraformer-zh                    │
│  ❌ 不可用 → 继续 Step 2                                │
└─────────────────────────────────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
             YES                   NO
              │                     │
              ▼                     ▼
┌──────────────────┐    ┌─────────────────────────────────┐
│ FunASR 识别      │    │ Step 2: 检查 Whisper Small       │
│                  │    │ ✅ 可用 → 使用 Whisper Small     │
│ 生成 SRT ✅      │    │ ❌ 不可用 → 继续 Step 3         │
└──────────────────┘    └─────────────────────────────────┘
                                        │
                             ┌──────────┴──────────┐
                             │                     │
                            YES                   NO
                             │                     │
                             ▼                     ▼
                 ┌──────────────────┐   ┌─────────────────────────────────┐
                 │  Whisper Small   │   │ Step 3: 检查 bcut-asr           │
                 │  识别            │   │ ✅ 可用 → 使用 bcut-asr         │
                 │  生成 SRT ✅     │   │ ❌ 不可用 → 返回 None          │
                 └──────────────────┘   └─────────────────────────────────┘
                                                       │
                                          ┌────────────┴────────────┐
                                          │                         │
                                         YES                        NO
                                          │                         │
                                          ▼                         ▼
                               ┌──────────────────┐    ┌──────────────────┐
                               │   bcut-asr       │    │ 返回 None        │
                               │   识别           │    │ 使用空大纲       │
                               │   生成 SRT ✅    │    │                  │
                               └──────────────────┘    └──────────────────┘
```

---

## 6. 使用指南

### 6.1 默认使用（推荐）

```python
from backend.utils.speech_recognizer import generate_subtitle_for_video

# 自动选择最优方案（FunASR → Whisper Small → bcut-asr）
srt_path = generate_subtitle_for_video("input.mp4")
```

### 6.2 指定方法

```python
# 指定使用 FunASR
srt_path = generate_subtitle_for_video(
    "input.mp4",
    method="funasr",
    language="zh"
)

# 指定使用 Whisper Small
srt_path = generate_subtitle_for_video(
    "input.mp4",
    method="whisper_local",
    model="small"
)
```

### 6.3 指定输出路径

```python
# 自定义输出路径
srt_path = generate_subtitle_for_video(
    "input.mp4",
    output_path="output/subtitles.srt"
)
```

### 6.4 在流水线中使用

```python
# simple_pipeline_adapter 会自动处理
srt_path = await pipeline_adapter._generate_subtitle_automatically(
    video_path="input.mp4",
    metadata_dir=Path("project/metadata")
)
```

---

## 7. 配置参数

### 7.1 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `FUNASR_MODEL` | FunASR模型 | `paraformer-zh` |
| `WHISPER_MODEL` | Whisper模型 | `small`, `medium` |
| `SPEECH_RECOGNITION_METHOD` | 默认方法 | `funasr`, `whisper_local` |

### 7.2 默认参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `method` | `auto` | 自动选择最优方案 |
| `model` | `base`/`small` | FunASR用base，Whisper用small |
| `language` | `auto` | 自动检测语言 |
| `output_format` | `srt` | 输出格式 |

---

## 8. 性能对比

### 8.1 中文识别准确率

| 方案 | 准确率 | 测试条件 |
|------|--------|----------|
| **FunASR Paraformer-zh** | 95%+ | 理想录音环境 |
| Whisper Large | 93%+ | 理想录音环境 |
| Whisper Medium | 90%+ | 理想录音环境 |
| Whisper Small | 85%+ | 理想录音环境 |
| bcut-asr | 85%+ | 理想录音环境 |

### 8.2 内存占用

| 方案 | 模型大小 | 推理内存 | 总内存占用 |
|------|----------|----------|------------|
| **FunASR Paraformer-zh** | ~200MB | ~500MB | **~1GB** |
| Whisper Small | ~500MB | ~2GB | ~3GB |
| Whisper Medium | ~1.5GB | ~4GB | ~5-6GB |
| Whisper Large | ~3GB | ~8GB | ~10GB+ |

### 8.3 处理速度（1分钟视频）

| 方案 | 处理时间 | 实时率 |
|------|----------|--------|
| bcut-asr | ~3秒 | ~20x |
| **FunASR** | ~5秒 | ~12x |
| Whisper Small | ~8秒 | ~7x |
| Whisper Medium | ~20秒 | ~3x |
| Whisper Large | ~60秒 | ~1x |

---

## 9. 依赖安装

### 9.1 FunASR（推荐）

```bash
pip install funasr
```

### 9.2 Whisper

```bash
pip install openai-whisper
```

### 9.3 bcut-asr

```bash
# 自动安装（推荐）
python scripts/install_bcut_asr.py

# 或手动安装
git clone https://github.com/SocialSisterYi/bcut-asr.git
cd bcut-asr
pip install .
```

### 9.4 ffmpeg（必需）

```bash
# macOS
brew install ffmpeg

# Ubuntu
sudo apt install ffmpeg

# Windows
winget install ffmpeg
```

---

## 10. 故障排除

### 10.1 FunASR 常见问题

| 问题 | 解决方案 |
|------|----------|
| 导入失败 | `pip install funasr` |
| 模型下载慢 | 设置镜像：`pip install -i https://pypi.tuna.tsinghua.edu.cn/simple funasr` |
| CPU 占用高 | 正常现象，FunASR 默认使用 CPU 推理 |

### 10.2 Whisper 常见问题

| 问题 | 解决方案 |
|------|----------|
| 导入失败 | `pip install openai-whisper` |
| 模型下载慢 | 手动下载：`whisper --model large` |
| CUDA 不可用 | 正常，默认使用 CPU 推理 |

### 10.3 bcut-asr 常见问题

| 问题 | 解决方案 |
|------|----------|
| 网络超时 | 检查网络连接，或使用代理 |
| 识别失败 | 检查音频文件是否正常 |

---

## 11. 附录

### 11.1 相关文件

| 文件 | 说明 |
|------|------|
| `backend/utils/speech_recognizer.py` | 核心语音识别模块 |
| `backend/services/simple_pipeline_adapter.py` | 流水线适配器 |
| `docs/CLIP_STRUCTURE_DESIGN.md` | 切片结构设计文档 |
| `scripts/install_bcut_asr.py` | bcut-asr 安装脚本 |

### 11.2 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0 | - | 初始版本，支持 bcut-asr 和 Whisper |
| v2.0 | 2026-05-13 | 新增 FunASR 支持，优化降级策略 |

### 11.3 参考资料

- [FunASR 官方文档](https://github.com/modelscope/FunASR)
- [Whisper 官方文档](https://github.com/openai/whisper)
- [bcut-asr GitHub](https://github.com/SocialSisterYi/bcut-asr)

---

**文档版本**: v2.0
**最后更新**: 2026-05-13
**维护者**: AutoClip开发团队
