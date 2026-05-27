# Prompt 多步拆分 — 多轮缺陷分析与修正方案

> **结论先行：原四步方案存在 8 个缺陷，其中 4 个为致命级。修正方案为"三步 + 代码后处理"，总 LLM 调用次数从 14 次降至 3 次。**

---

## 第 1 轮分析：结构性缺陷

### 缺陷 1（致命）：错误传播无阻断机制

```
Step1 边界识别错误
  → Step2 基于错误边界做合并（雪上加霜）
    → Step3 基于错误话题做评分（全盘皆错）
      → Step4 基于错误内容生成标题（张冠李戴）
```

**与 merged 的对比**：merged 模式在一次调用中完成所有任务，LLM 在给片段打分时仍然可以看到完整 SRT，有机会在评分阶段"察觉"到边界切错了并调整。四步模式下，一旦 Step1 出错，后续步骤没有恢复能力——因为它们根本看不到完整 SRT。

**严重性评价**：致命。一次边界错误会导致全部输出报废，且无法自动恢复。

---

### 缺陷 2（致命）：Step 2 输入缺失原始 SRT，无法做语义合并

方案第 2 步的架构图写着"输入: Step1 输出的所有话题 + 完整 SRT"，但我实际写的 `FUNCLIP_STEP2_CLUSTER_PROMPT` 中**只传了 JSON 摘要，没有传原始 SRT 文本**。

这意味着 Step 2 的 LLM 只能基于 outline（15 字摘要）来判断是否合并，完全看不到原始字幕内容。例如：

| 话题 A outline | 话题 B outline | LLM 仅见 | 实际情况 |
|---------------|---------------|---------|---------|
| "京油子嘴的特点" | "王爷势力为何复杂" | 两个不同话题 | 原文中是"京油子→油滑→所以王爷势力复杂的"的因果链 |

没有原始 SRT，LLM 无法发现这种因果关系。**反向追溯和溯源牵引完全失效。**

**严重性评价**：致命。Step 2 的存在意义被掏空。

---

### 缺陷 3（致命）：Step 3 逐话题独立评分——评分不可比较

```
Step 3 调用 A: 话题1 → 某次 LLM 状态 → 评分 0.82
Step 3 调用 B: 话题2 → 另一次 LLM 状态 → 评分 0.85
```

**问题**：两次独立 LLM 调用之间不存在"评分基准共享"。同一个话题内容，两次调用可能分别给出 0.7 和 0.9——因为 GLM-4-Flash 的评分判断受随机性影响。这意味着：

- 最终排序可能不准确（评分高的不一定真的好）
- 不能用 `final_score >= 0.5` 来筛选（不同调用的 0.5 含义不同）
- 无法做"全局最高分话题"的判断

**严重性评价**：致命。评分环节的核心价值被破坏。

---

### 缺陷 4（致命）：Step 3 评分时 LLM 看不到完整 SRT，无法验证边界

Step 3 只传入单话题的 SRT 片段，缺少该话题前后 SRT 的上下文。评分时需要判断：
- "话题完整度"：是否具备引入+核心+收尾——这需要看到话题边界的上下文才能判断
- "反向追溯"：文章结尾引用的概念是否在前文存在——看不到前文

**严重性评价**：致命。三个评分维度中有两个依赖跨边界上下文。

---

## 第 2 轮分析：Prompt 内容缺陷

### 缺陷 5（严重）：原方案 Step 1 砍掉了关键的 7 条规则

对照 merged prompt，我发现我的四步方案 Step 1 简化过度，缺失了以下关键规则：

| 规则 | merged 有 | 四步 Step1 | 影响 |
|------|----------|-----------|------|
| **情绪连续不拆分例外** | ✅ | ❌ | 会把"怼人+继续怼人"拆成两个话题 |
| **跨间隙语义验证（4~60秒）** | ✅ | ❌ | 虚假间隙导致话题碎片化 |
| **产品推介三分类（自然/突兀/多产品）** | ✅ | ❌ | 全混为"类型切换=新话题"，丢失"自然引出应合并"的细腻度 |
| **自然过渡不拆分** | ✅ | ❌ | 钩子→核心的自然演进被切断 |
| **反向追溯规则** | ✅ | ❌ | 收尾入选但前导入选丢失时无法回溯 |
| **溯源牵引规则** | ✅ | ❌ | 依赖叙事背景的内容变得莫名其妙 |
| **被其他话题打断后的跨段合并** | ✅ | 简化为"同一话题的第二个segment" | 缺少 180s/600s 的量化判定条件 |

**根本原因**：我在设计 Step 1 时过度追求"prompt 短"，一刀切砍掉了大量精细化规则。这些规则恰恰是 merged prompt 使系统能正确处理复杂直播场景的核心。

---

### 缺陷 6（中等）：removed_sections 应该由代码计算，不应让 LLM 做

merged prompt 要求 LLM 标记 removed_sections（静音剔除），这个任务完全可以通过代码确定性完成——`_validate_segments_with_srt` 函数已经实现了这个功能。让 LLM 做静音标记存在两个问题：

1. LLM 算时间差容易出错
2. 增加了 Step 1 的认知负担

---

## 第 3 轮分析：执行流程缺陷

### 缺陷 7（严重）：14 次 API 调用的实际延迟远超预期

```
假设 6 个话题的场景：
  Step 1: 1 次（~60 行 prompt）→ 预计 5-8 秒
  Step 2: 1 次（~40 行 prompt）→ 预计 3-5 秒
  Step 3: 6 次（~25 行 prompt）→ 预计 2-4 秒/次 × 6 = 12-24 秒
  Step 4: 6 次（~15 行 prompt）→ 预计 1-3 秒/次 × 6 = 6-18 秒
  总计：26-55 秒
```

对比 merged 模式单次调用 30-60 秒，**延迟改善微乎其微**，但复杂度翻了几倍。

更严重的是，GLM-4-Flash 免费版可能有 **QPS 限制**（如 3 次/秒）。连续 14 次调用大概率触发限流，导致部分调用失败。

---

### 缺陷 8（中等）：中间状态管理复杂度高，每步都可能成为断点

```
数据流：原始SRT → Step1中间JSON → Step2合并JSON → Step3逐话题JSON → Step4标题文本
              ↑ 可能失败      ↑ 可能失败       ↑ 某话题失败      ↑ 某话题失败
```

每一步都需要：
- 保存中间结果到 checkpoint 文件
- try-catch 包裹
- 失败重试逻辑
- 兜底回退策略

代码复杂度相比现在的 merged 模式（一个 try-catch + `_fallback_process`）至少翻 4 倍。

---

## 第 4 轮：修正方案设计

### 设计原则

经过三轮分析，提炼出以下设计原则：

| 原则 | 说明 |
|------|------|
| **分解认知域，不分解语义上下文** | 边界识别必须保留完整 SRT 上下文 |
| **批量 > 逐条** | 评分和标题用批量调用（一次看到所有话题），保证评分可比 |
| **LLM 做语义，代码做计算** | removed_sections、边界对齐、间隙填充全部交给代码 |
| **降低调用次数是硬指标** | 目标 ≤ 3 次 LLM 调用 |

### 修正架构：三步 + 代码后处理（3 次 LLM 调用）

```
原始 SRT
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: 带全规则的话题边界识别（1 次调用，~90 行 prompt）        │
│                                                                 │
│ 保留 merged prompt 的全部边界识别规则（精简表达但逻辑完整）：      │
│   - 前向依赖检验 + 指代词/因果词/承前词触发词                     │
│   - 收尾检验 + 情绪连续不拆分例外                                 │
│   - 跨间隙语义验证（4~60秒虚假间隙处理）                          │
│   - 跨段话题合并（打断后重连，含180s/600s量化规则）               │
│   - 产品推介三分类（自然引出/突兀/多产品）                        │
│   - 自然过渡不拆分（钩子→核心的连续演进）                         │
│   - 反向追溯规则 + 溯源牵引规则                                   │
│                                                                 │
│ 不包含（交给后两步或代码）：                                      │
│   ❌ 加权评分公式 → Step 2                                       │
│   ❌ 标题生成 → Step 3                                           │
│   ❌ removed_sections 标记 → 代码后处理                           │
│   ❌ 低俗词汇过滤 → Step 3                                       │
│   ❌ 全局硬性约束自检 → 代码后处理                                │
│                                                                 │
│ 输出: 话题列表（含 id, outline, segments, topic_type）           │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ 代码后处理（0 次 LLM 调用）                                       │
│                                                                 │
│ 1. _validate_segments_with_srt(): 边界对齐 + 间隙填充             │
│ 2. 计算 removed_sections（基于 SRT 时间戳差值，确定性计算）        │
│ 3. 合并相邻同类型短话题（< 20 秒的相邻话题自动合并）               │
│                                                                 │
│ 输出: 修正后的话题列表                                            │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: 逐话题批量评分（1 次调用，~45 行 prompt）                 │
│                                                                 │
│ 一次传入所有话题（含完整 SRT 片段文本），LLM 可以横向比较：         │
│   - 输入: 所有话题的 {id, outline, srt_text, topic_type,          │
│           segments 时长}                                         │
│   - 评分维度: 看点价值 × 0.5 + 话题完整度 × 0.3                   │
│             + 叙事流畅度 × 0.2                                    │
│   - 输出: 每个话题的 final_score + sub_scores + recommend_reason  │
│                                                                 │
│ 关键优势: 同一次 LLM 调用内完成所有评分 → 评分基准统一、可比较     │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: 逐话题批量标题生成（1 次调用，~30 行 prompt）             │
│                                                                 │
│ 一次传入所有话题（含 SRT、outline、recommend_reason、topic_type）， │
│ 批量生成标题：                                                    │
│   - 输入: 每个话题的 {id, srt_text, outline, topic_type,         │
│           recommend_reason}                                       │
│   - 输出: 每个话题的 title                                        │
│                                                                 │
│ 关键优势:                                                        │
│   - 批量调用减少延迟（1 次 vs. N 次）                             │
│   - 标题间可以保证差异化（LLM 能看到所有话题，避免雷同标题）        │
│   - 低俗词汇过滤集中在一处处理                                     │
└─────────────────────────────────────────────────────────────────┘
  │
  ▼
最终后处理: 按 final_score 降序排序 → 取前 6 个 → 按时间升序重新编号 id
```

---

### 修正后与原始四步方案对比

| 维度 | 原始四步方案 | 修正三步方案 | 改善 |
|------|------------|------------|------|
| LLM 调用次数 | 2+N+N（最多 14 次） | 3 次 | **↓ 79%** |
| 边界规则完整性 | 6 条简化规则 | ~20 条完整规则 | **与 merged 持平** |
| 评分可比较性 | 独立调用，不可比 | 同次调用，可比较 | **修复致命缺陷** |
| Step 2 是否有原始 SRT | 无（仅 JSON 摘要） | 不需要独立的合并步骤 | **消除整步** |
| removed_sections | LLM 计算 | 代码计算 | **更可靠** |
| 代码复杂度 | 高（14 个 try-catch） | 中（3 个 try-catch） | **↓ 50%** |
| 最大单步 prompt 行数 | 60 行 | 90 行 | 仍在可控范围 |
| QPS 压力 | 高（14 次连续调用） | 低（3 次调用） | **消除限流风险** |

---

### 为什么去掉了独立的"聚类合并"步骤

原始 merged prompt 中的跨段合并规则本质上是一种"边界修正"——告诉 LLM"虽然你看到两个分离的段落，但如果是同一话题就合在一起"。在修正方案中：

1. Step 1 的 prompt 本身就包含"跨段话题合并"规则，LLM 在边界识别阶段就会把同一话题的不同段落输出为同一个 topic 的多个 segments
2. 因此不需要独立的 Step 2 来二次合并
3. 代码后处理的"相邻同类型短话题合并"覆盖了 LLM 可能遗漏的合并场景

---

### 各步骤 Prompt（修正版）

#### Step 1 Prompt：带全规则的话题边界识别（~90 行）

```python
FUNCLIP_STEP1_BOUNDARY_PROMPT = """## 任务
分析下方SRT字幕，识别每个独立话题的边界和类型。只输出JSON数组，不要任何解释或分析。

## 输出格式
```json
[
  {
    "id": "1",
    "outline": "话题概述（20字以内，描述从引入到收尾的完整内容）",
    "segments": [
      {"start": "00:01:00,000", "end": "00:05:30,000"}
    ],
    "topic_type": "knowledge"
  }
]
```
时间格式hh:mm:ss,fff。每条话题可包含多个segments（被打断后重连的情况）。没有精彩内容时输出[]。

## 话题类型
"highlight": 冲突金句/情绪峰值/反转观点
"knowledge": 知识点讲解/经验分享/数据分析
"product": 商品卖点/价格功能/购买引导
"fun": 段子/八卦/娱乐互动
"daily": 过渡铺垫/流程介绍/日常对话

## 话题边界判定规则

### 1. 前向依赖检验（相邻SRT条目对）
SRT(N+1)满足以下任一条件 → 与SRT(N)同话题：
- 指代词：这/那/他/它/这个/那个 开头指向SRT(N)内容
- 因果词：为什么/所以/因此/因为 解释SRT(N)内容
- 承前词：刚才/说到/提到/那你说 引用SRT(N)内容
- 对SRT(N)某表述的回应、解释、举例或延伸

### 2. 收尾检验
SRT(N)满足以下状态 → 话题可能结束：
- 结论性表述：总之/所以说/明白了吧/你知道吧
- 从具体案例回到一般性总结
满足收尾 + SRT(N+1)不依赖SRT(N) → 话题边界

### 3. 情绪连续不拆分例外
SRT(N)看似收尾，但SRT(N+1)与之满足以下任一条件 → 不拆分：
- 同一情绪线延续：在同一语境下继续评论/吐槽，话题关键词一致
- 同一叙事延续：SRT(N+1)引用/回指SRT(N)中提到的具体细节
- 同一对话对象：针对同一观众/事件的连续回应
判断方法：去掉收尾词后，SRT(N)和SRT(N+1)是否仍是连贯语流？

### 4. 跨间隙语义验证
相邻短条目（每条≤3秒，间隙≤3秒）先合并为语义段落再做话题分析。
跨4~60秒间隙判定同话题条件：
- 后块是对前块的案例验证或例证
- 后块是对前块的延伸、对比或补充
- 后块引用了前块的核心概念（"刚才说的XX"）

### 5. 跨段话题合并（被打断后重连）
同一话题被其他话题打断，出现在时间线多段时，满足以下条件 → 合并为同一话题的多段：
- 后文是对前文的补充/举例/延伸/深化
- 后文是主播个人经历结合来说明前文观点
- 后文是对前文观点的总结/呼应/收尾

判定为新话题的条件：
- 主播明确说"换个话题""接下来说说"
- 语义优先级兜底：有内容承接/"刚才说到" → 仍合并
- 间隔>180秒 + 穿插≥3个话题 → 新话题
- 间隔>600秒 + 穿插≥1个话题 → 新话题
- 前文已有明确收尾 + 后文无"刚才说到"等承接 → 新话题

### 6. 产品推介分类规则
- 自然引出：内容自然延伸（"电影里的撒尿牛丸→我们家的牛肉丸"）→ 合并
- 突兀出现：与前后无承接（刚聊完历史突然说"上链接"）→ 独立为product话题
- 连续多产品：先卖A再卖B再卖C → 各自独立为product话题
判断方法：去掉产品部分，前文话题是否完整自洽？完整→独立；不完整→合并

### 7. 自然过渡不拆分
钩子(段子/故事/顺口溜)→核心话题的自然推进，节奏连贯无明显切换信号 → 同一话题，不拆分。

### 8. 反向追溯规则
话题收尾引用了前文概念 → 向前回溯到该概念首次出现位置，一并纳入。最大回溯不超过起始时间前5分钟或遇到上一话题的收尾信号。

### 9. 溯源牵引规则
核心内容依赖前文叙事背景（如"食神里的撒尿牛丸"引入产品），去掉背景后不懂 → 前文一并纳入。

## 硬性约束
- segments按开始时间升序排列
- segment起止对齐SRT首尾时间戳，不切割单条字幕
- 单话题总时长≤5分钟，超出则从自然边界拆
- 最多输出8个话题（后续步骤会筛选到6个）
"""
```

#### Step 2 Prompt：批量评分（~45 行）

```python
FUNCLIP_STEP2_BATCH_SCORE_PROMPT = """## 任务
对下方所有话题做评分。你必须在同一次判断中横向比较它们，确保评分可比较。

## 所有话题
```json
[
  {
    "id": "1",
    "outline": "话题概述",
    "topic_type": "knowledge",
    "total_duration_seconds": 185,
    "srt_text": "00:01:00,000 --> 00:01:05,000\\n这是第一条字幕内容...\\n...(完整SRT)"
  }
]
```

## 评分维度
- 看点价值(0~1): 冲突金句/独家信息/情绪爆发。锚点：0.9=金句冲突，0.7=干货知识，0.5=日常讲述
- 话题完整度(0~1): 引入+核心+收尾的完整度。锚点：0.9=三段完整，0.7=有核心+收尾，0.5=仅核心
- 叙事流畅度(0~1): 逻辑连贯性。锚点：0.9=一气呵成，0.7=偶尔卡顿，0.5=多处卡顿

## 计算
final_score = 看点价值×0.5 + 话题完整度×0.3 + 叙事流畅度×0.2

## 输出
```json
{
  "scores": [
    {
      "id": "1",
      "final_score": 0.75,
      "sub_scores": {"看点价值": 0.8, "话题完整度": 0.7, "叙事流畅度": 0.7},
      "recommend_reason": "基于实际内容的推荐理由（≤20字）"
    }
  ]
}
```
只输出 final_score >= 0.5 的话题。recommend_reason 每条不同，基于实际内容。同分时排序优先级：highlight > knowledge > product > fun > daily。
"""
```

#### Step 3 Prompt：批量标题生成（~25 行）

```python
FUNCLIP_STEP3_BATCH_TITLE_PROMPT = """## 任务
为下方每个话题生成一个吸引人的标题。所有标题必须互不相同。

## 话题列表
```json
[
  {
    "id": "1",
    "topic_type": "knowledge",
    "outline": "话题概述",
    "recommend_reason": "推荐理由",
    "srt_text": "完整字幕文本(最多取前200字符)"
  }
]
```

## 标题规则
1. 8~20个中文字符
2. 优先钩子句式：设问/悬念/对比/数字/感叹
3. 禁用低俗词汇（装逼/傻逼/他妈的/逼味等），替换为中性表述（犀利点评/直率吐槽）
4. 不得照抄字幕原始低俗措辞

## 输出
```json
{
  "titles": [
    {"id": "1", "title": "标题文本"}
  ]
}
```
"""
```

---

### 与 merged prompt 的规则对照完整性检查

| merged prompt 规则 | 修正 Step 1 | Step 2 | Step 3 | 代码后处理 |
|-------------------|------------|--------|--------|-----------|
| 前向依赖检验 | ✅ 规则 1 | — | — | — |
| 收尾检验 | ✅ 规则 2 | — | — | — |
| 情绪连续不拆分例外 | ✅ 规则 3 | — | — | — |
| 跨间隙语义验证 | ✅ 规则 4 | — | — | — |
| 跨段话题合并 | ✅ 规则 5 | — | — | — |
| 产品推介三分类 | ✅ 规则 6 | — | — | — |
| 自然过渡不拆分 | ✅ 规则 7 | — | — | — |
| 反向追溯 | ✅ 规则 8 | — | — | — |
| 溯源牵引 | ✅ 规则 9 | — | — | — |
| 加权评分公式 | — | ✅ 三因子 | — | — |
| 看点价值 | — | ✅ | — | — |
| 话题完整度 | — | ✅ | — | — |
| 叙事流畅度 | — | ✅ | — | — |
| 排序类型优先级 | — | ✅ | — | — |
| 标题生成 | — | — | ✅ | — |
| 低俗词汇过滤 | — | — | ✅ | — |
| 边界对齐SRT | — | — | — | ✅ `_validate_segments_with_srt` |
| removed_sections | — | — | — | ✅ 时间戳差值计算 |
| segments升序 | ✅ | — | — | ✅ 排序 |
| 无重叠检查 | — | — | — | ✅ `_deduplicate_clip_segments` |
| id重新编号 | — | — | — | ✅ 最终排序后编号 |

**覆盖率：merged prompt 的 20 条规则，修正方案 100% 覆盖，无遗漏。**

---

### 延迟预估

```
Step 1: 1 次（~90 行 prompt）→ 预计 6-10 秒
Step 2: 1 次（~45 行 prompt）→ 预计 3-5 秒
Step 3: 1 次（~25 行 prompt）→ 预计 2-4 秒
代码后处理: ~1 秒
总计: 12-20 秒
```

对比 merged 模式 30-60 秒，**修正方案延迟降低 50-67%**。

---

### 验收标准

```
[ ] Step 1 输出的 segments 按时间升序排列
[ ] Step 1 输出的 topic_type 正确分类（knowledge/product/highlight/fun/daily）
[ ] Step 1 正确处理产品推介三分类（自然/突兀/多产品）
[ ] Step 2 所有话题的 sub_scores 可追溯
[ ] Step 2 评分横向可比较（同一 base 的评分基准）
[ ] Step 3 所有标题互不相同
[ ] Step 3 标题不包含低俗词汇
[ ] 全链路成功率 ≥ 90%
[ ] 总处理时间 ≤ merged 模式的 50%
[ ] 输出 JSON 格式正确率 100%
[ ] 产品推荐不与干货知识混在同一话题
[ ] removed_sections 由代码正确计算
```

---

## 第 5 轮分析：修正方案的再验证（2026-05-25）

> **本轮对"三步 + 代码后处理"修正方案进行独立核查，发现 22 个新缺陷，其中 10 个为致命级。**

### 第 5 轮缺陷总览

| 轮次 | 聚焦范围 | 致命 | 严重 | 中等 | 低 | 合计 |
|------|---------|------|------|------|-----|------|
| 5-A | Step 1 边界识别 Prompt | 2 | 3 | 1 | 0 | 6 |
| 5-B | Step 2 批量评分 Prompt | 2 | 3 | 1 | 0 | 6 |
| 5-C | Step 3 批量标题 Prompt | 2 | 3 | 0 | 0 | 5 |
| 5-D | 代码后处理 + 流程集成 | 1 | 3 | 2 | 0 | 6 |
| 5-E | 整体流程端到端 | 3 | 2 | 1 | 0 | 6 |
| **合计** | | **10** | **14** | **5** | **0** | **29*** |

> \* 含与原四步方案重叠的 7 个缺陷（已计入原始 8 个缺陷统计中），净新增 **22 个**。

---

### 第 5-A 轮：Step 1 边界识别 Prompt 检查

#### 缺陷 5A-1（致命）："没有精彩内容时输出[]" 与纯边界识别职责冲突

```diff
修正 Step 1 的设计意图是"仅做边界识别 + 话题分类"，但 Prompt 末尾写了：
+ "没有精彩内容时输出[]"

- 问题：Step 1 的职责是识别"话题边界"，不是判断"精彩程度"
- "精彩"是 Step 2 评分阶段的概念
- 让 Step 1 做精彩度判断 → LLM 可能在边界识别阶段就"过早起筛"，
  跳过那些边界清晰但不那么精彩的潜在话题
```

**实际影响**：短知识片段、过渡性产品介绍等内容可能被 Step 1 直接丢弃，Step 2 根本没机会评分。

**修正方向**：改为"字幕中无明显独立话题时输出[]"，将"精彩"的判断留给 Step 2。

---

#### 缺陷 5A-2（致命）：缺少"处理步骤"的程序性指引

```diff
merged prompt 有明确的五步处理流程：
第一步：话题识别与完善 → 第二步：对齐边界到SRT条目 → 
第三步：标记纯静音 → 第四步：打分与排序 → 第五步：自检复核

修正 Step 1 只有规则列表（规则1~9），没有"先做什么、后做什么"的程序性指引。
- GLM-4-Flash 对规则列表的执行顺序不可控
+ LLM 可能先尝试合并再识别依赖链，或跳跃执行
```

**实际影响**：LLM 可能按"最显眼的规则"而不是"最合理的顺序"来工作，导致边界识别混乱。

**修正方向**：在规则列表前增加"分析步骤"小节，明确：先依赖链分析 → 再跨段合并 → 再反向追溯 → 再溯源牵引 → 最后分类。

---

#### 缺陷 5A-3（严重）：outline "20字以内" 约束与多段话题不匹配

```diff
修正 Step 1 要求 outline 不超过 20 字，但多段话题可能包含：
- 3 段分布在 15 分钟内的内容
- 包含反转、个人经历、产品种草等多个子情节

+ 20 字对复杂话题过于压缩，Step 2 评分时依赖 outline 理解话题，
  过度压缩的 outline 可能导致评分失真
```

**修正方向**：改为"30字以内"，或按 segment 数量动态放宽（≤2段: 20字，>2段: 30字）。

---

#### 缺陷 5A-4（严重）：规则 8 的"最大回溯不超过5分钟"依赖尚不存在的上下文

```diff
规则 8: "最大回溯不超过起始时间前5分钟或遇到上一话题的收尾信号"

- "起始时间"在 Step 1 阶段指的是 topic 的第一个 segment 的开始时间
- 但 topic 的最终时间边界在代码后处理阶段还会被调整
+ LLM 可能在 Step 1 中基于不准确的"起始时间"做出错误回溯决策
```

**修正方向**：在规则中明确"从当前话题最靠前的 segment 起始时间向前回溯"。

---

#### 缺陷 5A-5（严重）：规则 5 的跨段合并量化阈值（180s/600s）在纯边界识别阶段可能被误用

```diff
规则 5: "间隔>180秒 + 穿插≥3个话题 → 新话题"
       "间隔>600秒 + 穿插≥1个话题 → 新话题"

- 这些阈值在 merged prompt 中是有效的，因为 LLM 在同一上下文中
  同时看到所有话题，可以精确"计数"穿插的话题数
- 但在 Step 1 中，LLM 还在识别过程中，可能无法准确判断"穿插了多少个话题"
+ 可能导致过度拆分或过度合并
```

**修正方向**：将量化阈值规则改为定性描述，精确计数交给代码后处理。

---

#### 缺陷 5A-6（中等）：缺少"自检复核"步骤

```diff
merged prompt 第五步自检包括：
1. 被选中片段SRT条目完整归属
2. 不同片段间无重叠
3. 每条SRT唯一归属
4. 边界验证（去掉前导后是否奇怪）
5. removed_sections时间正确
6. 时间格式验证

修正 Step 1 没有自检环节。
- LLM 输出的 segments 可能重叠、遗漏SRT条目、或切割单条字幕内部
+ 这些错误需要代码后处理来修复，但修复的前提是能检测到
```

**修正方向**：在 Step 1 末尾增加简化版自检清单，至少包含"无重叠"和"对齐SRT边界"两项。

---

### 第 5-B 轮：Step 2 批量评分 Prompt 检查

#### 缺陷 5B-1（致命）：srt_text 总量可能超出 GLM-4-Flash 上下文窗口

```diff
Step 2 为每个话题传入"完整SRT片段文本"。
假设 Step 1 输出 8 个话题，每个话题平均 150 条 SRT：
- 每条 SRT ~40 字符
- 每个话题 150×40 = 6,000 字符
- 8 个话题 = 48,000 字符 + Prompt ~1,500 字符 = ~50,000 字符

- GLM-4-Flash 免费版上下文窗口: 8K tokens（约 12,000 中文字符）
  或 128K（付费版）
+ 如果用户使用的是免费版（8K），一次传入全部话题会触发截断
```

**实际影响**：超出上下文窗口的部分会被截断，部分话题完全无法被评分 → 评分不完整。

**修正方向**：
- 方案 A：按 topic_type 优先级分两批（highlight+knowledge 一批，product+fun+daily 一批），高分类型优先
- 方案 B：每个话题只传前 100 条 SRT + 最后 20 条 SRT（覆盖引入和收尾）
- 方案 C：代码预估算 token 数，超出时自动分批

---

#### 缺陷 5B-2（致命）：LLM 不知道话题是另一个 LLM 识别的，可能重新评估边界

```diff
Step 2 接收到的是 Step 1 输出的话题和对应的 SRT 片段。
- LLM 没有被告知"这些边界已经由前序步骤确定，不需要重新评估"
+ LLM 可能在评分时对边界产生质疑：
  "这个 SRT 片段似乎包含了两个不同话题..."
  → 从而给出不准确的评分（因为它在用"边界是否正确"来判断"内容好不好"）
```

**修正方向**：在 Prompt 开头明确说明"以下话题的边界已经过专业分析确定，你只需对内容质量评分，不要质疑或重新评估边界"。

---

#### 缺陷 5B-3（严重）：排序优先级规则不应放在评分 Prompt 中

```diff
Step 2 Prompt: "同分时排序优先级：highlight > knowledge > product > fun > daily"

- 这是纯机械的排序逻辑，应在代码中实现
+ 放在 Prompt 中会分散 LLM 在"评分"核心任务上的注意力
+ LLM 可能"为了方便排序"而人为抬高 highlight 类型话题的分数
```

**修正方向**：从 Prompt 删除排序规则，改为代码后处理中按 `(-final_score, -type_priority)` 排序。

---

#### 缺陷 5B-4（严重）：final_score >= 0.5 的过滤应由代码执行

```diff
Step 2 Prompt: "只输出 final_score >= 0.5 的话题"

- 让 LLM 做阈值过滤有两个问题：
  1. LLM 的评分基准不稳定，不同调用的 0.5 含义不同
  2. 如果 LLM 误把所有话题判为 < 0.5，输出空列表，Step 3 无数据可处理
+ 应让 LLM 输出所有话题的分数，代码根据分数排序后取前 6 或应用阈值
```

**修正方向**：移除阈值过滤指令，改为"为每个话题打分"，代码处理过滤和 Top-K。

---

#### 缺陷 5B-5（严重）：recommend_reason "每条不同" 在批量模式下仍可能失败

```diff
虽然批量模式比逐条模式好，但如果两个话题内容相似：
- 两个 product 类型话题都是护肤品介绍
- 两个 knowledge 话题都讲"如何选品"
→ LLM 可能给出几乎相同的 recommend_reason

+ 合并方案中通过代码检测到这个问题（set 去重检查）
+ 三步方案中缺少类似的后处理校验
```

**修正方向**：Step 2 处理完成后，代码检测 recommend_reason 重复率，重复率 > 50% 时触发重试。

---

#### 缺陷 5B-6（中等）：total_duration_seconds 应由代码预计算

```diff
Step 2 输入格式包含 "total_duration_seconds": 185
- 这是每个话题所有 segment 的总时长，需要精确计算
+ 如果让 LLM 计算，可能出错（时间加减对 LLM 是弱项）
+ 应作为代码预处理步骤，在调用 Step 2 前计算好并填入
```

**修正方向**：在 Step 2 的代码实现中，调用前自动计算每个 topic 的 total_duration_seconds。

---

### 第 5-C 轮：Step 3 批量标题 Prompt 检查

#### 缺陷 5C-1（致命）："最多取前200字符" 对倒叙结构话题致命

```diff
Step 3 中 srt_text: "完整字幕文本(最多取前200字符)"

- 许多直播话题的结构是：
  引入（无聊） → 核心冲突（精彩） → 收尾
  或者：抛钩子（一句话） → 铺垫 → 核心观点

+ 前 200 字符可能只覆盖了引入/铺垫部分
+ 基于引入部分生成的标题与话题核心内容脱节
```

**修正方向**：
- 方案 A：取话题中间 1/3 位置的 SRT（经验上核心内容通常在中间）
- 方案 B：结合 outline + recommend_reason + 前 200 字符 + 后 200 字符
- 方案 C：代码在截取 SRT 时做智能选择——优先保留包含 outline 关键词的段落

---

#### 缺陷 5C-2（致命）：推荐理由（recommend_reason）作为标题输入来源不可靠

```diff
Step 3 输入依赖 recommend_reason（来自 Step 2）。
如果 Step 2 失败或 recommend_reason 质量差：

场景1: Step 2 返回了空/默认的 recommend_reason
      → Step 3 基于错误信号生成标题，可能文不对题
场景2: Step 2 调用超时/限流
      → Step 3 无 recommend_reason 可用，需要 fallback 方案
```

**修正方向**：
- 为 recommend_reason 设计 fallback：使用 outline 的前 30 字作为替代
- 当 Step 2 完全不可用时，跳过 Step 2 和 Step 3，使用 outline 作为标题

---

#### 缺陷 5C-3（严重）：缺少标题去重的代码后处理

```diff
虽然 Prompt 要求"所有标题必须互不相同"，但 LLM 不保证执行。
+ 需要代码后处理检测：如果两个标题相似度 > 80%（编辑距离），
  强制为相似度更高的那个重新生成标题
```

**修正方向**：标题生成后做编辑距离检测，相似度阈值 0.8 时触发单条重试。

---

#### 缺陷 5C-4（严重）：标题字符数约束缺少验证

```diff
"8~20个中文字符" 是软约束。
+ LLM 可能输出 5 字或 25 字的标题
+ 需要代码后处理做长度验证和截断/补全
```

**修正方向**：代码检测标题长度，< 8 字时追加 outline 关键词，> 20 字时截断到最后一个标点或第 20 字。

---

#### 缺陷 5C-5（严重）：低俗词汇过滤依赖 LLM，不可靠

```diff
"禁用低俗词汇（装逼/傻逼/他妈的/逼味等）"

- 这是白名单式过滤，LLM 可能不理解"逼味"需要替换
- 或者替换为另一个低俗词（如"傻逼"→"弱智"，仍不友善）
+ 需要代码层做确定性过滤：正则匹配 + 替换表
```

**修正方向**：代码后处理增加低俗词正则匹配，命中时用预设的安全替换词自动修正。

---

### 第 5-D 轮：代码后处理 + 流程集成检查

#### 缺陷 5D-1（致命）：缺少 Step 1 返回空数组时的完整降级路径

```diff
三种场景会导致 Step 1 输出 []：
1. 视频太短（< 30 秒），无独立话题
2. LLM 理解错误（将全部内容视为一个话题，但不符合输出格式）
3. GLM-4-Flash 返回格式错误被解析为空

当前设计：Step 1 → 代码后处理 → Step 2 → Step 3
如果 Step 1 输出 []，整个管道断裂。
+ 必须定义：Step 1 输出 [] 时，是直接返回 _fallback_process 还是重试
```

**修正方向**：
```
Step 1 输出 [] 的处理：
  if Step 1 输出数量 == 0:
    └─ 重试 1 次（可能是临时性 LLM 故障）
       ├─ 重试后仍有输出 → 正常继续
       └─ 重试后仍为 0 → _fallback_process(srt_text)
```

---

#### 缺陷 5D-2（严重）：代码后处理中"合并相邻同类型短话题"可能破坏 LLM 意图

```diff
代码后处理步骤 3: "合并相邻同类型短话题（< 20 秒的相邻话题自动合并）"

+ 但 LLM 可能有意将相邻片段分开：
  例: topic A = "牛肉丸太好吃了"（product, 15秒）
       topic B = "但这款更便宜"（product, 18秒）
  这两个是不同产品的独立推介，LLM 正确拆分了
  → 代码合并后：15+18=33 秒的混乱产品对比片段
```

**修正方向**：
- 合并前检查两个话题的 outline 相似度
- 只有 outline 语义相似时才合并（用关键词交集判断）
- 不同产品名称 → 不合并

---

#### 缺陷 5D-3（严重）：各步骤失败时缺少检查点恢复机制

```diff
如果 Step 2 调用超时：
- Step 1 的结果已经产生（LLM 调用已消耗 token）
- 但整个流程失败
+ 重新触发 → Step 1 重新调用 → 浪费 token 且可能产生不同结果

当前代码有字符串级别的日志，但没有结构化的中间结果持久化。
```

**修正方向**：
```python
# 伪代码
checkpoint = load_checkpoint(project_id)
if not checkpoint.get('step1_output'):
    step1_output = call_step1(srt_text)
    save_checkpoint(project_id, 'step1_output', step1_output)
else:
    step1_output = checkpoint['step1_output']
```

---

#### 缺陷 5D-4（严重）：_validate_segments_with_srt 不支持新输出格式

```diff
现有 _validate_segments_with_srt 函数处理 merged 方案的输出格式：
- 读 clip.get('removed_sections') 并更新
- 修正 seg 的 start/end 边界

三步方案的 Step 1 输出不包含 removed_sections（由代码后处理计算）。
+ 需要新增一个"轻量版"验证函数，只做：边界对齐 + 间隙填充
+ 或者修改现有函数，增加 mode 参数区分两种场景
```

**修正方向**：新增 `_validate_step1_segments(step1_clips, srt_text)` 函数，仅做边界修正。

---

#### 缺陷 5D-5（中等）：TopicPreCluster 预处理的适用性

```diff
现有的 _llm_process_merged 在调用 LLM 前使用 TopicPreCluster 增强 SRT：
  - 预聚类标记话题块
  - 生成 enhanced_text（带聚类标记的 SRT）

+ 三步方案的 Step 1 是否也需要 TopicPreCluster 预处理？
+ 文档未提及，但这是 merged 模式效果好的关键因素之一
```

**修正方向**：在三步流程的 Step 1 前同样执行 TopicPreCluster 预处理。

---

#### 缺陷 5D-6（中等）：removed_sections 的代码计算方式需要明确

```diff
方案说"代码后处理计算 removed_sections"，但未给出具体算法。

现有 merged 方案的 _validate_segments_with_srt 中有静音检测逻辑：
- 检测 segment 内 SRT 条目间的 > 2 秒间隙
- 标记为 removed_section

+ 三步方案需要明确：
  1. 是复用现有的间隙检测逻辑？
  2. 还是需要更精细的 VAD 数据辅助判断？
```

**修正方向**：在三步方案的代码后处理中，直接调用 `_validate_segments_with_srt` 的间隙检测部分（解耦为独立函数）。

---

### 第 5-E 轮：整体流程端到端检查

#### 缺陷 5E-1（致命）：评分权重变更未经实证验证

```diff
merged 方案: final_score = 看点价值×0.4 + 话题完整度×0.3 + 叙事流畅度×0.3
修正方案:   final_score = 看点价值×0.5 + 话题完整度×0.3 + 叙事流畅度×0.2

看点价值权重: 0.4 → 0.5 (+25%)
叙事流畅度权重: 0.3 → 0.2 (-33%)

影响分析:
- 慢节奏干货讲解（叙事流畅度高但看点价值中等）→ 分数下降 → 可能被挤出 Top 6
- 短促金句（看点价值高但叙事不流畅）→ 分数上升 → 更容易入选
+ 可能导致输出偏向"短平快"内容，丢失深度话题
```

**修正方向**：保持与 merged 一致的权重（0.4/0.3/0.3），避免引入额外的不可控变量。

---

#### 缺陷 5E-2（致命）：失去 merged 模式中 LLM"评分即修正"的自我纠错能力

```diff
merged 模式的核心优势：单次调用中，LLM 可以在评分时发现边界错误并调整。

例：LLM 在 merged 中识别话题边界时：
  "这个话题从 00:01:00 开始...等等，前面还有引入铺垫...应该是 00:00:30"
  → 直接在同一个推理过程中修正

三步方案：
  Step 1 确定了边界 → Step 2 只能基于该边界评分
  → 即使 Step 2 发现边界有问题，也无法修正（它不输出边界信息）
  → 边界错误会一直传播到最终输出
```

**实际影响**：这是三步方案最根本的结构性缺陷。边界错误无法在后续步骤中被修正，与 merged 方案的能力存在本质差距。

**修正方向**：
- 方案 A（高风险）：在 Step 2 增加一个可选字段 `boundary_suggestion`，允许 LLM 建议边界调整
- 方案 B（保守）：不改变架构，接受此缺陷；通过提高 Step 1 的 Prompt 质量来降低边界错误率
- 方案 C（折中）：Step 2 评分完成后，代码检查低分话题的边界是否合理，不合理则重新调用 Step 1（仅对该话题区域）

---

#### 缺陷 5E-3（致命）：三步骤间的数据传递格式未标准化，缺少守卫代码

```diff
数据流转换链:
Step 1 输出: {id, outline, segments, topic_type}
    ↓ 代码转换：提取 srt_text、计算 total_duration_seconds
Step 2 输入: {id, outline, topic_type, total_duration_seconds, srt_text}
    ↓ 代码合并：将 scores 合并到 topic 数据
Step 3 输入: {id, topic_type, outline, recommend_reason, srt_text}

每一步的转换都是字符串拼接/JSON 序列化，任一环节出错 → 后续步骤的 LLM 调用失败。
+ 当前方案没有定义中间数据格式的 Schema 验证
+ 没有 transient error 的重试机制
```

**修正方向**：为每个步骤的输入/输出定义 Pydantic 模型，在步骤间传递时进行验证。

---

#### 缺陷 5E-4（严重）：缺少对"单话题视频"的处理

```diff
merged prompt: "最少输出2个（字幕只有单个话题时最少1个）"
修正 Step 1: "最多输出8个话题"（未提及最少）

如果视频只有一个话题（短直播片段、单人讲解视频）：
- Step 1 正确输出 1 个话题
- Step 2 对该话题评分
- Step 3 生成 1 个标题
→ 正常流程可以处理

但如果 Step 1 输出 0 个话题（LLM 误判为无独立话题）：
→ 当前方案无处理逻辑
```

**修正方向**：Step 1 最低输出 1 个话题（覆盖整个 SRT），除非 SRT 为空。

---

#### 缺陷 5E-5（严重）：GLM-4-Flash 随机性对三步一致性的影响

```diff
GLM-4-Flash 的非确定性：
- 同一输入两次调用可能产生不同的输出
- 三步方案涉及 3 次独立调用

场景：用户对同一视频发起两次处理
  调用1: Step 1 识别 7 个话题（略有不同边界） → 选出 Top 6 → 生成标题
  调用2: Step 1 识别 6 个话题（不同的边界） → 选出 Top 6 → 生成标题
  → 两次结果差异可能很大，用户体验差

merged 方案虽然也有随机性，但只有 1 次调用，波动范围更可控。
```

**修正方向**：在 Step 1 的 Prompt 中设置 `temperature=0.1`（低温减少随机性），并在代码层做输出稳定性校验。

---

#### 缺陷 5E-6（中等）：验收标准与实现路径不匹配

```diff
现有验收标准（11 项）:
[x] 全链路成功率 ≥ 90%
[x] 总处理时间 ≤ merged 模式的 50%
[x] 输出 JSON 格式正确率 100%

这些是"结果指标"但不是"过程指标"。
+ 缺少各步骤的独立验收标准
+ 缺少中间输出的格式验证标准
```

**修正方向**：为每个步骤增加独立的验收项。

---

## 第 6 轮：缺陷汇总与修复优先级

### 缺陷分级汇总

| 优先级 | 数量 | 典型缺陷 | 不修复的后果 |
|--------|------|---------|-------------|
| **P0（致命）** | 10 | 5B-2 评分时重新评估边界、5E-2 失去自我纠错、5B-1 上下文溢出 | 输出完全错误或流程崩溃 |
| **P1（严重）** | 14 | 5A-3 outline 过度压缩、5C-1 截取位置不当、5D-2 过度合并 | 输出质量明显下降 |
| **P2（中等）** | 5 | 5A-6 缺少自检、5D-5 预处理遗漏、5E-6 验收标准不完善 | 健壮性不足 |

### 最关键的 5 个修复建议

```
1. 【P0 - 5E-2】在 Step 2 中增加 boundary_suggestion 字段，
   允许 LLM 在评分时建议边界调整 → 恢复 merged 的自我纠错能力

2. 【P0 - 5B-1】Step 2 增加 token 预估 + 自动分批机制，
   防止长 SRT 超出上下文窗口 → 确保评分完整性

3. 【P0 - 5B-2】Step 2 Prompt 明确声明"边界已确定、只评分"，
   防止 LLM 重新评估边界 → 避免评分失真

4. 【P0 - 5E-1】保持与 merged 一致的评分权重(0.4/0.3/0.3)，
   避免引入新的不可控变量 → 确保迁移平滑

5. 【P0 - 5D-1】为每个步骤增加检查点持久化 + 空输出降级路径，
   确保任一步骤失败时不会丢失已完成的工作 → 提升可靠性
```

---

### 最终评价

**三步方案的 10 个致命缺陷中，5E-2（失去自我纠错能力）是最根本的结构性问题。**

merged 方案的核心竞争力在于：LLM 在单次推理中可以"边做边改"。三步方案将"识别"和"评分"分拆后，丢失了这个能力。

**然而**，这不意味着三步方案没有价值。它的价值在于：
1. **降低单次 Prompt 复杂度** → 提高指令遵循率（尤其是 GLM-4-Flash 这种小模型）
2. **批量评分确保可比较性** → 解决 merged 中评分不一致的问题
3. **分离关注点** → 每一步可以独立优化 Prompt

**结论**：三步方案是对 merged 的有效补充，但不是替代。建议作为 **merged 的降级/备选方案**，在以下场景使用：
- merged 方案的指令遵循率低于阈值时自动切换
- GLM-4-Flash（8K 上下文）等小模型场景
- 需要严格评分可比较性的场景

**不建议**完全替换 merged 方案。两者应共存，LLM 管理器根据模型能力和历史成功率动态选择。</think>现在进行最终评价。

---

## 最终评价

**三步方案的核心结构性问题**是 5E-2：失去了 merged 模式中"评分即修正"的自我纠错能力。merged 模式在单次推理中，LLM 可以边识别边界边评分边调整；三步方案将"识别"和"评分"分拆后，边界错误会一直传播到最终输出而无法修正。

**然而，三步方案仍有其不可替代的价值：**

1. **降低单步 Prompt 复杂度**（90 行 vs 250 行）→ 提高小模型（GLM-4-Flash）的指令遵循率
2. **批量评分确保可比较性** → 解决 merged 中评分不一致的核心问题
3. **分离关注点** → 每一步可以独立优化 Prompt，迭代效率更高

**最终建议**：三步方案不应完全替代 merged，而是作为 **merged 的备选/降级方案**：

- 当 merged 方案的指令遵循率低于阈值时自动切换
- GLM-4-Flash（8K 上下文）等小模型场景下优先使用
- 需要严格评分可比较性时使用

同时，**P0 级别的 5 个关键修复**建议在实施前完成：

| # | 修复项 | 成本 |
|---|--------|------|
| 1 | Step 2 增加 `boundary_suggestion` 字段恢复纠错能力 | 中 |
| 2 | Step 2 token 预估 + 自动分批 | 低 |
| 3 | Step 2 明确"边界已确定、只评分"声明 | 极低 |
| 4 | 评分权重回退到 0.4/0.3/0.3 与 merged 一致 | 极低 |
| 5 | 各步骤检查点持久化 + 空输出降级路径 | 中 |

**总的缺陷统计：5 轮分析共发现 22 个净新增缺陷，其中致命 10 个、严重 14 个。三步方案与 merged 方案应共存互补，而非互相替代。**

---

## 第 7 轮：P0 致命级缺陷 — 详细修复方案

> **5 个 P0 级修复方案，按实施难度从低到高排列。**

---

### P0 修复 1：评分权重回退到 0.4/0.3/0.3 与 merged 一致

**对应缺陷**：5E-1

**问题**：修正方案将权重从 `0.4/0.3/0.3` 改为 `0.5/0.3/0.2`，看重点价值权重 +25%、叙事流畅度 -33%。这会导致慢节奏干货讲解被挤出 Top 6，输出偏向"短平快"。

**修复范围**：仅改一行 Prompt 中的公式数字，零代码改动。

**修复前**（Step 2 Prompt）：
```
final_score = 看点价值×0.5 + 话题完整度×0.3 + 叙事流畅度×0.2
```

**修复后**：
```
final_score = 看点价值×0.4 + 话题完整度×0.3 + 叙事流畅度×0.3
```

**副作用**：无。这是回退到 merged 已验证的权重，风险最低。

**验证方法**：用同一视频分别跑 merged 和三步方案，Top 6 的话题类型分布应大致一致（偏差 ≤ 1 个话题）。

---

### P0 修复 2：Step 2 Prompt 声明"边界已确定、只评分"

**对应缺陷**：5B-2

**问题**：Step 2 的 LLM 不知道话题边界是 Step 1 确定的，可能在评分时质疑边界（"这个片段好像包含两个话题..."），导致评分失真。

**修复范围**：Step 2 Prompt 开头加一句声明，零代码改动。

**修复后 Prompt**（仅改动首段）：

```python
FUNCLIP_STEP2_BATCH_SCORE_PROMPT = """## 重要前提
以下话题的边界已经过专业分析确定，你**不需要、也不应该**质疑或重新评估边界。
你的唯一任务是对内容质量进行评分。即使你认为某个话题的边界可以更优，也请基于给定的SRT片段进行评分。

## 任务
对下方所有话题做评分。你必须在同一次判断中横向比较它们，确保评分可比较。

## 所有话题
```json
[
  {
    "id": "1",
    "outline": "话题概述",
    "topic_type": "knowledge",
    "total_duration_seconds": 185,
    "srt_text": "00:01:00,000 --> 00:01:05,000\\n这是第一条字幕内容...\\n...(完整SRT)"
  }
]
```

## 评分维度
- 看点价值(0~1): 冲突金句/独家信息/情绪爆发。锚点：0.9=金句冲突，0.7=干货知识，0.5=日常讲述
- 话题完整度(0~1): 引入+核心+收尾的完整度。锚点：0.9=三段完整，0.7=有核心+收尾，0.5=仅核心
- 叙事流畅度(0~1): 逻辑连贯性。锚点：0.9=一气呵成，0.7=偶尔卡顿，0.5=多处卡顿

## 计算
final_score = 看点价值×0.4 + 话题完整度×0.3 + 叙事流畅度×0.3

## 输出
```json
{
  "scores": [
    {
      "id": "1",
      "final_score": 0.75,
      "sub_scores": {"看点价值": 0.8, "话题完整度": 0.7, "叙事流畅度": 0.7},
      "recommend_reason": "基于实际内容的推荐理由（≤20字）",
      "boundary_suggestion": null
    }
  ]
}
```
为**每一个**输入话题打分并输出，不要跳过任何话题。不要自行过滤低分话题。
recommend_reason 每条不同，基于实际内容。
boundary_suggestion 为 null 或字符串（格式见下方说明）。

## boundary_suggestion 字段（可选）
如果你在评分过程中发现某个话题的边界存在明显问题（例如：开头缺少必要的引入铺垫、结尾被过早截断、或者包含了明显不属于该话题的内容），你可以在此字段给出建议。格式为：

"建议[扩展/收缩/前移/后移]边界：[具体说明，如'应将开头前移30秒以包含产品引入背景']"

如果你认为边界没有问题，请填写 null。大多数情况下此字段应为 null。

注意：此字段仅作为建议供后续代码参考，不会自动修改边界。
"""
```

**关键改动**：
1. 新增"重要前提"段落：明确声明边界已确定、只评分
2. `final_score` 公式回退到 `0.4/0.3/0.3`（合并 P0 修复 1）
3. 新增 `boundary_suggestion` 字段（合并 P0 修复 3 的接口）
4. 移除 `final_score >= 0.5` 过滤指令 → 改为"为每一个输入话题打分"
5. 移除排序优先级规则 → 交给代码

**验证方法**：在无 boundary_suggestion 的正常场景下，Step 2 的评分结果应与 merged 方案中对应话题的评分接近（偏差 ≤ 0.15）。

---

### P0 修复 3：Step 2 增加 boundary_suggestion 字段恢复自我纠错能力

**对应缺陷**：5E-2（三步方案最根本的结构性缺陷）

**问题**：merged 的核心优势是 LLM 在评分时能发现并修正边界错误。三步方案将识别和评分分离后丢失了此能力。

**修复思路**：不改变三步架构，而是在 Step 2 中增加一个"旁路通道"——`boundary_suggestion` 字段。LLM 在评分时如果发现边界问题，可以通过此字段提出修正建议，代码后处理中评估并应用合理的建议。

**为什么不做自动边界修正？** 如果让 LLM 在 Step 2 中直接输出修正后的 segments，会导致：
- Step 2 的职责膨胀（评分 + 边界修正）
- 修正后的边界可能与 Step 1 的其他话题冲突（重叠、遗漏）
- 破坏了三步架构的清晰分工

因此采用"建议模式"：LLM 提出建议 → 代码验证建议的合理性 → 决定是否应用。

#### 3.1 boundary_suggestion 的格式规范

```
"建议扩展开头：[原因，如'话题开头缺少产品引入铺垫，00:01:00前30秒有"食神里的撒尿牛丸"铺垫']"

"建议收缩结尾：[原因，如'00:08:30之后的内容已切换到下一话题']"

"建议前移开头：[原因，如'当前开头落在了一条SRT的中间位置']"

"建议移除内部段：segment #2 [原因，如'该段内容与话题无关，属于误归类']"
```

#### 3.2 代码实现：`_apply_boundary_suggestions()`

```python
def _apply_boundary_suggestions(
    topics: List[Dict],
    scores: List[Dict],
    srt_entries: List[Dict]
) -> List[Dict]:
    """
    处理 Step 2 返回的 boundary_suggestion，验证并应用合理的建议。

    建议应用规则：
    1. 扩展开头：新起点必须对齐某条SRT的首时间戳，且不侵占前一个话题的已占用SRT
    2. 收缩结尾：新终点必须对齐某条SRT的尾时间戳
    3. 前移/后移：同扩展/收缩
    4. 移除内部段：只有当移除后话题仍有 ≥ 1 个 segment 且 ≥ 10 秒时才执行
    5. 激进建议（移动 > 60 秒）→ 忽略（可能是 LLM 幻觉）
    """
    import re

    for score_item in scores:
        suggestion = score_item.get('boundary_suggestion')
        if not suggestion or suggestion == 'null' or suggestion == 'None':
            continue

        topic_id = score_item.get('id')
        topic = next((t for t in topics if t.get('id') == topic_id), None)
        if not topic:
            continue

        segments = topic.get('segments', [])
        if not segments:
            continue

        # 解析建议类型
        suggestion_lower = suggestion.lower()

        if '扩展' in suggestion and ('开头' in suggestion or '向前' in suggestion):
            _handle_extend_start(suggestion, topic, segments, srt_entries)

        elif '扩展' in suggestion and ('结尾' in suggestion or '向后' in suggestion):
            _handle_extend_end(suggestion, topic, segments, srt_entries)

        elif '收缩' in suggestion and '结尾' in suggestion:
            _handle_shrink_end(suggestion, topic, segments, srt_entries)

        elif '收缩' in suggestion and '开头' in suggestion:
            _handle_shrink_start(suggestion, topic, segments, srt_entries)

        elif '移除' in suggestion and ('内部' in suggestion or 'segment' in suggestion.lower()):
            _handle_remove_segment(suggestion, topic, segments)

        elif '前移' in suggestion:
            _handle_extend_start(suggestion, topic, segments, srt_entries)

        elif '后移' in suggestion:
            _handle_shrink_start(suggestion, topic, segments, srt_entries)

        else:
            logger.info(f"boundary_suggestion 格式无法解析，跳过: {suggestion[:100]}")

    return topics


def _handle_extend_start(suggestion: str, topic: Dict, segments: List[Dict],
                          srt_entries: List[Dict]):
    """扩展开头：向前扩展第一个 segment 的 start 时间"""
    # 尝试从建议中提取时间偏移量
    time_match = re.search(r'(\d+)\s*秒', suggestion)
    extend_seconds = int(time_match.group(1)) if time_match else 10

    # 激进检查
    if extend_seconds > 60:
        logger.warning(f"扩展建议偏移量过大({extend_seconds}秒)，可能是LLM幻觉，跳过")
        return

    first_seg_start = _srt_time_to_seconds(segments[0]['start'])
    new_start_sec = max(0, first_seg_start - extend_seconds)

    # 对齐到最近的 SRT 条目首时间戳
    aligned_start = _align_to_srt_start(new_start_sec, srt_entries)

    if aligned_start is not None and aligned_start < first_seg_start:
        segments[0]['start'] = _seconds_to_srt_time(aligned_start)
        logger.info(
            f"boundary_suggestion 已应用: 话题{topic['id']} 开头前移 "
            f"{first_seg_start - aligned_start:.1f}秒 → {_seconds_to_srt_time(aligned_start)}"
        )


def _handle_shrink_end(suggestion: str, topic: Dict, segments: List[Dict],
                        srt_entries: List[Dict]):
    """收缩结尾：提前最后一个 segment 的 end 时间"""
    time_match = re.search(r'(\d+)\s*秒', suggestion)
    shrink_seconds = int(time_match.group(1)) if time_match else 10

    if shrink_seconds > 60:
        logger.warning(f"收缩建议偏移量过大({shrink_seconds}秒)，可能是LLM幻觉，跳过")
        return

    last_seg_end = _srt_time_to_seconds(segments[-1]['end'])
    new_end_sec = last_seg_end - shrink_seconds

    aligned_end = _align_to_srt_end(new_end_sec, srt_entries)

    if aligned_end is not None and aligned_end < last_seg_end:
        segments[-1]['end'] = _seconds_to_srt_time(aligned_end)
        logger.info(
            f"boundary_suggestion 已应用: 话题{topic['id']} 结尾收缩 "
            f"{last_seg_end - aligned_end:.1f}秒 → {_seconds_to_srt_time(aligned_end)}"
        )


def _handle_shrink_start(suggestion: str, topic: Dict, segments: List[Dict],
                          srt_entries: List[Dict]):
    """收缩开头：推迟第一个 segment 的 start 时间"""
    time_match = re.search(r'(\d+)\s*秒', suggestion)
    shrink_seconds = int(time_match.group(1)) if time_match else 10

    if shrink_seconds > 60:
        return

    first_seg_start = _srt_time_to_seconds(segments[0]['start'])
    new_start_sec = first_seg_start + shrink_seconds

    aligned_start = _align_to_srt_start(new_start_sec, srt_entries)

    if aligned_start is not None and aligned_start > first_seg_start:
        segments[0]['start'] = _seconds_to_srt_time(aligned_start)
        logger.info(
            f"boundary_suggestion 已应用: 话题{topic['id']} 开头后移 "
            f"{aligned_start - first_seg_start:.1f}秒 → {_seconds_to_srt_time(aligned_start)}"
        )


def _handle_extend_end(suggestion: str, topic: Dict, segments: List[Dict],
                        srt_entries: List[Dict]):
    """扩展结尾"""
    time_match = re.search(r'(\d+)\s*秒', suggestion)
    extend_seconds = int(time_match.group(1)) if time_match else 10

    if extend_seconds > 60:
        return

    last_seg_end = _srt_time_to_seconds(segments[-1]['end'])
    new_end_sec = last_seg_end + extend_seconds

    aligned_end = _align_to_srt_end(new_end_sec, srt_entries)

    if aligned_end is not None and aligned_end > last_seg_end:
        segments[-1]['end'] = _seconds_to_srt_time(aligned_end)
        logger.info(
            f"boundary_suggestion 已应用: 话题{topic['id']} 结尾后移 "
            f"{aligned_end - last_seg_end:.1f}秒 → {_seconds_to_srt_time(aligned_end)}"
        )


def _handle_remove_segment(suggestion: str, topic: Dict, segments: List[Dict]):
    """移除一个内部 segment"""
    seg_match = re.search(r'segment\s*#?\s*(\d+)', suggestion, re.IGNORECASE)
    if not seg_match:
        return
    seg_idx = int(seg_match.group(1)) - 1  # 转为 0-based

    if seg_idx < 0 or seg_idx >= len(segments):
        return

    # 安全底线：移除后必须有 ≥ 1 个 segment
    if len(segments) <= 1:
        logger.warning(f"boundary_suggestion 拒绝: 话题{topic['id']} 只有1个segment，不能移除")
        return

    removed_seg = segments.pop(seg_idx)
    logger.info(
        f"boundary_suggestion 已应用: 移除话题{topic['id']}的segment#{seg_idx+1} "
        f"({removed_seg['start']} -> {removed_seg['end']})"
    )


def _align_to_srt_start(target_sec: float, srt_entries: List[Dict]) -> Optional[float]:
    """找到最接近 target_sec 且 ≤ target_sec 的 SRT 条目首时间戳"""
    best = None
    for entry in srt_entries:
        if entry['start'] <= target_sec:
            if best is None or entry['start'] > best:
                best = entry['start']
    return best


def _align_to_srt_end(target_sec: float, srt_entries: List[Dict]) -> Optional[float]:
    """找到最接近 target_sec 且 ≥ target_sec 的 SRT 条目尾时间戳"""
    best = None
    for entry in srt_entries:
        if entry['end'] >= target_sec:
            if best is None or entry['end'] < best:
                best = entry['end']
    return best
```

#### 3.3 在三步流程中集成

```python
def _llm_process_three_step(self, srt_text: str):
    """三步流水线处理"""
    srt_entries = _parse_srt_timeline(srt_text)

    # Step 1: 边界识别
    step1_topics = self._call_step1_boundary(srt_text)
    if not step1_topics:
        return self._fallback_process(srt_text)

    # 代码后处理: 边界对齐
    step1_topics = _validate_step1_segments(step1_topics, srt_text)

    # Step 2: 批量评分（含 boundary_suggestion）
    step2_input = self._prepare_step2_input(step1_topics, srt_entries)
    step2_scores = self._call_step2_batch_score(step2_input)

    if step2_scores:
        # ★ 核心：应用 boundary_suggestion
        step1_topics = _apply_boundary_suggestions(
            step1_topics, step2_scores, srt_entries
        )

        # 将评分合并到 topic 数据
        step1_topics = _merge_scores_to_topics(step1_topics, step2_scores)

    # Step 3: 批量标题
    # ... 后续流程
```

#### 3.4 安全底线

| 规则 | 目的 |
|------|------|
| 偏移量 > 60 秒 → 忽略 | 防止 LLM 幻觉导致大范围边界错误 |
| 移除后 segments 数量 < 1 → 拒绝 | 防止话题被完全清空 |
| 新边界必须对齐 SRT 条目首/尾时间戳 | 防止切割单条字幕 |
| 最多应用 2 条建议/话题 | 防止一个话题被反复修改面目全非 |
| boundary_suggestion 为 null 的占比应 > 60% | 正常情况下大多数话题不需要修正 |

**验证方法**：
1. 单元测试：构造包含已知边界错误的话题数据，验证 `_apply_boundary_suggestions` 正确修正
2. 集成测试：用同一视频对比"有 boundary_suggestion"和"无 boundary_suggestion"的输出差异
3. 统计指标：log 中记录每个话题的 boundary_suggestion 被接受/拒绝的次数

---

### P0 修复 4：Step 2 token 预估 + 自动分批

**对应缺陷**：5B-1

**问题**：GLM-4-Flash 免费版上下文窗口仅 8K tokens（约 12,000 中文字符）。如果 Step 1 输出 8 个话题，每个 150 条 SRT，总输入约 50,000 字符，超出窗口导致截断。

**修复思路**：在调用 Step 2 前预估输入 token 数，超出阈值时按 topic_type 优先级自动分批。高优先级类型（highlight + knowledge）第一批发送，低优先级类型（product + fun + daily）第二批发送。

#### 4.1 中文 Token 估算函数

```python
# 放到 funclip_style.py 模块级别

# 中文字符到 token 的估算系数（保守估计）
# 1 个中文字符 ≈ 1.5~2.5 tokens（取决于模型的分词器）
# 取 2.0 作为保守系数，留 20% 安全边界
ZH_CHAR_TO_TOKEN_RATIO = 2.0
DEFAULT_MAX_TOKENS = 8192      # GLM-4-Flash 免费版
TOKEN_SAFETY_MARGIN = 0.8      # 只用 80% 的上下文窗口
RESERVED_OUTPUT_TOKENS = 2048  # 预留输出 token 数


def _estimate_tokens(text: str) -> int:
    """粗略估算中文文本的 token 数"""
    if not text:
        return 0
    # 中文字符 + 英文单词 + JSON 结构符号
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    other_chars = len(text) - chinese_chars
    # 中文字符 ≈ 2 tokens, 其他 ≈ 0.3 tokens/char（英文单词、JSON）
    return int(chinese_chars * ZH_CHAR_TO_TOKEN_RATIO + other_chars * 0.3)


def _should_batch_step2(topics_with_srt: List[Dict], max_tokens: int = None) -> bool:
    """判断 Step 2 输入是否需要分批"""
    if max_tokens is None:
        max_tokens = DEFAULT_MAX_TOKENS

    prompt_tokens = _estimate_tokens(FUNCLIP_STEP2_BATCH_SCORE_PROMPT)

    total_input_tokens = prompt_tokens
    for topic in topics_with_srt:
        total_input_tokens += _estimate_tokens(topic.get('srt_text', ''))
        total_input_tokens += _estimate_tokens(json.dumps({
            'id': topic.get('id'),
            'outline': topic.get('outline'),
            'topic_type': topic.get('topic_type'),
            'total_duration_seconds': topic.get('total_duration_seconds')
        }, ensure_ascii=False))

    effective_limit = int(max_tokens * TOKEN_SAFETY_MARGIN) - RESERVED_OUTPUT_TOKENS
    return total_input_tokens > effective_limit


def _split_topics_by_priority(topics_with_srt: List[Dict]) -> tuple:
    """
    按 topic_type 优先级分批。
    批次1 (高优先): highlight + knowledge
    批次2 (低优先): product + fun + daily
    """
    TYPE_PRIORITY = {'highlight': 1, 'knowledge': 1, 'product': 2, 'fun': 2, 'daily': 2}

    batch1 = [t for t in topics_with_srt if TYPE_PRIORITY.get(t.get('topic_type'), 2) == 1]
    batch2 = [t for t in topics_with_srt if TYPE_PRIORITY.get(t.get('topic_type'), 2) == 2]

    return batch1, batch2
```

#### 4.2 在 Step 2 调用中集成

```python
def _call_step2_batch_score(self, topics_with_srt: List[Dict]) -> List[Dict]:
    """
    调用 Step 2 批量评分，自动检测是否需要分批。

    Returns:
        scores 列表，格式: [{"id": "1", "final_score": 0.75, ...}, ...]
    """
    if not topics_with_srt:
        return []

    if _should_batch_step2(topics_with_srt):
        logger.info(
            f"Step 2 输入 token 超阈值，启动分批评分 "
            f"(共 {len(topics_with_srt)} 个话题)"
        )
        batch1, batch2 = _split_topics_by_priority(topics_with_srt)
        logger.info(f"  批次1(高优先): {len(batch1)} 个话题")
        logger.info(f"  批次2(低优先): {len(batch2)} 个话题")

        all_scores = []

        # 批次1: 高优先级话题
        if batch1:
            scores1 = self._do_step2_call(batch1, batch_label="批次1")
            all_scores.extend(scores1)

        # 批次2: 低优先级话题
        if batch2:
            # 如果批1已经很多话题，可以降低批2的优先级
            scores2 = self._do_step2_call(batch2, batch_label="批次2")
            all_scores.extend(scores2)

        logger.info(f"分批评分完成，共 {len(all_scores)} 个分数")
        return all_scores
    else:
        return self._do_step2_call(topics_with_srt, batch_label="单批")


def _do_step2_call(self, topics_with_srt: List[Dict], batch_label: str = "") -> List[Dict]:
    """执行单次 Step 2 LLM 调用"""
    try:
        input_json = json.dumps(topics_with_srt, ensure_ascii=False, indent=2)
        logger.info(f"Step 2 [{batch_label}] LLM调用: {len(topics_with_srt)} 个话题, "
                    f"输入长度 {len(input_json)} 字符, 预估 {_estimate_tokens(input_json)} tokens")

        response = self.llm_manager.current_provider.call(
            FUNCLIP_STEP2_BATCH_SCORE_PROMPT,
            "以下是待评分的话题数据：\n" + input_json,
            max_tokens=2048,
            temperature=0.2  # 低温降低评分随机性
        )

        if not response or not response.content:
            logger.warning(f"Step 2 [{batch_label}] 返回空响应")
            return []

        result = self._parse_step2_response(response.content)
        logger.info(f"Step 2 [{batch_label}] 解析成功: {len(result)} 个分数")
        return result

    except Exception as e:
        logger.error(f"Step 2 [{batch_label}] 调用失败: {e}")
        return []


def _parse_step2_response(self, response_text: str) -> List[Dict]:
    """解析 Step 2 返回的 JSON"""
    # 复用现有的多策略 JSON 解析逻辑（与 _parse_merged_response 类似）
    def _try_parse(json_str):
        try:
            data = json.loads(_clean_trailing_commas(json_str))
            if isinstance(data, dict) and 'scores' in data:
                return data['scores']
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
        return None

    def _clean_trailing_commas(s):
        return re.sub(r',\s*([\]}])', r'\1', s)

    # 策略1: 直接解析
    result = _try_parse(response_text)
    if result:
        return result

    # 策略2: 从 ```json 代码块提取
    for block in re.findall(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text):
        result = _try_parse(block)
        if result:
            return result

    # 策略3: 从文本中提取 {...} 或 [...]
    for pattern in [r'\{[\s\S]*"scores"[\s\S]*\}', r'\[[\s\S]*"final_score"[\s\S]*\]']:
        match = re.search(pattern, response_text)
        if match:
            result = _try_parse(match.group())
            if result:
                return result

    logger.warning(f"无法解析 Step 2 响应: {response_text[:300]}")
    return []
```

#### 4.3 降级：单批无法容纳时的备选策略

```python
def _prepare_step2_input(self, topics: List[Dict], srt_entries: List[Dict]) -> List[Dict]:
    """
    准备 Step 2 的输入数据。
    如果单个话题的 SRT 过大，截取关键部分。
    """
    topics_with_srt = []
    for topic in topics:
        segments = topic.get('segments', [])
        if not segments:
            continue

        # 提取该话题范围内的 SRT 文本
        srt_text = _extract_srt_for_topic(segments, srt_entries)

        # 如果 srt_text 仍然太大（> 2000 字符），只取首尾
        if len(srt_text) > 2000:
            srt_lines = srt_text.split('\n')
            head_lines = srt_lines[:80]   # 前 ~80 条
            tail_lines = srt_lines[-30:]  # 后 ~30 条
            srt_text = '\n'.join(head_lines) + '\n...(中间省略)...\n' + '\n'.join(tail_lines)
            logger.info(f"话题{topic['id']} SRT过长({len(srt_lines)}条)，截取首{len(head_lines)}+尾{len(tail_lines)}条")

        # 计算总时长
        total_duration = sum(
            _srt_time_to_seconds(seg['end']) - _srt_time_to_seconds(seg['start'])
            for seg in segments
        )

        topics_with_srt.append({
            'id': topic.get('id', ''),
            'outline': topic.get('outline', ''),
            'topic_type': topic.get('topic_type', 'daily'),
            'total_duration_seconds': round(total_duration, 1),
            'srt_text': srt_text
        })

    return topics_with_srt
```

**验证方法**：
1. 构造 8 个话题各 200 条 SRT → 验证自动分批触发
2. 构造 2 个话题各 20 条 SRT → 验证不触发分批（正常路径）
3. 对比分批和单批（如果数据量小到能放进去）的评分差异，偏差应 ≤ 0.1

---

### P0 修复 5：检查点持久化 + 空输出降级路径

**对应缺陷**：5D-1、5D-3

**问题**：
1. Step 1 返回 `[]` 时整个管道断裂，无降级路径
2. Step 2 调用超时后重试需要重新跑 Step 1，浪费 token
3. 中间结果没有持久化，调试困难

**修复思路**：为每个步骤增加检查点文件（JSON），包含：
- 步骤的输入/输出数据
- 时间戳和重试次数
- 历史步骤的结果（避免重复执行）

#### 5.1 检查点管理器

```python
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

CHECKPOINT_DIR_NAME = "pipeline_checkpoints"


class PipelineCheckpoint:
    """三步流水线检查点管理器"""

    def __init__(self, metadata_dir: Path):
        self.checkpoint_dir = metadata_dir / CHECKPOINT_DIR_NAME
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file = self.checkpoint_dir / "three_step_state.json"
        self._state = self._load()

    def _load(self) -> Dict:
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            'version': 1,
            'created_at': time.time(),
            'steps': {}
        }

    def _save(self):
        self._state['updated_at'] = time.time()
        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    def has_step(self, step_name: str) -> bool:
        return step_name in self._state.get('steps', {})

    def get_step_output(self, step_name: str) -> Optional[Any]:
        step = self._state.get('steps', {}).get(step_name)
        if step and step.get('status') == 'success':
            return step.get('output')
        return None

    def save_step_output(self, step_name: str, output: Any, metadata: Dict = None):
        self._state.setdefault('steps', {})[step_name] = {
            'status': 'success',
            'output': output,
            'timestamp': time.time(),
            'retry_count': self._state['steps'].get(step_name, {}).get('retry_count', 0),
            'metadata': metadata or {}
        }
        self._save()

    def mark_step_failed(self, step_name: str, error: str):
        step = self._state.setdefault('steps', {}).setdefault(step_name, {})
        step['status'] = 'failed'
        step['error'] = str(error)[:500]
        step['retry_count'] = step.get('retry_count', 0) + 1
        step['timestamp'] = time.time()
        self._save()

    def should_retry(self, step_name: str, max_retries: int = 2) -> bool:
        step = self._state.get('steps', {}).get(step_name, {})
        return step.get('retry_count', 0) < max_retries

    def clear(self):
        self._state = {
            'version': 1,
            'created_at': time.time(),
            'steps': {}
        }
        self._save()
```

#### 5.2 三步流程中的检查点集成

```python
def _llm_process_three_step(self, srt_text: str):
    """三步流水线处理（带检查点恢复）"""
    checkpoint = PipelineCheckpoint(self.metadata_dir)

    # ==========================================
    # Step 1: 边界识别（带检查点 + 空输出降级）
    # ==========================================
    step1_topics = checkpoint.get_step_output('step1_boundary')

    if step1_topics is None:
        logger.info("Step 1 检查点未命中，开始执行...")
        srt_entries = _parse_srt_timeline(srt_text)

        step1_topics = self._do_step1_with_retry(srt_text, srt_entries, checkpoint)

        if step1_topics is None:
            # 重试耗尽 → 降级
            logger.warning("Step 1 重试耗尽，降级到 _fallback_process")
            checkpoint.clear()
            return self._fallback_process(srt_text)

    # 空输出降级：Step 1 返回 []
    if not step1_topics:
        logger.warning("Step 1 输出为空数组（LLM判断无独立话题），降级")
        checkpoint.clear()
        # 构造一个覆盖全文的"默认话题"
        srt_entries = _parse_srt_timeline(srt_text)
        if srt_entries:
            step1_topics = [{
                'id': '1',
                'outline': '完整内容',
                'segments': [{
                    'start': srt_entries[0]['start_str'],
                    'end': srt_entries[-1]['end_str']
                }],
                'topic_type': 'daily'
            }]
            logger.info("已构造默认单话题")
        else:
            return self._fallback_process(srt_text)

    # 代码后处理: 边界对齐 + 间隙填充
    step1_topics = _validate_step1_segments(step1_topics, srt_text)
    checkpoint.save_step_output('step1_boundary', step1_topics,
                                 {'topic_count': len(step1_topics)})

    # 重新获取 srt_entries（可能尚未初始化）
    srt_entries = _parse_srt_timeline(srt_text)

    # ==========================================
    # Step 2: 批量评分（带检查点）
    # ==========================================
    step2_scores = checkpoint.get_step_output('step2_scores')
    if step2_scores is None:
        logger.info("Step 2 检查点未命中，开始执行...")
        step2_input = self._prepare_step2_input(step1_topics, srt_entries)

        step2_scores = self._call_step2_batch_score(step2_input)

        if step2_scores:
            # 应用 boundary_suggestion
            step1_topics = _apply_boundary_suggestions(
                step1_topics, step2_scores, srt_entries
            )
            checkpoint.save_step_output('step2_scores', step2_scores,
                                         {'score_count': len(step2_scores)})
        else:
            checkpoint.mark_step_failed('step2_scores', 'Step 2 返回空')
            logger.warning("Step 2 评分失败，将使用默认评分继续")

    # 合并评分到 topic 数据（含降级：无评分时使用默认值）
    step1_topics = _merge_scores_to_topics(step1_topics, step2_scores or [])

    # ==========================================
    # Step 3: 批量标题（带检查点）
    # ==========================================
    step3_titles = checkpoint.get_step_output('step3_titles')
    if step3_titles is None:
        logger.info("Step 3 检查点未命中，开始执行...")
        step3_input = self._prepare_step3_input(step1_topics)

        step3_titles = self._call_step3_batch_title(step3_input)

        if step3_titles:
            checkpoint.save_step_output('step3_titles', step3_titles,
                                         {'title_count': len(step3_titles)})

    # 合并标题到 topic 数据
    step1_topics = _merge_titles_to_topics(step1_topics, step3_titles or [])

    # ==========================================
    # 最终后处理
    # ==========================================
    # 按 final_score 降序排序 → 取前 6 → 按时间升序重新编号 id
    step1_topics.sort(key=lambda t: t.get('final_score', 0), reverse=True)
    step1_topics = step1_topics[:6]
    step1_topics.sort(key=lambda t: _srt_time_to_seconds(t['segments'][0]['start']))
    for i, topic in enumerate(step1_topics):
        topic['id'] = str(i + 1)

    # 转换为下游兼容格式
    clips = _convert_topics_to_clips(step1_topics)
    collections = self._generate_collections(clips)

    # 流程完成，清理检查点
    checkpoint.clear()

    logger.info(f"三步流水线完成: {len(clips)} 个片段")
    return clips, collections


def _do_step1_with_retry(self, srt_text: str, srt_entries: List[Dict],
                          checkpoint: PipelineCheckpoint) -> Optional[List[Dict]]:
    """带重试的 Step 1 调用"""
    max_retries = 2

    for attempt in range(max_retries + 1):
        try:
            # 预处理
            enhanced_text = self._prepare_enhanced_text(srt_text)

            step1_topics = self._call_step1_boundary(enhanced_text)

            if step1_topics is not None:
                # 成功（包括返回 []）
                return step1_topics
            else:
                # 解析失败（None vs [] 的区别：None=解析失败，[]=无话题）
                logger.warning(f"Step 1 第{attempt+1}次调用解析失败")
                checkpoint.mark_step_failed('step1_boundary', 'JSON解析失败')

        except Exception as e:
            logger.error(f"Step 1 第{attempt+1}次调用异常: {e}")
            checkpoint.mark_step_failed('step1_boundary', str(e))

        if attempt < max_retries:
            logger.info(f"Step 1 重试 ({attempt+1}/{max_retries})...")

    return None


def _call_step1_boundary(self, srt_text: str) -> Optional[List[Dict]]:
    """调用 Step 1 LLM"""
    try:
        response = self.llm_manager.current_provider.call(
            FUNCLIP_STEP1_BOUNDARY_PROMPT,
            "这是待分析的直播srt字幕：\n" + srt_text,
            max_tokens=4096,
            temperature=0.1  # 低温减少随机性
        )

        if not response or not response.content:
            return None

        # 保存原始响应用于调试
        debug_path = self.metadata_dir / "step1_raw_response.txt"
        with open(debug_path, 'w', encoding='utf-8') as f:
            f.write(response.content)

        return self._parse_step1_response(response.content)

    except Exception as e:
        logger.error(f"Step 1 调用异常: {e}")
        return None


def _call_step3_batch_title(self, topics_data: List[Dict]) -> List[Dict]:
    """调用 Step 3 LLM"""
    try:
        input_json = json.dumps(topics_data, ensure_ascii=False, indent=2)
        response = self.llm_manager.current_provider.call(
            FUNCLIP_STEP3_BATCH_TITLE_PROMPT,
            "以下是待生成标题的话题列表：\n" + input_json,
            max_tokens=2048,
            temperature=0.3
        )

        if not response or not response.content:
            return []

        return self._parse_step3_response(response.content)

    except Exception as e:
        logger.error(f"Step 3 调用异常: {e}")
        return []
```

#### 5.3 辅助函数

```python
def _validate_step1_segments(topics: List[Dict], srt_text: str) -> List[Dict]:
    """
    Step 1 专用的边界验证（轻量版，不含 removed_sections 处理）。
    复用 _validate_segments_with_srt 的边界对齐 + 间隙填充逻辑。
    """
    # 给每个 topic 加空的 removed_sections（兼容现有函数签名）
    for topic in topics:
        topic.setdefault('removed_sections', [])

    # 复用现有函数（它会处理边界对齐 + 间隙填充 + removed_sections 计算）
    topics = _validate_segments_with_srt(topics, srt_text)

    return topics


def _merge_scores_to_topics(topics: List[Dict], scores: List[Dict]) -> List[Dict]:
    """将 Step 2 的评分合并到 topic 数据"""
    score_map = {s.get('id'): s for s in scores}

    for topic in topics:
        tid = topic.get('id', '')
        score_data = score_map.get(tid, {})
        topic['final_score'] = score_data.get('final_score', 0.5)
        topic['sub_scores'] = score_data.get('sub_scores', {})
        topic['recommend_reason'] = score_data.get('recommend_reason',
                                                    topic.get('outline', '')[:20])

    return topics


def _merge_titles_to_topics(topics: List[Dict], titles: List[Dict]) -> List[Dict]:
    """将 Step 3 的标题合并到 topic 数据"""
    title_map = {t.get('id'): t.get('title', '') for t in titles}

    for topic in topics:
        tid = topic.get('id', '')
        title = title_map.get(tid, '')
        if title:
            # 标题后处理：长度验证 + 低俗词过滤
            title = _postprocess_title(title, topic)
            topic['title'] = title
        else:
            # 降级：使用 outline 作为标题
            topic['title'] = topic.get('outline', '未命名片段')[:20]

    return topics


# 低俗词替换表
VULGAR_WORD_MAP = {
    '装逼': '犀利点评',
    '傻逼': '令人费解',
    '他妈的': '真性情',
    '逼味': '独特风格',
    '傻X': '争议观点',
    '脑残': '出人意料',
    '弱智': '令人困惑',
}


def _postprocess_title(title: str, topic: Dict) -> str:
    """标题后处理：长度验证 + 低俗词过滤 + 相似度检测"""
    # 低俗词过滤
    for vulgar, replacement in VULGAR_WORD_MAP.items():
        title = title.replace(vulgar, replacement)

    # 长度验证
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', title))
    if chinese_chars < 8:
        # 太短：追加 outline 关键词
        outline = topic.get('outline', '')
        title = title + '：' + outline[:15]
    elif chinese_chars > 20:
        # 太长：截断到最后一个标点或第 20 字
        chinese_positions = [i for i, c in enumerate(title) if '\u4e00' <= c <= '\u9fff']
        if len(chinese_positions) > 20:
            cut_pos = chinese_positions[19] + 1  # 第20个中文字符后
            # 尝试在标点处截断
            for punct in '，。！？…~':
                punct_pos = title[:cut_pos].rfind(punct)
                if punct_pos > 0:
                    cut_pos = punct_pos + 1
                    break
            title = title[:cut_pos]

    return title


def _convert_topics_to_clips(topics: List[Dict]) -> List[Dict]:
    """将 topic 数据转换为下游 video_generator 兼容的 clips 格式"""
    clips = []
    for topic in topics:
        segments = topic.get('segments', [])
        if not segments:
            continue
        clip = {
            'id': topic.get('id', ''),
            'outline': topic.get('outline', ''),
            'generated_title': topic.get('title', topic.get('outline', '')),
            'start_time': segments[0]['start'],
            'end_time': segments[-1]['end'],
            'final_score': topic.get('final_score', 0.5),
            'recommend_reason': topic.get('recommend_reason', ''),
            'content': [],
            '_segments': segments,
            '_removed_sections': topic.get('removed_sections', [])
        }
        clips.append(clip)
    return clips


def _prepare_enhanced_text(self, srt_text: str) -> str:
    """预处理 SRT 文本（与 merged 方案保持一致）"""
    cleaned_srt = _clean_filler_words(srt_text)
    try:
        from backend.pipeline.topic_precluster import TopicPreCluster
        precluster = TopicPreCluster()
        report = precluster.process(srt_text)
        if report.clusters:
            logger.info(f"预聚类完成: {report.stats}")
            return report.enhanced_text
    except Exception as e:
        logger.warning(f"预聚类失败: {e}")
    return cleaned_srt
```

#### 5.4 降级路径总览

```
Step 1 返回 []（无话题）
  └─ 构造"默认单话题"（覆盖全文）
     └─ 如果 SRT 也为空 → _fallback_process

Step 1 调用失败/解析失败
  └─ 重试 2 次
     ├─ 重试成功 → 正常继续
     └─ 重试耗尽 → _fallback_process

Step 2 返回空/调用失败
  └─ 使用默认评分（final_score=0.5, recommend_reason=outline前20字）
     └─ 继续执行 Step 3

Step 3 返回空/调用失败
  └─ 使用 outline 前 20 字作为标题
     └─ 继续执行最终后处理

全部步骤失败
  └─ _fallback_process（按固定时间等分SRT）
```

**验证方法**：
1. 模拟 Step 1 返回 `[]` → 验证默认单话题构造逻辑
2. 模拟 Step 2 调用超时 → 验证检查点恢复（不重新跑 Step 1）
3. 模拟全部步骤失败 → 验证最终降级到 `_fallback_process`
4. 正常流程 → 验证检查点在流程完成后被清理

---

### 五个修复的集成顺序

```
修复4 (简单Prompt改一行)
  └─→ 修复3 (简单Prompt加一句)
      └─→ 修复1 (中：Step 2 增加字段 + 代码处理)
          └─→ 修复2 (中：token预估 + 分批逻辑)
              └─→ 修复5 (中：检查点管理器 + 降级路径)
```

建议按此顺序逐个实施并验证，每完成一个修复就跑一次完整的端到端测试。修复 4 和修复 3 是"零风险"改动（仅改 Prompt 文字），可以作为第一批提交。</think>文档已更新完毕。5 个 P0 修复方案的详细内容现在都在 [方案文档](file:///e:/ClipProject/autoclip-main1/autoclip-main/docs/superpowers/plans/2026-05-25-multistep-prompt-split.md) 的"第 7 轮"中。

---

## 五个 P0 修复概览

| # | 修复项 | 对应缺陷 | 改动范围 | 难度 |
|---|--------|---------|---------|------|
| 1 | 评分权重回退 | 5E-1 | 改 1 行 Prompt | ★ |
| 2 | 声明"边界已确定、只评分" | 5B-2 | 加 3 行 Prompt | ★ |
| 3 | boundary_suggestion 字段 | 5E-2 | 新增 ~150 行代码 | ★★★ |
| 4 | token 预估 + 自动分批 | 5B-1 | 新增 ~100 行代码 | ★★ |
| 5 | 检查点持久化 + 降级路径 | 5D-1, 5D-3 | 新增 ~250 行代码 | ★★★ |

**建议实施顺序**：修复 1 → 修复 2 → 修复 3 → 修复 4 → 修复 5（从零风险到高复杂度渐变）。

**修复 3（boundary_suggestion）是最关键的**——它直接解决了三步方案"失去自我纠错能力"这个根本性结构缺陷。通过让 LLM 在评分时提出边界修正建议 + 代码安全校验后再应用，在不破坏三步架构的前提下恢复了 merged 方案的核心优势。

<｜DSML｜tool_calls>
<｜DSML｜invoke name="TodoWrite">
<｜DSML｜parameter name="todos" string="false">[{"content": "P0修复1: Step2增加boundary_suggestion字段恢复自我纠错能力", "id": "p0-1", "priority": "high", "status": "completed"}, {"content": "P0修复2: Step2增加token预估+自动分批机制", "id": "p0-2", "priority": "high", "status": "completed"}, {"content": "P0修复3: Step2 Prompt明确声明边界已确定只评分", "id": "p0-3", "priority": "high", "status": "completed"}, {"content": "P0修复4: 评分权重回退到0.4/0.3/0.3与merged一致", "id": "p0-4", "priority": "high", "status": "completed"}, {"content": "P0修复5: 各步骤检查点持久化+空输出降级路径", "id": "p0-5", "priority": "high", "status": "completed"}, {"content": "将所有P0修复方案写入文档", "id": "p0-6", "priority": "high", "status": "completed"}]

<｜DSML｜tool_calls>
<｜DSML｜invoke name="TodoWrite">
<｜DSML｜parameter name="todos" string="false">[{"content": "读取当前Prompt多步拆分方案文档", "id": "1", "priority": "high", "status": "completed"}, {"content": "第1轮缺陷分析：Step 1边界识别Prompt的深入检查", "id": "2", "priority": "high", "status": "completed"}, {"content": "第2轮缺陷分析：Step 2批量评分Prompt的深入检查", "id": "3", "priority": "high", "status": "completed"}, {"content": "第3轮缺陷分析：Step 3批量标题Prompt的深入检查", "id": "4", "priority": "high", "status": "completed"}, {"content": "第4轮缺陷分析：代码后处理和整体流程的完整性验证", "id": "5", "priority": "high", "status": "completed"}, {"content": "第5轮缺陷分析：与现有代码的集成兼容性检查", "id": "6", "priority": "high", "status": "completed"}, {"content": "汇总所有缺陷并更新方案文档", "id": "7", "priority": "high", "status": "completed"}]