# AutoClip 项目借鉴 FunClip 分析报告

## 📋 概述

本报告详细分析了阿里巴巴开源的 FunClip 项目的核心特性，并提出了 AutoClip 项目在 Step 1-6 各阶段可以借鉴的改进方案。

---

## 🎯 FunClip 核心特性分析

### 1. 工业级 ASR 集成
- **Paraformer-Large**: 阿里巴巴开源的最优中文 ASR 模型之一
  - ModelScope 下载量 1300万+
  - 一体化准确时间戳预测
- **SeACo-Paraformer**: 支持热词定制化
- **CAM++**: 说话人识别模型

### 2. LLM 智能剪辑 (v2.0.0)
- 集成 Qwen、GPT 系列模型
- 默认提示词配置
- 可自定义提示词探索
- 基于 SRT 字幕的智能时间戳提取

### 3. 多段自由剪辑
- 支持选择文本片段或说话人
- 自动返回完整 SRT 字幕
- 自动返回目标片段 SRT 字幕

### 4. 易用性
- Gradio Web 界面
- 支持本地部署
- 支持在线体验 (ModelScope / HuggingFace)
- 命令行调用支持

---

## 🔍 AutoClip Step 1-6 分析

### Step 1: 大纲提取 (`step1_outline.py`)

#### 当前实现
```python
- SRT 解析
- 30分钟时间分块
- LLM 调用提取大纲
- 保存中间结果
```

#### 可借鉴点

| 借鉴项 | 优先级 | 描述 |
|--------|--------|------|
| **热词感知大纲** | 🟥 高 | 引入 FunClip 的热词概念，帮助 LLM 识别标志性话题开头 |
| **说话人感知** | 🟧 中 | 如果有说话人信息，可以按说话人分组大纲 |
| **大纲提示词优化** | 🟧 中 | 参考 FunClip 的提示词设计，强调"标志性开头"识别 |

#### 具体建议

**建议 1.1: 热词增强提示词**

```python
# 在 step1_outline.py 中
def _enhance_prompt_with_hotwords(self, prompt: str, srt_data: List[Dict]) -> str:
    """
    从 SRT 中提取高频词作为热词，增强大纲提取
    
    借鉴 FunClip 的热词定制化思想
    """
    # 提取高频词
    all_text = " ".join([item['text'] for item in srt_data])
    hotwords = self._extract_hotwords(all_text)
    
    enhanced_prompt = f"""{prompt}

【重要提示】
请特别关注以下可能是话题标志性开头的热词：
{', '.join(hotwords[:10])}

如果某个话题以这些词开头，请确保将其作为独立话题的起点。
"""
    return enhanced_prompt
```

---

### Step 2: 时间线提取 (`step2_timeline.py`)

#### 当前实现
```python
- 按 chunk_index 分组大纲
- 批量调用 LLM 定位时间
- 宽松边界限制 (±5秒)
- 跨边界话题合并
- 完整性验证
```

#### 可借鉴点

| 借鉴项 | 优先级 | 描述 |
|--------|--------|------|
| **标志性开头识别** | 🟥 高 | 借鉴 FunClip 的提示词，要求 LLM 从"京油子、卫嘴子"这类标志性开头开始定位 |
| **热词增强定位** | 🟥 高 | 将用户指定的热词或自动提取的热词传递给 LLM，帮助准确定位 |
| **说话人过滤支持** | 🟧 中 | 支持按说话人选择和过滤话题 |
| **LLM 智能剪辑模式** | 🟧 中 | 参考 FunClip v2.0 的 LLM 智能剪辑模式 |

#### 具体建议

**建议 2.1: 增强时间线定位提示词**

在 `backend/prompt/时间点.txt` 中已添加了：

```
【重要】话题完整性要求：
1. 开头完整性：定位开始时间时，必须找到话题的"标志性开头"或"引子"
   - 例如：如果话题是"地域文化性格分析"，而字幕中有"京油子、卫嘴子、保定府的狗腿子"
     这样的标志性开头，必须从这个开头开始定位
```

这个改进可以立即生效。

**建议 2.2: 说话人感知的时间线提取**

```python
# 在 step2_timeline.py 中新增
def _extract_timeline_with_speaker(
    self, 
    outlines: List[Dict], 
    speaker_info: Optional[Dict] = None
) -> List[Dict]:
    """
    支持说话人信息的时间线提取
    
    借鉴 FunClip 的 CAM++ 说话人识别功能
    """
    timeline_data = self.extract_timeline(outlines)
    
    if speaker_info:
        # 为每个话题添加说话人标签
        for item in timeline_data:
            speaker = self._find_dominant_speaker(item, speaker_info)
            item['speaker'] = speaker
    
    return timeline_data
```

**建议 2.3: 热词增强的时间线定位**

```python
# 在 step2_timeline.py 中
def _enhance_timeline_prompt(
    self, 
    prompt: str, 
    hotwords: List[str] = None
) -> str:
    """
    增强时间线定位提示词，添加热词信息
    
    借鉴 FunClip 的 SeACo-Paraformer 热词定制化
    """
    if not hotwords:
        return prompt
    
    hotword_section = f"""
【热词辅助定位】
请特别注意以下关键词出现的时间：
{', '.join(hotwords)}

如果某个时间点附近出现了这些词，请考虑将其作为话题边界。
"""
    return prompt + hotword_section
```

---

### Step 3: 内容评分 (`step3_scoring.py`)

#### 当前实现
```python
- LLM 评分
- 本地评分降级
- 默认评分降级
- 多层降级机制
```

#### 可借鉴点

| 借鉴项 | 优先级 | 描述 |
|--------|--------|------|
| **说话人质量评分** | 🟧 中 | 增加"说话人多样性"、"主要说话人"等评分维度 |
| **热词匹配评分** | 🟧 中 | 话题中包含的热词越多，评分越高 |
| **LLM 推荐理由展示** | 🟩 低 | 参考 FunClip 的推荐理由展示方式 |

#### 具体建议

**建议 3.1: 多维度评分增强**

```python
# 在 step3_scoring.py 中
def _calculate_multi_dimension_score(
    self, 
    clip: Dict, 
    hotwords: List[str] = None
) -> float:
    """
    多维度评分，借鉴 FunClip 的评价维度
    
    维度包括：
    - 内容完整性
    - 标志性开头
    - 热词匹配度
    - 说话人质量
    """
    base_score = clip.get('score', 0.5)
    enhancement = 0
    
    # 1. 标志性开头检查
    outline = clip.get('outline', '').lower()
    has_signature = any(word in outline for word in ['俗话说', '话说', '你知道吗', '京油子', '卫嘴子'])
    if has_signature:
        enhancement += 0.1
    
    # 2. 热词匹配
    if hotwords:
        match_count = sum(1 for word in hotwords if word.lower() in outline)
        enhancement += min(match_count * 0.05, 0.15)
    
    return min(1.0, base_score + enhancement)
```

---

### Step 4: 标题生成 (`step4_title.py`)

#### 当前实现
```python
- 使用 outline 作为标题
- 备用：content 前50字
- 备用："精彩片段{n}"
```

#### 可借鉴点

| 借鉴项 | 优先级 | 描述 |
|--------|--------|------|
| **标志性开头保留** | 🟥 高 | 标题中保留"京油子、卫嘴子"这类标志性开头 |
| **热词前置** | 🟧 中 | 将热词放在标题前面，提高吸引力 |
| **说话人标签** | 🟩 低 | 添加说话人信息到标题 |

#### 具体建议

**建议 4.1: 智能标题优化**

```python
# 在 step4_title.py 中
def _optimize_title_with_signature(
    self, 
    title: str, 
    clip: Dict, 
    hotwords: List[str] = None
) -> str:
    """
    优化标题，保留标志性开头
    
    借鉴 FunClip 的标题生成思路
    """
    content = clip.get('content', '').lower()
    outline = clip.get('outline', '').lower()
    
    # 检查是否有标志性开头
    signature_patterns = [
        '京油子', '卫嘴子', '俗话说', '话说', 
        '你知道', '你看', '我跟你说'
    ]
    
    for pattern in signature_patterns:
        if pattern in content:
            # 找到标志性句子
            idx = content.find(pattern)
            if idx >= 0:
                # 提取从标志性开头开始的完整句子
                end_idx = content.find('。', idx)
                if end_idx > idx:
                    signature_text = content[idx:end_idx+1]
                    if len(signature_text) < 50:
                        return signature_text
    
    # 如果没有标志性开头，尝试热词优化
    if hotwords:
        for hotword in hotwords:
            if hotword.lower() in outline and hotword not in title:
                return f"{hotword}：{title}"
    
    return title
```

---

### Step 5: 聚类 (`step5_clustering.py`)

#### 当前实现
```python
- 简单的连续3片分组
- 生成"精彩合集 n"标题
```

#### 可借鉴点

| 借鉴项 | 优先级 | 描述 |
|--------|--------|------|
| **说话人聚类** | 🟧 中 | 相同说话人的片段聚合成一类 |
| **主题词聚类** | 🟧 中 | 基于热词和关键词进行更智能的聚类 |
| **动态聚类大小** | 🟩 低 | 根据内容密度自动调整每集大小 |

#### 具体建议

**建议 5.1: 智能主题聚类**

```python
# 在 step5_clustering.py 中
def _intelligent_clustering(
    self, 
    clips: List[Dict], 
    hotwords: List[str] = None
) -> List[Dict]:
    """
    智能聚类，借鉴 FunClip 的主题理解能力
    
    - 说话人聚类
    - 热词相似度聚类
    """
    clusters = []
    
    # 1. 先按说话人分组（如果有说话人信息）
    clips_by_speaker = defaultdict(list)
    for clip in clips:
        speaker = clip.get('speaker', 'unknown')
        clips_by_speaker[speaker].append(clip)
    
    # 2. 对每个说话人的片段进行二次聚类
    for speaker, speaker_clips in clips_by_speaker.items():
        # 基于热词相似度聚类
        speaker_clusters = self._cluster_by_similarity(speaker_clips, hotwords)
        clusters.extend(speaker_clusters)
    
    return clusters
```

---

### Step 6: 视频生成 (`step6_video.py`)

#### 当前实现
```python
- 批量提取切片
- 静音处理
- 并行处理
- 字幕生成支持
```

#### 可借鉴点

| 借鉴项 | 优先级 | 描述 |
|--------|--------|------|
| **边界扩展优化** | 🟥 高 | 我们已经实现了！但可以借鉴 FunClip 的默认值 (2秒) |
| **热词标注字幕** | 🟧 中 | 在字幕中高亮显示热词和标志性开头 |
| **说话人标签字幕** | 🟧 中 | 在字幕中添加说话人标签 |
| **字幕嵌入视频** | 🟩 低 | 参考 FunClip 的字幕嵌入功能 |
| **边界预览工具** | 🟩 低 | 提供界面让用户调整每个切片的边界 |

#### 具体建议

**建议 6.1: 热词高亮字幕**

```python
# 在 video_processor.py 中
def _generate_highlighted_subtitle(
    self, 
    srt_path: Path, 
    hotwords: List[str] = None,
    output_path: Path = None
) -> Path:
    """
    生成热词高亮的字幕
    
    借鉴 FunClip 的字幕处理思路
    """
    import re
    
    with open(srt_path, 'r', encoding='utf-8') as f:
        srt_content = f.read()
    
    if hotwords:
        # 为热词添加高亮标记（可以是 HTML 或 ASS 格式）
        for word in hotwords:
            pattern = re.compile(re.escape(word))
            srt_content = pattern.sub(f"<font color='red'>{word}</font>", srt_content)
    
    if not output_path:
        output_path = srt_path.parent / f"{srt_path.stem}_highlighted.srt"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(srt_content)
    
    return output_path
```

---

## 🏗️ 整体架构借鉴

### 1. Gradio 轻量级界面 (可选)

借鉴 FunClip，为 AutoClip 添加一个轻量级的 Gradio 界面，用于快速测试和演示：

```python
# backend/gradio_demo.py
import gradio as gr
from pathlib import Path

def create_gradio_interface():
    with gr.Blocks(title="AutoClip Demo") as demo:
        gr.Markdown("# AutoClip - 智能视频切片系统")
        
        with gr.Row():
            video_input = gr.Video(label="上传视频")
            srt_output = gr.File(label="SRT 字幕")
        
        with gr.Row():
            hotwords_input = gr.Textbox(
                label="热词（逗号分隔）",
                placeholder="京油子,卫嘴子,保定府的狗腿子"
            )
            recognize_btn = gr.Button("识别字幕")
        
        with gr.Row():
            text_select = gr.Textbox(label="选择片段文本")
            clip_btn = gr.Button("提取片段")
        
        output_video = gr.Video(label="提取结果")
        
        # 绑定事件...
    
    return demo
```

### 2. 提示词管理系统

借鉴 FunClip 的可配置提示词，建立提示词管理系统：

```python
# backend/core/prompt_manager.py
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

@dataclass
class PromptConfig:
    name: str
    content: str
    description: str

class PromptManager:
    """
    提示词管理器，借鉴 FunClip 的可配置提示词
    
    支持：
    - 预设提示词
    - 用户自定义提示词
    - 提示词版本管理
    """
    
    def __init__(self, prompt_dir: Path):
        self.prompt_dir = prompt_dir
        self._load_presets()
    
    def get_prompt(self, name: str) -> PromptConfig:
        """获取指定名称的提示词"""
        pass
    
    def list_prompts(self) -> List[str]:
        """列出所有可用提示词"""
        pass
    
    def save_custom_prompt(self, name: str, content: str, description: str):
        """保存用户自定义提示词"""
        pass
```

---

## 📊 实施优先级

### 第一阶段（高优先级）
1. ✅ **Step 2: 标志性开头识别** - 已部分实现，继续完善
2. ✅ **Step 6: 边界扩展优化** - 已实现（2秒）
3. **Step 1: 热词感知大纲**
4. **Step 4: 智能标题优化**

### 第二阶段（中优先级）
1. **Step 2: 说话人过滤支持**
2. **Step 3: 多维度评分**
3. **Step 5: 智能主题聚类**
4. **提示词管理系统**

### 第三阶段（低优先级）
1. **Gradio 轻量级界面**
2. **Step 6: 热词高亮字幕**
3. **Step 6: 说话人标签字幕**
4. **边界预览工具**

---

## 🎯 关键技术点总结

### 1. 热词体系
- **自动热词提取**: 从 SRT 中提取高频词
- **用户自定义热词**: 允许用户指定重要关键词
- **热词传播**: 热词信息在 Step 1-6 之间传递

### 2. 标志性开头识别
- **提示词设计**: 强调从标志性开头开始
- **模式匹配**: 常见开头模式识别
- **完整性验证**: 检查话题是否包含完整开头

### 3. 说话人感知
- **CAM++ 集成**: 如果有说话人信息
- **说话人聚类**: 相同说话人的片段聚合
- **说话人过滤**: 允许用户选择感兴趣的说话人

### 4. LLM 智能剪辑模式
- **双重提示词**: FunClip 风格的提示词组合
- **自定义提示词**: 用户可配置的提示词
- **时间戳提取**: 从 LLM 输出中智能提取时间戳

---

## 📁 修改文件清单

### 已有改进
- ✅ `backend/prompt/时间点.txt` - 添加了话题完整性要求
- ✅ `backend/prompt/大纲.txt` - 添加了话题命名要求
- ✅ `backend/pipeline/step2_timeline.py` - 添加了完整性验证
- ✅ `backend/utils/video_processor.py` - 边界扩展已优化为2秒

### 建议新增/修改
1. `backend/utils/hotword_extractor.py` - 热词提取工具
2. `backend/core/prompt_manager.py` - 提示词管理器
3. `backend/gradio_demo.py` - 轻量级演示界面
4. `backend/pipeline/step1_outline.py` - 增强热词支持
5. `backend/pipeline/step4_title.py` - 智能标题优化
6. `backend/pipeline/step5_clustering.py` - 智能聚类
7. `backend/pipeline/step3_scoring.py` - 多维度评分

---

## 🔚 总结

FunClip 的核心优势在于：
1. **工业级 ASR** - Paraformer 系列模型
2. **热词定制化** - SeACo-Paraformer
3. **说话人识别** - CAM++
4. **LLM 智能剪辑** - v2.0 新特性
5. **易用的界面** - Gradio

AutoClip 已经有了很好的架构基础，通过借鉴这些特性，可以：
- ✅ 提高话题边界的准确性
- ✅ 确保内容完整性
- ✅ 增强用户体验
- ✅ 提供更智能的剪辑选择

建议从第一阶段的改进开始，逐步完善各个环节。
