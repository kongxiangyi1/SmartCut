"""
基于FunClip风格的单步LLM处理方案
"""
import logging
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
from backend.pipeline.step6_video import VideoGenerator

logger = logging.getLogger(__name__)

# 第一阶段Prompt：仅识别片段边界，不生成标题
FUNCLIP_CLIP_ONLY_PROMPT = """## 任务
分析下方SRT字幕，识别精彩的时间连续片段（单段），输出JSON数组。只输出JSON，不要任何解释。

## 输入数据格式
SRT字幕包含序号、时间范围和文本三部分：
```
1
00:00:00,000 --> 00:00:05,000
大家好欢迎来到直播间
```
条目间时间差为无字幕静音段。相邻短条目（每条≤3秒，间隙≤3秒）视为同一段连续内容，不做中断。

## 输出格式（严格遵守）
```json
[
  {
    "id": "1",
    "outline": "内容概述",
    "start": "00:00:00,000",
    "end": "00:05:30,123",
    "final_score": 0.85,
    "recommend_reason": "包含干货观点和金句冲突"
  }
]
```
时间格式hh:mm:ss,fff。最多4条片段，按精彩程度降序输出。起止时间必须对齐SRT条目首尾时间戳，严禁切割单条字幕内部时间段。没有精彩内容时输出[]。单个片段时长建议10秒以上，无硬性上限。

## 评分标准
final_score为看点价值的单一评分（0~1）。评分锚点：0.9=精彩金句或激烈冲突，0.7=干货知识或强转折，0.5=有趣互动或商品卖点，0.3=普通闲聊但有情绪。recommend_reason基于该片段实际内容撰写，每条必须不同，不超过20字。多段同分时按类型优先级排序：冲突金句 > 干货知识 > 商品卖点 > 趣味闲聊 > 日常讲述。"""

# 第二阶段Prompt：为每个片段独立生成标题（仅基于该片段自己的字幕文本）
FUNCLIP_TITLE_PROMPT = """你是一个短视频标题策划专家。根据下方字幕文本，生成1个吸引人的标题。

## 核心原则
1. **忠于原文**: 标题必须严格基于下方字幕文本，不得无中生有。
2. **突出亮点**: 精准捕捉片段最核心的观点、最激烈的情绪或最有价值的信息。
3. **精炼有力**: 简洁有冲击力，8~20个中文字符，可加感叹号。
4. **用语规范**: 禁用低俗词汇（装逼、傻逼、他妈的等），字幕中的低俗措辞需替换为中性表述（犀利点评、直率吐槽）。
5. **钩子写法优先**: 优先使用设问/悬念/对比/数字等钩子句式（如"为什么XX能卖爆？""XX的3个真相"），避免平铺直叙的"XX介绍""XX讨论"。

## 该片段的字幕文本
{clip_srt_text}

## 参考信息（仅作背景了解，无需嵌入标题）
话题：{outline}
推荐理由：{recommend_reason}

## 示例
字幕：家人们今天这款面膜成分表前三全是好东西，价格才九块九
输出：这款面膜成分太能打了

## 输出
只输出标题文本，不要引号、序号或任何额外内容。
"""

# ============================================================
# 三步方案 Prompt：Step 1 边界识别（仅识别话题边界，不评分不生成标题）
# ============================================================
FUNCLIP_STEP1_BOUNDARY_PROMPT = """## 任务
分析下方SRT字幕，识别所有独立话题的边界。你的任务是**划分话题边界**，不是评分。
只输出JSON数组，不要任何解释或分析。

## 输出格式（严格遵守）
```json
[
  {
    "id": "1",
    "outline": "话题内容概述（基于实际SRT内容，50字以内）",
    "topic_type": "knowledge",
    "segments": [
      {"start": "00:01:00,000", "end": "00:05:30,000"},
      {"start": "00:12:00,000", "end": "00:14:00,000"}
    ]
  },
  {
    "id": "2",
    "outline": "话题内容概述",
    "topic_type": "highlight",
    "segments": [
      {"start": "00:08:00,000", "end": "00:09:30,000"}
    ]
  }
]
```

**topic_type 分类**（必须准确归类）：
- highlight: 冲突金句、情绪爆发、怼人名场面、激烈观点交锋
- knowledge: 干货知识、技能讲解、深度分析
- product: 产品推销、卖货讲解、优惠介绍
- fun: 趣味段子、搞笑互动、娱乐内容
- daily: 日常闲聊、普通互动、一般性讲述

**segments 规则**：
- 同一话题可能被其他话题打断，出现在时间轴多段，需用多个segment表示
- segments 按时间升序排列
- 时间格式 hh:mm:ss,fff（逗号分隔毫秒）
- 起止时间必须对齐SRT条目首尾时间戳，严禁切割单条字幕

## 输入数据格式
SRT字幕包含序号、时间范围和文本三部分：
```
1
00:00:00,000 --> 00:00:05,000
大家好欢迎来到直播间
```

## 关键概念：什么是"完整话题"

一个完整话题是一组逻辑上相互依赖的对话单元。判定方法是**依赖链检验**：
> 去掉某段内容后，另一段变得不完整或难以理解 → 同话题

### 前向依赖检验（相邻条目对SRT N和N+1）
SRT(N+1)是否假设观众已经知道SRT(N)的信息？
- 指代词：这/那/他/它 → "这个评论"
- 因果词：为什么/所以/因此/因为 → "为什么王爷势力复杂"
- 承前词：刚才/说到/提到/那你说 → "刚才那个顺口溜"
- 对前文某表述的回应、解释、举例或延伸
满足任意一条 → 依赖成立 → 同话题

### 收尾检验（判断话题边界）
SRT(N)是否达到了收尾状态？
- 结论性表述：总之/所以说/明白了吧/你知道吧
- 从具体案例回到一般性总结
满足收尾 + SRT(N+1)不依赖SRT(N) → 此处为自然话题边界

**情绪连续不拆分例外**：
如果SRT(N)看似收尾，但SRT(N+1)与之满足以下任一条件，则视为未收尾，必须合并：
① **同一情绪线延续**：SRT(N+1)继续在同一语境下发表评论/吐槽/怼人，话题关键词一致
② **同一叙事延续**：SRT(N+1)引用/回指SRT(N)中提到的具体细节
③ **同一对话对象延续**：SRT(N)和SRT(N+1)针对同一观众/事件的连续回应

### 跨段话题合并（被其他话题打断的场景）
同一话题可能被其他话题打断，出现在时间线多段。**归属同一话题**的条件：
- 后文是对前文的补充、举例、延伸、深化
- 后文是主播的个人经历结合来说明前文观点
- 后文是对前文观点的总结、呼应

**判定为新话题**的条件（满足任意一条）：
- 主播明确说"换个话题""接下来说说""再聊一个"等换场话术
- 前后内容语义完全无关，且无过渡衔接
- 时间间隔超过180秒，中间穿插3个及以上独立无关话题，无语义承接

**语义优先级兜底**：不论间隔和穿插数量，存在内容承接、观点回溯或明显语义延续 → 优先判定为同话题。但前文已有明确收尾总结的，后续即使出现相同关键词也不再自动承接。

**不得强行合并**：语义完全无关的内容（如产品卖货、闲聊段子、正经知识讲解分别属于不同类别），即使由同一主播连续说出，也应为不同话题独立输出。

## 数量控制
- 输出 4~8 个话题，按时间升序排列 id
- 没有可提取的内容时输出 []
"""

# ============================================================
# 三步方案 Prompt：Step 2 批量评分（边界已确定，仅评分 + 可选边界建议）
# ============================================================
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

## 评分维度（注意：仅评分，不修改边界）
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
recommend_reason 每条不同，基于实际内容，≤20字。
boundary_suggestion 为 null 或字符串（格式见下方说明）。

## boundary_suggestion 字段（可选）
如果你在评分过程中发现某个话题的边界存在明显问题（例如：开头缺少必要的引入铺垫、结尾被过早截断、或者包含了明显不属于该话题的内容），你可以在此字段给出建议。格式为：

"建议[扩展/收缩/前移/后移]边界：[具体说明，含建议的时间偏移秒数]"

示例：
- "建议扩展开头：话题开头缺少产品引入铺垫，00:01:00前约30秒有铺垫内容，建议前移30秒以包含引入"
- "建议收缩结尾：00:08:30之后的内容已切换到下一话题，建议后移-15秒"
- "建议前移开头：当前开头落在了一条SRT的中间位置，建议前移5秒对齐SRT边界"
- "建议移除内部段：segment #2 的内容与该话题无关，属于误归类"

如果你认为边界没有问题，请填写 null。大多数情况下此字段应为 null。

注意：此字段仅作为建议供后续代码参考，不会自动修改边界。
"""

# ============================================================
# 三步方案 Prompt：Step 3 批量标题生成
# ============================================================
FUNCLIP_STEP3_BATCH_TITLE_PROMPT = """## 任务
为下方每个话题独立生成一个吸引人的短视频标题。每个标题必须基于该话题的实际SRT内容。

## 核心原则
1. **忠于原文**: 标题必须严格基于该话题的SRT文本，不得无中生有。
2. **突出亮点**: 精准捕捉片段最核心的观点、最激烈的情绪或最有价值的信息。
3. **精炼有力**: 简洁有冲击力，8~20个中文字符，可加感叹号。
4. **用语规范**: 禁用低俗词汇（装逼、傻逼、他妈的等），字幕中的低俗措辞需替换为中性表述（如犀利点评、直率吐槽）。
5. **钩子写法优先**: 优先使用设问/悬念/对比/数字等钩子句式，避免平铺直叙。
6. **差异化**: 每个话题的标题必须不同，不可重复。

## 所有话题
```json
[
  {
    "id": "1",
    "outline": "话题概述",
    "topic_type": "knowledge",
    "recommend_reason": "推荐理由",
    "srt_text": "00:01:00,000 --> 00:01:05,000\\n第一条字幕...\\n...(该话题的完整SRT)"
  }
]
```

## 输出
```json
{
  "titles": [
    {"id": "1", "title": "生成的标题文本"},
    {"id": "2", "title": "生成的标题文本"}
  ]
}
```
为**每一个**输入话题生成标题，不要跳过。
每个标题8~20个中文字符，禁止低俗词汇。
"""

# ============================================================
# 合并方案 Prompt：单次LLM调用完成话题切分 + 多段合并 + 标题生成
# ============================================================
FUNCLIP_MERGED_PROMPT = """## 任务
提取下方SRT字幕中的完整话题作为精彩片段。只输出JSON数组，不要任何解释或分析。

## 输出格式（严格遵守）
```json
[
  {
    "id": "1",
    "title": "话题1的标题文本（知识分享类）",
    "outline": "主播从某话题引入，展开核心观点，最后收尾总结的完整内容",
    "segments": [
      {"start": "00:01:00,000", "end": "00:05:30,000"}
    ],
    "final_score": 0.85,
    "recommend_reason": "推荐理由示例文字",
    "removed_sections": []
  },
  {
    "id": "2",
    "title": "话题2的标题文本（卖货讲解类）",
    "outline": "主播介绍某产品的功能特点、使用效果和优惠活动",
    "segments": [
      {"start": "00:08:00,000", "end": "00:09:00,000"}
    ],
    "final_score": 0.75,
    "recommend_reason": "推荐理由示例文字",
    "removed_sections": []
  }
]
```
时间格式hh:mm:ss,fff（逗号分隔毫秒）。没有可提取的内容时输出[]。识别出多个独立话题时，每个话题输出为一个独立对象，不要将无关话题合并为同一个话题。

**重要：以上JSON示例仅展示输出格式，示例中的标题/概述/推荐理由均为占位文字，你必须根据实际字幕内容生成，不得照抄示例文字。**

## 输入数据格式
SRT字幕包含序号、时间范围和文本三部分：
```
1
00:00:00,000 --> 00:00:05,000
大家好欢迎来到直播间
```
条目间时间差为无字幕静音段。

**静音推断方法**：SRT条目N结束到条目N+1开始之间的时间差值即为静音时间段。差值超过2秒的连续区间可标记为需剔除的纯静音。推理时无需音频信息，仅通过SRT时间戳差值判断即可。

## 关键概念：什么是"完整话题"

一个完整话题是一组逻辑上相互依赖的对话单元。判定方法是**依赖链检验**：
> 去掉某段内容后，另一段变得不完整或难以理解 → 同话题

一个完整话题通常包含以下阶段（了解此结构有助于边界判断，但不要求话题必须拥有所有阶段）：
- **前导引入/钩子**：开启话题的启动话术（互动请求、设问引入、故事开头、顺口溜/段子、叙事背景铺垫），**一切为后续核心内容做铺垫的"引子"都属于前导引入**，应与核心内容合并为同一话题
- **核心论述**：围绕主题展开的正文内容
- **收尾总结**：话题的自然结束（结论性表述、一般化归纳）

### 前向依赖检验（相邻条目对SRT N和N+1）
SRT(N+1)是否假设观众已经知道SRT(N)的信息？
- 指代词：这/那/他/它 → "这个评论"
- 因果词：为什么/所以/因此/因为 → "为什么王爷势力复杂"
- 承前词：刚才/说到/提到/那你说 → "刚才那个顺口溜"
- 对前文某表述的回应、解释、举例或延伸
满足任意一条 → 依赖成立 → 同话题

### 收尾检验（判断话题边界）
SRT(N)是否达到了收尾状态？
- 结论性表述：总之/所以说/明白了吧/你知道吧
- 从具体案例回到一般性总结
满足收尾 + SRT(N+1)不依赖SRT(N) → 此处为自然话题边界

**情绪连续不拆分例外**：
如果SRT(N)看似收尾，但SRT(N+1)与之满足以下任一条件，则视为未收尾，必须合并：
① **同一情绪线延续**：SRT(N+1)继续在同一语境下发表评论/吐槽/怼人，话题关键词（人物、事件、产品）一致
② **同一叙事延续**：SRT(N+1)引用/回指SRT(N)中提到的具体细节
③ **同一对话对象延续**：SRT(N)和SRT(N+1)针对同一观众/同一事件的连续回应

**判断方法**：去掉收尾词后，SRT(N)和SRT(N+1)是否仍然是同一段连贯语流？如是，则未收尾，合并。除非SRT(N+1)使用了明确换场话术（"接下来说说""换个话题"）。

### 跨间隙语义验证（4~60秒间隙）
ASR产生的短SRT条目可能制造虚假间隙。相邻短条目（每条≤3秒，间隙≤3秒）先合并为语义段落再做话题分析。
跨间隙判定（同话题依条件）：
- 后块是对前块的案例验证或例证
- 后块是对前块的延伸、对比或补充
- 后块引用了前块的核心概念（如"刚才说的XX"）

### 跨段话题合并（被其他话题打断的场景）
同一话题可能被其他话题打断，出现在时间线多段。**归属同一话题**的条件：
- 后文是对前文的补充、举例、延伸、深化
- 后文是主播的个人经历结合来说明前文观点
- 后文是对前文观点的总结、呼应、口号收尾

**判定为新话题**的条件（满足任意一条）：
- 主播明确说"换个话题""接下来说说""再聊一个"等换场话术
- 前后内容语义完全无关，且无过渡衔接
- **时间间隔超过180秒**，中间穿插**3个及以上**独立无关话题，无语义承接
- **时间间隔超过600秒**，即便只穿插1个无关话题，无语义承接

**语义优先级兜底**：不论间隔和穿插数量，存在内容承接、观点回溯（"刚才说到"）或明显语义延续 → 优先判定为同话题。但前文已有明确收尾总结的，后续即使出现相同关键词也不再自动承接。

**不得强行合并**：语义完全无关的内容（如产品卖货、闲聊段子、正经知识讲解分别属于不同类别），即使由同一主播连续说出，也应为不同话题独立输出。

**话题类型切换是新话题的强信号**：当主播从知识讲解/故事叙述突然切换到产品推销/卖货话术时，即使话题看似相关（如"地域性格"→"鸡肉丸产品"），也判定为新话题，不得合并。卖货话术、知识分享、闲聊段子是三种不同话题类型。

**自然过渡不拆分**：如果内容从钩子（段子/故事/顺口溜）自然推进到核心话题，或从话题自然过渡到产品讲解（如"说到这个XX，我家就有这个产品"），节奏连贯无明显切换信号，应视为同一完整片段，不得强行拆分。

### 反向追溯规则
如果收尾被选入但前导引入未被包含，需向前回溯定位引入的起点：
1. 检查收尾是否引用前文的某个概念/案例
2. 向前回溯到这些概念首次出现的位置
3. 继续回溯直到遇到明确的新话题启动器（换场话术、上一个话题的收尾信号、连续30秒以上无SRT条目），最大回溯范围不超过当前topic起始时间前5分钟
4. 将前导引入和核心论述合并进来

### 溯源牵引规则
如果核心内容依赖于前文的叙事背景（如"食神里的撒尿牛丸"引入牛肉丸），去掉背景后观众不知道"为什么突然说这个"，则该背景必须作为前导引入保留。

**注意**：同一关键词/同一产品 ≠ 同一个话题。两次出现无语义承接且间隔超过180秒+穿插3个话题 → 视为不同独立话题。

## 处理步骤

### 第一步：话题识别与完善
① **依赖链分析**：通读字幕，用上述前向依赖检验和收尾检验识别出每个独立话题的核心段落。不要因为主播停顿几秒就认为是新话题。
② **跨段合并**：用跨段话题合并规则，将同一话题被打散的段落合并为同一话题。
③ **反向追溯**：对合并后的每个话题，检查收尾是否引用了前文概念/案例。如果收尾被选入但前导引入未被包含，向前回溯补齐前导引入和核心论述。
④ **溯源牵引**：检查核心内容是否依赖于前文的叙事背景，如果是则将背景作为前导引入保留。

### 第二步：对齐边界到SRT条目
每个segment的start和end必须对齐到某条SRT的首尾时间戳。严禁落在两条SRT之间的间隙中，严禁切割单条字幕内部。

**同一话题的多个segment之间不得跳过有文本的SRT条目**。如果两个segment属于同一话题且之间有文本SRT未被包含，应扩展segment边界覆盖它们。

### 第三步：标记纯静音
removed_sections仅用于存放segment时间覆盖范围内、被SRT条目实际占据时间段之外的超过2秒连续无字幕纯静音空档。例如segment范围为00:01:00-00:05:30，其中SRT条目的时间戳覆盖了00:01:00-00:02:30和00:02:35-00:05:30，则00:02:30-00:02:35这5秒静音间隙可放入removed_sections。所有带文本的SRT条目必须保留在segments中。不同话题之间的天然间隙不属于任何segment，无需标记。

### 第四步：打分与排序
评分标准：
- **看点价值（0~1）**：内容是否包含冲突金句、独家信息、情绪爆发等。0.9=强烈金句冲突，0.7=有价值干货，0.5=日常讲述，0.3=平淡无意义
- **话题完整度（0~1）**：是否具备引入+核心+收尾的完整链路。0.9=三段完整，0.7=有核心+收尾，0.5=仅有核心论述，0.3=被截断
- **叙事流畅度（0~1）**：逻辑连续、无重复啰嗦、衔接自然。0.9=一气呵成，0.7=偶尔卡顿不影响理解，0.5=多处卡顿但仍连贯，0.3=逻辑断裂、多处重复、难以理解

```
final_score = 看点价值×0.4 + 话题完整度×0.3 + 叙事流畅度×0.3
```
排序优先级（从高到低）：先按话题类型分类排序，同类型内再按分数降序排列。**类型分类仅影响排序优先级，不影响看点价值评分的计算**——所有片段都需按评分标准计算final_score。
- **冲突金句**：情绪峰值、激烈争论、反转观点、爆点金句
- **干货知识**：知识点讲解、经验分享、数据分析、实用技巧
- **商品卖点**：产品价格、功能效果、使用体验、购买引导
- **趣味闲聊**：段子、八卦、娱乐互动、轻松话题
- **常规日常讲述**：过渡铺垫、流程介绍、无亮点日常对话
同优先级内按分数降序排列。仅输出final_score ≥ 0.5的片段，低于0.5的不纳入输出。
最多取前**6个**作为最终输出。
单个segment时长建议10秒~5分钟。最终输出的话题**总播放时长建议不低于20秒**（多个segment之和）。低于20秒的短话题，如果语义上可自然合并到相邻主话题则优先合并；无法合并的高评分短金句（评分≥0.7）可保留独立输出，但须在推荐理由中标注"短精华"。

### 第五步：自检复核
1. **被选中片段**的所有SRT条目均完成归属，无遗漏无交叉（未选中的话题SRT无需覆盖标注）
2. 不同片段之间的segments时间区间无重叠
3. 每条**被选中片段**的SRT仅归属于一个片段
4. **边界验证**：去掉前导部分后读核心内容——如果变得奇怪则边界应扩展包含；同样检查收尾最后一条SRT之后紧邻的下一条SRT是否存在语义承接——如果存在但未被包含，则边界扩展
5. removed_sections中的时间区间，均对应SRT条目间超过2秒的连续间隙，无文本SRT条目被剔除
6. 所有时间戳格式为hh:mm:ss,fff（逗号分隔毫秒）

## 输出字段说明

| 字段 | 说明 |
|------|------|
| id | 在完成打分和排序、取前6个输出后，按起始时间升序重新编号："1","2","3"... |
| title | 概括话题核心看点的标题，用语正面积极，禁用低俗词汇。不得直接照搬字幕中的原始低俗措辞（装逼/傻逼/他妈的等），需替换为中性或正面表述（犀利点评/直率吐槽/独特见解） |
| outline | 描述从引入到收尾的全部话题内容梗概 |
| segments | 话题分散的多段时间区间数组，按开始时间升序排列 |
| final_score | 0~1浮点数 |
| recommend_reason | 基于该片段实际内容撰写，突出独特看点，每条片段必须不同，不超过30字 |
| removed_sections | 仅存放合规静音剔除时段，每项包含start/end。无静音则为空数组 |

## 全局硬性约束
1. 时间格式hh:mm:ss,fff（逗号分隔毫秒），匹配SRT时间格式
2. 不同片段的segments时间区间完全独立，无交叉
3. 每条**被选中片段**的SRT唯一归属于一个片段，未选中话题的SRT无归属要求
4. 单条SRT不可拆分，segment起止只能对齐SRT条目的首尾时间戳
5. 文本不可剔除，所有带文本的SRT条目保留在segments中
6. 多人连麦围绕同一主题发言时统一合并为单个话题，不按人物拆分
7. 话题无收尾话术而戛然中止时以最后一句核心论述的时间戳作为结束边界
8. 低俗词汇的过滤规则：
    - 低俗/侮辱性措辞只影响标题生成（标题中替换为中性表述），不影响内容价值评分
    - **例外**：如果该片段的核心看点是知识分享、剧情讲解、产品引出的前置铺垫——即使含有少量低俗口语化表达，应保留内容价值评分，仅在标题中做中性化处理；不得因低俗用词将整段有价值话题丢弃
9. 最多6个独立话题片段，最少输出2个（字幕只有单个话题时最少1个）
10. 仅输出JSON数组，禁止增加多余文字、注释或说明内容
11. **产品推介按引出方式处理**：
    (a) **自然引出应合并**：如果产品是从话题内容自然延伸出来的——如"电影里的撒尿牛丸→我们家的牛肉丸"、"说到XX问题/场景→我家产品就是这个效果"——则属于"自然过渡不拆分"场景，应合并为同一话题
    (b) **突兀出现应独立**：如果产品讲解与前后话题无内容承接关系（如刚聊完历史突然说"来，上链接"），则独立输出为单独卖货话题
    (c) **多个独立产品互不合并**：连续介绍的多个不同产品（先卖牛肉丸再卖鸡蛋再卖手表）各自为独立话题
    **判断方法**：去掉产品讲解部分，看前文话题是否完整自洽。完整自洽→产品独立；不完整（缺少铺垫/过渡）→产品是自然延伸。
12. **标题用语规范**：
    - 禁用低俗词汇：装逼/傻逼/他妈的/逼味等，标题中必须替换为中性表述（犀利点评/直率吐槽/独特见解）
    - 禁用直接侮辱性表述：字幕中怼人/骂人的内容，标题用"对XX的独特看法""引发争议的观点"等中性化概括
    - 标题须独立创作，不得照抄字幕中任何原始措辞
13. **跨话题连续性检测**：
    多个CLIP在供给阶段是独立切分的，合并阶段须检测相邻CLIP的话题边界：
    - 如果某个CLIP的最后1~3条SRT与另一个CLIP的开头明显是同一话题的延续
      （如"那个就是河北人做采购的"→"那个隔着电话都逼逼味十足"），
      则这两个CLIP应视为同一话题，合并为一个segment组
    - 判断标志：两段内容共享核心关键词（同一人物/事件/产品/地域）、
      存在明显的指代承接（"那个""就是""他们"指向同一对象）、
      去掉CLIP边界后前后是连贯的一段话
    - 产品/商品名称本身不构成话题合并依据
      （如CLIP1提到"手表"，CLIP2详细讲"手表功能"→仍需检查内容是否在同一叙事线内）"""

# 填充词列表（预处理时剔除——只剔除无意义的口吃/犹豫/套话）
FILLER_WORDS = {
    # 犹豫音
    '嗯', '呃', '哦', '嗯嗯', '呃呃',
    # 笑声
    '哈哈', '嘿嘿',
    # 口头禅/犹豫词
    '那个', '那个啥', '这个', '这个这个', '那个那个',
    # 重复性停顿（"然后然后"、"就是就是"等语无伦次）
    '然后然后', '就是就是', '那个那个',
    # 套话（无信息量的引导语）
    '我们可以看到', '大家可以看到',
    '总的来说', '总的来说呢',
}


def _clean_filler_words(text: str) -> str:
    """从文本中剔除填充词"""
    import re
    for word in sorted(FILLER_WORDS, key=len, reverse=True):
        text = re.sub(re.escape(word), '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _deduplicate_clip_segments(merged_clips: List[Dict]) -> List[Dict]:
    """
    跨clip去重：不同clip的segments如果有时间重叠，从segments更多的clip中剔除整个重叠段
    
    策略：segments少的clip（更专注）优先保留重叠部分，从segments多的clip中剔除
    """
    if len(merged_clips) < 2:
        return merged_clips

    # 按segments数量升序排序（少的优先保留），记录原始位置用于回写
    indexed = list(enumerate(merged_clips))
    indexed.sort(key=lambda x: len(x[1].get('segments', [])))

    reserved_ranges = []  # [(start_seconds, end_seconds)] 已保留的时间范围

    for orig_idx, clip in indexed:
        original_segments = clip.get('segments', [])
        filtered = []
        for seg in original_segments:
            seg_start = _srt_time_to_seconds(seg['start'])
            seg_end = _srt_time_to_seconds(seg['end'])

            has_overlap = False
            for rs, re in reserved_ranges:
                if seg_start < re and seg_end > rs:
                    has_overlap = True
                    break

            if not has_overlap:
                filtered.append(seg)
                reserved_ranges.append((seg_start, seg_end))

        merged_clips[orig_idx]['segments'] = filtered

    # 移除没有segments的clip
    result = [c for c in merged_clips if c.get('segments')]

    if len(result) < len(merged_clips):
        logger.info(f"跨clip去重: 移除了{len(merged_clips) - len(result)}个重叠片段")

    return result


def _compute_effective_segments(segments: List[Dict], removed_sections: List[Dict],
                                 buffer: float = 0.2) -> List[Dict]:
    """
    计算有效段列表：从segments中减去removed_sections的时间范围
    
    对每段的有效内容两侧添加buffer秒缓冲，防止切割时裁剪掉语音首尾。
    各缓冲段之间不重叠（间隙过小时合并），不超出原始segment边界。
    """
    if not removed_sections:
        return segments

    # 将removed_sections转为秒数并排序
    removed = []
    for rs in removed_sections:
        rs_start = _srt_time_to_seconds(rs['start'])
        rs_end = _srt_time_to_seconds(rs['end'])
        if rs_end > rs_start:
            removed.append((rs_start, rs_end))
    removed.sort()

    # 合并重叠的removed区间
    merged_removed = []
    for start, end in removed:
        if merged_removed and start <= merged_removed[-1][1]:
            merged_removed[-1] = (merged_removed[-1][0], max(merged_removed[-1][1], end))
        else:
            merged_removed.append([start, end])

    # 对每个segment减去removed区间，再加缓冲
    effective = []
    for seg in segments:
        seg_start = _srt_time_to_seconds(seg['start'])
        seg_end = _srt_time_to_seconds(seg['end'])

        cuts = [(seg_start, seg_end)]
        for rm_start, rm_end in merged_removed:
            new_cuts = []
            for cs, ce in cuts:
                if rm_start >= ce or rm_end <= cs:
                    new_cuts.append((cs, ce))
                else:
                    if cs < rm_start:
                        new_cuts.append((cs, rm_start))
                    if ce > rm_end:
                        new_cuts.append((rm_end, ce))
            cuts = new_cuts

        # 对每段有效内容加缓冲，但不超出原始segment边界，且不重叠
        buffered = []
        for cs, ce in cuts:
            bs = max(seg_start, cs - buffer)
            be = min(seg_end, ce + buffer)
            if buffered and bs <= buffered[-1][1]:
                buffered[-1] = (buffered[-1][0], max(buffered[-1][1], be))
            else:
                buffered.append((bs, be))

        for bs, be in buffered:
            if be - bs > 0.5:
                effective.append({
                    'start': _seconds_to_srt_time(bs),
                    'end': _seconds_to_srt_time(be)
                })

    return effective


def _log_topic_details(merged_clips: List[Dict], srt_text: str):
    """详细日志：输出每个话题包含的segments、字幕内容及归类原因"""
    entries = _parse_srt_timeline(srt_text)
    if not entries:
        return

    logger.info("")
    logger.info("=" * 60)
    logger.info("话题分组详情")
    logger.info("=" * 60)

    for clip in merged_clips:
        clip_id = clip.get('id', '?')
        title = clip.get('title', clip.get('outline', '未命名话题'))
        outline = clip.get('outline', '')
        reason = clip.get('recommend_reason', '')

        logger.info(f"")
        logger.info(f"--- 话题 {clip_id}: {title} ---")
        logger.info(f"概述: {outline}")
        if reason:
            logger.info(f"归类原因: {reason}")

        segments = clip.get('segments', [])
        logger.info(f"包含 {len(segments)} 个时间段:")

        for si, seg in enumerate(segments):
            seg_start = _srt_time_to_seconds(seg['start'])
            seg_end = _srt_time_to_seconds(seg['end'])

            contained = [e for e in entries if e['start'] >= seg_start and e['end'] <= seg_end]

            logger.info(f"  时间段{si+1}: {seg['start']} -> {seg['end']} ({len(contained)}条字幕)")
            for entry in contained:
                logger.info(f"    [{entry['start_str']} -> {entry['end_str']}] {entry['text']}")

        removed = clip.get('removed_sections', [])
        if removed:
            logger.info(f"  剔除 {len(removed)} 段无关/静音内容:")
            for rs in removed:
                logger.info(f"    {rs['start']} -> {rs['end']}: {rs.get('reason', '')}")

    logger.info("=" * 60)


def _merge_srt_segments(srt_path: Path, merged_clips: List[Dict]) -> List[Dict]:
    """
    将合并方案的输出（含多段segments）转换为标准格式
    每个多段clip被拆分为多个独立clip（后续由视频拼接实现合并）
    """
    video_clips = []
    for i, clip in enumerate(merged_clips):
        segments = clip.get('segments', [])
        if not segments:
            continue
        global_start = segments[0]['start']
        global_end = segments[0]['end']
        for seg in segments[1:]:
            if seg['start'] < global_start:
                global_start = seg['start']
            if seg['end'] > global_end:
                global_end = seg['end']
        video_clips.append({
            'id': clip.get('id', str(i + 1)),
            'outline': clip.get('outline', ''),
            'generated_title': clip.get('title', f"片段_{i+1}"),
            'start_time': global_start,
            'end_time': global_end,
            'final_score': clip.get('final_score', 0.5),
            'recommend_reason': clip.get('recommend_reason', ''),
            'content': [],
            '_segments': segments,
            '_removed_sections': clip.get('removed_sections', [])
        })
    return video_clips


def _srt_time_to_seconds(time_str: str) -> float:
    """将SRT时间格式(hh:mm:ss,fff)转换为秒数"""
    time_str = time_str.replace(',', '.')
    parts = time_str.split(':')
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])


def _seconds_to_srt_time(seconds: float) -> str:
    """将秒数转换为SRT时间格式(hh:mm:ss,fff)"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace('.', ',')


def _parse_srt_timeline(srt_text: str) -> List[Dict]:
    """解析SRT文本，返回按时间排序的条目列表"""
    entries = []
    blocks = re.split(r'\n\s*\n', srt_text.strip())
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        
        time_line = lines[1]
        time_match = re.match(r'(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})', time_line)
        if not time_match:
            continue
        
        start = _srt_time_to_seconds(time_match.group(1))
        end = _srt_time_to_seconds(time_match.group(2))
        text = ' '.join(lines[2:]).strip()
        
        entries.append({
            'start': start,
            'end': end,
            'start_str': time_match.group(1).replace('.', ','),
            'end_str': time_match.group(2).replace('.', ','),
            'text': text,
            'duration': end - start
        })
    
    entries.sort(key=lambda e: e['start'])
    return entries


def _filter_vad_silence_by_segments(vad_silence: List[tuple],
                                     segments: List[Dict],
                                     min_silence_duration: float = 2.0) -> List[Dict]:
    """
    将 VAD 检测到的全音频静音区间，筛选为只落在指定 segments 范围内的静音段

    Args:
        vad_silence: VAD输出的全音频静音区间 [(start_sec, end_sec), ...]
        segments: 时间段列表 [{'start': 'hh:mm:ss,fff', 'end': 'hh:mm:ss,fff'}]
        min_silence_duration: 最短静音时长

    Returns:
        格式化的静音段列表，可直接追加到 removed_sections
    """
    seg_ranges = []
    for seg in segments:
        s = _srt_time_to_seconds(seg['start'])
        e = _srt_time_to_seconds(seg['end'])
        seg_ranges.append((s, e))

    result = []
    for silence_start, silence_end in vad_silence:
        for seg_start, seg_end in seg_ranges:
            overlap_start = max(silence_start, seg_start)
            overlap_end = min(silence_end, seg_end)
            if overlap_end - overlap_start >= min_silence_duration:
                result.append({
                    'start': _seconds_to_srt_time(overlap_start),
                    'end': _seconds_to_srt_time(overlap_end),
                    'reason': f"VAD检测静音({overlap_end-overlap_start:.1f}秒)"
                })

    return result


def _validate_segments_with_srt(merged_clips: List[Dict], srt_text: str, 
                                  silence_threshold: float = 2.0) -> List[Dict]:
    """
    用SRT时间戳验证和修正LLM返回的片段边界

    Args:
        merged_clips: LLM返回的片段列表
        srt_text: 原始SRT文本
        silence_threshold: 静音阈值（秒），SRT间隙超过此值标记为静音

    Returns:
        修正后的片段列表
    """
    entries = _parse_srt_timeline(srt_text)
    if not entries:
        logger.warning("无法解析SRT时间线，跳过验证")
        return merged_clips

    logger.info(f"SRT时间线解析完成: {len(entries)} 条字幕条目")
    
    for clip in merged_clips:
        segments = clip.get('segments', [])
        if not segments:
            continue
        
        validated_segments = []
        all_removed = clip.get('removed_sections', [])
        
        for seg in segments:
            seg_start = _srt_time_to_seconds(seg.get('start', '00:00:00,000'))
            seg_end = _srt_time_to_seconds(seg.get('end', '00:00:00,000'))
            
            # 找到完全在segment范围内的SRT条目
            contained = [e for e in entries if e['start'] >= seg_start and e['end'] <= seg_end]
            
            if not contained:
                # 检测LLM是否切割了SRT内部（seg边界落在某条SRT中间）
                overlapping = [e for e in entries if e['start'] < seg_end and e['end'] > seg_start]
                if overlapping:
                    first = overlapping[0]
                    last = overlapping[-1]
                    overlap_start = min(seg_start, first['start'])
                    overlap_end = max(seg_end, last['end'])
                    logger.info(f"  修复LLM切割SRT: [{seg['start']}->{seg['end']}] 包含{len(overlapping)}条SRT，"
                                f"扩展为[{_seconds_to_srt_time(overlap_start)}->{_seconds_to_srt_time(overlap_end)}]")
                    seg_start = overlap_start
                    seg_end = overlap_end
                    contained = overlapping
                else:
                    # 该segment内没有任何SRT条目 -> 全是静音，剔除
                    all_removed.append({
                        'start': seg['start'],
                        'end': seg['end'],
                        'reason': f"该时间范围内无字幕（纯静音）"
                    })
                    logger.info(f"  剔除无字幕段: {seg['start']} -> {seg['end']}")
                    continue
            
            # 对齐边界到第一条和最后一条SRT的时间
            validated_start = contained[0]['start']
            validated_end = contained[-1]['end']
            
            # 检查内部间隙
            for i in range(len(contained) - 1):
                gap = contained[i + 1]['start'] - contained[i]['end']
                if gap > silence_threshold:
                    all_removed.append({
                        'start': _seconds_to_srt_time(contained[i]['end']),
                        'end': _seconds_to_srt_time(contained[i + 1]['start']),
                        'reason': f"SRT时间戳间隙{gap:.1f}秒（静音）"
                    })
                    logger.info(f"  内部静音: {_seconds_to_srt_time(contained[i]['end'])} -> "
                                f"{_seconds_to_srt_time(contained[i + 1]['start'])} ({gap:.1f}秒)")
            
            validated_segments.append({
                'start': _seconds_to_srt_time(validated_start),
                'end': _seconds_to_srt_time(validated_end)
            })
            
            # 记录边界修正量
            start_diff = validated_start - seg_start
            end_diff = seg_end - validated_end
            if abs(start_diff) > 0.1 or abs(end_diff) > 0.1:
                logger.info(f"  边界修正: [{seg['start']}->{seg['end']}] -> "
                            f"[{_seconds_to_srt_time(validated_start)}->{_seconds_to_srt_time(validated_end)}] "
                            f"(前修{start_diff:.1f}s, 后修{-end_diff:.1f}s)")
        
        # ===== 新增：填充同一clip内segment之间的间隙和重叠 =====
        # 如果间隙中有带文本的SRT条目，合并前后segment；重叠段也合并
        if len(validated_segments) >= 2:
            i = 0
            while i < len(validated_segments) - 1:
                curr_end_sec = _srt_time_to_seconds(validated_segments[i]['end'])
                next_start_sec = _srt_time_to_seconds(validated_segments[i+1]['start'])
                
                # 重叠处理：后一段开始时间在前一段结束之前
                if curr_end_sec >= next_start_sec:
                    logger.info(f"  修复重叠: {validated_segments[i]['end']}->{validated_segments[i+1]['start']}")
                    validated_segments[i]['end'] = validated_segments[i+1]['end']
                    del validated_segments[i+1]
                    continue
                
                # 找到间隙中完全包含的SRT条目
                gap_srts = [
                    e for e in entries
                    if e['start'] >= curr_end_sec and e['end'] <= next_start_sec
                    and e.get('text', '').strip()
                ]
                
                if gap_srts:
                    logger.info(f"  填充间隙: {validated_segments[i]['end']}->{validated_segments[i+1]['start']} "
                                f"(含{len(gap_srts)}条有文本SRT)")
                    # 合并：当前段延伸到下一段结束
                    validated_segments[i]['end'] = validated_segments[i+1]['end']
                    del validated_segments[i+1]
                    # i不变，继续检查新间隙
                else:
                    i += 1
            logger.info(f"  间隙填充后: {len(validated_segments)} 个时间段")
        
        clip['segments'] = validated_segments if validated_segments else segments
        
        # 合并去重removed_sections
        existing_starts = {(r['start'], r['end']) for r in clip.get('removed_sections', [])}
        for r in all_removed:
            key = (r['start'], r['end'])
            if key not in existing_starts:
                clip.setdefault('removed_sections', []).append(r)
                existing_starts.add(key)
    
    return merged_clips


def parse_funclip_timestamps(input_text):
    """解析FunClip风格的时间戳提取"""
    timestamps = re.findall(r'\[(\d{2}:\d{2}:\d{2},?\d{0,3})\s*-\s*(\d{2}:\d{2}:\d{2},?\d{0,3})\]', input_text)
    times_list = []
    
    for start_time, end_time in timestamps:
        start_millis = _convert_time_to_millis(start_time)
        end_millis = _convert_time_to_millis(end_time)
        times_list.append([start_millis, end_millis])
    
    return times_list

def _convert_time_to_millis(time_str):
    """将时间字符串转换为毫秒"""
    try:
        hours, minutes, seconds, milliseconds = map(int, re.split('[:,]', time_str))
        return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds
    except Exception as e:
        logger.warning(f"时间转换失败: {time_str}, 使用默认值: {e}")
        return 0


# ============================================================
# 三步方案工具函数：boundary_suggestion 处理（P0修复3）
# ============================================================

def _apply_boundary_suggestions(
    topics: List[Dict],
    scores: List[Dict],
    srt_entries: List[Dict]
) -> List[Dict]:
    """
    处理 Step 2 返回的 boundary_suggestion，验证并应用合理的建议。

    建议应用规则：
    1. 扩展开头：新起点必须对齐某条SRT的首时间戳
    2. 收缩结尾：新终点必须对齐某条SRT的尾时间戳
    3. 前移/后移：同扩展/收缩
    4. 移除内部段：只有当移除后话题仍有 ≥ 1 个 segment 时才执行
    5. 激进建议（移动 > 60 秒）→ 忽略（可能是 LLM 幻觉）
    """
    applied_count = 0
    max_suggestions_per_topic = 2

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

        suggestion_lower = suggestion.lower()
        handled = False

        if '扩展' in suggestion and ('开头' in suggestion or '向前' in suggestion):
            _handle_extend_start(suggestion, topic, segments, srt_entries)

        elif '扩展' in suggestion and ('结尾' in suggestion or '向后' in suggestion):
            _handle_extend_end(suggestion, topic, segments, srt_entries)

        elif '收缩' in suggestion and '结尾' in suggestion:
            _handle_shrink_end(suggestion, topic, segments, srt_entries)

        elif '收缩' in suggestion and '开头' in suggestion:
            _handle_shrink_start(suggestion, topic, segments, srt_entries)

        elif '移除' in suggestion and ('内部' in suggestion or 'segment' in suggestion_lower):
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
    time_match = re.search(r'(\d+)\s*秒', suggestion)
    extend_seconds = int(time_match.group(1)) if time_match else 10

    if extend_seconds > 60:
        logger.warning(f"扩展建议偏移量过大({extend_seconds}秒)，可能是LLM幻觉，跳过")
        return

    first_seg_start = _srt_time_to_seconds(segments[0]['start'])
    new_start_sec = max(0, first_seg_start - extend_seconds)

    aligned_start = _align_to_srt_start(new_start_sec, srt_entries)

    if aligned_start is not None and aligned_start < first_seg_start:
        segments[0]['start'] = _seconds_to_srt_time(aligned_start)
        logger.info(
            f"boundary_suggestion 已应用: 话题{topic['id']} 开头前移 "
            f"{first_seg_start - aligned_start:.1f}秒 → {_seconds_to_srt_time(aligned_start)}"
        )


def _handle_shrink_end(suggestion: str, topic: Dict, segments: List[Dict],
                        srt_entries: List[Dict]):
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
    seg_match = re.search(r'segment\s*#?\s*(\d+)', suggestion, re.IGNORECASE)
    if not seg_match:
        return
    seg_idx = int(seg_match.group(1)) - 1

    if seg_idx < 0 or seg_idx >= len(segments):
        return

    if len(segments) <= 1:
        logger.warning(f"boundary_suggestion 拒绝: 话题{topic['id']} 只有1个segment，不能移除")
        return

    removed_seg = segments.pop(seg_idx)
    logger.info(
        f"boundary_suggestion 已应用: 移除话题{topic['id']}的segment#{seg_idx+1} "
        f"({removed_seg['start']} -> {removed_seg['end']})"
    )


def _align_to_srt_start(target_sec: float, srt_entries: List[Dict]) -> Optional[float]:
    best = None
    for entry in srt_entries:
        if entry['start'] <= target_sec:
            if best is None or entry['start'] > best:
                best = entry['start']
    return best


def _align_to_srt_end(target_sec: float, srt_entries: List[Dict]) -> Optional[float]:
    best = None
    for entry in srt_entries:
        if entry['end'] >= target_sec:
            if best is None or entry['end'] < best:
                best = entry['end']
    return best


# ============================================================
# 三步方案工具函数：token 预估与自动分批（P0修复4）
# ============================================================

ZH_CHAR_TO_TOKEN_RATIO = 2.0
DEFAULT_MAX_TOKENS = 8192
TOKEN_SAFETY_MARGIN = 0.8
RESERVED_OUTPUT_TOKENS = 2048


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * ZH_CHAR_TO_TOKEN_RATIO + other_chars * 0.3)


def _should_batch_step2(topics_with_srt: List[Dict], max_tokens: int = None) -> bool:
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
    TYPE_PRIORITY = {'highlight': 1, 'knowledge': 1, 'product': 2, 'fun': 2, 'daily': 2}
    batch1 = [t for t in topics_with_srt if TYPE_PRIORITY.get(t.get('topic_type'), 2) == 1]
    batch2 = [t for t in topics_with_srt if TYPE_PRIORITY.get(t.get('topic_type'), 2) == 2]
    return batch1, batch2


# ============================================================
# 三步方案工具函数：检查点持久化（P0修复5）
# ============================================================

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


# ============================================================
# 三步方案辅助函数：数据转换（P0修复3-5共享）
# ============================================================

VULGAR_WORD_MAP = {
    '装逼': '犀利点评',
    '傻逼': '令人费解',
    '他妈的': '真性情',
    '逼味': '独特风格',
    '傻X': '争议观点',
    '脑残': '出人意料',
    '弱智': '令人困惑',
}


def _validate_step1_segments(topics: List[Dict], srt_text: str) -> List[Dict]:
    for topic in topics:
        topic.setdefault('removed_sections', [])
    return _validate_segments_with_srt(topics, srt_text)


def _merge_scores_to_topics(topics: List[Dict], scores: List[Dict]) -> List[Dict]:
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
    title_map = {t.get('id'): t.get('title', '') for t in titles}
    for topic in topics:
        tid = topic.get('id', '')
        title = title_map.get(tid, '')
        if title:
            title = _postprocess_title(title, topic)
            topic['title'] = title
        else:
            topic['title'] = topic.get('outline', '未命名片段')[:20]
    return topics


def _postprocess_title(title: str, topic: Dict) -> str:
    for vulgar, replacement in VULGAR_WORD_MAP.items():
        title = title.replace(vulgar, replacement)

    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', title))
    if chinese_chars < 8:
        outline = topic.get('outline', '')
        title = title + '：' + outline[:15]
    elif chinese_chars > 20:
        chinese_positions = [i for i, c in enumerate(title) if '\u4e00' <= c <= '\u9fff']
        if len(chinese_positions) > 20:
            cut_pos = chinese_positions[19] + 1
            for punct in '，。！？…~':
                punct_pos = title[:cut_pos].rfind(punct)
                if punct_pos > 0:
                    cut_pos = punct_pos + 1
                    break
            title = title[:cut_pos]
    return title


def _convert_topics_to_clips(topics: List[Dict]) -> List[Dict]:
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


class FunClipStyleProcessor:
    """基于FunClip风格的单步LLM处理方案"""
    
    def __init__(self, metadata_dir: Path = None):
        from backend.core.llm_manager import LLMManager
        self.llm_manager = LLMManager()
        self.metadata_dir = metadata_dir or Path('.')
        self.chunks_dir = self.metadata_dir / "funclip_chunks"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
    
    def process(self, srt_path: Path, processing_mode: str = "two_stage"):
        """完整的单步处理流程

        Args:
            srt_path: SRT文件路径
            processing_mode: 处理模式
                - "two_stage": 两阶段方案（默认，先识别边界再生成标题）
                - "merged": 合并方案（单次LLM调用完成所有任务）
                - "three_step": 三步方案（边界识别→评分→标题，含检查点与降级）
        """
        logger.info("="*60)
        logger.info(f"使用FunClip风格处理开始 [模式: {processing_mode}]")
        logger.info("="*60)
        
        # 1. 读取和解析SRT
        srt_text = self._read_srt(srt_path)
        
        # 2. 单步LLM处理（根据模式选择）
        clips, collections = self._single_step_llm_process(srt_text, processing_mode)
        
        # 3. 保存结果
        self._save_results(clips, collections)
        
        return clips, collections
    
    def _read_srt(self, srt_path: Path):
        """读取SRT文件"""
        try:
            with open(srt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.warning(f"读取SRT失败: {e}")
            return ""
    
    def _single_step_llm_process(self, srt_text: str, processing_mode: str = "two_stage"):
        """单步LLM处理，根据模式选择不同方案"""
        if not self.llm_manager.current_provider:
            logger.warning("没有可用的LLM提供商，使用降级方案")
            return self._fallback_process(srt_text)
        
        if processing_mode == "merged":
            return self._llm_process_merged(srt_text)
        elif processing_mode == "three_step":
            return self._llm_process_three_step(srt_text)
        else:
            return self._llm_process_with_llm(srt_text)
    
    def _llm_process_with_llm(self, srt_text: str):
        """两阶段LLM处理：1.识别片段 2.每段独立生成标题"""
        try:
            # ===== 第一阶段：仅识别片段边界 =====
            logger.info("开始第一阶段LLM调用（识别片段边界）...")
            logger.info(f"输入SRT文本长度: {len(srt_text)} 字符")
            
            response = self.llm_manager.current_provider.call(
                FUNCLIP_CLIP_ONLY_PROMPT,
                "这是待裁剪的视频srt字幕：\n" + srt_text,
                max_tokens=8192
            )
            
            if not response or not response.content:
                logger.warning("第一阶段LLM返回空响应，使用降级方案")
                return self._fallback_process(srt_text)
            
            logger.info(f"第一阶段LLM响应成功，长度: {len(response.content)} 字符")
            
            clips = self._parse_clips_only(response.content)
            
            if not clips:
                logger.warning("第一阶段未能解析出片段，使用降级方案")
                return self._fallback_process(srt_text)
            
            logger.info(f"第一阶段识别到 {len(clips)} 个片段")
            for clip in clips:
                logger.info(f"  片段{clip.get('id')}: {clip.get('outline', 'N/A')}, "
                          f"时间: {clip.get('start', 'N/A')} -> {clip.get('end', 'N/A')}, "
                          f"评分: {clip.get('final_score', 0)}")
            
            # ===== 第二阶段：为每个片段独立生成标题 =====
            logger.info("=" * 40)
            logger.info("开始第二阶段：为每个片段独立生成标题")
            logger.info("=" * 40)
            
            for clip in clips:
                clip_id = clip.get('id', '')
                start_time = clip.get('start', '')
                end_time = clip.get('end', '')
                outline = clip.get('outline', '')
                recommend_reason = clip.get('recommend_reason', '')
                
                # 提取该片段自己的SRT文本
                clip_srt = self._extract_srt_segment(srt_text, start_time, end_time)
                
                if not clip_srt:
                    logger.warning(f"片段{clip_id}无法提取字幕文本，使用outline作为标题")
                    clip['generated_title'] = outline
                    continue
                
                logger.info(f"为片段{clip_id}生成标题，SRT长度: {len(clip_srt)} 字符")
                logger.debug(f"片段{clip_id}的SRT文本: {clip_srt[:200]}...")
                
                title_response = self.llm_manager.current_provider.call(
                    FUNCLIP_TITLE_PROMPT.format(
                        outline=outline,
                        recommend_reason=recommend_reason,
                        clip_srt_text=clip_srt
                    ),
                    None
                )
                
                if title_response and title_response.content:
                    title = title_response.content.strip()
                    # 清理可能的引号和多余字符
                    title = title.strip('"').strip("'").strip()
                    clip['generated_title'] = title
                    logger.info(f"  片段{clip_id}标题: {title}")
                else:
                    logger.warning(f"片段{clip_id}标题生成失败，使用outline")
                    clip['generated_title'] = outline
            
            # 生成合集
            collections = self._generate_collections(clips)
            
            logger.info(f"两阶段处理完成，共 {len(clips)} 个片段")
            return clips, collections
            
        except Exception as e:
            logger.warning(f"LLM处理失败: {e}，使用降级方案")
            return self._fallback_process(srt_text)
    
    def _llm_process_merged(self, srt_text: str):
        """合并方案：单次LLM调用完成话题切分 + 多段合并 + 标题生成 + 静音剔除"""
        try:
            # ===== 预处理：剔除填充词 =====
            logger.info("开始预处理SRT文本（剔除填充词）...")
            original_len = len(srt_text)
            cleaned_srt = _clean_filler_words(srt_text)
            logger.info(f"预处理完成: {original_len} -> {len(cleaned_srt)} 字符 (剔除 {original_len - len(cleaned_srt)} 字符)")

            enhanced_text = None
            try:
                from backend.pipeline.topic_precluster import TopicPreCluster
                precluster = TopicPreCluster()
                report = precluster.process(srt_text)
                if report.clusters:
                    logger.info(f"预聚类完成: {report.stats}")
                    enhanced_text = report.enhanced_text
                else:
                    logger.info(f"预聚类: 未发现有效聚类 ({report.stats['total_entries']}条, {report.stats.get('coverage_ratio', 0):.0%}覆盖)")
                    enhanced_text = cleaned_srt
            except Exception as e:
                logger.warning(f"预聚类失败，回退到清理后SRT: {e}")
                enhanced_text = cleaned_srt

            logger.info("开始合并方案LLM调用（话题切分 + 标题生成 + 静音剔除）...")
            logger.info(f"输入SRT文本长度: {len(enhanced_text)} 字符")

            response = self.llm_manager.current_provider.call(
                FUNCLIP_MERGED_PROMPT,
                "这是待分析剪辑的直播srt字幕：\n" + enhanced_text,
                max_tokens=8192
            )

            if not response or not response.content:
                logger.warning("合并方案LLM返回空响应，使用降级方案")
                return self._fallback_process(srt_text)

            logger.info(f"合并方案LLM响应成功，长度: {len(response.content)} 字符")
            logger.info(f"合并方案LLM响应内容: {response.content[:500]}")

            # 保存原始响应到文件（用于调试）
            try:
                debug_path = self.metadata_dir / "funclip_raw_response.txt"
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(response.content)
                logger.info(f"原始LLM响应已保存到: {debug_path}")
            except Exception as e:
                logger.warning(f"保存原始LLM响应失败: {e}")

            merged_clips = self._parse_merged_response(response.content)

            if not merged_clips:
                logger.warning("合并方案未能解析出片段，使用降级方案")
                return self._fallback_process(srt_text)

            # 校验recommend_reason是否所有片段相同（照抄示例的典型表现）
            if len(merged_clips) >= 2:
                reasons = [c.get('recommend_reason', '') for c in merged_clips]
                if len(set(reasons)) == 1:
                    logger.warning(f"所有片段的recommend_reason完全相同: '{reasons[0]}'，可能是照抄了示例")
                elif len(merged_clips) >= 3 and len(set(reasons)) <= 2:
                    logger.warning(f"多数片段的recommend_reason重复，仅{len(set(reasons))}种不同值")

            # 跨clip去重：确保不同clip的segments不重叠（先于gap-filling执行）
            logger.info("开始跨clip去重...")
            merged_clips = _deduplicate_clip_segments(merged_clips)
            logger.info(f"去重后保留 {len(merged_clips)} 个片段")

            # SRT时间戳验证：修正边界 + 填充间隙 + 标记内部静音
            logger.info("开始SRT时间戳验证（修正LLM边界 + 填充间隙 + 剔除静音）...")
            merged_clips = _validate_segments_with_srt(merged_clips, srt_text)
            logger.info(f"SRT验证完成")

            # 输出详细分组日志：每个话题的segments、字幕内容、归类原因
            _log_topic_details(merged_clips, srt_text)

            logger.info(f"合并方案识别到 {len(merged_clips)} 个片段")
            for clip in merged_clips:
                seg_count = len(clip.get('segments', []))
                removed_count = len(clip.get('removed_sections', []))
                logger.info(
                    f"  片段{clip.get('id')}: {clip.get('title', 'N/A')}, "
                    f"{seg_count}个时间段, "
                    f"评分: {clip.get('final_score', 0)}, "
                    f"剔除{removed_count}段无关内容"
                )

            # 转换格式以匹配下游视频生成
            clips = _merge_srt_segments(None, merged_clips)
            collections = self._generate_collections(clips)

            logger.info(f"合并方案处理完成，共 {len(clips)} 个片段")
            return clips, collections

        except Exception as e:
            logger.warning(f"合并方案LLM处理失败: {e}，使用降级方案")
            return self._fallback_process(srt_text)

    def _prepare_enhanced_text(self, srt_text: str) -> str:
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

    def _extract_srt_for_topic(self, segments: List[Dict], srt_entries: List[Dict]) -> str:
        if not segments or not srt_entries:
            return ""
        seg_start = _srt_time_to_seconds(segments[0]['start'])
        seg_end = _srt_time_to_seconds(segments[-1]['end'])
        relevant = [e for e in srt_entries if e['end'] >= seg_start and e['start'] <= seg_end]
        lines = []
        for i, entry in enumerate(relevant):
            lines.append(f"{entry['start_str']} --> {entry['end_str']}")
            lines.append(entry['text'])
            if i < len(relevant) - 1:
                lines.append("")
        return '\n'.join(lines)

    def _prepare_step2_input(self, topics: List[Dict], srt_entries: List[Dict]) -> List[Dict]:
        topics_with_srt = []
        for topic in topics:
            segments = topic.get('segments', [])
            if not segments:
                continue
            srt_text = self._extract_srt_for_topic(segments, srt_entries)
            if len(srt_text) > 2000:
                srt_lines = srt_text.split('\n')
                head_lines = srt_lines[:80]
                tail_lines = srt_lines[-30:]
                srt_text = '\n'.join(head_lines) + '\n...(中间省略)...\n' + '\n'.join(tail_lines)
                logger.info(f"话题{topic['id']} SRT过长({len(srt_lines)}条)，截取首{len(head_lines)}+尾{len(tail_lines)}条")

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

    def _prepare_step3_input(self, topics: List[Dict]) -> List[Dict]:
        srt_entries = None
        topics_data = []
        for topic in topics:
            segments = topic.get('segments', [])
            srt_text = ""
            if segments and srt_entries is None:
                srt_entries = []
            if segments:
                srt_text = "SRT文本未提取"

            topics_data.append({
                'id': topic.get('id', ''),
                'outline': topic.get('outline', ''),
                'topic_type': topic.get('topic_type', 'daily'),
                'recommend_reason': topic.get('recommend_reason', ''),
                'srt_text': srt_text
            })
        return topics_data

    def _call_step1_boundary(self, srt_text: str) -> Optional[List[Dict]]:
        try:
            response = self.llm_manager.current_provider.call(
                FUNCLIP_STEP1_BOUNDARY_PROMPT,
                "这是待分析的直播srt字幕：\n" + srt_text,
                max_tokens=4096,
                temperature=0.1
            )

            if not response or not response.content:
                return None

            debug_path = self.metadata_dir / "step1_raw_response.txt"
            with open(debug_path, 'w', encoding='utf-8') as f:
                f.write(response.content)

            return self._parse_step1_response(response.content)

        except Exception as e:
            logger.error(f"Step 1 调用异常: {e}")
            return None

    def _parse_step1_response(self, response_text: str) -> Optional[List[Dict]]:
        def _try_parse(json_str):
            try:
                data = json.loads(re.sub(r',\s*([\]}])', r'\1', json_str))
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and 'topics' in data:
                    return data['topics']
            except json.JSONDecodeError:
                pass
            return None

        result = _try_parse(response_text)
        if result is not None:
            return result

        for block in re.findall(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text):
            result = _try_parse(block)
            if result is not None:
                return result

        match = re.search(r'\[[\s\S]*"segments"[\s\S]*\]', response_text)
        if match:
            result = _try_parse(match.group())
            if result is not None:
                return result

        logger.warning(f"无法解析 Step 1 响应: {response_text[:300]}")
        return None

    def _do_step1_with_retry(self, srt_text: str, srt_entries: List[Dict],
                              checkpoint: 'PipelineCheckpoint') -> Optional[List[Dict]]:
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                enhanced_text = self._prepare_enhanced_text(srt_text)
                step1_topics = self._call_step1_boundary(enhanced_text)
                if step1_topics is not None:
                    return step1_topics
                logger.warning(f"Step 1 第{attempt+1}次调用解析失败")
                checkpoint.mark_step_failed('step1_boundary', 'JSON解析失败')
            except Exception as e:
                logger.error(f"Step 1 第{attempt+1}次调用异常: {e}")
                checkpoint.mark_step_failed('step1_boundary', str(e))
            if attempt < max_retries:
                logger.info(f"Step 1 重试 ({attempt+1}/{max_retries})...")
        return None

    def _call_step2_batch_score(self, topics_with_srt: List[Dict]) -> List[Dict]:
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
            if batch1:
                scores1 = self._do_step2_call(batch1, batch_label="批次1")
                all_scores.extend(scores1)
            if batch2:
                scores2 = self._do_step2_call(batch2, batch_label="批次2")
                all_scores.extend(scores2)
            logger.info(f"分批评分完成，共 {len(all_scores)} 个分数")
            return all_scores
        else:
            return self._do_step2_call(topics_with_srt, batch_label="单批")

    def _do_step2_call(self, topics_with_srt: List[Dict], batch_label: str = "") -> List[Dict]:
        try:
            input_json = json.dumps(topics_with_srt, ensure_ascii=False, indent=2)
            logger.info(f"Step 2 [{batch_label}] LLM调用: {len(topics_with_srt)} 个话题, "
                        f"输入长度 {len(input_json)} 字符, 预估 {_estimate_tokens(input_json)} tokens")

            response = self.llm_manager.current_provider.call(
                FUNCLIP_STEP2_BATCH_SCORE_PROMPT,
                "以下是待评分的话题数据：\n" + input_json,
                max_tokens=2048,
                temperature=0.2
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
        def _try_parse(json_str):
            try:
                data = json.loads(re.sub(r',\s*([\]}])', r'\1', json_str))
                if isinstance(data, dict) and 'scores' in data:
                    return data['scores']
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
            return None

        result = _try_parse(response_text)
        if result is not None:
            return result

        for block in re.findall(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text):
            result = _try_parse(block)
            if result is not None:
                return result

        for pattern in [r'\{[\s\S]*"scores"[\s\S]*\}', r'\[[\s\S]*"final_score"[\s\S]*\]']:
            match = re.search(pattern, response_text)
            if match:
                result = _try_parse(match.group())
                if result is not None:
                    return result

        logger.warning(f"无法解析 Step 2 响应: {response_text[:300]}")
        return []

    def _call_step3_batch_title(self, topics_data: List[Dict]) -> List[Dict]:
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

    def _parse_step3_response(self, response_text: str) -> List[Dict]:
        def _try_parse(json_str):
            try:
                data = json.loads(re.sub(r',\s*([\]}])', r'\1', json_str))
                if isinstance(data, dict) and 'titles' in data:
                    return data['titles']
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
            return None

        result = _try_parse(response_text)
        if result is not None:
            return result

        for block in re.findall(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text):
            result = _try_parse(block)
            if result is not None:
                return result

        match = re.search(r'\{[\s\S]*"titles"[\s\S]*\}', response_text)
        if match:
            result = _try_parse(match.group())
            if result is not None:
                return result

        logger.warning(f"无法解析 Step 3 响应: {response_text[:300]}")
        return []

    def _llm_process_three_step(self, srt_text: str):
        """三步流水线处理：边界识别 → 批量评分 → 批量标题（带检查点与降级）"""
        try:
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
                    logger.warning("Step 1 重试耗尽，降级到 _fallback_process")
                    checkpoint.clear()
                    return self._fallback_process(srt_text)

            if not step1_topics:
                logger.warning("Step 1 输出为空数组（LLM判断无独立话题），降级")
                checkpoint.clear()
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

            step1_topics = _validate_step1_segments(step1_topics, srt_text)
            checkpoint.save_step_output('step1_boundary', step1_topics,
                                         {'topic_count': len(step1_topics)})

            srt_entries = _parse_srt_timeline(srt_text)

            # ==========================================
            # Step 2: 批量评分（带检查点 + boundary_suggestion）
            # ==========================================
            step2_scores = checkpoint.get_step_output('step2_scores')
            if step2_scores is None:
                logger.info("Step 2 检查点未命中，开始执行...")
                step2_input = self._prepare_step2_input(step1_topics, srt_entries)
                step2_scores = self._call_step2_batch_score(step2_input)

                if step2_scores:
                    step1_topics = _apply_boundary_suggestions(
                        step1_topics, step2_scores, srt_entries
                    )
                    checkpoint.save_step_output('step2_scores', step2_scores,
                                                 {'score_count': len(step2_scores)})
                else:
                    checkpoint.mark_step_failed('step2_scores', 'Step 2 返回空')
                    logger.warning("Step 2 评分失败，将使用默认评分继续")

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

            step1_topics = _merge_titles_to_topics(step1_topics, step3_titles or [])

            # ==========================================
            # 最终后处理：排序 → Top 6 → 按时间升序
            # ==========================================
            step1_topics.sort(key=lambda t: t.get('final_score', 0), reverse=True)
            step1_topics = step1_topics[:6]
            step1_topics.sort(key=lambda t: _srt_time_to_seconds(t['segments'][0]['start']))
            for i, topic in enumerate(step1_topics):
                topic['id'] = str(i + 1)

            clips = _convert_topics_to_clips(step1_topics)
            collections = self._generate_collections(clips)

            checkpoint.clear()

            logger.info(f"三步流水线完成: {len(clips)} 个片段")
            return clips, collections

        except Exception as e:
            logger.warning(f"三步流水线处理失败: {e}，使用降级方案")
            return self._fallback_process(srt_text)

    def _parse_merged_response(self, response_text: str) -> List[Dict]:
        """解析合并方案LLM返回的数据"""
        merged_clips = []

        def _clean_trailing_commas(json_str: str) -> str:
            """移除JSON中数组/对象末尾的逗号（LLM常见错误）"""
            return re.sub(r',\s*([\]}])', r'\1', json_str)

        def _try_parse(json_str: str) -> Optional[List[Dict]]:
            """尝试解析JSON，包含尾部逗号修复"""
            if not json_str:
                return None
            try:
                data = json.loads(_clean_trailing_commas(json_str))
                if isinstance(data, list):
                    result = []
                    for i, item in enumerate(data):
                        if 'segments' in item and isinstance(item['segments'], list) and len(item['segments']) > 0:
                            item['id'] = str(item.get('id', i + 1))
                            result.append(item)
                    if result:
                        return result
            except json.JSONDecodeError:
                pass
            return None

        # 1. 直接解析（纯JSON，无多余文字）
        result = _try_parse(response_text)
        if result:
            logger.info(f"JSON解析成功，共 {len(result)} 个片段")
            return result

        # 2. 从代码块中提取（```json ... ```）
        for block in re.findall(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text):
            start = block.find('[')
            end = block.rfind(']')
            if start >= 0 and end > start:
                result = _try_parse(block[start:end + 1])
                if result:
                    logger.info(f"从代码块解析JSON成功，共 {len(result)} 个片段")
                    return result

        # 3. 从文本中直接查找JSON数组（忽略前后文字）
        start_idx = response_text.find('[')
        end_idx = response_text.rfind(']')
        if start_idx >= 0 and end_idx > start_idx:
            result = _try_parse(response_text[start_idx:end_idx + 1])
            if result:
                logger.info(f"从文本提取JSON成功，共 {len(result)} 个片段")
                return result

        # 4. 兜底：逐行找可能的JSON片段
        lines = response_text.split('\n')
        json_candidates = []
        in_block = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('```'):
                in_block = not in_block
                continue
            if in_block or stripped.startswith('{') or stripped.startswith('[') or stripped.startswith('"'):
                json_candidates.append(line)
        if json_candidates:
            candidate_text = '\n'.join(json_candidates)
            start_idx = candidate_text.find('[')
            end_idx = candidate_text.rfind(']')
            if start_idx >= 0 and end_idx > start_idx:
                result = _try_parse(candidate_text[start_idx:end_idx + 1])
                if result:
                    logger.info(f"从逐行提取解析JSON成功，共 {len(result)} 个片段")
                    return result

        logger.warning(f"无法解析合并方案响应，原始响应长度: {len(response_text)}")
        logger.warning(f"响应内容(前1000): {response_text[:1000]}")
        logger.warning(f"响应内容(最后200): {response_text[-200:]}")
        # 检查响应中是否包含JSON的关键标记
        has_bracket = '[' in response_text and ']' in response_text
        has_code_block = '```' in response_text
        has_segments = '"segments"' in response_text
        logger.warning(f"解析诊断: 方括号={has_bracket}, 代码块={has_code_block}, segments字段={has_segments}")
        return merged_clips
    
    def _parse_clips_only(self, response: str) -> List[Dict]:
        """解析第一阶段LLM返回的片段数据（不含标题）"""
        clips = []

        def _clean_trailing_commas(json_str: str) -> str:
            return re.sub(r',\s*([\]}])', r'\1', json_str)

        # 直接解析JSON
        try:
            data = json.loads(_clean_trailing_commas(response))
            if isinstance(data, list):
                clips = data
                for i, clip in enumerate(clips):
                    if 'id' not in clip or not clip['id']:
                        clip['id'] = str(i + 1)
                logger.info(f"JSON解析成功，共 {len(clips)} 个片段")
                return clips
        except json.JSONDecodeError:
            pass

        # 从代码块中提取
        for block in re.findall(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response):
            start = block.find('[')
            end = block.rfind(']')
            if start >= 0 and end > start:
                try:
                    data = json.loads(_clean_trailing_commas(block[start:end + 1]))
                    if isinstance(data, list):
                        clips = data
                        for i, clip in enumerate(clips):
                            if 'id' not in clip or not clip['id']:
                                clip['id'] = str(i + 1)
                        logger.info(f"从代码块解析JSON成功，共 {len(clips)} 个片段")
                        return clips
                except json.JSONDecodeError:
                    pass

        # 从文本中提取
        start_idx = response.find('[')
        end_idx = response.rfind(']')
        if start_idx >= 0 and end_idx > start_idx:
            try:
                data = json.loads(_clean_trailing_commas(response[start_idx:end_idx + 1]))
                if isinstance(data, list):
                    clips = data
                    for i, clip in enumerate(clips):
                        if 'id' not in clip or not clip['id']:
                            clip['id'] = str(i + 1)
                    logger.info(f"从文本提取JSON成功，共 {len(clips)} 个片段")
                    return clips
            except json.JSONDecodeError:
                pass

        clips = self._extract_clips_from_text(response)
        return clips
    
    def _extract_srt_segment(self, full_srt: str, start_time: str, end_time: str) -> str:
        """从完整SRT中提取指定时间范围内的字幕文本"""
        lines = []
        in_range = False
        
        for line in full_srt.split('\n'):
            # 匹配时间行: 00:00:00,000 --> 00:00:05,000
            time_match = re.match(
                r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})',
                line
            )
            if time_match:
                seg_start = time_match.group(1)
                seg_end = time_match.group(2)
                # 检查是否与目标时间范围有重叠
                if (self._time_to_seconds(seg_start) <= self._time_to_seconds(end_time) and
                    self._time_to_seconds(seg_end) >= self._time_to_seconds(start_time)):
                    in_range = True
                else:
                    in_range = False
            
            if in_range:
                lines.append(line)
        
        return '\n'.join(lines)
    
    @staticmethod
    def _time_to_seconds(time_str: str) -> float:
        """将SRT时间格式转换为秒数"""
        try:
            time_str = time_str.replace(',', '.')
            parts = time_str.split(':')
            h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
            return h * 3600 + m * 60 + s
        except Exception:
            return 0
    
    def _extract_clips_from_text(self, text: str):
        """从LLM响应中提取片段"""
        clips = []
        
        # 清理文本
        text = text.strip()
        
        # 尝试多种正则表达式模式
        patterns = [
            # 模式1: JSON格式中的outline字段
            r'\{\s*"outline"\s*:\s*"([^"]+)"[^}]*"start"\s*:\s*"([^"]+)"[^}]*"end"\s*:\s*"([^"]+)"[^}]*\}',
            # 模式2: Markdown格式
            r'\d+\.\s*\[(\d{2}:\d{2}:\d{2},?\d{0,3})\s*-\s*(\d{2}:\d{2}:\d{2},?\d{0,3})\]\s*([^\n]+)',
            # 模式3: 纯时间戳格式
            r'\[(\d{2}:\d{2}:\d{2},?\d{0,3})\s*-\s*(\d{2}:\d{2}:\d{2},?\d{0,3})\]\s*([^\n\[\]]+)',
        ]
        
        for i, pattern in enumerate(patterns):
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                logger.info(f"使用模式{i+1}成功匹配到 {len(matches)} 个片段")
                for j, match in enumerate(matches[:6]):  # 最多6个片段
                    if len(match) >= 3:
                        start_time, end_time, content = match[0], match[1], match[2]
                        clip = {
                            'id': str(j + 1),
                            'outline': content.strip(),
                            'start': start_time,
                            'end': end_time,
                            'content': [content.strip()],
                            'final_score': 0.7 + (j * 0.05),
                            'recommend_reason': '精彩片段',
                            'generated_title': f'精彩片段{str(j+1)}'
                        }
                        clips.append(clip)
                break
        
        return clips
    
    def _generate_collections(self, clips):
        """基于clips生成简单的合集"""
        if not clips:
            return []
        
        collections = [{
            'id': '1',
            'collection_title': '全部内容',
            'collection_summary': f'包含{len(clips)}个片段',
            'clip_ids': [clip['id'] for clip in clips]
        }]
                
        return collections
    
    def _fallback_process(self, srt_text: str):
        """降级方案，无LLM时使用简单处理"""
        logger.info("使用降级方案：按时间分段")
        clips = []
        
        # 解析SRT获取实际时长
        srt_entries = self._parse_srt_simple(srt_text)
        if srt_entries:
            # 根据实际内容分段
            total_duration = srt_entries[-1].get('end_seconds', 1200) if srt_entries else 1200
            interval = min(total_duration / 4, 300)  # 最多5分钟一段
        else:
            interval = 300
        
        time_intervals = []
        current_time = 0
        while current_time < (srt_entries[-1].get('end_seconds', 1200) if srt_entries else 1200):
            end_time = min(current_time + interval, 
                         (srt_entries[-1].get('end_seconds', 1200) if srt_entries else 1200))
            time_intervals.append((
                self._seconds_to_srt_time(current_time),
                self._seconds_to_srt_time(end_time)
            ))
            current_time = end_time
            if len(time_intervals) >= 4:
                break
        
        for i, (start, end) in enumerate(time_intervals):
            clips.append({
                'id': str(i + 1),
                'outline': f'片段{i+1}',
                'start': start,
                'end': end,
                'final_score': 0.5,
                'recommend_reason': '自动分段',
                'generated_title': f'精彩片段{i+1}'
            })
        
        collections = [{
            'id': '1',
            'collection_title': '自动合集',
            'collection_summary': '全部内容',
            'clip_ids': [clip['id'] for clip in clips]
        }]
            
        return clips, collections
    
    def _parse_srt_simple(self, srt_text: str) -> List[Dict]:
        """解析SRT文本获取时间信息"""
        entries = []
        pattern = r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})'
        matches = re.findall(pattern, srt_text)
        
        for match in matches:
            start_seconds = int(match[0])*3600 + int(match[1])*60 + int(match[2]) + int(match[3])/1000
            end_seconds = int(match[4])*3600 + int(match[5])*60 + int(match[6]) + int(match[7])/1000
            entries.append({
                'start_seconds': start_seconds,
                'end_seconds': end_seconds
            })
        
        return entries
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """将秒数转换为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def _save_results(self, clips: List[Dict], collections: List[Dict]):
        """保存处理结果"""
        try:
            clips_path = self.metadata_dir / "funclip_clips.json"
            with open(clips_path, 'w', encoding='utf-8') as f:
                json.dump(clips, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存 {len(clips)} 个切片到 {clips_path}")
            
            collections_path = self.metadata_dir / "funclip_collections.json"
            with open(collections_path, 'w', encoding='utf-8') as f:
                json.dump(collections, f, ensure_ascii=False, indent=2)
            logger.info(f"已保存 {len(collections)} 个合集到 {collections_path}")
        except Exception as e:
            logger.warning(f"保存结果失败: {e}")


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
            f"[0:a]atrim=start={start_sec}:end={end_sec},asetpts=PTS-STARTPTS[a{label_idx}];"
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
        # 视频编码耗时无法预估，不使用固定 timeout（避免 subprocess 因
        # timeout 被错误计算为负数而立即超时）。
        # timeout=None 表示无限等待，ffmpeg 完成后自然返回。
        result = subprocess.run(cmd, capture_output=True,
                                encoding='utf-8', errors='ignore', timeout=None)
        if result.returncode == 0:
            logger.info(f"多段拼接成功: {label_idx}段 -> {output_path}")
            return True
        else:
            logger.error(f"多段拼接失败: {result.stderr}")
            return False
    except subprocess.TimeoutExpired as e:
        logger.error(f"多段提取超时: {e} (timeout={e.timeout})")
        return False
    except Exception as e:
        logger.error(f"多段提取异常: {e}")
        return False


def run_funclip_pipeline(srt_path: Path,
                         video_path: Path,
                         metadata_dir: Path,
                         clips_output_dir: Path,
                         collections_output_dir: Path,
                         processing_mode: str = "two_stage"):
    """运行FunClip风格的完整流水线

    Args:
        srt_path: SRT字幕文件路径
        video_path: 输入视频路径
        metadata_dir: 元数据目录
        clips_output_dir: 切片输出目录
        collections_output_dir: 合集输出目录
        processing_mode: 处理模式
            - "two_stage": 两阶段方案（默认）
            - "merged": 合并方案（单次LLM调用）
    """
    processor = FunClipStyleProcessor(metadata_dir)
    clips, collections = processor.process(srt_path, processing_mode)

    logger.info("=" * 60)
    logger.info(f"处理完成，共生成 {len(clips)} 个切片 [模式: {processing_mode}]")
    for i, clip in enumerate(clips):
        has_multi = " [多段]" if clip.get('_segments') and len(clip['_segments']) > 1 else ""
        logger.info(f"  切片{clip.get('id', i+1)}: {clip.get('generated_title', 'N/A')}{has_multi}")
        logger.info(f"    时间: {clip.get('start_time', 'N/A')} -> {clip.get('end_time', 'N/A')}")
        logger.info(f"    评分: {clip.get('final_score', 0)}")
    logger.info("=" * 60)

    # 复用 FunASR 的 fsmn-vad 结果检测静音（无需独立运行 Silero VAD）
    vad_silence_all = []
    try:
        if srt_path and srt_path.exists():
            vad_path = Path(str(srt_path).replace('.srt', '.vad.json'))
            if vad_path.exists():
                import json
                speech_segs = json.load(open(vad_path, encoding='utf-8'))
                logger.info(f"复用 FunASR VAD 数据: {len(speech_segs)} 段语音")
                duration = speech_segs[-1]['end'] if speech_segs else 0.0
                prev_end = 0.0
                for seg in speech_segs:
                    if seg['start'] - prev_end >= 2.0:
                        vad_silence_all.append((prev_end, seg['start']))
                    prev_end = seg['end']
                if duration - prev_end >= 2.0:
                    vad_silence_all.append((prev_end, duration))
                logger.info(f"从 VAD 数据推导出 {len(vad_silence_all)} 段静音(>=2s)")

                if vad_silence_all:
                    vad_count = 0
                    for clip in clips:
                        segments = clip.get('_segments', [])
                        if not segments:
                            continue
                        clip_vad = _filter_vad_silence_by_segments(
                            vad_silence_all, segments
                        )
                        if clip_vad:
                            existing = clip.setdefault('_removed_sections', [])
                            existing.extend(clip_vad)
                            vad_count += len(clip_vad)
                    logger.info(f"VAD静音检测完成: 共添加 {vad_count} 段音频级静音到各片段")
            else:
                logger.info("VAD 数据文件不存在，跳过音频级静音检测")
    except Exception as e:
        logger.warning(f"VAD静音检测跳过: {e}")

    # 转换格式以匹配 video_generator 的期望
    clips_for_video = []
    for clip in clips:
        # 兼容两种字段名：merged模式用start_time/end_time，two_stage模式用start/end
        start_time = clip.get('start_time') or clip.get('start') or '00:00:00,000'
        end_time = clip.get('end_time') or clip.get('end') or '00:05:00,000'
        video_clip = {
            'id': clip.get('id', ''),
            'outline': clip.get('outline', ''),
            'generated_title': clip.get('generated_title', f"片段_{clip.get('id', '')}"),
            'start_time': start_time,
            'end_time': end_time,
            'final_score': clip.get('final_score', 0.5),
            'recommend_reason': clip.get('recommend_reason', ''),
            'content': clip.get('content', [])
        }
        # 合并模式：使用LLM返回的多段segments
        if clip.get('_segments'):
            video_clip['_segments'] = clip['_segments']
        # 两阶段模式：用start_time/end_time构造单段segments
        elif start_time != '00:00:00,000' or end_time != '00:05:00,000':
            video_clip['_segments'] = [{'start': start_time, 'end': end_time}]
        if clip.get('_removed_sections'):
            video_clip['_removed_sections'] = clip['_removed_sections']
        clips_for_video.append(video_clip)

    from backend.utils.video_processor import VideoProcessor as VP
    # 视频生成
    video_generator = VideoGenerator(
        clips_dir=clips_output_dir,
        collections_dir=collections_output_dir,
        metadata_dir=metadata_dir
    )

    # 处理多段不连续切片
    temp_dir = metadata_dir / "temp_segments"
    successful_clips = []
    processed_clips_data = []

    for video_clip in clips_for_video:
        segments = video_clip.get('_segments', None)
        removed = video_clip.get('_removed_sections', [])
        clip_id = video_clip['id']
        title = video_clip.get('generated_title', f"片段_{clip_id}")

        safe_title = VP.sanitize_filename(title)
        output_path = clips_output_dir / f"{clip_id}_{safe_title}.mp4"

        # 计算有效段（跳过removed_sections中的静音/无关内容）
        effective_segments = _compute_effective_segments(segments, removed) if (segments and removed) else segments

        # 防御：segments为空时跳过该切片（LLM可能返回None）
        if not effective_segments:
            logger.warning(f"切片 {video_clip['id']} 无有效段（_segments为空），跳过")
            continue

        if len(effective_segments) > 1:
            # 多段不连续：提取每段再拼接
            logger.info(f"多段切片 {clip_id}: {len(effective_segments)} 个有效时间段，正在提取拼接...")
            success = _extract_multi_segment_clip(
                video_path, output_path, effective_segments, temp_dir
            )
            if success:
                successful_clips.append(output_path)
                # 计算实际总时长（各段时长之和，不含间隙）
                total_duration = sum(
                    _srt_time_to_seconds(s['end']) - _srt_time_to_seconds(s['start'])
                    for s in effective_segments
                )
                start_sec = _srt_time_to_seconds(effective_segments[0]['start'])
                actual_end_sec = start_sec + total_duration
                processed_clips_data.append({
                    'id': clip_id,
                    'title': title,
                    'start_time': _seconds_to_srt_time(start_sec),
                    'end_time': _seconds_to_srt_time(actual_end_sec),
                    'output_path': str(output_path),
                    'keyframe_aligned': False,
                    'multi_segment': True,
                    'segment_count': len(effective_segments)
                })
                logger.info(f"  多段切片 {clip_id} 提取成功 ({len(effective_segments)}段合并)")
            else:
                logger.error(f"  多段切片 {clip_id} 提取失败")
        else:
            # 单段：使用原有方式
            logger.info(f"单段切片 {clip_id}: 常规切割...")
            start_time = effective_segments[0].get('start', video_clip.get('start_time', '00:00:00,000'))
            end_time = effective_segments[0].get('end', video_clip.get('end_time', '00:05:00,000'))

            if VP.extract_clip(video_path, output_path, start_time, end_time):
                successful_clips.append(output_path)
                processed_clips_data.append({
                    'id': clip_id,
                    'title': title,
                    'start_time': start_time,
                    'end_time': end_time,
                    'output_path': str(output_path),
                    'keyframe_aligned': False,
                    'multi_segment': False
                })
                logger.info(f"  单段切片 {clip_id} 提取成功")
            else:
                logger.error(f"  单段切片 {clip_id} 提取失败")

    # 生成合集
    successful_collections = video_generator.generate_collections(collections)

    # 更新元数据
    for clip in clips_for_video:
        for processed in processed_clips_data:
            if processed['id'] == clip['id']:
                clip['start_time'] = processed.get('start_time', clip['start_time'])
                clip['end_time'] = processed.get('end_time', clip['end_time'])
                break

    # 保存元数据
    video_generator.save_clip_metadata(clips_for_video, metadata_dir / "clips_metadata.json")
    video_generator.save_collection_metadata(collections, metadata_dir / "collections_metadata.json")

    # 同时保存到项目根目录
    project_dir = metadata_dir.parent
    try:
        video_generator.save_clip_metadata(clips_for_video, project_dir / "clips_metadata.json")
        video_generator.save_collection_metadata(collections, project_dir / "collections_metadata.json")
        logger.info(f"元数据已保存到项目根目录: {project_dir}")
    except Exception as e:
        logger.warning(f"保存备用元数据失败: {e}")

    logger.info(f"FunClip方案处理完成 [模式: {processing_mode}]")
    logger.info(f"  成功: {len(successful_clips)}/{len(clips_for_video)} 个切片")
    logger.info(f"  合集: {len(successful_collections)} 个")

    return clips, collections
