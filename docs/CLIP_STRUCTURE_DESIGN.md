# 理想切片结构设计文档

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档名称 | CLIP_STRUCTURE_DESIGN.md |
| 版本 | v2.0 |
| 创建日期 | 2026-05-13 |
| 状态 | 核心文档 |
| 关联模块 | smart_clip_generator, hook_extractor, product_detector, topic_validator |

---

## 1. 概述

### 1.1 文档目的

本文档定义AutoClip项目中"理想切片"的完整结构和实现逻辑，确保切片质量达到以下标准：
- 话题单一：一个切片只讲述一个问题/事件/内容
- 结构完整：切片有明确的开始和结尾
- 钩子有效：钩子与话题内容强相关
- 转化自然：产品引导与话题无缝衔接

### 1.2 核心设计原则

1. **话题内提取钩子**：钩子必须来自话题内部，而非话题外部
2. **单一话题原则**：每个切片只围绕一个核心话题展开
3. **完整性验证**：确保话题有始有终，避免半截话切片
4. **语义相关性**：钩子、话题、产品三者语义必须相关联

---

## 2. 核心概念定义

### 2.1 话题（Topic）

**定义**：话题是视频中围绕一个核心问题、事件或内容的完整论述段落。

**话题特征**：
- 有明确的边界（开始时间和结束时间）
- 内容围绕一个核心主题
- 论述相对完整（有开头、发展、结尾）

**话题结构**：
```json
{
    "id": "topic_001",
    "outline": "科技股投资策略",
    "content": ["AI基建是核心", "半导体值得关注", "避免追高"],
    "start_time": "00:10:00,000",
    "end_time": "00:15:30,000",
    "duration": 330.0,
    "completeness_score": 0.85
}
```

### 2.2 钩子（Hook）

**定义**：钩子是话题开头的精华部分，用于在最短时间内吸引观众注意力。

**钩子特征**：
- 位于话题开头（时间范围：topic_start ~ topic_start + max_hook_duration）
- 具有强吸引力和情感共鸣
- 通常3-12秒长度
- **必须来自话题内部**

**错误示例**：
```
话题内容：今天给大家讲一下半导体行业的投资机会
❌ 错误钩子（来自话题外）："大家好，欢迎来到直播间"
   → 钩子与话题内容无关
```

**正确示例**：
```
话题内容：今天给大家讲一下半导体行业的投资机会
✅ 正确钩子（来自话题开头）："你知道吗？半导体行业即将迎来爆发期"
   → 钩子与话题内容强相关，是话题的开头精华
```

### 2.3 产品引导（Product Pitch）

**定义**：产品引导是话题结束后，引导观众进行购买决策的内容片段。

**产品引导特征**：
- 通常位于话题结束后（或话题末尾）
- 包含购买链接、优惠信息等产品相关内容
- 与话题内容语义相关

### 2.4 切片（Clip）

**定义**：切片是由钩子 + 核心话题 + 产品引导组成的完整视频片段。

**切片结构**：
```
┌─────────────────────────────────────────────────────────────────┐
│                         完整切片                                  │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │      钩子       │  │    核心话题     │  │   产品引导      │ │
│  │   (3-12秒)      │  │   (≥30秒)       │  │   (≥5秒)        │ │
│  │                 │  │                 │  │                 │ │
│  │ 来自话题开头    │  │ 单一问题/事件   │  │ 与话题相关      │ │
│  │ 吸引注意力      │  │ 深入阐述        │  │ 促进转化        │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│       ↑                        ↑                      ↑         │
│       │                        │                      │         │
│   Hook Start              Topic Start             Pitch End     │
│                         Topic End                        │
└─────────────────────────────────────────────────────────────────┘
         clip_start                                        clip_end
```

---

## 3. 切片结构详细设计

### 3.1 切片结构定义

**理想切片 = 钩子（来自话题内）+ 核心话题 + 产品引导**

```
切片开始                                              切片结束
    │                                                    │
    ▼                                                    ▼
┌────────────────────────────────────────────────────────┐
│  话题开头(3-12秒)   │    话题主体(≥30秒)    │ 产品引导│
│                    │                       │         │
│  ┌──────────────┐  │  ┌─────────────────┐  │ ┌─────┐ │
│  │    钩子     │→│  │                 │  │ │产品 │ │
│  │ (Hook)     │  │  │   核心话题      │→│ │Pitch│ │
│  │ 吸引注意   │  │  │   (Topic)       │  │ │     │ │
│  │ 情感共鸣   │  │  │   单一话题      │  │ │转化 │ │
│  └──────────────┘  │                 │  │ └─────┘ │
│                    │                 │  │          │
│  ← Hook Duration →│← Topic Duration →│← Pitch →   │
│       3-12秒        │      ≥30秒       │    ≥5秒   │
└────────────────────────────────────────────────────────┘
```

### 3.2 各组件职责

| 组件 | 位置 | 时长 | 核心职责 |
|------|------|------|----------|
| **钩子(Hook)** | 话题开头 | 3-12秒 | 吸引注意力，激发兴趣 |
| **核心话题(Topic)** | 话题主体 | ≥30秒 | 传递价值，深入阐述 |
| **产品引导(Pitch)** | 话题结尾 | ≥5秒 | 促进转化，引导购买 |

### 3.3 钩子提取原则（核心变更）

**重要**：钩子必须从当前话题**内部**提取，而不是从话题外部获取。

#### 3.3.1 正确设计

```python
# ✅ 正确：从话题开头提取钩子
def extract_hook_from_topic(topic: Dict, srt_data: List[Dict]) -> Optional[Dict]:
    """
    从话题内部提取钩子
    钩子范围：topic_start ~ topic_start + max_hook_duration
    """
    topic_start = topic['start_time']
    topic_end = topic['end_time']
    max_hook_duration = 12  # 最大钩子时长

    # 在话题开头范围内寻找钩子
    hook_candidates = []
    for sub in srt_data:
        if topic_start <= sub['start_time'] <= topic_end:
            # 检查是否在钩子时间范围内
            hook_duration = sub['end_time'] - topic_start
            if hook_duration <= max_hook_duration:
                hook_candidates.append(sub)

    # 选择最佳钩子
    return select_best_hook(hook_candidates)
```

#### 3.3.2 错误设计（当前问题代码）

```python
# ❌ 错误：从话题开始前的时间范围内找钩子
def extract_hook_WRONG(topic: Dict, srt_data: List[Dict]) -> Optional[Dict]:
    """
    当前错误实现：钩子时间范围在话题开始之前
    """
    topic_start = topic['start_time']
    hook_end_sec = topic_start  # 钩子结束时间 = 话题开始时间
    hook_start_sec = max(0, topic_start - max_duration)  # ❌ 话题外！

    # 在话题开始前找钩子（错误）
    for sub in srt_data:
        if hook_start_sec <= sub['start_time'] < hook_end_sec:  # ❌ 话题外
            ...
```

### 3.4 钩子类型分类

| 类型 | 模式关键词 | 时长特征 | 适用场景 |
|------|----------|----------|----------|
| **疑问型** | 你知道吗、为什么、怎么样、什么是 | 中等(5-10秒) | 知识类、解释类话题 |
| **悬念型** | 没想到、竟然、其实、真相 | 较短(3-8秒) | 揭秘类、故事类话题 |
| **利益型** | 免费、福利、干货、技巧 | 中等(5-10秒) | 教程类、攻略类话题 |
| **数字型** | 3个、5个、十大、第一 | 较短(3-6秒) | 盘点类、列表类话题 |
| **对比型** | vs、对比、区别、哪个更好 | 中等(5-10秒) | 评测类、选择类话题 |
| **趋势型** | 最新、火爆、必看、重磅 | 较短(3-6秒) | 新闻类、热点类话题 |

### 3.5 话题质量标准

#### 3.5.1 单一性标准

**定义**：一个话题只围绕一个核心问题、事件或内容展开。

**验证方法**：
```python
def validate_topic_single(topic: Dict) -> bool:
    """
    验证话题是否单一
    返回 True 表示话题单一，返回 False 表示话题包含多个主题
    """
    content = topic.get('content', [])

    if len(content) <= 1:
        return True  # 单一条目，默认单一

    # 计算内容条目之间的语义相似度
    similarities = []
    for i in range(len(content)):
        for j in range(i + 1, len(content)):
            sim = calculate_semantic_similarity(content[i], content[j])
            similarities.append(sim)

    # 平均相似度低于阈值，认为话题不单一
    avg_similarity = sum(similarities) / len(similarities) if similarities else 0
    return avg_similarity >= SINGLE_TOPIC_THRESHOLD  # 阈值：0.5
```

#### 3.5.2 完整性标准

**定义**：话题有明确的开始和结尾，论述相对完整。

**完整性评估因素**：

| 因素 | 权重 | 说明 |
|------|------|------|
| 有开头语 | 0.2 | 包含"首先、今天、我们"等开头词 |
| 有结尾语 | 0.3 | 包含"所以、因此、总结、最后"等结尾词 |
| 时长合理 | 0.2 | 至少30秒，不超过10分钟 |
| 内容充实 | 0.3 | 子话题点数量≥3 |

**完整性评分公式**：
```
completeness_score = has_start * 0.2 + has_end * 0.3 + duration_score * 0.2 + content_score * 0.3
```

---

## 4. 组件详细设计

### 4.1 话题提取器（TopicExtractor）

#### 4.1.1 核心职责

- 从视频字幕中识别并提取话题
- 验证话题的单一性和完整性
- 过滤无效或低质量话题

#### 4.1.2 接口定义

```python
class TopicExtractor:
    """话题提取器"""

    def extract_topics(self, srt_data: List[Dict]) -> List[Dict]:
        """
        从字幕数据中提取话题

        Args:
            srt_data: SRT格式的字幕数据

        Returns:
            话题列表，每个话题包含：
            - id: 话题ID
            - outline: 话题标题
            - content: 子话题要点列表
            - start_time: 开始时间
            - end_time: 结束时间
            - duration: 持续时间
            - single_score: 单一性评分
            - completeness_score: 完整性评分
        """
        pass

    def validate_topic(self, topic: Dict) -> Dict:
        """
        验证话题质量

        Returns:
            包含验证结果的字典：
            - is_valid: 是否有效
            - single_score: 单一性评分
            - completeness_score: 完整性评分
            - issues: 问题列表
        """
        pass
```

#### 4.1.3 内部流程

```
输入：SRT字幕数据
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  1. 话题边界识别                                         │
│     - 识别话题开始/结束标志                               │
│     - 使用LLM进行话题分割                                 │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  2. 话题结构提取                                          │
│     - 提取话题标题（outline）                            │
│     - 提取子话题要点（content）                          │
│     - 计算时间范围                                       │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  3. 话题质量验证                                          │
│     - 单一性验证（是否多主题）                           │
│     - 完整性验证（是否有始有终）                         │
│     - 时长验证（是否合理）                               │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  4. 话题过滤与排序                                        │
│     - 过滤低质量话题                                     │
│     - 按质量评分排序                                     │
└─────────────────────────────────────────────────────────┘
         │
         ▼
输出：高质量话题列表
```

### 4.2 钩子提取器（HookExtractor）

#### 4.2.1 核心职责（修正版）

- 从话题**内部**（开头部分）提取钩子
- 对钩子进行多维度评分
- 确保钩子与话题语义相关

#### 4.2.2 接口定义

```python
class HookExtractor:
    """钩子提取器（话题内版本）"""

    def __init__(self):
        self.config = {
            'max_duration': 12,      # 最大钩子时长（秒）
            'min_duration': 3,       # 最小钩子时长（秒）
            'min_score': 8,          # 最低评分阈值（0-20）
        }

    def extract_hook_from_topic(self, topic: Dict, srt_data: List[Dict]) -> Optional[Dict]:
        """
        从话题内部提取钩子

        关键：钩子必须来自话题开头部分
        钩子时间范围：topic_start ~ topic_start + max_duration

        Args:
            topic: 话题数据
            srt_data: SRT字幕数据

        Returns:
            钩子数据，包含：
            - start_time: 钩子开始时间
            - end_time: 钩子结束时间
            - text: 钩子文本
            - hook_type: 钩子类型（question/suspense/benefit等）
            - quality_score: 质量评分
        """
        pass

    def score_hook(self, hook_candidate: Dict, srt_data: List[Dict]) -> float:
        """
        对钩子候选进行评分（0-20分）

        评分维度：
        - 钩子模式匹配：最高10分
        - 情感结尾：2分
        - 长度适中：2分
        - 情感强度：2分
        - 内容相关性：4分（新增）
        """
        pass
```

#### 4.2.3 提取流程（修正版）

```
输入：话题 + 字幕数据
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Step 1: 确定钩子提取范围                                │
│  ┌───────────────────────────────────────────────────┐  │
│  │  hook_start = topic_start                        │  │
│  │  hook_end = topic_start + max_duration (12秒)   │  │
│  │                                                   │  │
│  │  ⚠️ 关键：钩子必须在话题内部，不允许在话题外    │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Step 2: 收集候选字幕                                    │
│  - 筛选 hook_start <= subtitle_start < hook_end 的字幕  │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Step 3: 候选评分                                        │
│  - 钩子模式匹配（最高10分）                              │
│  - 情感结尾（2分）                                       │
│  - 长度适中（2分）                                       │
│  - 情感强度（2分）                                       │
│  - 内容相关性（4分）- 新增                               │
└─────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Step 4: 选择最佳钩子                                    │
│  - 评分 >= min_score (8分)                              │
│  - 选择评分最高的候选                                    │
└─────────────────────────────────────────────────────────┘
         │
         ▼
输出：最佳钩子 或 None（未找到合格钩子）
```

#### 4.2.4 评分维度详解

| 评分维度 | 最高分 | 评分标准 |
|----------|--------|----------|
| **钩子模式匹配** | 10分 | question(5), suspense(5), benefit(5), attention(4), number(4)... |
| **情感结尾** | 2分 | 以"？！..."结尾 |
| **长度适中** | 2分 | 8-25字最佳 |
| **情感强度** | 2分 | 包含"太、超级、非常"等词 |
| **内容相关性** | 4分 | 钩子内容与话题主体的相关性（新增） |

### 4.3 钩子类型识别器

#### 4.3.1 类型定义

```python
HOOK_PATTERNS = {
    'greeting': {
        'keywords': ['大家好', '欢迎来到', '我是', '哈喽', '各位朋友'],
        'score': 3,
        'emotion': 'neutral'
    },
    'question': {
        'keywords': ['你知道吗', '为什么', '怎么样', '什么是', '如何', '怎么'],
        'score': 5,
        'emotion': 'curiosity'
    },
    'suspense': {
        'keywords': ['没想到', '竟然', '其实', '真相', '秘密', '惊人'],
        'score': 5,
        'emotion': 'surprise'
    },
    'benefit': {
        'keywords': ['免费', '福利', '干货', '技巧', '方法', '秘诀'],
        'score': 5,
        'emotion': 'excitement'
    },
    'number': {
        'keywords': ['3个', '5个', '10个', '三大', '五大', '十大', '第一'],
        'score': 4,
        'emotion': 'interest'
    },
    'contrast': {
        'keywords': ['vs', '对比', '区别', '不同', '差异'],
        'score': 3,
        'emotion': 'debate'
    },
    'trend': {
        'keywords': ['最新', '火爆', '趋势', '必看', '重磅'],
        'score': 3,
        'emotion': 'urgency'
    },
    'attention': {
        'keywords': ['注意看', '大家看', '仔细看', '接下来', '请看'],
        'score': 4,
        'emotion': 'alert'
    }
}
```

### 4.4 产品匹配器（ProductMatcher）

#### 4.4.1 核心职责

- 从视频中识别产品/带货内容
- 为话题匹配最合适的产品引导
- 确保产品与话题语义相关

#### 4.4.2 接口定义

```python
class ProductMatcher:
    """产品匹配器"""

    def extract_products(self, srt_data: List[Dict]) -> List[Dict]:
        """
        从字幕中提取产品片段

        Returns:
            产品片段列表，每个包含：
            - id: 产品ID
            - start_time: 开始时间
            - end_time: 结束时间
            - text: 产品介绍文本
            - categories: 匹配的产品类别
            - confidence: 置信度
        """
        pass

    def find_best_match(self, topic: Dict, products: List[Dict], srt_data: List[Dict]) -> Optional[Dict]:
        """
        为话题找到最匹配的产品片段

        匹配算法：
        综合评分 = 时间距离(30%) + 语义相似度(30%) + 置信度(20%) + 位置相关(20%)

        Returns:
            最佳匹配产品 或 None
        """
        pass
```

#### 4.4.3 产品关键词库

```python
PRODUCT_KEYWORDS = {
    'purchase': {
        'keywords': ['链接', '购买', '点击', '下单', '购物车', '小黄车', '购物袋'],
        'weight': 1.0
    },
    'promotion': {
        'keywords': ['优惠', '福利', '限时', '特价', '秒杀', '折扣', '满减'],
        'weight': 1.0
    },
    'product': {
        'keywords': ['商品', '推荐', '好物', '神器', '必备', '精选'],
        'weight': 0.8
    },
    'brand': {
        'keywords': ['品牌', '官方', '正品', '旗舰店'],
        'weight': 0.6
    }
}
```

### 4.5 切片生成器（ClipGenerator）

#### 4.5.1 核心职责

- 协调各组件生成完整切片
- 确保切片质量达标
- 组装最终输出

#### 4.5.2 接口定义

```python
class ClipGenerator:
    """切片生成器"""

    def __init__(self):
        self.topic_extractor = TopicExtractor()
        self.hook_extractor = HookExtractor()
        self.product_matcher = ProductMatcher()

    def generate_clips(self, video_path: Path, srt_data: List[Dict]) -> List[Dict]:
        """
        生成完整切片列表

        流程：
        1. 提取话题
        2. 验证话题质量
        3. 从话题内提取钩子
        4. 为话题匹配产品
        5. 组装完整切片
        6. 质量检查
        7. 返回高质量切片

        Returns:
            切片列表
        """
        pass

    def _assemble_clip(self, topic: Dict, hook: Optional[Dict],
                      product: Optional[Dict]) -> Dict:
        """
        组装单个切片

        切片结构：
        - clip_start = hook.start_time (如果有钩子)
        - clip_end = product.end_time (如果有产品)
        - hook 必须在 topic 内部
        - topic 必须完整
        """
        pass
```

---

## 5. 质量保障体系

### 5.1 话题质量标准

| 标准 | 阈值 | 说明 |
|------|------|------|
| 单一性评分 | ≥ 0.5 | 子话题内容之间的语义相似度 |
| 完整性评分 | ≥ 0.6 | 包含开头、结尾、时长、内容 |
| 最小时长 | ≥ 30秒 | 普通话题 |
| 产品讲解最小时长 | ≥ 15秒 | 包含产品的话题 |

### 5.2 钩子质量标准

| 标准 | 阈值 | 说明 |
|------|------|------|
| 钩子评分 | ≥ 8分 | 0-20分量表 |
| 钩子时长 | 3-12秒 | 最佳范围 |
| 内容相关性 | ≥ 0.3 | 钩子与话题的语义相似度 |

### 5.3 切片质量标准

| 标准 | 阈值 | 说明 |
|------|------|------|
| 总时长 | 40秒 - 10分钟 | 最佳范围 |
| 完整性 | ≥ 0.6 | 话题完整，无半截话 |
| 钩子有效性 | True | 钩子来自话题内部 |
| 产品相关性 | ≥ 0.3 | 产品与话题语义相关 |

### 5.4 质量检查流程

```
每个切片生成后，都需要通过质量检查：

┌─────────────────────────────────────────────────────────┐
│  质量检查清单                                           │
├─────────────────────────────────────────────────────────┤
│  □ 话题单一性验证（single_score >= 0.5）               │
│  □ 话题完整性验证（completeness_score >= 0.6）         │
│  □ 钩子来源验证（hook 在 topic 内部）                  │
│  □ 钩子质量验证（hook_score >= 8）                    │
│  □ 产品相关性验证（similarity >= 0.3）               │
│  □ 时长验证（duration 符合要求）                      │
└─────────────────────────────────────────────────────────┘
         │
         ▼
    所有检查通过？
         │
    ┌────┴────┐
    │         │
   YES        NO
    │         │
    ▼         ▼
  输出    标记为低质量切片
  切片    或跳过
```

---

## 6. 数据结构定义

### 6.1 话题结构

```python
@dataclass
class Topic:
    id: str                          # 话题唯一ID
    outline: str                     # 话题标题
    content: List[str]              # 子话题要点列表
    start_time: str                 # 开始时间（HH:MM:SS,mmm）
    end_time: str                   # 结束时间（HH:MM:SS,mmm）
    duration: float                 # 持续时间（秒）
    single_score: float             # 单一性评分（0-1）
    completeness_score: float        # 完整性评分（0-1）
    quality_score: float             # 综合质量评分（0-1）
```

### 6.2 钩子结构

```python
@dataclass
class Hook:
    start_time: str                 # 钩子开始时间
    end_time: str                   # 钩子结束时间
    text: str                       # 钩子文本内容
    hook_type: str                  # 钩子类型（question/suspense/benefit等）
    quality_score: float             # 质量评分（0-20）
    matched_keyword: str            # 匹配的关键词
```

### 6.3 产品片段结构

```python
@dataclass
class ProductPitch:
    id: str                         # 产品ID
    start_time: str                 # 开始时间
    end_time: str                   # 结束时间
    text: str                        # 产品介绍文本
    categories: List[str]           # 产品类别列表
    confidence: float                # 置信度（0-1）
```

### 6.4 切片结构

```python
@dataclass
class Clip:
    id: str                         # 切片唯一ID
    topic_id: str                    # 关联的话题ID
    topic_title: str                 # 话题标题

    # 钩子（来自话题内部）
    hook: Optional[Hook]             # 钩子数据

    # 核心话题
    topic: Topic                     # 完整话题数据

    # 产品引导
    product_pitch: Optional[ProductPitch]  # 产品数据

    # 时间范围
    start_time: str                  # 切片开始时间
    end_time: str                    # 切片结束时间
    duration: float                  # 切片时长（秒）

    # 质量指标
    quality_score: float              # 综合质量评分
    completeness_score: float        # 完整性评分
    hook_topic_relevance: float      # 钩子-话题相关性
    topic_product_relevance: float   # 话题-产品相关性

    # 标记
    has_valid_hook: bool             # 是否有有效钩子
    has_product: bool               # 是否包含产品引导
```

---

## 7. 配置参数

### 7.1 话题提取配置

```python
TOPIC_CONFIG = {
    # 时长过滤
    "min_duration": 30,              # 普通话题最短时长（秒）
    "min_product_duration": 15,      # 产品话题最短时长（秒）
    "max_duration": 600,             # 最长时长（秒）

    # 质量过滤
    "min_single_score": 0.5,         # 单一性阈值
    "min_completeness_score": 0.6,   # 完整性阈值
}
```

### 7.2 钩子提取配置

```python
HOOK_CONFIG = {
    "max_duration": 12,              # 最大钩子时长（秒）
    "min_duration": 3,               # 最小钩子时长（秒）
    "min_score": 8,                  # 最低评分（0-20）

    # 评分权重
    "score_weights": {
        "pattern_match": 10,          # 模式匹配
        "emotion_ending": 2,          # 情感结尾
        "length": 2,                  # 长度适中
        "emotion_intensity": 2,       # 情感强度
        "content_relevance": 4,       # 内容相关性
    }
}
```

### 7.3 产品匹配配置

```python
PRODUCT_CONFIG = {
    "min_duration": 5,               # 产品片段最短时长（秒）
    "max_search_range": 300,         # 产品搜索最大时间范围（秒）
    "min_confidence": 0.5,           # 最低置信度
    "min_relevance": 0.3,            # 最低语义相关性

    # 匹配权重
    "match_weights": {
        "time_distance": 0.3,        # 时间距离
        "semantic": 0.3,              # 语义相似度
        "confidence": 0.2,           # 置信度
        "position": 0.2              # 位置相关性
    }
}
```

---

## 8. 实施计划

### 8.1 第一阶段：核心模块重构

| 任务 | 优先级 | 工作内容 |
|------|--------|----------|
| 修复钩子提取逻辑 | P0 | 修改hook_extractor.py，确保钩子从话题内部提取 |
| 实现话题质量验证 | P0 | 添加单一性和完整性验证 |
| 更新切片组装逻辑 | P0 | 修改smart_clip_generator.py |

### 8.2 第二阶段：质量体系完善

| 任务 | 优先级 | 工作内容 |
|------|--------|----------|
| 实现质量检查流程 | P1 | 添加质量检查清单 |
| 添加质量反馈机制 | P2 | 记录切片表现数据 |

---

## 9. 附录

### 9.1 相关文件

| 文件路径 | 说明 |
|---------|------|
| `backend/utils/smart_clip_generator.py` | 切片生成器（待修改） |
| `backend/utils/hook_extractor.py` | 钩子提取器（待修改） |
| `backend/utils/topic_validator.py` | 话题验证器（待新增） |
| `backend/utils/product_detector.py` | 产品检测器 |
| `backend/utils/reuse_library.py` | 复用库管理器 |

### 9.2 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0 | - | 初始版本 |
| v2.0 | 2026-05-13 | 修正钩子提取原则：钩子必须从话题内部提取 |

---

**文档版本**: v2.0
**最后更新**: 2026-05-13
**维护者**: AutoClip开发团队
