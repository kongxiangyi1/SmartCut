# AutoClip 优化方案 - 第一阶段实施计划

## 📋 概述

本方案基于对 FunClip 的分析，提供了具体的可执行优化计划，重点解决"地域文化性格分析"这类话题切片不完整的问题。

**目标**: 确保话题从"京油子、卫嘴子、保定府的狗腿子"这类标志性开头开始，内容完整。

---

## 🎯 问题分析

### 核心问题
1. LLM 定位时间时，没有识别到标志性开头
2. 热词信息没有充分利用
3. 话题完整性缺乏验证机制

### 根本原因
| 问题 | 说明 |
|------|------|
| 提示词不够明确 | 没有强调"从标志性开头开始"的重要性 |
| 热词体系缺失 | 没有从视频内容中提取标志性词汇 |
| 缺乏完整性验证 | 切完后没有检查话题是否包含完整开头 |

---

## 📅 第一阶段实施计划

### 阶段目标
1. ✅ **已完成**: 优化提示词（Step 2）
2. ✅ **已完成**: 优化边界扩展（Step 6）
3. 🔄 **进行中**: 实现热词提取工具
4. 🔄 **进行中**: 优化 Step 1 大纲提取
5. 🔄 **进行中**: 优化 Step 4 标题生成

---

## 🏗️ 第一阶段 - 核心模块实现

### 1. 热词提取工具 (`backend/utils/hotword_extractor.py`)

**目标**: 从视频内容中自动提取标志性词汇和高频词。

```python
"""
热词提取工具 - 借鉴 FunClip 的热词定制化思想
"""
import re
import logging
from typing import List, Dict, Any, Optional
from collections import Counter
from pathlib import Path

logger = logging.getLogger(__name__)

# 常见标志性开头模式
SIGNATURE_PATTERNS = [
    '京油子', '卫嘴子', '保定府的狗腿子',
    '俗话说', '话说', '你知道', '你看', '我跟你说',
    '你知道吗', '你想啊', '你看啊', '我告诉你',
    '有句话说', '有这么句话', '你听说过吗',
    '我们都知道', '大家都知道', '众所周知',
    '今天讲', '今天说', '今天聊',
    '今天给大家讲', '今天给大家说', '今天给大家聊',
    '我们来聊', '我们来说', '我们来讲',
]

# 停用词（不应该被提取为热词）
STOPWORDS = {
    '的', '是', '在', '了', '和', '与', '或', 
    '以及', '等', '之', '于', '这', '那', 
    '有', '我', '你', '他', '我们', '你们', '他们',
    '这个', '那个', '就是', '还是', '也是',
    '所以', '因为', '但是', '而且', '然后',
}

class HotwordExtractor:
    """热词提取器"""
    
    def __init__(self, min_freq: int = 2, min_word_len: int = 2):
        self.min_freq = min_freq
        self.min_word_len = min_word_len
    
    def extract_from_srt(
        self, 
        srt_data: List[Dict], 
        top_k: int = 20
    ) -> List[Dict]:
        """
        从 SRT 数据中提取热词
        
        Args:
            srt_data: SRT 解析结果
            top_k: 返回前 K 个热词
            
        Returns:
            [
                {
                    'word': '京油子',
                    'frequency': 5,
                    'is_signature': True,
                    'positions': [...]
                },
                ...
            ]
        """
        logger.info(f"从 SRT 数据中提取热词，共 {len(srt_data)} 条字幕")
        
        # 1. 收集所有文本
        all_text = " ".join([
            item.get('text', '') 
            for item in srt_data
        ])
        
        # 2. 提取候选词
        candidate_words = self._extract_candidate_words(all_text)
        
        # 3. 统计词频
        word_counter = Counter(candidate_words)
        
        # 4. 过滤和排序
        hotwords = []
        for word, freq in word_counter.most_common(top_k * 2):
            if freq >= self.min_freq:
                hotword_info = {
                    'word': word,
                    'frequency': freq,
                    'is_signature': word in SIGNATURE_PATTERNS,
                    'positions': self._find_word_positions(word, srt_data)
                }
                hotwords.append(hotword_info)
        
        # 5. 排序：标志性开头优先，然后按词频
        hotwords.sort(
            key=lambda x: (not x['is_signature'], -x['frequency'])
        )
        
        hotwords = hotwords[:top_k]
        logger.info(f"提取到 {len(hotwords)} 个热词: {[w['word'] for w in hotwords]}")
        return hotwords
    
    def _extract_candidate_words(self, text: str) -> List[str]:
        """
        从文本中提取候选词（简单的中文分词）
        
        TODO: 可以集成 Jieba 等分词库提升准确率
        """
        words = []
        
        # 1. 先检查是否有已知的标志性词
        for pattern in SIGNATURE_PATTERNS:
            if pattern in text:
                words.append(pattern)
        
        # 2. 按标点和空格分割
        separators = r'[，。！？；：、\s\n]'
        segments = re.split(separators, text)
        
        # 3. 提取 N-gram
        for segment in segments:
            if len(segment) >= 2:
                # 添加完整片段
                if segment not in STOPWORDS:
                    words.append(segment)
                
                # 添加 2-gram
                if len(segment) >= 4:
                    for i in range(len(segment) - 1):
                        bigram = segment[i:i+2]
                        if bigram not in STOPWORDS:
                            words.append(bigram)
        
        return words
    
    def _find_word_positions(
        self, 
        word: str, 
        srt_data: List[Dict]
    ) -> List[Dict]:
        """查找词在 SRT 中的位置"""
        positions = []
        
        for item in srt_data:
            text = item.get('text', '')
            if word in text:
                positions.append({
                    'start_time': item.get('start_time'),
                    'end_time': item.get('end_time'),
                    'text': text
                })
        
        return positions
    
    def get_signature_openings(
        self, 
        hotwords: List[Dict]
    ) -> List[str]:
        """获取标志性开头词列表"""
        return [
            w['word'] 
            for w in hotwords 
            if w['is_signature']
        ]
```

---

### 2. 增强 Step 1 大纲提取 (`backend/pipeline/step1_outline.py`)

**目标**: 引入热词概念，帮助 LLM 更好地识别话题边界。

```python
# 在 step1_outline.py 中添加

class OutlineExtractor:
    # ... 现有代码 ...
    
    def __init__(self, metadata_dir: Path = None, prompt_files: Dict = None):
        # ... 现有初始化代码 ...
        
        # 新增：热词提取器
        self.hotword_extractor = HotwordExtractor()
        self.hotwords = []
    
    def extract_outline(self, srt_path: Path) -> List[Dict]:
        """
        从 SRT 文件提取视频大纲 - 增强版
        
        新增功能：
        - 热词提取
        - 热词增强的提示词
        """
        logger.info("开始提取视频大纲（增强版）")
        
        # 1. 解析 SRT 文件
        try:
            srt_data = self.text_processor.parse_srt(srt_path)
            if not srt_data:
                logger.warning("SRT 文件为空或解析失败")
                return []
        except Exception as e:
            logger.error(f"解析 SRT 文件失败: {e}")
            return []
        
        # 【新增】2. 提取热词
        self.hotwords = self.hotword_extractor.extract_from_srt(srt_data)
        
        # 【新增】3. 保存热词到中间文件
        self._save_hotwords(self.hotwords)
        
        # 4. 基于时间智能分块
        chunks = self.text_processor.chunk_srt_data(srt_data, interval_minutes=30)
        
        # 5. 保存文本块和 SRT 块
        chunk_files = self._save_chunks_to_files(chunks)
        self._save_srt_chunks(chunks)
        
        # 6. 处理每个文本块
        all_outlines = []
        
        for i, chunk_file in enumerate(chunk_files):
            logger.info(f"处理第 {i+1}/{len(chunks)} 个文本块: {chunk_file.name}")
            try:
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    chunk_text = f.read()
                
                if not self.llm_manager.current_provider:
                    logger.warning("没有可用的 LLM 提供商")
                    break
                
                # 【新增】获取当前块的相关热词
                chunk_hotwords = self._get_chunk_hotwords(i, self.hotwords, chunks)
                
                # 【新增】增强提示词
                enhanced_prompt = self._enhance_prompt_with_hotwords(
                    self.outline_prompt,
                    chunk_hotwords
                )
                
                input_data = {"text": chunk_text}
                try:
                    response = self.llm_manager.current_provider.call(
                        enhanced_prompt, 
                        input_data
                    )
                    llm_content = response.content if response else None
                except Exception as llm_error:
                    logger.warning(f"LLM 调用失败: {llm_error}")
                    llm_content = None
                
                if llm_content:
                    parsed_outlines = self._parse_outline_response(
                        llm_content, 
                        i,
                        chunk_hotwords  # 【新增】传递热词
                    )
                    all_outlines.extend(parsed_outlines)
                else:
                    logger.warning(f"第 {i+1} 个文本块返回空响应")
            except Exception as e:
                logger.error(f"处理第 {i+1} 个文本块失败: {e}")
                continue
        
        # 7. 合并和去重
        final_outlines = self._merge_outlines(all_outlines)
        logger.info(f"大纲提取完成，共 {len(final_outlines)} 个话题")
        
        return final_outlines
    
    def _save_hotwords(self, hotwords: List[Dict]):
        """保存热词到元数据目录"""
        hotwords_file = self.metadata_dir / "step1_hotwords.json"
        with open(hotwords_file, 'w', encoding='utf-8') as f:
            json.dump(hotwords, f, ensure_ascii=False, indent=2)
        logger.info(f"热词已保存到: {hotwords_file}")
    
    def _get_chunk_hotwords(
        self, 
        chunk_index: int, 
        hotwords: List[Dict], 
        chunks: List[Dict]
    ) -> List[str]:
        """获取当前块的相关热词"""
        if not hotwords or not chunks:
            return []
        
        chunk = chunks[chunk_index]
        chunk_start = self.text_processor.time_to_seconds(
            chunk.get('start_time', '00:00:00,000')
        )
        chunk_end = self.text_processor.time_to_seconds(
            chunk.get('end_time', '01:00:00,000')
        )
        
        chunk_hotwords = []
        for hotword in hotwords:
            for pos in hotword.get('positions', []):
                pos_time = self.text_processor.time_to_seconds(
                    pos.get('start_time', '00:00:00,000')
                )
                if chunk_start <= pos_time <= chunk_end:
                    chunk_hotwords.append(hotword['word'])
                    break
        
        return list(set(chunk_hotwords))
    
    def _enhance_prompt_with_hotwords(
        self, 
        prompt: str, 
        hotwords: List[str]
    ) -> str:
        """用热词增强提示词"""
        if not hotwords:
            return prompt
        
        signature_words = [w for w in hotwords if w in SIGNATURE_PATTERNS]
        
        enhancement = f"""

【重要提示】
以下是本视频中出现的重要关键词，它们很可能是话题的标志性开头：

标志性开头词：
{', '.join(signature_words) if signature_words else '无'}

其他热词：
{', '.join([w for w in hotwords if w not in signature_words])}

请特别注意：
1. 如果某个话题以标志性开头词开始，请确保将其作为独立话题的起点
2. 话题标题应该尽量包含这些标志性词汇
3. 不要把完整的话题切分成多个部分
"""
        
        return prompt + enhancement
    
    def _parse_outline_response(
        self, 
        response: str, 
        chunk_index: int,
        hotwords: List[str] = None  # 【新增】
    ) -> List[Dict]:
        """解析大纲响应 - 增强版"""
        outlines = []
        lines = response.split('\n')
        current_outline = None
        
        for line in lines:
            line = line.strip()
            
            if re.match(r'^\d+\.\s*\*\*', line):
                if current_outline:
                    outlines.append(current_outline)
                
                topic_name = line.split('**')[1] if '**' in line else line.split('.', 1)[1].strip()
                
                # 【新增】检查标题是否包含热词，如果没有尝试优化
                topic_name = self._optimize_topic_title(topic_name, hotwords)
                
                current_outline = {
                    'title': topic_name,
                    'subtopics': [],
                    'chunk_index': chunk_index,
                    'has_signature': any(w in topic_name for w in SIGNATURE_PATTERNS) if hotwords else False
                }
            
            elif line.startswith('-') and current_outline:
                subtopic = line[1:].strip()
                current_outline['subtopics'].append(subtopic)
        
        if current_outline:
            outlines.append(current_outline)
        
        return outlines
    
    def _optimize_topic_title(self, title: str, hotwords: List[str]) -> str:
        """
        优化话题标题 - 如果标题中没有热词，考虑重命名
        
        例如：
        "地域文化分析" -> "京油子、卫嘴子：地域文化分析"
        """
        if not hotwords:
            return title
        
        for hotword in hotwords:
            if hotword in title:
                return title
        
        # 标题中没有热词，看看是否应该添加标志性开头
        for signature in SIGNATURE_PATTERNS:
            if signature in hotwords:
                return f"{signature}：{title}"
        
        return title
```

---

### 3. 增强 Step 2 时间线提取 (`backend/pipeline/step2_timeline.py`)

**目标**: 利用热词信息，确保时间从标志性开头开始定位。

```python
# 在 step2_timeline.py 中添加

class TimelineExtractor:
    # ... 现有代码 ...
    
    def __init__(self, metadata_dir: Path = None, prompt_files: Dict = None):
        # ... 现有初始化代码 ...
        
        # 新增：加载热词
        self.hotwords = self._load_hotwords(metadata_dir)
    
    def _load_hotwords(self, metadata_dir: Path) -> List[str]:
        """从元数据目录加载热词"""
        hotwords_file = metadata_dir / "step1_hotwords.json"
        if hotwords_file.exists():
            try:
                with open(hotwords_file, 'r', encoding='utf-8') as f:
                    hotword_data = json.load(f)
                    return [w['word'] for w in hotword_data]
            except Exception as e:
                logger.warning(f"加载热词失败: {e}")
        return []
    
    def _enhance_timeline_prompt(self, prompt: str, chunk_index: int) -> str:
        """增强时间线定位提示词 - 添加热词信息"""
        if not self.hotwords:
            return prompt
        
        enhancement = f"""

【话题定位参考】
以下是本视频中的重要热词，请注意它们出现的时间：
{', '.join(self.hotwords[:10])}

【重要规则】
1. 话题的开始时间必须从包含标志性词汇的那句话开始
2. 即使这意味着话题会跨越之前设定的块边界
3. 如果不确定边界，宁可往前多包含一些内容
"""
        
        return prompt + enhancement
    
    # 修改 extract_timeline 方法，使用增强的提示词
    def extract_timeline(self, outlines: List[Dict]) -> List[Dict]:
        # ... 现有代码 ...
        
        # 修改第 3 步，使用增强的提示词
        for chunk_index, chunk_outlines in outlines_by_chunk.items():
            logger.info(f"处理块 {chunk_index}")
            
            # ... 现有代码 ...
            
            if llm_cache_path.exists():
                # ... 缓存处理 ...
            else:
                # ... 构建 SRT 文本 ...
                
                # 【新增】增强提示词
                enhanced_prompt = self._enhance_timeline_prompt(
                    self.timeline_prompt, 
                    chunk_index
                )
                
                input_data = {
                    "outline": llm_input_outlines,
                    "srt_text": srt_text_for_prompt
                }
                
                # ... 调用 LLM ...
```

---

### 4. 优化 Step 4 标题生成 (`backend/pipeline/step4_title.py`)

**目标**: 标题中保留标志性开头，提高识别度。

```python
"""
Step 4: 标题生成 - 优化版
"""
import logging
from typing import List, Dict, Any
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# 标志性开头模式
SIGNATURE_PATTERNS = [
    '京油子', '卫嘴子', '保定府的狗腿子',
    '俗话说', '话说', '你知道', '你看', '我跟你说',
    '你知道吗', '你想啊', '你看啊', '我告诉你',
    '有句话说', '有这么句话', '你听说过吗',
]

def _load_hotwords(metadata_dir: Path) -> List[str]:
    """加载热词"""
    hotwords_file = metadata_dir / "step1_hotwords.json"
    if hotwords_file.exists():
        try:
            with open(hotwords_file, 'r', encoding='utf-8') as f:
                hotword_data = json.load(f)
                return [w['word'] for w in hotword_data]
        except Exception as e:
            logger.warning(f"加载热词失败: {e}")
    return []

def _find_signature_in_content(content: str) -> str:
    """在内容中查找标志性开头"""
    for pattern in SIGNATURE_PATTERNS:
        if pattern in content:
            idx = content.find(pattern)
            if idx >= 0:
                # 找到从标志性开头到第一个句号的内容
                end_idx = content.find('。', idx)
                if end_idx > idx:
                    return content[idx:end_idx+1]
    return ""

def _optimize_title_with_signature(title: str, clip: Dict, hotwords: List[str]) -> str:
    """
    优化标题 - 保留标志性开头
    
    示例：
    "地域文化分析" -> "京油子、卫嘴子：地域文化分析"
    """
    content = clip.get('content', '')
    
    # 1. 查找标志性开头
    signature = _find_signature_in_content(content)
    if signature:
        # 如果标题中没有包含标志性开头，添加到前面
        if signature not in title:
            return f"{signature}：{title}"
    
    # 2. 如果没有标志性开头，检查是否有热词
    if hotwords:
        for hotword in hotwords:
            if hotword in content and hotword not in title:
                # 标题中没有热词，但内容中有，添加到前面
                return f"{hotword}：{title}"
    
    return title

async def run_step4_title(
    project_id: str,
    metadata_dir: Path,
    clips: List[Dict[str, Any]],
    llm_client=None
) -> List[Dict[str, Any]]:
    """
    为每个片段生成标题 - 优化版
    
    新增功能：
    - 加载热词
    - 标志性开头识别
    - 热词前置
    """
    logger.info(f"Step 4: 为 {len(clips)} 个片段生成标题（优化版）")
    
    # 【新增】加载热词
    hotwords = _load_hotwords(metadata_dir)
    if hotwords:
        logger.info(f"加载到 {len(hotwords)} 个热词: {hotwords[:10]}")
    
    for clip in clips:
        # 优先使用 outline 作为标题
        title = ""
        outline = clip.get('outline', '')
        
        if isinstance(outline, dict):
            title = outline.get('title', '') or outline.get('content', '')
        elif isinstance(outline, str) and outline:
            title = outline
        
        # 如果没有 outline，使用 content
        if not title:
            content = clip.get('content', '')
            if content:
                title = content[:50] + "..." if len(content) > 50 else content
            else:
                clip_id = clip.get('id', 0)
                title = f"精彩片段{int(clip_id)+1}"
        
        # 【新增】优化标题 - 保留标志性开头
        optimized_title = _optimize_title_with_signature(title, clip, hotwords)
        clip['title'] = optimized_title
        
        # 确保 content 字段始终存在
        if "content" not in clip:
            clip["content"] = optimized_title
    
    # 保存结果
    output_file = metadata_dir / "step4_titles.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(clips, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Step 4 完成: 标题已保存到 {output_file}")
    return clips
```

---

## 🧪 测试方案

### 1. 单元测试

**测试文件**: `tests/test_hotword_extractor.py`

```python
import pytest
from backend.utils.hotword_extractor import HotwordExtractor, SIGNATURE_PATTERNS

def test_extract_signature_words():
    """测试标志性开头提取"""
    extractor = HotwordExtractor()
    
    # 模拟 SRT 数据
    srt_data = [
        {
            'text': '京油子、卫嘴子、保定府的狗腿子，这是一句老话',
            'start_time': '00:00:05,000',
            'end_time': '00:00:10,000'
        },
        {
            'text': '我们今天就来聊聊这个话题',
            'start_time': '00:00:10,000',
            'end_time': '00:00:15,000'
        }
    ]
    
    hotwords = extractor.extract_from_srt(srt_data, top_k=10)
    
    # 检查是否提取到了标志性词
    signature_words = [w for w in hotwords if w['is_signature']]
    assert len(signature_words) > 0
    assert '京油子' in [w['word'] for w in signature_words]

def test_title_optimization():
    """测试标题优化"""
    from backend.pipeline.step4_title import _optimize_title_with_signature
    
    clip = {
        'content': '京油子、卫嘴子、保定府的狗腿子，这是一句老话。我们今天来聊聊地域文化。',
        'outline': '地域文化分析'
    }
    
    hotwords = ['京油子', '卫嘴子', '保定府的狗腿子']
    
    optimized_title = _optimize_title_with_signature(
        '地域文化分析', 
        clip, 
        hotwords
    )
    
    assert '京油子' in optimized_title
```

---

## 📊 实施步骤

### 第 1 步：创建热词提取工具
- [ ] 创建 `backend/utils/hotword_extractor.py`
- [ ] 实现热词提取逻辑
- [ ] 编写单元测试

### 第 2 步：增强 Step 1
- [ ] 修改 `step1_outline.py`
- [ ] 集成热词提取器
- [ ] 增强提示词
- [ ] 优化标题生成逻辑

### 第 3 步：增强 Step 2
- [ ] 修改 `step2_timeline.py`
- [ ] 加载热词
- [ ] 增强提示词
- [ ] 测试标志性开头识别

### 第 4 步：优化 Step 4
- [ ] 重写 `step4_title.py`
- [ ] 实现标题优化逻辑
- [ ] 测试热词前置

### 第 5 步：集成测试
- [ ] 完整运行 Step 1-6
- [ ] 验证"地域文化性格分析"类话题的完整性
- [ ] 检查边界扩展效果

---

## 📁 文件结构

```
backend/
├── utils/
│   └── hotword_extractor.py       # 【新增】热词提取工具
├── pipeline/
│   ├── step1_outline.py            # 【修改】增强版
│   ├── step2_timeline.py           # 【修改】增强版
│   ├── step3_scoring.py            # 【待修改】
│   ├── step4_title.py              # 【修改】优化版
│   ├── step5_clustering.py         # 【待修改】
│   └── step6_video.py              # 【已修改】
└── prompt/
    ├── 大纲.txt                    # 【已修改】
    └── 时间点.txt                   # 【已修改】

tests/
└── test_hotword_extractor.py       # 【新增】

docs/
└── FUNCLIP_INTEGRATION_ANALYSIS.md # 【已创建】
```

---

## 🎯 成功指标

| 指标 | 目标 |
|------|------|
| 标志性开头识别率 | >90% 的话题能从正确的开头开始 |
| 标题包含热词比例 | >70% 的标题包含标志性词汇 |
| 用户满意度 | 反馈"切片完整"的比例显著提升 |

---

## 🔧 降级方案

如果热词提取出现问题：

```python
# 在 hotword_extractor.py 中
def _safe_extract(self, srt_data: List[Dict]) -> List[Dict]:
    """安全的热词提取 - 失败时返回空列表"""
    try:
        return self.extract_from_srt(srt_data)
    except Exception as e:
        logger.warning(f"热词提取失败: {e}")
        return []  # 降级：不使用热词
```

---

## 📝 总结

本方案重点解决了三个问题：

1. **热词体系** - 自动提取标志性词汇
2. **提示词优化** - 明确要求从标志性开头定位
3. **完整性验证** - 检查话题是否包含完整开头

通过这些改进，应该能显著提升"地域文化性格分析"这类话题的切片完整性！
