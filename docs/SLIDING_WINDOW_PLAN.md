# 滑动窗口分块方案

## 一、背景与目标

### 1.1 问题描述

当前视频切片系统采用**固定大小分块**策略，存在以下问题：

1. **话题被硬切断**：分块边界正好落在话题中间，导致切片内容不完整
2. **上下文丢失**：分块时无法考虑前后内容的语义连贯性
3. **边界话题质量差**：被切断的话题片段无法形成有效的视频切片

### 1.2 目标

通过引入**滑动窗口重叠分块**策略，从根本上减少话题被切断的问题：

- 目标：话题切断率降至 5% 以下
- 窗口重叠区域用于二次分析，确保话题边界完整

---

## 二、方案设计

### 2.1 核心思想

滑动窗口分块的核心是**允许相邻分块之间存在重叠区域**：

```
传统固定分块：
|--------分块1--------|--------分块2--------|--------分块3--------
                     硬切点                硬切点

滑动窗口分块（overlap=30秒）：
|--------分块1--------|
          |--------分块2--------|
                    |--------分块3--------|
          ↑重叠区域↑         ↑重叠区域↑
```

### 2.2 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `chunk_size` | 300秒（5分钟） | 分块大小 |
| `overlap_minutes` | 1分钟 | 相邻分块重叠时长 |
| `min_topic_duration` | 90秒 | 话题最小时长（阶段一已实现） |
| `anchor_window_size` | 30秒 | 锚点检测窗口大小 |

### 2.3 架构设计

```
原始字幕文本
    │
    ▼
┌─────────────────────────┐
│  滑动窗口分块器          │
│  SlidingWindowChunker   │
│  - chunk_text()         │
│  - overlap_minutes 参数 │
└─────────────────────────┘
    │
    ├──→ 分块1（0-300秒）
    ├──→ 分块2（240-540秒）← 与分块1重叠60秒
    ├──→ 分块3（480-780秒）← 与分块2重叠60秒
    │
    ▼
┌─────────────────────────┐
│  多模态边界检测器         │
│  MultimodalBoundary     │
│  - 文本语义边界          │
│  - 语音停顿边界          │
│  - 视频场景边界          │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│  话题锚点检测器          │
│  TopicAnchorDetector    │
│  - 边界话题识别          │
│  - 跨窗口去重           │
└─────────────────────────┘
    │
    ▼
完整话题列表（无切断）
```

---

## 三、文件修改

### 3.1 新增文件

| 文件路径 | 说明 |
|----------|------|
| `backend/utils/sliding_window_chunker.py` | 滑动窗口分块器 |
| `backend/utils/topic_anchor_detector.py` | 话题锚点检测器 |

### 3.2 修改文件

| 文件路径 | 修改内容 |
|----------|----------|
| `backend/utils/text_processor.py` | 添加 `overlap_minutes` 参数 |
| `backend/pipeline/step1_outline.py` | 优化去重逻辑，支持跨窗口去重 |

---

## 四、详细实现

### 4.1 滑动窗口分块器

**文件**：`backend/utils/sliding_window_chunker.py`

```python
class SlidingWindowChunker:
    def __init__(
        self,
        chunk_size: int = 300,      # 分块大小（秒）
        overlap_minutes: int = 1,    # 重叠时长（秒）
        min_chunk_size: int = 60     # 最小分块大小
    ):
        self.chunk_size = chunk_size
        self.overlap_minutes = overlap_minutes
        self.min_chunk_size = min_chunk_size

    def chunk_text(
        self,
        text: str,
        subtitles: List[Dict],
        time_offset: int = 0
    ) -> List[Dict]:
        """
        执行滑动窗口分块

        返回:
            List[Dict]: 分块列表，每个分块包含:
                - text: 分块文本
                - start_time: 起始时间（秒）
                - end_time: 结束时间（秒）
                - subtitles: 该分块内的字幕片段
        """
```

**分块策略**：

1. **首块特殊处理**：从0开始，不向前重叠
2. **中间块**：向前重叠 `overlap_minutes`
3. **末块**：确保覆盖到字幕结尾
4. **最小分块**：如果剩余内容小于 `min_chunk_size`，合并到前一块

### 4.2 话题锚点检测器

**文件**：`backend/utils/topic_anchor_detector.py`

```python
class TopicAnchorDetector:
    def __init__(self, anchor_window_size: int = 30):
        self.anchor_window_size = anchor_window_size

    def detect_anchors(
        self,
        chunks: List[Dict],
        timeline_data: List[Dict]
    ) -> List[Dict]:
        """
        检测话题锚点（边界话题）

        策略：
        1. 识别重叠区域内的重复话题
        2. 选择完整度更高的话题作为锚点
        3. 过滤被切断的话题
        """
```

**去重逻辑**：

1. **锚点识别**：在重叠区域中，识别重复出现的话题
2. **完整性评分**：评估话题在窗口中的完整程度
3. **选择锚点**：选择完整度 > 80% 的话题作为有效锚点
4. **合并边界**：将跨越窗口边界的话题合并到完整的那一侧

### 4.3 text_processor.py 修改

**文件**：`backend/utils/text_processor.py`

添加 `overlap_minutes` 参数：

```python
def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap_minutes: int = 1  # 新增参数
) -> List[str]:
    """
    分块函数（支持滑动窗口）

    Args:
        text: 待分块文本
        chunk_size: 分块大小（字符数）
        overlap_minutes: 重叠时长（分钟），用于边界话题处理
    """
```

### 4.4 step1_outline.py 修改

**文件**：`backend/pipeline/step1_outline.py`

优化去重逻辑：

```python
def _deduplicate_outlines(
    outlines: List[Dict],
    overlap_threshold: float = 0.6
) -> List[Dict]:
    """
    跨窗口去重

    Args:
        outlines: 所有大纲
        overlap_threshold: 时间重叠阈值，超过则认为重复

    Returns:
        去重后的大纲列表
    """
```

---

## 五、配置项

### 5.1 shared_config.py

```python
# 滑动窗口配置
SLIDING_WINDOW = {
    "enabled": True,              # 是否启用滑动窗口
    "chunk_size": 300,             # 分块大小（秒）
    "overlap_minutes": 1,         # 重叠时长（分钟）
    "min_topic_duration": 90,     # 话题最小时长（秒）
    "anchor_window_size": 30,     # 锚点检测窗口（秒）
}
```

---

## 六、测试计划

### 6.1 单元测试

| 测试项 | 验证点 |
|--------|--------|
| `SlidingWindowChunker.chunk_text()` | 分块数量、边界时间、重叠区域 |
| `TopicAnchorDetector.detect_anchors()` | 锚点识别、去重效果、完整性评分 |

### 6.2 集成测试

| 测试项 | 验证点 |
|--------|--------|
| 完整流程 | 话题切断率、边界准确率 |
| 性能测试 | 处理时间增幅 < 30% |

### 6.3 验收标准

- 话题切断率降至 5% 以下
- 边界准确率维持 96% 以上
- 处理时间增幅 < 30%

---

## 七、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 重叠区域增加处理时间 | 中 | 默认 overlap_minutes=1，可配置 |
| 去重逻辑复杂 | 中 | 分阶段实现，先简单后复杂 |
| 内存占用增加 | 低 | 流式处理，避免一次性加载 |

---

## 八、开发计划

| 阶段 | 任务 | 工期 |
|------|------|------|
| 1 | 实现 SlidingWindowChunker | 0.5天 |
| 2 | 修改 text_processor.py | 0.5天 |
| 3 | 实现 TopicAnchorDetector | 1天 |
| 4 | 优化 step1_outline.py 去重 | 0.5天 |
| 5 | 单元测试与集成测试 | 1天 |

**总计：3.5天（可弹性调整至5天）**
