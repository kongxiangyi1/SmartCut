# LLM智能切片异常降级处理方案 - 完整重构版

---

## 一、背景与目标

### 1.1 现有方案核心缺陷

| 缺陷类型 | 问题描述 | 严重程度 |
|---------|---------|---------|
| 评分逻辑无效 | 仅依靠字幕长度+音频能量，无法识别精彩内容 | 🔴 致命 |
| 模式定位模糊 | "本地降级"用户体验差，价值不对等 | 🔴 严重 |
| 降级链路缺失 | 降级失败后无兜底，直接报错 | 🟡 中等 |
| 状态监听缺失 | 仅上传前校验，运行时LLM失效无感知 | 🟡 中等 |
| 代码架构冗余 | 双代码路径，维护成本高 | 🟡 中等 |
| 配置无快照 | 历史任务受后续配置修改影响 | 🟡 中等 |
| 用户预期管理差 | 模式名称、文案导致用户困惑 | 🟡 中等 |

### 1.2 重构目标

```
┌─────────────────────────────────────────────────────────────────┐
│                         重构目标体系                            │
├─────────────────────────────────────────────────────────────────┤
│  1. 废除无语义评分 → 建立有实际价值的降级模式                     │
│  2. 清晰模式定位 → 区分正式生产 vs 演示预览                      │
│  3. 有序降级链路 → 每层都有可用产出                              │
│  4. 运行时监控 → LLM状态全程可感知                             │
│  5. 策略模式重构 → 统一调度，消除冗余                           │
│  6. 配置快照锁定 → 历史任务配置不变                             │
│  7. 用户预期管理 → 清晰文案，零困惑                             │
│  8. 多层容错机制 → 异常自动降级，优雅失败                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、模式体系重构

### 2.1 新模式定位体系

#### 正式生产模式（Production Modes）

| 模式 | 标识 | 定位 | 输出质量 | LLM依赖 |
|------|------|------|---------|---------| 
| **AI智能模式** | `ai_smart` | 最佳体验，完整功能 | ⭐⭐⭐⭐⭐ | 必须 |
| **字幕整理模式** | `subtitle_organized` | 降级但有价值，标准化产出 | ⭐⭐⭐ | 不依赖 |

#### 演示预览模式（Demo Modes）

| 模式 | 标识 | 定位 | 输出质量 | 标注要求 |
|------|------|------|---------|---------|
| **快速预览** | `quick_preview` | 仅演示效果，不可用于正式业务 | ⭐⭐ | 必须标注"演示" |
| **原始转写** | `raw_transcript` | 仅转写文本，无结构化输出 | ⭐ | 必须标注"原始" |

### 2.2 模式对比矩阵

```
┌──────────────┬────────────┬────────┬────────┬────────┬────────┬────────┐
│    模式      │   标识     │ 字幕整理│ 大纲   │ 精彩片段│ 智能标题│ 聚类合集│
├──────────────┼────────────┼────────┼────────┼────────┼────────┼────────┤
│ AI智能模式   │ ai_smart   │   ✅   │   ✅   │   ✅   │   ✅   │   ✅   │
│ 字幕整理模式 │ subtitle   │   ✅   │   ❌   │   ❌   │   ❌   │   ❌   │
│ 快速预览     │ preview    │   ✅   │   ⚠️   │   ⚠️   │   ⚠️   │   ⚠️   │
│ 原始转写     │ raw        │   ✅   │   ❌   │   ❌   │   ❌   │   ❌   │
└──────────────┴────────────┴────────┴────────┴────────┴────────┴────────┘

✅ = LLM驱动高质量输出
⚠️ = 本地算法模拟，质量有限，仅演示用
❌ = 不包含该功能
```

### 2.3 模式选择决策树

```
                        ┌─────────────────┐
                        │  用户上传视频   │
                        └────────┬────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   LLM配置状态检测       │
                    └────────────┬───────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
   ┌───────────┐          ┌───────────┐          ┌───────────┐
   │  可用正常 │          │ 配额用完   │          │ 未配置    │
   └─────┬─────┘          └─────┬─────┘          └─────┬─────┘
         │                       │                       │
         ▼                       ▼                       ▼
   ┌───────────┐          ┌───────────┐          ┌───────────┐
   │ AI智能模式│          │  提示用户 │          │  引导配置 │
   │ (推荐使用)│          │  选择模式  │          │  或降级   │
   └───────────┘          └───────────┘          └───────────┘
```

### 2.4 各模式输出规格

#### AI智能模式 (`ai_smart`)

```
输出结构：
{
  "mode": "ai_smart",
  "status": "completed",
  "outputs": {
    "subtitle": {
      "path": "/data/projects/xxx/subtitles/final.srt",
      "format": "srt",
      "duration": "02:30:45"
    },
    "outline": {
      "topics": [
        {
          "id": 1,
          "title": "AI对教育的影响",
          "start_time": "00:05:30",
          "end_time": "00:15:20",
          "subtopics": ["个性化学习", "教师角色转变"]
        }
      ]
    },
    "highlights": {
      "clips": [
        {
          "id": 1,
          "title": "AI将彻底改变传统教育模式",
          "start_time": "00:08:15",
          "end_time": "00:10:30",
          "score": 9.2,
          "reason": "观点鲜明，有数据支撑"
        }
      ]
    },
    "collections": {
      "groups": [
        {
          "id": "col_1",
          "name": "AI教育应用系列",
          "clips": [1, 3, 5]
        }
      ]
    }
  }
}
```

#### 字幕整理模式 (`subtitle_organized`)

```
输出结构：
{
  "mode": "subtitle_organized",
  "status": "completed",
  "outputs": {
    "subtitle": {
      "path": "/data/projects/xxx/subtitles/organized.srt",
      "format": "srt",
      "duration": "02:30:45",
      "enhancements": {
        "speaker_diarization": true,
        "punctuation_restored": true,
        "format_normalized": true
      }
    }
  },
  "limitations": [
    "无AI生成的大纲结构",
    "无精彩片段识别",
    "无智能标题生成",
    "无合集推荐"
  ]
}
```

#### 快速预览模式 (`quick_preview`) - 仅演示

```
输出结构：
{
  "mode": "quick_preview",
  "status": "completed",
  "warning": "⚠️ 本模式仅供演示预览，输出质量有限，不适合正式业务使用",
  "is_demo": true,
  "outputs": {
    "subtitle": {...},
    "basic_segments": {
      "method": "silence_detection",
      "segments": [
        {
          "start": "00:00:00",
          "end": "00:05:00",
          "text_preview": "前5分钟的字幕内容预览..."
        }
      ]
    },
    "basic_titles": {
      "method": "first_sentence",
      "titles": ["使用字幕首句作为标题，仅供演示"]
    }
  }
}
```

---

## 三、有序降级链路设计

### 3.1 降级链路架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           降级链路总览                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│    ┌─────────────┐                                                     │
│    │ Step 0: 素材 │ ← 视频下载/上传                                    │
│    │  准备阶段    │                                                     │
│    └──────┬──────┘                                                     │
│           │                                                             │
│           ▼                                                             │
│    ┌─────────────┐                                                     │
│    │ Step 1: 字幕 │ ← 语音转写                                         │
│    │  生成阶段    │                                                     │
│    └──────┬──────┘                                                     │
│           │                                                             │
│    ┌──────┴──────┐                                                      │
│    │ LLM状态检测 │                                                       │
│    └──────┬──────┘                                                      │
│           │                                                             │
│  ┌────────┼────────┐                                                    │
│  │        │        │                                                    │
│  ▼        ▼        ▼                                                    │
│ AI可用  配额用完  不可用                                                │
│  │        │        │                                                    │
│  ▼        ▼        ▼                                                    │
│ ┌─────────────┐  ┌─────────────┐                                       │
│ │ Level 1     │  │ Level 2     │                                       │
│ │ AI智能模式  │  │ 字幕整理    │                                       │
│ └──────┬──────┘  └──────┬──────┘                                       │
│        │                │                                               │
│        │         ┌──────┴──────┐                                        │
│        │         │ 处理失败    │                                        │
│        │         └──────┬──────┘                                        │
│        │                │                                                │
│        │         ┌──────┴──────┐                                        │
│        │         │ 降级到      │                                        │
│        │         │ Level 3     │                                        │
│        │         └──────┬──────┘                                        │
│        │                │                                                │
│        │         ┌──────┴──────┐                                        │
│        │         │ 仍失败      │                                        │
│        │         └──────┬──────┘                                        │
│        │                │                                                │
│        │         ┌──────┴──────┐                                        │
│        │         │ 降级到      │                                        │
│        │         │ Level 4     │                                        │
│        │         └──────┬──────┘                                        │
│        │                │                                                │
│        ▼                ▼                                                │
│   ┌─────────────────────────────┐                                       │
│   │     Level 4: 友好错误       │                                       │
│   │     返回明确错误信息        │                                       │
│   └─────────────────────────────┘                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 降级层级详细定义

| Level | 层级 | 触发条件 | 输出 | 质量 |
|-------|------|---------|------|------|
| 1 | AI智能模式 | LLM可用+配额充足 | 完整大纲+精彩片段+标题+聚类 | ⭐⭐⭐⭐⭐ |
| 2 | 字幕整理模式 | LLM不可用/配额用完 | 标准化字幕+增强整理 | ⭐⭐⭐ |
| 3 | 原始转写模式 | Level 2失败 | 原始字幕文件 | ⭐⭐ |
| 4 | 友好错误提示 | Level 3失败 | 明确错误信息+解决建议 | - |

### 3.3 降级决策流程

```python
class DegradationDecisionEngine:
    """
    降级决策引擎
    根据实时状态决定当前可用的最佳处理模式
    """
    
    def decide_mode(self, project_id: str) -> ProcessMode:
        """
        决策算法：
        1. 检测LLM实时状态
        2. 考虑项目配置的快照
        3. 返回可用的最佳模式
        """
        # Step 1: 获取项目快照（如果有）
        project_snapshot = self._get_project_snapshot(project_id)
        if project_snapshot:
            # 已开始的任务使用快照中的模式
            return project_snapshot.mode
        
        # Step 2: 检测LLM实时状态
        llm_status = self._check_llm_status()
        
        # Step 3: 决策
        if llm_status.is_available and llm_status.has_quota:
            return ProcessMode.AI_SMART
        elif llm_status.can_organize_subtitle:
            return ProcessMode.SUBTITLE_ORGANIZED
        elif llm_status.can_raw_transcript:
            return ProcessMode.RAW_TRANSCRIPT
        else:
            return ProcessMode.UNAVAILABLE
    
    def should_degrade(self, current_level: int, error: Exception) -> Tuple[bool, Optional[int]]:
        """
        判断是否需要降级
        返回: (是否降级, 目标层级)
        """
        # 不可降级的错误
        non_degradable_errors = [
            UnsupportedFormatError,
            FileNotFoundError,
            InsufficientStorageError,
        ]
        
        if isinstance(error, tuple(non_degradable_errors)):
            return False, None
        
        # 可降级的错误，尝试降一级
        next_level = min(current_level + 1, 4)
        return True, next_level
```

### 3.4 运行时状态监听

```python
class LLMStateMonitor:
    """
    LLM运行时状态监听器
    监控LLM配置变化，配额消耗，自动触发降级决策
    """
    
    def __init__(self):
        self._subscribers: List[Callable] = []
        self._last_check: Optional[datetime] = None
        self._cached_status: Optional[LLMStatus] = None
    
    def subscribe(self, callback: Callable):
        """订阅状态变化"""
        self._subscribers.append(callback)
    
    def notify_status_change(self, old_status: LLMStatus, new_status: LLMStatus):
        """通知所有订阅者状态变化"""
        for callback in self._subscribers:
            try:
                callback(old_status, new_status)
            except Exception as e:
                logger.error(f"状态变化通知失败: {e}")
    
    async def check_and_notify(self, project_id: str) -> LLMStatus:
        """
        检查LLM状态，如有变化则通知
        """
        current_status = self._get_llm_status()
        
        if self._cached_status and current_status != self._cached_status:
            # 状态变化，通知订阅者
            self.notify_status_change(self._cached_status, current_status)
            
            # 对于处理中的任务，评估是否需要降级
            await self._evaluate_running_tasks(project_id, current_status)
        
        self._cached_status = current_status
        self._last_check = datetime.now()
        return current_status
    
    async def _evaluate_running_tasks(self, project_id: str, status: LLMStatus):
        """
        评估运行中的任务是否需要降级
        """
        running_projects = self._get_running_projects()
        
        for project in running_projects:
            if self._should_degrade_project(project, status):
                await self._trigger_degradation(project, status)
    
    def _should_degrade_project(self, project: Project, status: LLMStatus) -> bool:
        """
        判断运行中的项目是否应该降级
        """
        # 配额耗尽
        if not status.has_quota and project.current_mode == ProcessMode.AI_SMART:
            return True
        
        # 配置被禁用
        if not status.is_available and project.current_mode == ProcessMode.AI_SMART:
            return True
        
        return False
```

---

## 四、后端架构优化

### 4.1 策略模式架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                      统一调度器 (PipelineDirector)              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                    策略接口层                           │   │
│   │  ┌─────────────────────────────────────────────────┐   │   │
│   │  │           PipelineStrategy (抽象基类)           │   │   │
│   │  │  + execute() -> PipelineResult                  │   │   │
│   │  │  + get_capabilities() -> Set[Capability]        │   │   │
│   │  │  + get_quality_level() -> int                   │   │   │
│   │  └─────────────────────────────────────────────────┘   │   │
│   └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│              ┌───────────────┼───────────────┐                 │
│              │               │               │                 │
│              ▼               ▼               ▼                 │
│   ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ │
│   │ AISmartStrategy │ │SubtitleStrategy │ │ PreviewStrategy │ │
│   │                 │ │                 │ │                 │ │
│   │ - LLM Outliner  │ │ - LLM Disabled  │ │ - Silence Detect│ │
│   │ - LLM Timeline  │ │ - Normalizer     │ │ - Basic Segment │ │
│   │ - LLM Scorer    │ │ - Formatter      │ │ - First Sentence│ │
│   │ - LLM Titler    │ │                 │ │                 │ │
│   │ - LLM Clusterer │ │                 │ │                 │ │
│   └─────────────────┘ └─────────────────┘ └─────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 策略接口定义

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from enum import Enum

class Capability(Enum):
    SUBTITLE_GENERATION = "subtitle"
    OUTLINE_EXTRACTION = "outline"
    HIGHLIGHT_DETECTION = "highlight"
    TITLE_GENERATION = "title"
    COLLECTION_CLUSTERING = "clustering"
    SEMANTIC_UNDERSTANDING = "semantic"

@dataclass
class PipelineResult:
    status: str  # "success", "partial", "failed"
    mode: str
    outputs: Dict[str, Any]
    warnings: List[str]
    errors: List[str]
    quality_level: int  # 1-5
    is_demo: bool = False

class PipelineStrategy(ABC):
    """处理流水线策略抽象基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._setup_components()
    
    @abstractmethod
    def _setup_components(self):
        """子类实现：设置具体组件"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Set[Capability]:
        """返回该策略支持的能力"""
        pass
    
    def get_quality_level(self) -> int:
        """返回该策略的质量等级 (1-5)"""
        return len(self.get_capabilities())
    
    def is_demo_mode(self) -> bool:
        """是否为演示模式"""
        return False
    
    async def execute(
        self, 
        video_path: str, 
        subtitle_path: Optional[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> PipelineResult:
        """
        执行流水线
        子类可重写以自定义执行流程
        """
        try:
            # 统一的错误处理和进度回调
            return await self._execute_impl(video_path, subtitle_path, progress_callback)
        except Exception as e:
            return self._handle_error(e)
    
    @abstractmethod
    async def _execute_impl(
        self,
        video_path: str,
        subtitle_path: Optional[str],
        progress_callback: Optional[Callable]
    ) -> PipelineResult:
        """子类实现：具体执行逻辑"""
        pass
    
    def _handle_error(self, error: Exception) -> PipelineResult:
        """统一错误处理"""
        return PipelineResult(
            status="failed",
            mode=self.__class__.__name__,
            outputs={},
            warnings=[],
            errors=[str(error)],
            quality_level=0
        )
```

### 4.3 AI智能策略实现

```python
class AISmartStrategy(PipelineStrategy):
    """
    AI智能模式策略
    使用完整的LLM能力进行语义分析和理解
    """
    
    def get_capabilities(self) -> Set[Capability]:
        return {
            Capability.SUBTITLE_GENERATION,
            Capability.OUTLINE_EXTRACTION,
            Capability.HIGHLIGHT_DETECTION,
            Capability.TITLE_GENERATION,
            Capability.COLLECTION_CLUSTERING,
            Capability.SEMANTIC_UNDERSTANDING,
        }
    
    def _setup_components(self):
        """设置AI驱动的组件"""
        self.outliner = LLMOutliner(
            provider=self.config.get('llm_provider'),
            model=self.config.get('llm_model'),
            prompt_template=self._load_prompt('outline')
        )
        
        self.timeline_extractor = LLMTimelineExtractor(
            outliner=self.outliner,
            text_processor=TextProcessor()
        )
        
        self.scorer = LLMScorer(
            outliner=self.outliner,
            recommendation_prompt=self._load_prompt('recommendation')
        )
        
        self.titler = LLMTitleGenerator(
            outliner=self.outliner,
            title_prompt=self._load_prompt('title')
        )
        
        self.clusterer = LLMClusterer(
            outliner=self.outliner,
            clustering_prompt=self._load_prompt('clustering')
        )
    
    async def _execute_impl(
        self,
        video_path: str,
        subtitle_path: Optional[str],
        progress_callback: Optional[Callable]
    ) -> PipelineResult:
        """执行AI智能流水线"""
        
        outputs = {}
        warnings = []
        
        # Step 1: 字幕生成（如果需要）
        if not subtitle_path:
            subtitle_path = await self._generate_subtitle(video_path, progress_callback)
            outputs['subtitle'] = subtitle_path
        else:
            outputs['subtitle'] = subtitle_path
        
        # Step 2: 大纲提取
        self._emit_progress(progress_callback, "EXTRACTING_OUTLINE", 10)
        outline = await self.outliner.extract(video_path, subtitle_path)
        outputs['outline'] = outline
        
        # Step 3: 时间线提取
        self._emit_progress(progress_callback, "EXTRACTING_TIMELINE", 30)
        timeline = await self.timeline_extractor.extract(outline, subtitle_path)
        outputs['timeline'] = timeline
        
        # Step 4: 精彩片段评分
        self._emit_progress(progress_callback, "SCORING_HIGHLIGHTS", 50)
        highlights = await self.scorer.score(timeline)
        outputs['highlights'] = highlights
        
        # Step 5: 标题生成
        self._emit_progress(progress_callback, "GENERATING_TITLES", 70)
        titled = await self.titler.generate(highlights)
        outputs['titled_clips'] = titled
        
        # Step 6: 聚类合集
        self._emit_progress(progress_callback, "CREATING_COLLECTIONS", 85)
        collections = await self.clusterer.cluster(titled)
        outputs['collections'] = collections
        
        # Step 7: 视频切割
        self._emit_progress(progress_callback, "GENERATING_VIDEOS", 95)
        videos = await self._generate_videos(titled, collections, video_path)
        outputs['videos'] = videos
        
        self._emit_progress(progress_callback, "COMPLETED", 100)
        
        return PipelineResult(
            status="success",
            mode="ai_smart",
            outputs=outputs,
            warnings=warnings,
            errors=[],
            quality_level=5,
            is_demo=False
        )
```

### 4.4 字幕整理策略实现

```python
class SubtitleOrganizedStrategy(PipelineStrategy):
    """
    字幕整理模式策略
    不使用LLM，对字幕进行标准化整理和增强
    """
    
    def get_capabilities(self) -> Set[Capability]:
        return {
            Capability.SUBTITLE_GENERATION,
        }
    
    def _setup_components(self):
        """设置本地字幕处理组件"""
        self.normalizer = SubtitleNormalizer()
        self.formatter = SubtitleFormatter()
        self.speaker_detector = SpeakerChangeDetector()
    
    async def _execute_impl(
        self,
        video_path: str,
        subtitle_path: Optional[str],
        progress_callback: Optional[Callable]
    ) -> PipelineResult:
        
        outputs = {}
        warnings = [
            "当前使用字幕整理模式，无AI生成的大纲、精彩片段等功能",
            "如需完整功能，请在设置中配置AI模型"
        ]
        
        # Step 1: 字幕生成/获取
        if not subtitle_path:
            subtitle_path = await self._generate_subtitle(video_path, progress_callback)
        
        self._emit_progress(progress_callback, "PROCESSING_SUBTITLE", 20)
        
        # Step 2: 说话人检测（基于音频特征）
        self._emit_progress(progress_callback, "DETECTING_SPEAKERS", 40)
        subtitle_data = await self._load_subtitle(subtitle_path)
        speakers = await self.speaker_detector.detect(video_path, subtitle_data)
        
        # Step 3: 标点恢复
        self._emit_progress(progress_callback, "RESTORING_PUNCTUATION", 60)
        punctuated = await self._restore_punctuation(subtitle_data)
        
        # Step 4: 格式标准化
        self._emit_progress(progress_callback, "NORMALIZING_FORMAT", 80)
        organized = await self._organize_subtitle(punctuated, speakers)
        
        # Step 5: 保存整理后的字幕
        output_path = await self._save_organized_subtitle(organized)
        outputs['subtitle'] = {
            'path': output_path,
            'enhancements': {
                'speaker_diarization': True,
                'punctuation_restored': True,
                'format_normalized': True
            }
        }
        
        self._emit_progress(progress_callback, "COMPLETED", 100)
        
        return PipelineResult(
            status="success",
            mode="subtitle_organized",
            outputs=outputs,
            warnings=warnings,
            errors=[],
            quality_level=3,
            is_demo=False
        )
```

### 4.5 预览演示策略实现

```python
class QuickPreviewStrategy(PipelineStrategy):
    """
    快速预览模式策略
    仅用于演示预览，明确标注不可用于正式业务
    """
    
    def get_capabilities(self) -> Set[Capability]:
        return {
            Capability.SUBTITLE_GENERATION,
        }
    
    def is_demo_mode(self) -> bool:
        return True
    
    def get_quality_level(self) -> int:
        return 1  # 最低质量
    
    async def _execute_impl(
        self,
        video_path: str,
        subtitle_path: Optional[str],
        progress_callback: Optional[Callable]
    ) -> PipelineResult:
        
        warnings = [
            "⚠️ 本模式为演示预览模式",
            "⚠️ 输出质量有限，不适合正式业务使用",
            "⚠️ 切片结果为算法模拟，非AI智能识别"
        ]
        
        # 仅做基础的字幕整理和简单分段
        # ... 简化实现
        
        return PipelineResult(
            status="success",
            mode="quick_preview",
            outputs={...},
            warnings=warnings,
            errors=[],
            quality_level=1,
            is_demo=True  # 关键标记
        )
```

### 4.6 统一调度器

```python
class PipelineDirector:
    """
    统一调度器
    根据LLM状态和用户选择，协调各策略执行
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
        # 注册所有策略
        self._strategies: Dict[ProcessMode, PipelineStrategy] = {
            ProcessMode.AI_SMART: AISmartStrategy(config),
            ProcessMode.SUBTITLE_ORGANIZED: SubtitleOrganizedStrategy(config),
            ProcessMode.QUICK_PREVIEW: QuickPreviewStrategy(config),
            ProcessMode.RAW_TRANSCRIPT: RawTranscriptStrategy(config),
        }
        
        # LLM状态监听器
        self._llm_monitor = LLMStateMonitor()
        
        # 配置快照管理器
        self._snapshot_manager = ConfigSnapshotManager()
    
    async def execute(
        self,
        project_id: str,
        video_path: str,
        requested_mode: Optional[ProcessMode] = None,
        progress_callback: Optional[Callable] = None
    ) -> PipelineResult:
        """
        执行流水线
        1. 确定可用模式
        2. 锁定配置快照
        3. 选择合适策略
        4. 执行并处理降级
        """
        
        # Step 1: 获取项目（如果存在）
        project = await self._get_project(project_id)
        
        # Step 2: 确定执行模式
        if project and project.snapshot:
            # 已锁定的任务使用快照配置
            mode = project.snapshot.mode
            logger.info(f"项目{project_id}使用快照模式: {mode}")
        else:
            # 新任务：决策可用模式
            mode = await self._decide_mode(project_id, requested_mode)
            
            # 如果请求的模式不可用，尝试降级
            if requested_mode and requested_mode != mode:
                logger.warning(f"请求模式{requested_mode}不可用，降级到{mode}")
        
        # Step 3: 创建/更新配置快照
        if not project or not project.snapshot:
            await self._snapshot_manager.create_snapshot(
                project_id, 
                mode, 
                self._llm_monitor.get_current_status()
            )
        
        # Step 4: 获取策略
        strategy = self._strategies.get(mode)
        if not strategy:
            raise ValueError(f"未知的处理模式: {mode}")
        
        # Step 5: 执行（带降级逻辑）
        return await self._execute_with_fallback(
            project_id,
            strategy,
            video_path,
            progress_callback
        )
    
    async def _execute_with_fallback(
        self,
        project_id: str,
        strategy: PipelineStrategy,
        video_path: str,
        progress_callback: Optional[Callable]
    ) -> PipelineResult:
        """
        带降级的执行
        如果策略失败，尝试降级到更基础的策略
        """
        
        # 获取当前层级
        current_level = self._get_quality_level(strategy)
        max_level = 4  # 最多降级4次
        
        # 排序策略（按质量从高到低）
        sorted_strategies = sorted(
            self._strategies.values(),
            key=lambda s: s.get_quality_level(),
            reverse=True
        )
        
        last_error = None
        
        for s in sorted_strategies:
            if s.get_quality_level() > current_level:
                continue  # 只考虑同级或降级
            
            try:
                logger.info(f"尝试执行策略: {s.__class__.__name__}")
                
                result = await s.execute(
                    video_path,
                    progress_callback=progress_callback
                )
                
                if result.status == "success":
                    return result
                else:
                    last_error = result.errors[-1] if result.errors else "Unknown error"
                    
            except Exception as e:
                logger.error(f"策略{s.__class__.__name__}执行失败: {e}")
                last_error = str(e)
                continue
        
        # 所有策略都失败
        return PipelineResult(
            status="failed",
            mode="unknown",
            outputs={},
            warnings=[],
            errors=[f"所有处理策略均失败: {last_error}"],
            quality_level=0
        )
    
    async def _decide_mode(
        self,
        project_id: str,
        requested_mode: Optional[ProcessMode]
    ) -> ProcessMode:
        """决策处理模式"""
        
        llm_status = await self._llm_monitor.check_and_notify(project_id)
        
        # 如果请求的模式可用，直接返回
        if requested_mode:
            if self._is_mode_available(requested_mode, llm_status):
                return requested_mode
        
        # 根据LLM状态自动选择
        if llm_status.is_fully_available:
            return ProcessMode.AI_SMART
        elif llm_status.can_process_subtitle:
            return ProcessMode.SUBTITLE_ORGANIZED
        elif llm_status.can_transcribe:
            return ProcessMode.RAW_TRANSCRIPT
        else:
            return ProcessMode.UNAVAILABLE
```

### 4.7 配置快照锁定机制

```python
class ConfigSnapshotManager:
    """
    配置快照管理器
    为每个项目创建配置快照，防止历史任务受后续修改影响
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create_snapshot(
        self,
        project_id: str,
        mode: ProcessMode,
        llm_status: LLMStatus
    ) -> ProjectSnapshot:
        """创建配置快照"""
        
        snapshot = ProjectSnapshot(
            project_id=project_id,
            mode=mode,
            created_at=datetime.now(),
            
            # LLM配置快照
            llm_provider=llm_status.provider,
            llm_model=llm_status.model,
            llm_api_key_encrypted=encrypt(llm_status.api_key),
            
            # 系统配置快照
            processing_config=json.dumps({
                'chunk_size': settings.processing_chunk_size,
                'min_score_threshold': settings.processing_min_score_threshold,
                'max_clips_per_collection': settings.processing_max_clips_per_collection,
            }),
            
            # 有效性标记
            is_locked=True
        )
        
        self.db.add(snapshot)
        await self.db.commit()
        
        logger.info(f"项目{project_id}配置快照已锁定: {mode}")
        
        return snapshot
    
    async def get_snapshot(self, project_id: str) -> Optional[ProjectSnapshot]:
        """获取项目的配置快照"""
        return self.db.query(ProjectSnapshot).filter(
            ProjectSnapshot.project_id == project_id,
            ProjectSnapshot.is_active == True
        ).first()
    
    async def validate_snapshot(self, project_id: str) -> Tuple[bool, Optional[str]]:
        """
        验证快照是否仍然有效
        返回: (是否有效, 无效原因)
        """
        snapshot = await self.get_snapshot(project_id)
        
        if not snapshot:
            return False, "快照不存在"
        
        if not snapshot.is_locked:
            return False, "快照未锁定"
        
        # 检查配置是否有重大变更
        current_llm_status = await self._get_current_llm_status()
        
        if snapshot.llm_provider != current_llm_status.provider:
            return False, f"LLM提供商已变更: {snapshot.llm_provider} -> {current_llm_status.provider}"
        
        # 允许模型升级，但不允许降级
        if self._is_downgrade(snapshot.llm_model, current_llm_status.model):
            return False, f"LLM模型已降级: {snapshot.llm_model} -> {current_llm_status.model}"
        
        return True, None
    
    async def rollback_snapshot(self, project_id: str, target_level: int):
        """
        回滚到指定层级的配置
        用于降级处理
        """
        snapshot = await self.get_snapshot(project_id)
        
        if snapshot:
            snapshot.rollback_level = target_level
            snapshot.rollback_at = datetime.now()
            await self.db.commit()
            
            logger.info(f"项目{project_id}已回滚到Level {target_level}")
```

---

## 五、前端交互优化

### 5.1 模式选择引导

```typescript
// types/mode.ts
export enum ProcessMode {
  AI_SMART = 'ai_smart',
  SUBTITLE_ORGANIZED = 'subtitle_organized',
  QUICK_PREVIEW = 'quick_preview',
  RAW_TRANSCRIPT = 'raw_transcript'
}

export interface ModeInfo {
  mode: ProcessMode;
  name: string;
  shortName: string;
  description: string;
  badge?: string;
  badgeColor?: string;
  icon: string;
  recommended: boolean;
  requiresLLM: boolean;
  isDemo: boolean;
  capabilities: Capability[];
}

// 模式定义
export const MODE_CONFIG: Record<ProcessMode, ModeInfo> = {
  [ProcessMode.AI_SMART]: {
    mode: ProcessMode.AI_SMART,
    name: 'AI智能模式',
    shortName: 'AI智能',
    description: '使用AI深度理解视频内容，生成精彩片段、智能标题和主题合集',
    badge: '推荐',
    badgeColor: 'green',
    icon: '🤖',
    recommended: true,
    requiresLLM: true,
    isDemo: false,
    capabilities: ['subtitle', 'outline', 'highlights', 'titles', 'collections']
  },
  
  [ProcessMode.SUBTITLE_ORGANIZED]: {
    mode: ProcessMode.SUBTITLE_ORGANIZED,
    name: '字幕整理模式',
    shortName: '字幕整理',
    description: '将字幕标准化整理，包括说话人标注和标点恢复，无AI分析',
    badge: '免费',
    badgeColor: 'blue',
    icon: '📝',
    recommended: false,
    requiresLLM: false,
    isDemo: false,
    capabilities: ['subtitle']
  },
  
  [ProcessMode.QUICK_PREVIEW]: {
    mode: ProcessMode.QUICK_PREVIEW,
    name: '快速预览',
    shortName: '预览',
    description: '仅供效果预览，使用基础算法模拟切片，不可用于正式业务',
    badge: '演示',
    badgeColor: 'orange',
    icon: '👁️',
    recommended: false,
    requiresLLM: false,
    isDemo: true,
    capabilities: ['subtitle']
  },
  
  [ProcessMode.RAW_TRANSCRIPT]: {
    mode: ProcessMode.RAW_TRANSCRIPT,
    name: '原始转写',
    shortName: '原始',
    description: '仅输出语音转写的原始文本，无任何处理',
    badge: '基础',
    badgeColor: 'gray',
    icon: '📄',
    recommended: false,
    requiresLLM: false,
    isDemo: false,
    capabilities: ['subtitle']
  }
};
```

### 5.2 配置状态检测与引导

```typescript
// hooks/useLLMConfig.ts
export const useLLMConfig = () => {
  const queryClient = useQueryClient();
  
  // 查询LLM配置状态
  const { data: configStatus, isLoading } = useQuery({
    queryKey: ['llm-config-status'],
    queryFn: () => api.getLLMConfigStatus(),
    refetchInterval: 30000,  // 每30秒刷新
    staleTime: 10000
  });
  
  // 检测状态并返回建议
  const getModeRecommendation = useCallback((): ModeInfo => {
    if (!configStatus) {
      return MODE_CONFIG[ProcessMode.RAW_TRANSCRIPT];
    }
    
    switch (configStatus.status) {
      case 'configured':
        return MODE_CONFIG[ProcessMode.AI_SMART];
      
      case 'rate_limited':
        return MODE_CONFIG[ProcessMode.SUBTITLE_ORGANIZED];
      
      case 'invalid_key':
      case 'not_configured':
        return MODE_CONFIG[ProcessMode.SUBTITLE_ORGANIZED];
      
      default:
        return MODE_CONFIG[ProcessMode.RAW_TRANSCRIPT];
    }
  }, [configStatus]);
  
  // 判断是否显示引导
  const shouldShowGuide = useCallback((): boolean => {
    if (!configStatus) return false;
    return configStatus.status !== 'configured';
  }, [configStatus]);
  
  return {
    configStatus,
    isLoading,
    getModeRecommendation,
    shouldShowGuide
  };
};
```

### 5.3 模式选择弹窗组件

```typescript
// components/ModeSelectionModal.tsx
interface ModeSelectionModalProps {
  open: boolean;
  onClose: () => void;
  onSelectMode: (mode: ProcessMode) => void;
  llmStatus: LLMStatus | null;
}

export const ModeSelectionModal: React.FC<ModeSelectionModalProps> = ({
  open,
  onClose,
  onSelectMode,
  llmStatus
}) => {
  const { getModeRecommendation } = useLLMConfig();
  const recommendedMode = getModeRecommendation();
  
  // 根据LLM状态过滤可用模式
  const availableModes = Object.values(MODE_CONFIG).filter(mode => {
    if (mode.requiresLLM && !llmStatus?.is_available) {
      return false;
    }
    return true;
  });
  
  const renderModeCard = (mode: ModeInfo) => {
    const isRecommended = mode.mode === recommendedMode.mode;
    
    return (
      <Card
        key={mode.mode}
        hoverable
        onClick={() => onSelectMode(mode.mode)}
        style={{
          borderColor: isRecommended ? mode.badgeColor : undefined,
          borderWidth: isRecommended ? 2 : 1
        }}
        className={mode.isDemo ? 'demo-mode-card' : undefined}
      >
        <div className="mode-header">
          <span className="mode-icon">{mode.icon}</span>
          <span className="mode-name">{mode.name}</span>
          {mode.badge && (
            <Tag color={mode.badgeColor}>{mode.badge}</Tag>
          )}
        </div>
        
        <p className="mode-description">{mode.description}</p>
        
        {/* 能力列表 */}
        <div className="mode-capabilities">
          {mode.capabilities.map(cap => (
            <span key={cap} className="capability-tag">
              {getCapabilityLabel(cap)}
            </span>
          ))}
        </div>
        
        {/* 演示模式警告 */}
        {mode.isDemo && (
          <Alert
            type="warning"
            showIcon
            message="演示模式"
            description="此模式仅供预览，输出质量有限，不适合正式业务使用"
            style={{ marginTop: 12 }}
          />
        )}
        
        {isRecommended && (
          <div className="recommended-hint">
            ⭐ 系统推荐
          </div>
        )}
      </Card>
    );
  };
  
  return (
    <Modal
      title="选择处理模式"
      open={open}
      onCancel={onClose}
      footer={null}
      width={700}
    >
      <div className="mode-selection-content">
        {/* LLM状态提示 */}
        {llmStatus?.status !== 'configured' && (
          <Alert
            type="info"
            showIcon
            message="AI模型状态"
            description={
              <span>
                {getLLMStatusMessage(llmStatus?.status)}
                <Button 
                  type="link" 
                  size="small"
                  onClick={() => router.push('/settings')}
                >
                  去配置 →
                </Button>
              </span>
            }
            style={{ marginBottom: 16 }}
          />
        )}
        
        {/* 模式选择卡片 */}
        <div className="mode-cards">
          {availableModes.map(renderModeCard)}
        </div>
        
        {/* 帮助链接 */}
        <div className="help-section">
          <Button type="link" onClick={() => window.open('/help/modes')}>
            了解更多关于处理模式的区别 →
          </Button>
        </div>
      </div>
    </Modal>
  );
};
```

### 5.4 结果展示组件

```typescript
// components/ProcessingResult.tsx
interface ProcessingResultProps {
  result: PipelineResult;
  mode: ProcessMode;
}

export const ProcessingResult: React.FC<ProcessingResultProps> = ({
  result,
  mode
}) => {
  const modeInfo = MODE_CONFIG[mode];
  
  return (
    <div className="processing-result">
      {/* 演示模式警告 */}
      {result.is_demo && (
        <Alert
          type="warning"
          showIcon
          icon={<ExclamationCircle />}
          message="演示模式输出"
          description={
            <ul>
              <li>本输出仅供效果预览，不适合正式业务使用</li>
              <li>如需高质量输出，请使用"AI智能模式"</li>
            </ul>
          }
          style={{ marginBottom: 16 }}
        />
      )}
      
      {/* 质量等级指示 */}
      <div className="quality-indicator">
        <span>输出质量：</span>
        <Rate 
          disabled 
          value={result.quality_level} 
          count={5}
          character={({ index = 0 }) => index < result.quality_level ? '⭐' : '☆'}
        />
        <span className="quality-label">
          {getQualityLabel(result.quality_level)}
        </span>
      </div>
      
      {/* 模式标识 */}
      <div className="mode-badge">
        <Tag color={modeInfo.badgeColor}>
          {modeInfo.icon} {modeInfo.name}
        </Tag>
      </div>
      
      {/* 警告信息 */}
      {result.warnings?.length > 0 && (
        <div className="result-warnings">
          {result.warnings.map((warning, i) => (
            <Alert
              key={i}
              type="info"
              message={warning}
              showIcon
              style={{ marginBottom: 8 }}
            />
          ))}
        </div>
      )}
      
      {/* 实际输出内容 */}
      <div className="result-content">
        {/* 根据不同模式渲染不同内容 */}
      </div>
    </div>
  );
};
```

### 5.5 状态实时显示

```typescript
// components/ProcessingStatus.tsx
export const ProcessingStatus: React.FC<{ projectId: string }> = ({ projectId }) => {
  const { data: status } = useProjectStatus(projectId);
  const { data: llmStatus } = useLLMConfig();
  
  // 运行时LLM状态变化检测
  useEffect(() => {
    if (status?.current_mode === 'ai_smart' && !llmStatus?.is_available) {
      // LLM在处理过程中变为不可用
      message.warning({
        content: 'AI模型状态已变更，正在评估处理方案...',
        duration: 5
      });
    }
  }, [llmStatus]);
  
  return (
    <div className="processing-status">
      {/* 当前模式 */}
      <div className="status-mode">
        <Tag>{MODE_CONFIG[status?.current_mode]?.name || '未知'}</Tag>
        {status?.is_demo && <Tag color="orange">演示模式</Tag>}
      </div>
      
      {/* 质量指示 */}
      <div className="status-quality">
        <Tooltip title="输出质量等级">
          <Progress
            percent={(status?.quality_level || 0) * 20}
            steps={5}
            size="small"
            format={() => ''}
          />
        </Tooltip>
        <span className="quality-text">
          {getQualityLabel(status?.quality_level || 0)}
        </span>
      </div>
      
      {/* 降级提示 */}
      {status?.degraded && (
        <Alert
          type="warning"
          message="处理已自动降级"
          description={status.degradation_reason}
          style={{ marginTop: 8 }}
        />
      )}
    </div>
  );
};
```

---

## 六、异常处理机制

### 6.1 异常分类体系

```python
class PipelineError(Enum):
    """流水线错误枚举"""
    
    # LLM相关错误
    LLM_NOT_CONFIGURED = "llm_not_configured"
    LLM_INVALID_KEY = "llm_invalid_key"
    LLM_RATE_LIMITED = "llm_rate_limited"
    LLM_SERVICE_UNAVAILABLE = "llm_service_unavailable"
    LLM_CONNECTION_FAILED = "llm_connection_failed"
    LLM_TIMEOUT = "llm_timeout"
    LLM_RESPONSE_PARSE_ERROR = "llm_response_parse_error"
    
    # 处理错误
    SUBTITLE_GENERATION_FAILED = "subtitle_generation_failed"
    VIDEO_NOT_FOUND = "video_not_found"
    UNSUPPORTED_FORMAT = "unsupported_format"
    INSUFFICIENT_STORAGE = "insufficient_storage"
    PROCESSING_TIMEOUT = "processing_timeout"
    
    # 降级失败
    DEGRADATION_FAILED = "degradation_failed"
    ALL_STRATEGIES_FAILED = "all_strategies_failed"

@dataclass
class PipelineErrorContext:
    """错误上下文"""
    error: PipelineError
    message: str
    original_exception: Optional[Exception]
    step: str
    recoverable: bool
    degradation_target: Optional[int] = None
    user_action: Optional[str] = None
    suggestion: Optional[str] = None
```

### 6.2 异常处理策略

```python
class ErrorHandler:
    """
    统一异常处理器
    根据异常类型决定处理策略
    """
    
    # 错误到降级目标的映射
    DEGRADATION_MAP = {
        PipelineError.LLM_NOT_CONFIGURED: 2,  # 降级到字幕整理
        PipelineError.LLM_INVALID_KEY: 2,
        PipelineError.LLM_RATE_LIMITED: 2,
        PipelineError.LLM_SERVICE_UNAVAILABLE: 2,
        PipelineError.LLM_CONNECTION_FAILED: 2,
        PipelineError.LLM_TIMEOUT: 2,
        PipelineError.LLM_RESPONSE_PARSE_ERROR: 2,
        PipelineError.SUBTITLE_GENERATION_FAILED: 3,  # 降级到原始转写
    }
    
    # 不可降级的错误
    NON_RECOVERABLE = {
        PipelineError.VIDEO_NOT_FOUND,
        PipelineError.UNSUPPORTED_FORMAT,
        PipelineError.INSUFFICIENT_STORAGE,
    }
    
    def handle(
        self,
        error: Exception,
        current_strategy: PipelineStrategy,
        context: PipelineErrorContext
    ) -> ErrorHandlingResult:
        """
        处理异常
        返回: 是否已恢复、降级目标、用户提示
        """
        
        # Step 1: 分类错误
        error_type = self._classify_error(error)
        
        # Step 2: 检查是否可恢复
        if error_type in self.NON_RECOVERABLE:
            return ErrorHandlingResult(
                recovered=False,
                degraded=False,
                message=self._get_user_message(error_type),
                suggestion=self._get_suggestion(error_type)
            )
        
        # Step 3: 尝试降级
        target_level = self.DEGRADATION_MAP.get(error_type)
        
        if target_level and target_level > current_strategy.get_quality_level():
            # 可以降级
            return ErrorHandlingResult(
                recovered=True,
                degraded=True,
                degradation_target=target_level,
                message=f"正在降级处理: {self._get_degradation_message(target_level)}",
                warning=self._get_degradation_warning(target_level)
            )
        else:
            # 无法继续降级
            return ErrorHandlingResult(
                recovered=False,
                degraded=False,
                message="处理失败",
                suggestion=self._get_final_suggestion(error_type)
            )
    
    def _get_user_message(self, error_type: PipelineError) -> str:
        """获取用户友好的错误消息"""
        messages = {
            PipelineError.LLM_NOT_CONFIGURED: "AI模型未配置",
            PipelineError.LLM_RATE_LIMITED: "AI模型配额已用完",
            PipelineError.VIDEO_NOT_FOUND: "视频文件未找到",
            # ...
        }
        return messages.get(error_type, "处理遇到问题")
    
    def _get_degradation_warning(self, target_level: int) -> str:
        """获取降级警告"""
        warnings = {
            2: "将使用字幕整理模式，不包含AI分析功能",
            3: "将使用原始转写模式，仅输出字幕文件",
            4: "无法继续处理，请检查视频文件或配置"
        }
        return warnings.get(target_level, "")
```

### 6.3 多层兜底容错

```python
class ResilientPipelineExecutor:
    """
    带容错机制的流水线执行器
    确保每一层降级都有产出
    """
    
    def __init__(self, director: PipelineDirector):
        self.director = director
        self.error_handler = ErrorHandler()
        self.fallback_strategies = self._build_fallback_chain()
    
    def _build_fallback_chain(self) -> List[PipelineStrategy]:
        """构建降级策略链"""
        return [
            AISmartStrategy(config),           # Level 1
            SubtitleOrganizedStrategy(config), # Level 2
            RawTranscriptStrategy(config),     # Level 3
        ]
    
    async def execute_with_resilience(
        self,
        project_id: str,
        video_path: str,
        initial_strategy: PipelineStrategy,
        progress_callback: Optional[Callable] = None
    ) -> PipelineResult:
        """
        带容错的执行
        确保即使失败也有最小可用输出
        """
        
        current_strategy = initial_strategy
        attempts = []
        
        while current_strategy:
            try:
                # 记录尝试
                attempts.append({
                    'strategy': current_strategy.__class__.__name__,
                    'level': current_strategy.get_quality_level()
                })
                
                # 执行
                result = await current_strategy.execute(
                    video_path,
                    progress_callback=progress_callback
                )
                
                # 检查结果
                if result.status == "success":
                    # 添加尝试历史
                    result.attempts = attempts
                    return result
                
                # 处理失败
                error = result.errors[-1] if result.errors else Exception("Unknown")
                handling = self.error_handler.handle(
                    error,
                    current_strategy,
                    PipelineErrorContext(...)
                )
                
                if handling.recovered and handling.degraded:
                    # 降级到下一策略
                    current_strategy = self._get_next_strategy(
                        current_strategy,
                        handling.degradation_target
                    )
                    continue
                else:
                    # 无法恢复，尝试最小可用输出
                    return await self._emergency_fallback(
                        project_id,
                        video_path,
                        attempts,
                        handling
                    )
                    
            except Exception as e:
                logger.error(f"策略执行异常: {e}")
                
                # 尝试下一个策略
                current_strategy = self._get_next_strategy(
                    current_strategy,
                    current_strategy.get_quality_level() + 1
                )
                
                if not current_strategy:
                    return await self._emergency_fallback(
                        project_id,
                        video_path,
                        attempts,
                        handling
                    )
        
        # 理论上不会到这里
        return self._create_failure_result(attempts)
    
    async def _emergency_fallback(
        self,
        project_id: str,
        video_path: str,
        attempts: List[Dict],
        handling: ErrorHandlingResult
    ) -> PipelineResult:
        """
        紧急兜底
        确保至少返回用户可理解的结果
        """
        
        logger.error(f"所有策略均失败，启用紧急兜底")
        
        # 保存失败记录
        await self._save_failure_log(project_id, attempts, handling)
        
        return PipelineResult(
            status="failed",
            mode="emergency_fallback",
            outputs={
                "original_video": video_path,
                "subtitle_attempted": True,
                "attempts": attempts
            },
            warnings=[
                "处理未能完成",
                handling.message,
                handling.suggestion or ""
            ].filter(bool),
            errors=[
                f"已尝试 {len(attempts)} 种处理策略，均未能成功",
                handling.message
            ],
            quality_level=0,
            is_demo=False
        )
    
    def _get_next_strategy(
        self,
        current: PipelineStrategy,
        target_level: int
    ) -> Optional[PipelineStrategy]:
        """获取下一个降级策略"""
        
        for strategy in self.fallback_strategies:
            if strategy.get_quality_level() < current.get_quality_level():
                if target_level is None or strategy.get_quality_level() <= target_level:
                    return strategy
        
        return None
```

---

## 七、实施要点总结

### 7.1 后端关键改动

| 改动项 | 文件位置 | 改动类型 | 说明 |
|--------|---------|---------|------|
| 策略接口 | `backend/pipeline/strategies.py` | 新增 | 抽象基类定义 |
| AI策略 | `backend/pipeline/ai_strategy.py` | 新增 | LLM驱动的完整实现 |
| 字幕策略 | `backend/pipeline/subtitle_strategy.py` | 新增 | 本地字幕整理 |
| 预览策略 | `backend/pipeline/preview_strategy.py` | 新增 | 演示模式 |
| 统一调度 | `backend/pipeline/director.py` | 新增 | 策略编排和降级 |
| 状态监听 | `backend/core/llm_monitor.py` | 新增 | LLM运行时监控 |
| 快照管理 | `backend/services/snapshot_manager.py` | 新增 | 配置快照锁定 |
| 异常处理 | `backend/utils/error_handler.py` | 新增 | 统一错误处理 |
| 模型更新 | `backend/models/project.py` | 修改 | 添加快照字段 |
| API更新 | `backend/api/v1/projects.py` | 修改 | 支持模式选择 |

### 7.2 前端关键改动

| 改动项 | 文件位置 | 改动类型 | 说明 |
|--------|---------|---------|------|
| 类型定义 | `frontend/src/types/mode.ts` | 新增 | 模式枚举和配置 |
| 配置Hook | `frontend/src/hooks/useLLMConfig.ts` | 新增 | LLM状态检测 |
| 模式选择 | `frontend/src/components/ModeSelectionModal.tsx` | 新增 | 模式选择弹窗 |
| 结果展示 | `frontend/src/components/ProcessingResult.tsx` | 新增 | 结果状态显示 |
| 状态显示 | `frontend/src/components/ProcessingStatus.tsx` | 新增 | 实时状态 |
| 上传改造 | `frontend/src/components/UploadButton.tsx` | 修改 | 集成模式选择 |
| API更新 | `frontend/src/services/api.ts` | 修改 | 添加状态接口 |

### 7.3 数据库改动

```sql
-- 新增表：配置快照
CREATE TABLE project_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    mode VARCHAR(50) NOT NULL,
    llm_provider VARCHAR(50),
    llm_model VARCHAR(100),
    llm_api_key_encrypted TEXT,
    processing_config JSON,
    is_locked BOOLEAN DEFAULT TRUE,
    rollback_level INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    rollback_at DATETIME,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- 修改表：projects
ALTER TABLE projects ADD COLUMN current_mode VARCHAR(50);
ALTER TABLE projects ADD COLUMN quality_level INTEGER DEFAULT 0;
ALTER TABLE projects ADD COLUMN is_demo BOOLEAN DEFAULT FALSE;
ALTER TABLE projects ADD COLUMN degradation_history JSON;
```

---

## 八、降级执行流程图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     降级执行完整流程                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  [开始处理]                                                              │
│      │                                                                  │
│      ▼                                                                  │
│  ┌───────────────────────┐                                              │
│  │ Step 1: 创建快照      │                                              │
│  │ 锁定当前LLM配置       │                                              │
│  └───────────┬───────────┘                                              │
│              │                                                           │
│              ▼                                                           │
│  ┌───────────────────────┐                                              │
│  │ Step 2: AI智能模式    │                                              │
│  │ (Level 1)             │                                              │
│  └───────────┬───────────┘                                              │
│              │                                                           │
│      ┌───────┴───────┐                                                   │
│      │               │                                                   │
│      ▼               ▼                                                   │
│   [成功]          [失败]                                                  │
│      │               │                                                   │
│      │          ┌────┴────────────────┐                                 │
│      │          │ 分析错误类型         │                                 │
│      │          └─────────┬───────────┘                                 │
│      │                    │                                              │
│      │           ┌────────┴────────┐                                     │
│      │           │ 可降级?         │                                     │
│      │           └────────┬────────┘                                     │
│      │            ┌──────┴──────┐                                        │
│      │            │             │                                        │
│      │            ▼             ▼                                        │
│      │        [是]          [否]                                         │
│      │            │             │                                        │
│      │            ▼             ▼                                        │
│      │   ┌────────────────┐  [返回友好错误]                              │
│      │   │ Step 3: 字幕整理│                                              │
│      │   │ (Level 2)      │                                              │
│      │   └───────┬────────┘                                              │
│      │           │                                                       │
│      │    ┌──────┴──────┐                                               │
│      │    │             │                                               │
│      │    ▼             ▼                                               │
│      │ [成功]        [失败]                                              │
│      │    │             │                                               │
│      │    │       ┌─────┴─────────┐                                      │
│      │    │       │ 可降级?       │                                      │
│      │    │       └──────┬────────┘                                      │
│      │    │        ┌─────┴─────┐                                         │
│      │    │        │           │                                         │
│      │    │        ▼           ▼                                         │
│      │    │     [是]         [否]                                        │
│      │    │        │           │                                         │
│      │    │        ▼           ▼                                         │
│      │    │ ┌────────────┐  [返回友好错误]                               │
│      │    │ │Step 4:原始 │                                              │
│      │    │ │(Level 3)   │                                              │
│      │    │ └─────┬──────┘                                              │
│      │    │       │                                                     │
│      │    │ ┌─────┴─────┐                                               │
│      │    │ │           │                                               │
│      │    │ ▼           ▼                                               │
│      │    │[成功]    [失败]                                              │
│      │    │ │           │                                               │
│      │    │ │           ▼                                               │
│      │    │ │    [紧急兜底]                                              │
│      │    │ │           │                                               │
│      │    │ │           ▼                                               │
│      │    │ │    [友好错误提示]                                          │
│      │    │ │           │                                               │
│      │    │ ▼           ▼                                               │
│      │    ▼ ▼           ▼                                               │
│      │    │ │           │                                               │
│      │    ▼ ▼           ▼                                               │
│  [返回结果] │           │                                               │
│      │     │           │                                               │
│      └─────┴───────────┘                                                 │
│              │                                                           │
│              ▼                                                           │
│  ┌───────────────────────┐                                              │
│  │ [记录降级历史]         │                                              │
│  │ 保存到project记录      │                                              │
│  └───────────┬───────────┘                                              │
│              │                                                           │
│              ▼                                                           │
│         [结束]                                                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 九、总结

### 9.1 核心改进点

| 改进维度 | 原有方案 | 新方案 |
|---------|--------|--------|
| 评分逻辑 | 字幕长度+音频能量 | 废除，本地模式不提供切片 |
| 模式定位 | "本地降级"模糊不清 | 清晰区分正式vs演示 |
| 降级链路 | 无序降级 | Level 1-4有序降级，每层有产出 |
| 状态监听 | 仅上传前校验 | 运行时实时监控 |
| 代码架构 | 双代码路径冗余 | 策略模式统一调度 |
| 配置管理 | 无快照 | 配置快照锁定机制 |
| 用户引导 | 模糊文案 | 清晰模式名称+图标+警告 |
| 容错机制 | 直接报错 | 多层兜底+友好提示 |
| 预览功能 | 伪装切片 | 明确标注"仅演示" |

### 9.2 预期效果

```
用户场景1: LLM正常配置
┌─────────────────────────────────────┐
│ ✅ AI智能模式 → 完整高质量输出       │
│    大纲 + 精彩片段 + 智能标题 + 聚类  │
└─────────────────────────────────────┘

用户场景2: LLM配额用完
┌─────────────────────────────────────┐
│ ⚠️ 提示用户 → 选择字幕整理模式       │
│    标准化字幕 + 说话人标注          │
└─────────────────────────────────────┘

用户场景3: LLM未配置但想看效果
┌─────────────────────────────────────┐
│ ⚠️ 明确告知 → 快速预览（演示模式）   │
│    ⚠️ 仅供预览，不可正式使用         │
│    基础字幕整理                      │
└─────────────────────────────────────┘

用户场景4: 视频处理失败
┌─────────────────────────────────────┐
│ ❌ 降级尝试 → 仍失败                 │
│    友好错误提示 + 解决建议           │
│    记录降级历史供排查                │
└─────────────────────────────────────┘
```

---

*文档版本: v2.0*
*重构日期: 2026-05-16*
*状态: 已完成完整方案设计*
