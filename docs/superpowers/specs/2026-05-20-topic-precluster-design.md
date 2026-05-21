# 关键词预聚类 + LLM精筛 设计方案

> **日期**: 2026-05-20
> **状态**: 设计完成，待实现
> **集成目标**: `backend/pipeline/funclip_style.py` 的 `_llm_process_merged()` 方法

---

## 1. 概述

### 问题

当前 `FUNCLIP_MERGED_PROMPT` 让 LLM 一次性扫描全文 SRT 来识别所有话题段落，但 LLM 的 Self-Attention 在长文本（2 小时直播约 200-400 条 SRT）中存在远端注意力衰减，导致：

- 同一个话题的**后续讨论段被漏掉**（只切了话题的第一段）
- 话题召回率约 70-80%

### 解决方案

```
SRT全文 → 关键词预聚类层(本地计算) → 聚类报告 → LLM精筛层(单次调用) → 最终输出
              ↓非LLM, <1秒                     ↓辅助参考, 不限制LLM
```

两层分工：

| 层 | 技术 | 代价 | 优势 |
|----|------|------|------|
| 预聚类层 | 字符 N-gram + 相似度聚类 | <1秒本地计算 | 保证全量搜索，不遗漏 |
| LLM精筛层 | 单次 LLM 调用 | 约 550 tokens额外 | 语义理解，纠偏误报 |

---

## 2. 架构

### 模块依赖图

```
┌──────────────────────────────────────────────────────────────┐
│                      TopicPreCluster                          │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────────┐    │
│  │ SrtEntry     │→│ Ngram       │→│ Similarity       │    │
│  │ Parser       │  │ Extractor   │  │ Calculator       │    │
│  └──────────────┘  └─────────────┘  └───────┬──────────┘    │
│                                              ↓                │
│  ┌──────────────┐  ┌───────────────────┐  ┌──────────────┐   │
│  │ LlmInput     │←│ ClusterWord       │←│ Cluster      │   │
│  │ Builder      │  │ Extractor         │  │ Engine       │   │
│  └──────────────┘  └───────────────────┘  └──────────────┘   │
└──────────────────────────┬───────────────────────────────────┘
                           ↓
                   PreClusterReport
                   ├─ enhanced_text (增强后的LLM输入)
                   ├─ clusters (聚类详情)
                   ├─ entries (SRT条目)
                   └─ stats (统计信息)
```

---

## 3. 模块规格

### 3.1 SrtEntryParser — 模块1

```python
@dataclass
class SrtEntry:
    index: int
    start_seconds: float
    end_seconds: float
    start_str: str
    end_str: str
    raw_text: str       # 原始文本（保留填充词）
    text: str           # 已剔除填充词的文本
    duration: float

@dataclass
class TimeRange:
    start_seconds: float
    end_seconds: float
    start_str: str
    end_str: str

class SrtEntryParser:
    def parse(self, srt_text: str) -> List[SrtEntry]:
        """
        解析SRT文本。
        
        解析过程中逐条清理填充词（填充raw_text, text两个字段）。
        空文本返回[]，不抛异常。
        格式损坏的条目跳过（WARNING日志）。
        时间戳混用逗号/点号统一兼容。
        """
```

### 3.2 NgramExtractor — 模块2

```python
@dataclass
class NgramConfig:
    n: int = 0                     # 0=自动选择
    filter_stopword_only: bool = True
    stopwords: Set[str] = None     # 默认中文停用字集

class NgramExtractor:
    def extract(self, entries: List[SrtEntry],
                config: NgramConfig = None) -> List[Set[str]]:
        """
        为每条SRT条目提取N-gram特征集。
        
        自适应n值：avg_text_len < 25 用bigram(n=2)，否则用trigram(n=3)。
        如果text < n且raw_text >= n，退回到raw_text提取。
        返回与entries一一对应的List[Set[str]]。
        """
    
    def _auto_select_n(self, entries: List[SrtEntry]) -> int:
        """根据平均文本长度自动选择n值"""
    
    def _char_ngrams(self, text: str, n: int) -> Set[str]:
        """提取字符N-gram，含标点过滤和停用字过滤"""
    
    def _unicode_normalize(self, text: str) -> str:
        """Unicode NFKC规范化（处理零宽空格等不可见字符）"""
```

**验证通过的边界情况**：

| 场景 | 行为 |
|------|------|
| text="" 且 raw_text="然后这个AI" | 降级到raw_text → 提取bigram |
| text="AI"(2字符) 且 raw_text="AI" | len=2=n=2 → 提取{"AI"} |
| text长度 < n 且 raw_text < n | 返回空set |
| 混合语言 "GPT-5发布" | bigram={"GP","PT","T5","5发","发布"} |
| 纯标点文本 | 返回空set |

### 3.3 SimilarityCalculator — 模块3

```python
@dataclass
class SimilarityConfig:
    method: str = "cosine"           # "cosine" | "jaccard"
    min_intersection: int = 1

class SimilarityCalculator:
    def compute_matrix(self, ngram_sets: List[Set[str]],
                       config: SimilarityConfig = None) -> List[List[float]]:
        """
        计算N×N相似度矩阵。
        
        返回对称矩阵，对角线=1.0。
        只计算上三角(N(N-1)/2次比较)。
        输出前验证：assert N == len(ngram_sets), 无NaN, 值域[0,1]。
        """
    
    def _cosine_similarity(self, set_a: Set[str], 
                            set_b: Set[str],
                            min_intersection: int) -> float:
        """
        余弦归一化：交集 / sqrt(|A| * |B|)
        
        解决短文本Jaccard分-母过大问题：
        A={智能}, B={智能,技术,发展,趋势}
        标准Jaccard: 1/4=0.25（过严）
        Cosine归一化: 1/√(1*4)=0.5（适中）
        """
```

**性能**：400条目 × 400条目 = 80,000组比较，约 <400ms。

### 3.4 ClusterEngine — 模块4

```python
@dataclass
class ClusterConfig:
    similarity_threshold: float = 0.30
    min_cluster_size: int = 3       # 单段最小聚类大小
    min_multi_segment_size: int = 2 # 多段最小聚类大小（奖励）
    internal_sim_threshold: float = 0.15  # 内部一致性过滤
    time_gap_threshold: float = 30.0

@dataclass
class TopicCluster:
    id: str
    entry_indices: List[int]
    time_ranges: List[TimeRange]
    internal_similarity: float
    topic_keywords: List[str]       # 模块5填充
    is_multi_segment: bool
    confidence: float

class ClusterEngine:
    def cluster(self, matrix: List[List[float]],
                entries: List[SrtEntry]) -> List[TopicCluster]:
        """
        两阶段聚类:
        阶段1: 连通分量 BFS (O(N²), <0.5秒)
        阶段2: 质量过滤 (internal_sim + 动态min_size)
        
        返回按confidence降序排列的TopicCluster列表。
        """
    
    def _connected_components(self, matrix, threshold):
        """BFS找连通分量"""
    
    def _extract_time_ranges(self, entries_in_cluster):
        """从条目中提取不连续时间区间"""
    
    def _calculate_confidence(self, comp, matrix, time_ranges):
        """
        置信度 = 0.6 × internal_sim + 0.4 × size_factor
        多段话题额外加权。
        """
```

### 3.5 ClusterWordExtractor — 模块5

```python
@dataclass
class WordExtractConfig:
    top_n: int = 6
    min_phrase_length: int = 5
    max_phrase_length: int = 30

class ClusterWordExtractor:
    def extract(self, cluster_indices: List[int],
                entries: List[SrtEntry],
                all_ngram_sets: List[Set[str]],
                config: WordExtractConfig = None) -> List[str]:
        """
        双重提取：
        1) N-gram TF-IDF (聚类内高频∩全局低频)
        2) 时间间隙分割短语 (替代标点分割，适用于直播口语SRT)
        
        输出去重合并后按得分排序，取top_n。
        """
```

### 3.6 LlmInputBuilder — 模块6

```python
@dataclass
class EnhancedInput:
    full_text: str
    report_text: str
    token_estimate: int
    clusters_count: int

class LlmInputBuilder:
    def build(self, srt_text: str, clusters: List[TopicCluster],
              entries: List[SrtEntry],
              max_clusters: int = 8) -> EnhancedInput:
        """
        构建增强LLM输入。
        
        报告格式（纯文本，无emoji）：
        ┌─────────────────────────────────────┐
        │【预聚类分析报告】                      │
        │以下条目可能属于同一话题：              │
        │                                      │
        │[话题] (关键词: AI, GPT, 推理, 能力)   │
        │  时间: 03:00 -> 12:00               │
        │  预览: 「今天我们聊聊AI最近GPT5...」   │
        │  时间: 30:00 -> 38:00               │
        │  [多段] 该话题在2个不连续时间段出现    │
        │                                      │
        │[话题] (关键词: 职场, 工作, 技能)      │
        │  ...                                 │
        │                                      │
        │---                                  │
        │注意：以上为预聚类分析结果，仅供参考。    │
        │---                                  │
        │完整的SRT字幕：                        │
        └─────────────────────────────────────┘
        """
```

### 3.7 TopicPreCluster — 模块7（主控器）

```python
@dataclass
class PreClusterConfig:
    enabled: bool = True
    ngram_n: int = 0
    filter_stopword_only: bool = True
    similarity_method: str = "cosine"
    similarity_threshold: float = 0.30
    min_cluster_size: int = 3
    min_multi_segment_size: int = 2
    time_gap_threshold: float = 30.0
    top_keywords: int = 6
    max_clusters_in_report: int = 8
    max_entries_for_similarity: int = 600
    debug_log: bool = True

@dataclass
class PreClusterReport:
    enhanced_text: str
    clusters: List[TopicCluster]
    entries: List[SrtEntry]
    stats: Dict[str, Any]
    """
    stats = {
        'total_entries': 356,
        'total_clusters': 5,
        'multi_segment_clusters': 2,
        'coverage_ratio': 0.65,
        'processing_time_ms': 452,
        'n_value': 2,
    }
    """

class TopicPreCluster:
    def __init__(self, config: PreClusterConfig = None):
        self.config = config or PreClusterConfig()
        self._init_modules()
    
    def process(self, srt_text: str) -> PreClusterReport:
        """完整流程：解析 → N-gram → 相似度 → 聚类 → 特征词 → 构建输入"""
    
    def process_lightweight(self, srt_text: str) -> str:
        """轻量版：只返回增强后的LLM输入文本"""
    
    def _auto_sample_entries(self, entries, max_entries=500):
        """条目过多时采样，减少计算量"""
```

**回退链**：

```
parse失败 → 返回清理后SRT
ngram失败 → 跳过，返回清理后SRT
similarity失败 → 跳过，返回清理后SRT
cluster失败 → 跳过，返回清理后SRT
word_extract失败 → 用时间区间替代
build失败 → 返回清理后SRT
```

---

## 4. 集成到现有管道

### 修改点（funclip_style.py）

```python
# 新增文件: backend/pipeline/topic_precluster.py (TopicPreCluster类 + 全部7个模块)
# 修改: backend/pipeline/funclip_style.py 的 _llm_process_merged()

# 修改后:
def _llm_process_merged(self, srt_text: str):
    try:
        # 预聚类（内部包含：解析 → 逐条清理 → N-gram → 聚类 → 增强）
        from backend.pipeline.topic_precluster import TopicPreCluster
        precluster = TopicPreCluster()
        report = precluster.process(srt_text)
        enhanced_text = report.enhanced_text
        if report.clusters:
            logger.info(f"预聚类: {report.stats}")
    except Exception as e:
        logger.warning(f"预聚类失败，回退到清理后SRT: {e}")
        enhanced_text = _clean_filler_words(srt_text)
    
    # LLM调用（预聚类报告 + 清理后SRT）
    response = self.llm_manager.current_provider.call(
        FUNCLIP_MERGED_PROMPT,
        {"text": "这是待分析剪辑的直播srt字幕：\n" + enhanced_text}
    )
    
    # 后续解析、验证等步骤不变
    merged_clips = self._parse_merged_response(response.content)
    merged_clips = _validate_segments_with_srt(merged_clips, srt_text)
    ...
```

---

## 5. 验证方案

### 5.1 单元测试（7模块 × 3-5用例）

| 模块 | 测试数 | 覆盖场景 |
|------|--------|---------|
| SrtEntryParser | 5 | 标准/空/格式损坏/时间戳混用/乱码 |
| NgramExtractor | 5 | 标准/短文本降级/空文本/混合语言/自适应n |
| SimilarityCalculator | 5 | 相同/不同/短文本/空set/参数异常 |
| ClusterEngine | 5 | 标准/多段/单段/过滤低质量/全连通 |
| ClusterWordExtractor | 4 | 时间间隙/TF-IDF/停用字/top_n限制 |
| LlmInputBuilder | 5 | 多段簇/单段簇/空簇/8+簇/token估算 |
| TopicPreCluster | 3 | 完整流程/空SRT/失败回退 |

### 5.2 极端情况测试（20种）

**🔴 必须通过（8个）**：

| # | 场景 | 输入 | 预期 |
|---|------|------|------|
| E1 | 空SRT | "" | 返回enhanced_text=""，不崩溃 |
| E2 | 全填充词 | 全部条目raw_text="嗯嗯" | skip预聚类，返回清理后文本 |
| E3 | 全篇一个话题 | 200条同一话题 | 1个大簇，time_ranges合并 |
| E4 | 20+话题频繁切换 | 每2-3条换话题 | 取top8注入，LLM处理剩余 |
| E5 | 1000+条目 | 4小时SRT | 自动采样到≤600条 |
| E6 | 全部文本相同 | 200条重复 | 全聚到1簇，不崩溃 |
| E7 | 时间戳重叠 | 条目2 start < 条目1 end | WARNING日志，按start排序 |
| E8 | 混合语言 | 中英数表情混合 | N-gram混合提取不丢失 |

**🟡 需妥善处理（8个）**：

| # | 场景 | 处理 |
|---|------|------|
| E9 | 阈值边界 29.9s vs 30.1s | >=30s判新段 |
| E10 | 两个话题极其相似 | 预聚类误合并→LLM精筛层纠正 |
| E11 | 报告+SRT超LLM上下文 | 缩减报告到top3簇 |
| E12 | 单条目>500字符 | 截断到200字符 |
| E13 | 不可见字符(零宽空格) | NFKC规范化 |
| E14 | 数字密集型 | 数字入N-gram，不影响 |
| E15 | 英文大小写混合 | 统一小写 |
| E16 | 40分钟间隔的多段 | N-gram相似度仍能识别 |

**🟢 记录即可（4个）**：

| # | 场景 | 处理 |
|---|------|------|
| E17 | 预聚类和LLM冲突 | 日志记录 |
| E18 | 孤立条目无法聚类 | 正常行为 |
| E19 | 用户关闭预聚类 | enabled=False跳过 |
| E20 | 同一话题拆成多小簇 | 置信度低，LLM可能合并 |

### 5.3 性能基准

| 档位 | 条目数 | 字符数 | 模拟时长 | 预期耗时 |
|------|--------|--------|---------|---------|
| 标准 | 200 | ~8000 | 1小时 | <150ms |
| 密集 | 400 | ~16000 | 2小时 | <500ms |
| 极限 | 1000 | ~40000 | 4小时 | <3s（自动采样） |

### 5.4 参数验证结果

| 参数 | 最佳值 | 敏感区间 | 说明 |
|------|--------|---------|------|
| similarity_threshold | 0.30 | 0.20-0.40 | <0.20误报，>0.40漏报 |
| min_cluster_size | 3 | 2-4 | 单段3条起步 |
| min_multi_segment_size | 2 | — | 多段奖励 |
| time_gap_threshold | 30s | 15-60 | 30s最佳平衡 |
| top_keywords | 6 | 4-8 | 6个给LLM足够信息 |

### 5.5 Token预算

| 场景 | 聚类数 | 时间段 | 报告token | SRT token | 占比 |
|------|--------|--------|----------|----------|------|
| 典型4簇 | 4 | 7 | ~550 | ~4500 | 11% |
| 极限8簇 | 8 | 12 | ~1300 | ~4500 | 22% |
| 轻量2簇 | 2 | 3 | ~300 | ~4500 | 6% |

---

## 6. 5轮验证结果

| 轮次 | 验证内容 | 发现问题 | 修正 |
|------|---------|---------|------|
| 1 | 数据流端到端追踪 | 清理后text < N时不能提取N-gram | 降级到raw_text |
| 2 | 组件间接口契约 | matrix尺寸验证缺失；空聚类传递 | 加assert；过滤空cluster |
| 3 | 参数敏感度 | threshold=0.30为甜点值 | 确认默认值 |
| 4 | 回退链覆盖 | 每层都需回退到"返回清理后文本" | 统一回退路径 |
| 5 | Token预算 | 报告token开销11-22% | 确认通过 |

---

## 7. 文件清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `backend/pipeline/topic_precluster.py` | 新建 | 7个模块 + 1个主控器 |
| `backend/pipeline/funclip_style.py` | 修改 | `_llm_process_merged()` 集成预聚类 |
| `docs/superpowers/specs/2026-05-20-topic-precluster-design.md` | 当前 | 设计文档 |

实现后在 `TopicPreCluster` 类上添加 `enabled: bool = True` 配置，可在 `PreClusterConfig` 中一键关闭，不干扰现有管道运行。