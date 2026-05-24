"""
基于FunClip风格的单步LLM处理方案
"""
import logging
import re
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
单个segment时长建议10秒~5分钟。低于10秒的短片段，如果语义上可自然合并到相邻主话题则合并，否则保留独立（高评分短金句不应被强制合并）。

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
| title | 完整概括话题从引入到收尾全流程的标题 |
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
8. 自动过滤低俗敏感违规内容，含违规内容的片段降低评分优先级
9. 最多6个独立话题片段，最少输出2个（字幕只有单个话题时最少1个）
10. 仅输出JSON数组，禁止增加多余文字、注释或说明内容
11. **产品推销内容必须独立输出**：卖货话术、产品功能介绍、优惠活动讲解等与知识分享/闲聊段子属于不同话题类型，即使紧挨着知识话题也要单独成段输出，不可合并到其他话题中"""

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


# Silero VAD 模型（懒加载）
_silero_vad_model = None

def _get_silero_vad_model():
    global _silero_vad_model
    if _silero_vad_model is None:
        try:
            from silero_vad import load_silero_vad
            _silero_vad_model = load_silero_vad()
            logger.info("Silero VAD 模型加载成功")
        except Exception as e:
            logger.error(f"Silero VAD 模型加载失败: {e}")
            return None
    return _silero_vad_model


def _detect_vad_silence_in_audio(audio_path: str, 
                                  min_silence_duration: float = 2.0,
                                  vad_threshold: float = 0.5) -> List[tuple]:
    """
    使用 Silero VAD 检测整段音频中的静音区间

    Args:
        audio_path: 音频文件路径（支持 wav/mp3 等格式）
        min_silence_duration: 最短静音时长（秒）
        vad_threshold: VAD 语音概率阈值

    Returns:
        静音区间列表 [(start_sec, end_sec), ...]
    """
    model = _get_silero_vad_model()
    if model is None:
        return []

    try:
        import soundfile as sf
        import numpy as np
        import torch
        from silero_vad import get_speech_timestamps

        y, orig_sr = sf.read(audio_path)

        if len(y.shape) > 1:
            y = np.mean(y, axis=1)

        if orig_sr != 16000:
            import librosa
            y = librosa.resample(y, orig_sr=orig_sr, target_sr=16000)
            sr = 16000
        else:
            sr = orig_sr

        duration = len(y) / sr
        logger.info(f"VAD加载音频完成: {duration:.1f}s @ {sr}Hz, {audio_path}")

        waveform = torch.from_numpy(y).float()
        speech_segs = get_speech_timestamps(
            waveform, model,
            threshold=vad_threshold,
            min_speech_duration_ms=250,
            min_silence_duration_ms=int(min_silence_duration * 1000),
            return_seconds=True
        )
        logger.info(f"VAD检测到 {len(speech_segs)} 段语音")

        silence_list = []
        prev_end = 0.0
        for seg in speech_segs:
            start = seg['start']
            if start - prev_end >= min_silence_duration:
                silence_list.append((prev_end, start))
            prev_end = seg['end']
        if duration - prev_end >= min_silence_duration:
            silence_list.append((prev_end, duration))

        logger.info(f"VAD检测到 {len(silence_list)} 段静音(>= {min_silence_duration}s)")
        return silence_list

    except Exception as e:
        logger.error(f"VAD音频静音检测异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []


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

    # Silero VAD 音频级静音检测（检测SRT条目内部的长停顿）
    vad_silence_all = []
    try:
        if video_path and video_path.exists():
            import librosa, tempfile, os, soundfile as sf
            logger.info(f"VAD: 从视频提取音频分析静音...")
            y, sr = librosa.load(str(video_path), sr=16000, mono=True)
            logger.info(f"VAD: 音频提取完成 ({len(y)/sr:.1f}s)")
            tmp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            tmp_wav_path = tmp_wav.name
            tmp_wav.close()
            sf.write(tmp_wav_path, y, sr)
            vad_silence_all = _detect_vad_silence_in_audio(tmp_wav_path)
            os.unlink(tmp_wav_path)

            if vad_silence_all:
                # 为每个clip筛选其segment范围内的静音
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
