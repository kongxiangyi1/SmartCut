# 语音转写优化方案设计文档

## 1. 现状分析

### 1.1 当前技术栈

| 组件 | 当前方案 | 版本 | 状态 |
|------|---------|------|------|
| **主引擎** | FunASR | 1.3.1 | ✅ 默认启用 |
| **备选引擎** | Whisper | 20231117 | ✅ 回退方案 |
| **辅助引擎** | bcut-asr | 最新 | ⚠️ 可选安装 |
| **VAD模型** | fsmn-vad | - | ✅ 已集成 |
| **标点恢复** | ct-punc | - | ✅ 已集成 |

### 1.2 性能瓶颈分析

```
1小时视频处理时间分解（当前状态）:
┌─────────────────────────────────────────────────────┐
│ 语音转写   ████████████████████░░░░░░░  ~35分钟    │
│ 字幕生成   █░░░░░░░░░░░░░░░░░░░░░░░░░░  ~2分钟     │
│ 其他处理   ███░░░░░░░░░░░░░░░░░░░░░░░░  ~8分钟     │
└─────────────────────────────────────────────────────┘
              语音转写占总耗时 75-80% ⚠️ 主要瓶颈
```

### 1.3 当前架构问题

| 问题 | 影响 | 严重程度 |
|------|------|---------|
| 强制CPU推理 | 速度慢，未利用GPU资源 | 🔴 高 |
| 无模型量化 | 内存占用大(>2GB) | 🟠 中 |
| 串行处理 | 无法利用多核CPU | 🟠 中 |
| 全视频识别 | 包含静音片段无效计算 | 🟡 低 |

---

## 2. 优化方案设计

### 2.1 总体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    语音转写优化架构                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │  视频输入    │ -> │  音频提取    │ -> │  VAD检测     │     │
│  │  (任意格式)  │    │  (16kHz WAV) │    │  (语音片段)  │     │
│  └──────────────┘    └──────────────┘    └──────┬───────┘     │
│                                                  │             │
│                                                  ▼             │
│  ┌──────────────────────────────────────────────────────┐      │
│  │              语音识别引擎层                          │      │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │      │
│  │  │  GPU加速    │  │  模型量化    │  │  并行处理    │  │      │
│  │  │  (CUDA)     │  │  (INT8)     │  │  (多线程)   │  │      │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │      │
│  └──────────────────────────────────────────────────────┘      │
│                                                  │             │
│                                                  ▼             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │  标点恢复    │ -> │  字幕生成    │ -> │  输出文件    │     │
│  │  (ct-punc)   │    │  (SRT/VTT)  │    │  (.srt/.vtt) │     │
│  └──────────────┘    └──────────────┘    └──────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 详细优化方案

### 3.1 方案一：GPU加速（核心优化）

**目标**：利用GPU大幅提升推理速度

**技术实现**：

```python
# backend/utils/speech_recognizer.py

def _generate_subtitle_funasr(self, video_path: Path, output_path: Path,
                               config: SpeechRecognitionConfig) -> Path:
    """优化后的FunASR语音识别"""
    
    # 自动检测计算设备
    device = self._detect_compute_device()
    logger.info(f"使用计算设备: {device}")
    
    # 带缓存的模型加载
    model = self._get_or_load_model(device)
    
    # 使用GPU进行推理
    result = model.generate(
        input=str(audio_path),
        return_timestamp=True,
        batch_size=8  # GPU批处理
    )
    
    return output_path

def _detect_compute_device(self) -> str:
    """自动检测可用的计算设备"""
    # 优先级: CUDA > MPS > CPU
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    
    # 检查环境变量手动指定
    env_device = os.environ.get("SPEECH_DEVICE", "").lower()
    if env_device in ["cuda", "mps", "cpu"]:
        return env_device
    
    return "cpu"

def _get_or_load_model(self, device: str) -> Any:
    """获取或加载模型（带缓存）"""
    global _FUNASR_MODEL_CACHE
    
    cache_key = f"{device}_quantized"
    
    if _FUNASR_MODEL_CACHE is None:
        logger.info(f"初始化FunASR模型 ({device})...")
        from funasr import AutoModel
        
        _FUNASR_MODEL_CACHE = AutoModel(
            model="paraformer-zh",
            vad_model="fsmn-vad",
            punc_model="ct-punc",
            device=device,
            disable_update=True,
            quantize=True,           # 启用量化
            int8=True,               # INT8量化
            cache_dir=str(Path.home() / ".cache" / "funasr")
        )
        logger.info("FunASR模型加载完成")
    
    return _FUNASR_MODEL_CACHE
```

**预期效果**：
| 指标 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 1小时视频处理 | 35分钟 | 5-8分钟 | **5-7倍** |
| 内存占用 | >2GB | ~500MB | **75%** |

---

### 3.2 方案二：VAD预处理优化

**目标**：跳过静音片段，只识别有声音的部分

**技术实现**：

```python
def _extract_speech_segments(self, audio_path: Path) -> List[Dict[str, float]]:
    """使用VAD检测语音片段，跳过静音"""
    logger.info("进行语音活动检测(VAD)...")
    
    from funasr import AutoModel
    
    # 单独加载轻量级VAD模型
    vad_model = AutoModel(model="fsmn-vad", device=self._detect_compute_device())
    result = vad_model.generate(input=str(audio_path))
    
    speech_segments = []
    for segment in result:
        if isinstance(segment, dict) and segment.get('type') == 'speech':
            speech_segments.append({
                'start': segment['start'] / 1000.0,
                'end': segment['end'] / 1000.0
            })
    
    logger.info(f"检测到 {len(speech_segments)} 个语音片段")
    return speech_segments

def _transcribe_segments(self, audio_path: Path, segments: List[Dict]) -> List[Dict]:
    """只对语音片段进行识别"""
    all_results = []
    
    for idx, segment in enumerate(segments):
        logger.info(f"识别片段 {idx+1}/{len(segments)}: "
                   f"{segment['start']:.2f}s - {segment['end']:.2f}s")
        
        # 提取片段音频
        segment_audio = self._extract_audio_segment(audio_path, segment)
        
        # 识别该片段
        result = self._recognize_audio(segment_audio)
        
        # 调整时间戳
        for item in result:
            item['start'] += segment['start']
            item['end'] += segment['end']
            all_results.append(item)
    
    return sorted(all_results, key=lambda x: x['start'])
```

**预期效果**：
- 静音占比高的视频处理时间减少 **30-50%**
- 减少无效计算，降低资源消耗

---

### 3.3 方案三：异步并行处理

**目标**：利用多核CPU并行处理多个任务

**技术实现**：

```python
# backend/utils/speech_recognizer.py

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

class AsyncSpeechRecognizer:
    """异步语音识别器"""
    
    def __init__(self, max_workers: Optional[int] = None):
        # 根据CPU核心数设置默认线程数
        self._max_workers = max_workers or min(4, os.cpu_count() or 4)
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
    
    async def generate_subtitles_batch(
        self,
        video_paths: List[Path],
        output_dir: Path,
        config: Optional[SpeechRecognitionConfig] = None
    ) -> List[Path]:
        """批量异步生成字幕"""
        logger.info(f"开始批量处理 {len(video_paths)} 个视频")
        
        async def process_single_video(video_path: Path) -> Path:
            """处理单个视频（在线程池中执行）"""
            output_path = output_dir / f"{video_path.stem}.srt"
            return await asyncio.to_thread(
                self._generate_subtitle_sync,
                video_path,
                output_path,
                config
            )
        
        # 并发处理，带并发限制
        semaphore = asyncio.Semaphore(self._max_workers)
        
        async def bounded_process(video_path: Path) -> Path:
            async with semaphore:
                return await process_single_video(video_path)
        
        # 并行执行所有任务
        tasks = [bounded_process(path) for path in video_paths]
        results = await asyncio.gather(*tasks)
        
        logger.info(f"批量处理完成，成功 {len(results)} 个")
        return results
    
    def _generate_subtitle_sync(
        self,
        video_path: Path,
        output_path: Path,
        config: Optional[SpeechRecognitionConfig]
    ) -> Path:
        """同步生成字幕（在线程池中调用）"""
        recognizer = SpeechRecognizer(config=config)
        return recognizer.generate_subtitle(video_path, output_path)
```

**预期效果**：
- 多视频批量处理时吞吐量提升 **3-4倍**
- 充分利用多核CPU资源

---

### 3.4 方案四：模型选择优化

**目标**：根据视频特征自动选择最优模型

**技术实现**：

```python
def select_optimal_model(duration_seconds: float, accuracy_requirement: str = "balanced") -> str:
    """
    根据视频时长和精度要求选择最优模型
    
    Args:
        duration_seconds: 视频时长（秒）
        accuracy_requirement: 精度要求 ("fast", "balanced", "high")
    
    Returns:
        模型名称
    """
    model_configs = {
        "tiny": {"duration_limit": 600, "accuracy": "low", "speed": "fast"},
        "small": {"duration_limit": 3600, "accuracy": "medium", "speed": "medium"},
        "medium": {"duration_limit": 7200, "accuracy": "high", "speed": "slow"},
        "large": {"duration_limit": float('inf'), "accuracy": "highest", "speed": "slowest"},
    }
    
    if accuracy_requirement == "fast":
        return "small"  # 优先速度
    elif accuracy_requirement == "high":
        return "large"  # 优先精度
    
    # 平衡模式：根据时长自动选择
    for model, config in model_configs.items():
        if duration_seconds <= config["duration_limit"]:
            return model
    
    return "large"

# 使用示例
video_duration = 3600  # 1小时
model = select_optimal_model(video_duration)
logger.info(f"为 {video_duration}秒 视频选择模型: {model}")
```

---

## 4. 实施计划

### 4.1 优先级排序

| 优先级 | 方案 | 实施难度 | 预期收益 |
|--------|------|---------|---------|
| **P0** | GPU加速 + 量化 | 低 | 5-7倍速度提升 |
| **P1** | VAD预处理 | 中 | 30-50%时间节省 |
| **P2** | 异步并行处理 | 中 | 3-4倍吞吐量提升 |
| **P3** | 模型自动选择 | 低 | 资源优化 |

### 4.2 实施步骤

```
阶段1（立即生效）:
├── 修改 speech_recognizer.py
│   ├── 添加设备自动检测
│   ├── 启用模型量化
│   └── 设置合理的批处理大小
└── 测试验证

阶段2（中期优化）:
├── 添加VAD预处理逻辑
├── 实现语音片段识别
└── 集成到主流程

阶段3（长期优化）:
├── 实现异步批量处理
├── 添加模型选择策略
└── 性能监控与调优
```

---

## 5. 配置与调优

### 5.1 环境变量配置

```bash
# .env 文件配置示例
SPEECH_DEVICE=cuda                  # cuda/mps/cpu
FUNASR_QUANTIZE=true                # 是否启用量化
FUNASR_MODEL=paraformer-zh          # 模型名称
MAX_WORKERS=4                       # 并行线程数
ENABLE_VAD=true                     # 是否启用VAD预处理
```

### 5.2 性能调优参数

| 参数 | 说明 | 推荐值 |
|------|------|--------|
| `batch_size` | GPU批处理大小 | 8-16 |
| `max_workers` | 并行线程数 | CPU核心数/2 |
| `int8` | INT8量化 | true |
| `enable_vad` | VAD预处理 | true |

---

## 6. 测试与验证

### 6.1 测试用例

| 测试项 | 测试场景 | 预期结果 |
|--------|---------|---------|
| GPU检测 | 有CUDA环境 | 返回cuda |
| GPU检测 | 无CUDA环境 | 回退到cpu |
| 模型量化 | 启用int8 | 内存占用<1GB |
| VAD预处理 | 静音占比50%视频 | 处理时间减少30%+ |
| 并行处理 | 4个视频批量处理 | 耗时接近单视频 |

### 6.2 性能基准测试

```python
# 测试脚本示例
def benchmark_speech_recognition():
    test_video = Path("test_video.mp4")  # 1小时测试视频
    
    # 测试不同配置
    configurations = [
        {"device": "cpu", "quantize": False},
        {"device": "cpu", "quantize": True},
        {"device": "cuda", "quantize": False},
        {"device": "cuda", "quantize": True},
    ]
    
    for config in configurations:
        start_time = time.time()
        
        # 设置环境变量
        os.environ["SPEECH_DEVICE"] = config["device"]
        
        # 执行识别
        generate_subtitle_for_video(test_video)
        
        elapsed = time.time() - start_time
        print(f"配置 {config} 耗时: {elapsed:.2f}秒")
```

---

## 7. 兼容性说明

### 7.1 硬件要求

| 设备类型 | 最低要求 | 推荐配置 |
|---------|---------|---------|
| CPU | 4核 | 8核+ |
| GPU | 无 | NVIDIA GPU (4GB+显存) |
| 内存 | 8GB | 16GB+ |
| 存储 | 10GB空闲 | 50GB+ SSD |

### 7.2 依赖安装

```bash
# 基础依赖
pip install funasr torch

# GPU支持（需匹配CUDA版本）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 可选：安装bcut-asr
git clone https://github.com/SocialSisterYi/bcut-asr.git
cd bcut-asr && pip install .
```

---

## 8. 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| GPU不可用 | 中 | 回退到CPU | 自动检测+优雅降级 |
| 模型下载失败 | 低 | 无法启动 | 提供离线模型包 |
| 内存不足 | 低 | OOM错误 | 量化+分块处理 |
| 并发资源竞争 | 低 | 性能下降 | 线程池限制 |

---

## 9. 预期效果总结

### 优化前后对比

| 指标 | 优化前 | 优化后 | 提升比例 |
|------|--------|--------|---------|
| 1小时视频处理时间 | 35分钟 | 5-8分钟 | **5-7倍** |
| 内存占用 | >2GB | ~500MB | **75%降低** |
| 多视频吞吐量 | 串行 | 3-4倍并行 | **300-400%** |
| 静音视频处理 | 全量识别 | VAD跳过 | **30-50%节省** |

---

## 附录：配置示例

### 生产环境配置

```python
# backend/config/speech_config.py

SPEECH_CONFIG = {
    "default_method": "funasr",
    "device": "auto",  # auto/cuda/mps/cpu
    "quantize": True,
    "batch_size": 8,
    "max_workers": 4,
    "enable_vad": True,
    "fallback_method": "whisper_local",
    "model_selection_strategy": "balanced",  # fast/balanced/high
}
```

### 启动命令

```bash
# 使用GPU加速
SPEECH_DEVICE=cuda python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# 使用CPU（无GPU环境）
SPEECH_DEVICE=cpu python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
