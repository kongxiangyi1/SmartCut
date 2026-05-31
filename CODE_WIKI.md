# AutoClip Code Wiki

> **项目名称**: AutoClip - AI视频智能切片系统  
> **文档版本**: 2.0.0  
> **最后更新**: 2026-05-17  
> **项目地址**: https://github.com/zhouxiaoka/autoclip

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [后端模块详解](#3-后端模块详解)
4. [前端模块详解](#4-前端模块详解)
5. [核心处理管线](#5-核心处理管线)
6. [数据模型](#6-数据模型)
7. [配置与部署](#7-配置与部署)
8. [API接口](#8-api接口)
9. [依赖关系](#9-依赖关系)
10. [开发指南](#10-开发指南)

---

## 1. 项目概述

### 1.1 项目定位

AutoClip 是一款基于AI的智能视频切片处理系统，支持从YouTube/Bilibili下载视频、自动分析提取精彩片段、智能生成合集。系统采用前后端分离架构，提供直观的Web管理界面和强大的异步后端处理能力。

### 1.2 功能特点

| 特性 | 说明 |
|------|------|
| 多平台下载 | 支持YouTube、Bilibili视频一键下载，支持本地文件上传 |
| AI智能分析 | 基于大语言模型的视频内容理解和结构分析 |
| 自动切片 | 智能识别精彩片段，自动切割并评分排序 |
| 智能合集 | AI推荐或手动创建视频合集，自动聚类分组 |
| 实时进度 | WebSocket/Celery异步任务，实时反馈处理进度 |
| 降级策略 | AI分析不可用时自动切换至字幕整理/原始转写模式 |
| 多LLM支持 | 支持Dashscope、OpenAI、Gemini等6个提供商 |
| 语音识别 | FunASR中文优化 + Whisper多语言双引擎 |

### 1.3 技术栈总览

| 层级 | 技术选型 | 版本 |
|------|----------|------|
| **后端框架** | FastAPI + Uvicorn | Python 3.9+ |
| **任务队列** | Celery + Redis | Celery 5.x, Redis 7.x |
| **数据库** | SQLAlchemy + SQLite | 支持升级PostgreSQL |
| **前端框架** | React 18 + TypeScript 5.2 | Vite 5.0 |
| **UI组件库** | Ant Design 5.12 | 企业级组件 |
| **状态管理** | Zustand 4.4 | 轻量级全局状态 |
| **视频处理** | FFmpeg + yt-dlp | 并行多线程优化 |
| **AI服务** | 通义千问(Qwen) / 多提供商 | DashScope/OpenAI等 |
| **语音识别** | FunASR + Whisper | 中文优化+多语言 |

---

## 2. 系统架构

### 2.1 整体架构图

```
+-----------------------+      HTTP/WebSocket      +-----------------------+
|     前端层 (Frontend)  |  <------------------>   |    API网关层 (Backend) |
|  +-----------------+   |                         |  +-----------------+   |
|  |   React 18 + TS |   |                         |  |   FastAPI       |   |
|  |   Ant Design 5  |   |                         |  |   APIRouter     |   |
|  |   Zustand Store |   |                         |  |   CORS/Security |   |
|  +-----------------+   |                         |  +-----------------+   |
|  /  HomePage           |                         |  /projects/*         |
|  /project/:id          |                         |  /clips/*            |
|  /settings             |                         |  /collections/*      |
|  /processing           |                         |  /youtube/*          |
|  /upload               |                         |  /bilibili/*         |
+-----------------------+                         |  /settings/*         |
                                                  |  /tasks/*            |
                                                  |  /health/*           |
                                                  +----------+------------+
                                                             |
          +----------------------+---------------------------+----------------------+
          |                      |                           |                      |
          v                      v                           v                      v
+----------------+    +-------------------+    +-------------------+    +-------------------+
|   服务层        |    |     管线层         |    |     数据访问层      |    |      工具层        |
|  (Services)    |    |   (Pipeline)      |    |  (Repositories)   |    |     (Utils)       |
+----------------+    +-------------------+    +-------------------+    +-------------------+
|ProcessingOrche-|    |PipelineManager    |    |ProjectRepository  |    |SpeechRecognition  |
|strator (770行) |    |Step1~Step6 (6步)  |    |ClipRepository     |    |VideoProcessor     |
|ProjectService  |    |Fallback Strategy  |    |CollectionRepo     |    |LLMClient (6提供商)|
|ClipService     |    |Degradation Chain  |    +-------------------+    |FFmpegUtils        |
|CollectionSvc   |    +-------------------+             |               |SubtitleUtils      |
|TaskService     |            |                         |               |File/Path/TimeUtils|
|Bili/YTSvc      |            v                         v               |Encryption (Fernet)|
|UploadService   |    +-------------------+    +-------------------+    +-------------------+
|SettingsService |    |    提示词模板       |    |    数据持久层       |
|LLMService      |    |  (Prompt)         |    |  (Persistence)    |
|SpeechService   |    +-------------------+    +-------------------+
|VideoService    |    |outline_prompt.py  |    | SQLite (autoclip.db)|
|SubtitleService |    |timeline_prompt.py |    | Redis (Cache/Queue) |
|DataSyncService |    |scoring_prompt.py  |    | FileSystem (data/)  |
|SimpleTaskRunner|    |title_prompt.py    |    +-------------------+
+----------------+    |clustering_prompt  |
                      +-------------------+
                               |
                               v
                      +-------------------+
                      |   任务队列层        |
                      |  (Celery Workers)  |
                      +-------------------+
                      | Processing Queue  |
                      | Video Queue       |
                      | Upload Queue      |
                      | Celery Beat       |
                      +-------------------+
```

### 2.2 前后端分离设计

```
+-------------+         HTTP/WebSocket          +-------------+
|  Frontend   |  <----------------------------> |   Backend   |
|  (Vite)     |     baseURL: localhost:8090     |  (Uvicorn)  |
|  Port 3000  |                                 |  Port 8090  |
+-------------+                                 +-------------+
| React Router|                                 | FastAPI     |
| Axios (300s)|                                 | APIRouter   |
| Zustand     |                                 | SQLAlchemy  |
| WebSocket   |                                 | Celery      |
+-------------+                                 +-------------+
```

### 2.3 部署架构

```
+-------------------------------------------------------------+
|                    Docker Compose (生产)                     |
|  +---------+  +---------+  +---------+  +---------+         |
|  |  Redis  |  | AutoClip|  |  Celery |  |  Celery |  +----+|
|  |  :6379  |  | App:8000|  | Worker  |  |  Beat   |  |Flow||
|  +---------+  +----+----+  +----+----+  +----+----+  |:5555||
|                    |            |            |       +----+|
+-------------------------------------------------------------+

+-----------------------+        +-----------------------+
|    本地开发 (Local)    |        |   Windows开发 (Local)  |
|  +-----------------+  |        |  +-----------------+  |
|  | Redis :6379     |  |        |  | 无需Redis       |  |
|  | Backend :8090   |  |        |  | SimpleTaskRunner|  |
|  | Frontend :3000  |  |        |  | Backend :8090   |  |
|  | Celery Worker   |  |        |  | Frontend :3000  |  |
|  +-----------------+  |        |  +-----------------+  |
+-----------------------+        +-----------------------+
```

---

## 3. 后端模块详解

### 3.1 API层 (`backend/api/`)

共23个文件，使用FastAPI的APIRouter组织路由。

| 路由文件 | 端点前缀 | 核心端点 | 职责 |
|----------|----------|----------|------|
| `routes/projects.py` | `/projects` | CRUD、处理、重试、状态 | 项目全生命周期管理 |
| `routes/clips.py` | `/clips` | CRUD、标题生成、评分 | 视频片段管理 |
| `routes/collections.py` | `/collections` | CRUD、生成合集视频 | 合集管理 |
| `routes/youtube.py` | `/youtube` | 下载、解析 | YouTube视频下载 |
| `routes/bilibili.py` | `/bilibili` | 下载、解析、上传 | B站视频下载与上传 |
| `routes/settings.py` | `/settings` | 获取/更新配置、测试API密钥 | 系统设置管理 |
| `routes/health.py` | `/health` | 健康检查、服务状态 | 服务状态监控 |
| `routes/tasks.py` | `/tasks` | 任务状态、进度查询 | 异步任务管理 |
| `routes/upload.py` | `/upload` | 文件上传处理 | 视频文件上传 |
| `routes/files.py` | `/files` | 文件服务、静态资源 | 文件下载与访问 |
| `routes/subtitle_editor.py` | `/subtitle-editor` | 字幕编辑、保存 | 字幕在线编辑 |

### 3.2 核心层 (`backend/core/`)

共10个文件，提供应用基础设施。

| 文件 | 职责 | 关键类/函数 |
|------|------|------------|
| `config.py` | Pydantic Settings应用配置 | `Settings`类，环境变量自动加载 |
| `database.py` | SQLAlchemy数据库连接与会话 | `engine`, `SessionLocal`, `get_db()` |
| `llm_manager.py` | LLM服务管理（多提供商切换） | `LLMManager`, 提供商注册与切换 |
| `celery_app.py` | Celery应用配置 | `celery_app`, 队列路由、定时任务 |
| `dependencies.py` | FastAPI依赖注入 | `get_db`, `get_current_user`等 |
| `exceptions.py` | 自定义异常类 | `AutoClipException`, `LLMException`等 |
| `security.py` | 安全和认证 | JWT处理、密码哈希 |
| `middleware.py` | 中间件配置 | CORS、请求日志、异常处理 |
| `events.py` | 应用事件处理 | startup/shutdown事件 |
| `logging_config.py` | 日志配置 | 结构化日志、文件轮转 |

### 3.3 模型层 (`backend/models/`)

共6个ORM模型文件。

#### 3.3.1 `project.py` - 项目模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 项目唯一标识 |
| `name` | String | 项目名称 |
| `status` | Enum | 状态：pending/processing/completed/failed |
| `source_url` | String | 原始视频URL |
| `video_path` | String | 本地视频文件路径 |
| `video_duration` | Float | 视频时长（秒） |
| `current_step` | Integer | 当前处理步骤（0-6） |
| `progress` | Float | 整体进度（0-100） |
| `project_type` | Enum | 类型：knowledge/business/entertainment等 |
| `created_at` | DateTime | 创建时间 |
| `updated_at` | DateTime | 更新时间 |

#### 3.3.2 `clip.py` - 片段模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 片段唯一标识 |
| `project_id` | UUID | 所属项目ID（外键） |
| `title` | String | 片段标题 |
| `start_time` | Float | 开始时间（秒，保留毫秒） |
| `end_time` | Float | 结束时间（秒，保留毫秒） |
| `duration` | Float | 片段时长 |
| `final_score` | Float | AI精彩评分 |
| `video_path` | String | 切片视频路径 |
| `status` | Enum | 状态：pending/generated/failed |

#### 3.3.3 `collection.py` - 合集模型

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID | 合集唯一标识 |
| `project_id` | UUID | 所属项目ID（外键） |
| `collection_title` | String | 合集名称 |
| `description` | Text | 合集描述 |
| `clip_ids` | JSON | 包含的片段ID列表 |
| `collection_type` | Enum | 类型：ai_recommended/manual |

#### 3.3.4 其他模型

| 文件 | 说明 |
|------|------|
| `task.py` | 异步任务模型：task_type, status, progress, result |
| `bilibili_account.py` | B站账号模型：cookie、登录状态 |
| `upload_record.py` | 上传记录模型：平台、状态、返回信息 |

### 3.4 服务层 (`backend/services/`)

共17个文件，核心业务逻辑封装。

| 文件 | 职责 | 规模/特点 |
|------|------|----------|
| `processing_orchestrator.py` | **流程编排核心**，管理6步处理流程 | 770行，最核心的业务编排器 |
| `project_service.py` | 项目CRUD操作 | 项目全生命周期管理 |
| `clip_service.py` | 片段管理 | 创建、更新、删除、查询片段 |
| `collection_service.py` | 合集管理 | 合集CRUD、视频生成调用 |
| `task_service.py` | 任务管理 | 异步任务状态跟踪 |
| `bilibili_service.py` | B站下载和上传 | yt-dlp下载、B站API上传 |
| `youtube_service.py` | YouTube下载 | yt-dlp集成 |
| `upload_service.py` | 文件上传处理 | 多文件上传、路径管理 |
| `settings_service.py` | 设置管理 | LLM配置、处理参数持久化 |
| `llm_service.py` | LLM调用服务 | 统一LLM调用入口 |
| `speech_service.py` | 语音识别服务 | FunASR/Whisper调度 |
| `video_service.py` | 视频处理服务 | FFmpeg操作封装 |
| `subtitle_service.py` | 字幕处理服务 | SRT解析、生成、编辑 |
| `data_sync_service.py` | 数据同步服务 | 文件系统与数据库同步 |
| `simple_task_runner.py` | 简化任务运行器 | **不依赖Redis**，本地执行 |

### 3.5 管线层 (`backend/pipeline/`)

共9个文件，实现6步智能处理流程。

| 文件 | 步骤 | 职责 | 技术要点 |
|------|------|------|----------|
| `step1_outline.py` | Step 1 | 大纲提取：AI分析视频内容结构 | LLM分析字幕/转写文本 |
| `step2_timeline.py` | Step 2 | 时间线提取：定位话题时间区间 | 从SRT字幕匹配话题 |
| `step3_scoring.py` | Step 3 | 精彩评分：多维度评估片段质量 | AI评分 + 本地评分降级 |
| `step4_title.py` | Step 4 | 标题生成：为高分片段生成标题 | LLM生成吸引力标题 |
| `step5_clustering.py` | Step 5 | 聚类分组：相关片段组成合集 | scikit-learn聚类 |
| `step6_video.py` | Step 6 | 视频生成：FFmpeg切割、字幕合成 | 并行提取、字幕烧录 |
| `base.py` | - | 管线基类 | 抽象接口定义 |
| `fallback.py` | - | 降级策略 | 三层备选：AI→字幕→转写 |
| `pipeline_manager.py` | - | 管线管理器 | 步骤调度、状态管理 |

### 3.6 数据访问层 (`backend/repositories/`)

共3个文件，Repository模式封装数据访问。

| 文件 | 职责 |
|------|------|
| `project_repository.py` | 项目数据查询、过滤、分页 |
| `clip_repository.py` | 片段数据查询、按项目/评分过滤 |
| `collection_repository.py` | 合集数据查询、关联片段加载 |

### 3.7 数据校验层 (`backend/schemas/`)

共6个文件，Pydantic模型定义请求/响应结构。

| 文件 | 说明 |
|------|------|
| `project.py` | 项目请求/响应模型：ProjectCreate, ProjectResponse, ProjectList |
| `clip.py` | 片段请求/响应模型：ClipCreate, ClipResponse, ClipUpdate |
| `collection.py` | 合集请求/响应模型：CollectionCreate, CollectionResponse |
| `task.py` | 任务模型：TaskCreate, TaskResponse, TaskStatus |
| `settings.py` | 设置模型：LLMConfig, ProcessingConfig, SystemSettings |
| `common.py` | 通用模型：PaginatedResponse, ErrorResponse, StandardResponse |

### 3.8 工具层 (`backend/utils/`)

共18个文件，通用工具函数。

| 文件 | 职责 | 关键函数/类 |
|------|------|------------|
| `speech_recognition.py` | 语音识别 | `FunASRRecognizer`, `WhisperRecognizer` |
| `video_processor.py` | 视频处理 | `VideoProcessor` - FFmpeg并行提取 |
| `ffmpeg_utils.py` | FFmpeg工具 | 命令构建、进度解析 |
| `subtitle_utils.py` | 字幕处理 | SRT解析、时间转换 |
| `llm_client.py` | LLM客户端 | 支持Dashscope/OpenAI/Gemini等6个提供商 |
| `file_utils.py` | 文件操作 | 安全写入、路径检查 |
| `path_manager.py` | 路径管理 | 项目目录结构生成 |
| `time_utils.py` | 时间处理 | 秒转SRT时间格式 |
| `text_utils.py` | 文本处理 | 清洗、截断、格式化 |
| `scoring_utils.py` | 评分工具 | 本地评分算法 |
| `download_utils.py` | 下载工具 | 文件下载、进度回调 |
| `encryption_utils.py` | 加密工具 | Fernet对称加密 |
| `config_utils.py` | 配置工具 | 配置读写、验证 |

### 3.9 提示词模板 (`backend/prompt/`)

共5个文件，AI提示词集中管理。

| 文件 | 用途 |
|------|------|
| `outline_prompt.py` | 大纲提取提示词：引导LLM分析视频结构 |
| `timeline_prompt.py` | 时间线提示词：从字幕定位话题时间区间 |
| `scoring_prompt.py` | 评分提示词：多维度评估片段质量 |
| `title_prompt.py` | 标题生成提示词：生成吸引力标题 |
| `clustering_prompt.py` | 聚类提示词：将片段主题归类 |

### 3.10 入口文件 (`backend/main.py`)

```python
# 核心职责
- 创建FastAPI应用实例 (title="AutoClip API")
- 注册CORS中间件 (允许前端跨域)
- 注册所有API路由 (api/v1/下所有路由)
- 配置全局异常处理器
- 数据库初始化 (Base.metadata.create_all)
- 启动/关闭事件处理
```

---

## 4. 前端模块详解

### 4.1 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| React | 18.2 | UI框架 |
| TypeScript | 5.2 | 类型安全 |
| Vite | 5.0 | 构建工具 |
| Ant Design | 5.12 | UI组件库 |
| Zustand | 4.4 | 状态管理 |
| React Router | 6.x | 路由管理 |
| Axios | 1.x | HTTP客户端 |
| React Player | - | 视频播放 |

### 4.2 路由配置

| 路由 | 页面组件 | 职责 |
|------|----------|------|
| `/` | `HomePage.tsx` | 项目列表、上传入口、搜索过滤 |
| `/project/:id` | `ProjectDetailPage.tsx` | 项目详情、合集展示、片段管理 |
| `/settings` | `SettingsPage.tsx` | LLM配置、语音识别设置、B站账号 |
| `/processing` | `ProcessingPage.tsx` | 处理进度监控 |
| `/upload` | `UploadStatusPage.tsx` | 上传状态展示 |

### 4.3 组件架构 (`frontend/src/components/`)

共46个组件，按功能分类：

| 类别 | 组件 | 职责 |
|------|------|------|
| **布局** | Header | 顶部导航栏、全局操作 |
| **项目** | ProjectCard, ProjectList, ProjectFilter | 项目卡片、列表、过滤 |
| **片段** | ClipCard, ClipList, ClipPlayer | 片段卡片、列表、播放 |
| **合集** | CollectionCard, CollectionList | 合集卡片、列表 |
| **上传** | FileUpload, UploadModal, UploadProgress | 文件上传、进度 |
| **下载** | BilibiliDownload, BilibiliManager | B站下载、账号管理 |
| **编辑** | SubtitleEditor | 字幕在线编辑 |
| **状态** | RealTimeStatus, TaskProgress, ProcessingStatus | 实时状态、任务进度 |

### 4.4 页面职责 (`frontend/src/pages/`)

共9个页面：

| 页面 | 职责 |
|------|------|
| `HomePage.tsx` | 项目总览、新建项目、搜索过滤、批量操作 |
| `ProjectDetailPage.tsx` | 视频预览、合集列表、片段管理、重新处理 |
| `SettingsPage.tsx` | LLM提供商配置、API密钥设置、语音识别引擎选择、B站Cookie配置 |
| `ProcessingPage.tsx` | 实时处理进度、步骤详情、日志展示 |
| `UploadStatusPage.tsx` | 上传队列、上传进度、错误重试 |

### 4.5 状态管理

#### Zustand Store (`frontend/src/store/`)

| Store | 文件 | 规模 | 职责 |
|-------|------|------|------|
| 项目状态 | `useProjectStore.ts` | 454行 | 全局项目数据、当前选中、过滤条件 |

#### 简化进度 Store (`frontend/src/stores/`)

| Store | 文件 | 规模 | 职责 |
|-------|------|------|------|
| 进度状态 | `useSimpleProgressStore.ts` | 188行 | 处理进度、步骤状态、错误信息 |

### 4.6 API交互 (`frontend/src/services/`)

#### `api.ts` - 核心API客户端 (560行)

```typescript
// Axios配置
const apiClient = axios.create({
  baseURL: 'http://localhost:8090/api/v1',
  timeout: 300000,  // 300秒超时
});

// 特性
- 响应自动解包data字段
- 429限流自动处理
- 智能错误提示（中文）
- 请求/响应拦截器
```

| API模块 | 文件 | 职责 |
|---------|------|------|
| 项目API | `api.ts` (内部) | 项目CRUD、处理触发 |
| 上传API | `uploadApi.ts` | 分片上传、进度跟踪 |
| 字幕API | `subtitleEditorApi.ts` | 字幕获取、保存、编辑 |

### 4.7 自定义Hooks (`frontend/src/hooks/`)

共7个Hooks：

| Hook | 文件 | 职责 |
|------|------|------|
| `useWebSocket` | `useWebSocket.ts` | WebSocket连接管理、自动重连 |
| `useProjectPolling` | `useProjectPolling.ts` | 项目状态轮询 |
| `useTaskProgress` | `useTaskProgress.ts` | 任务进度跟踪 |
| `useLLMConfig` | `useLLMConfig.ts` | LLM配置获取与更新 |
| `useNotifications` | `useNotifications.ts` | 全局通知管理 |
| `useTaskStatus` | `useTaskStatus.ts` | 任务状态查询 |
| `useCollectionVideoDownload` | `useCollectionVideoDownload.ts` | 合集视频下载 |

---

## 5. 核心处理管线

### 5.1 6步处理流程

```
用户上传/下载视频
        |
        v
+-------------------+
|  Step 1: 素材准备  |  下载视频、音频提取、获取字幕
|  step1_outline.py |  如果无字幕 -> 语音识别(FunASR/Whisper)
+-------------------+
        |
        v
+-------------------+
|  Step 2: 内容分析  |  AI分析视频内容结构
|  step2_timeline.py|  从字幕/转写提取话题大纲
+-------------------+
        |
        v
+-------------------+
|  Step 3: 时间线提取|  从SRT字幕定位话题时间区间
|  step3_scoring.py |  建立话题->时间戳映射
+-------------------+
        |
        v
+-------------------+
|  Step 4: 精彩评分  |  多维度评估片段质量
|  step4_title.py   |  AI评分(内容/完整/吸引力)
+-------------------+
        |
        v
+-------------------+
|  Step 5: 标题生成  |  为高分片段生成吸引力标题
|  step5_clustering.|  阈值过滤(默认0.7)
+-------------------+
        |
        v
+-------------------+
|  Step 6: 视频生成  |  FFmpeg切割视频
|  step6_video.py   |  添加字幕烧录、生成合集
+-------------------+
        |
        v
    处理完成
```

### 5.2 降级策略 (`backend/pipeline/fallback.py`)

当LLM服务不可用时，系统自动降级：

```
+----------------------------------+
|      首选: AI智能分析模式         |
|  (AI Smart Strategy)             |
|  依赖: LLM可用                    |
|  质量: ★★★★★                     |
+----------------------------------+
              | LLM不可用
              v
+----------------------------------+
|      备选1: 字幕整理模式          |
|  (Subtitle Organized Strategy)   |
|  依赖: SRT字幕文件                |
|  质量: ★★★☆☆                     |
+----------------------------------+
              | 无字幕文件
              v
+----------------------------------+
|      备选2: 原始转写模式          |
|  (Raw Transcript Strategy)       |
|  依赖: 语音识别结果               |
|  质量: ★★☆☆☆                     |
+----------------------------------+
```

### 5.3 数据流向

```
+------------+     +-------------+     +-------------+     +------------+
|  Input     | --> |  Step 1-2   | --> |  Step 3-5   | --> |  Step 6    |
| Video/URL  |     | 分析&识别    |     | 评分&聚类    |     | 视频生成    |
+------------+     +-------------+     +-------------+     +------------+
      |                  |                   |                  |
      v                  v                   v                  v
  data/projects/    subtitle.srt        clips_metadata     clips/*.mp4
  video.mp4         outline.json        collections.json   collections/*.mp4
```

---

## 6. 数据模型

### 6.1 数据库表结构

#### projects 表

```sql
CREATE TABLE projects (
    id              UUID PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    project_type    VARCHAR(50),    -- knowledge/business/entertainment/...
    status          VARCHAR(50),    -- pending/processing/completed/failed
    source_url      VARCHAR(1000),  -- 原始视频URL
    video_path      VARCHAR(500),   -- 本地视频路径
    subtitle_path   VARCHAR(500),   -- 字幕文件路径
    video_duration  FLOAT,          -- 视频时长(秒)
    current_step    INTEGER,        -- 当前步骤 0-6
    progress        FLOAT,          -- 整体进度 0-100
    clip_count      INTEGER DEFAULT 0,
    collection_count INTEGER DEFAULT 0,
    settings        JSON,           -- 项目特定设置
    created_at      DATETIME,
    updated_at      DATETIME,
    completed_at    DATETIME
);
```

#### clips 表

```sql
CREATE TABLE clips (
    id              UUID PRIMARY KEY,
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    start_time      FLOAT,          -- 开始时间(秒)
    end_time        FLOAT,          -- 结束时间(秒)
    duration        FLOAT,          -- 片段时长
    final_score     FLOAT,          -- AI精彩评分
    content_score   FLOAT,          -- 内容质量分
    completeness_score FLOAT,       -- 完整性分
    attractiveness_score FLOAT,     -- 吸引力分
    video_path      VARCHAR(500),   -- 切片视频路径
    subtitle_path   VARCHAR(500),   -- 切片字幕路径
    status          VARCHAR(50),    -- pending/generated/failed
    tags            JSON,           -- 标签列表
    clip_metadata   JSON,           -- 元数据
    collection_ids  JSON,           -- 所属合集ID列表
    created_at      DATETIME,
    updated_at      DATETIME
);
```

#### collections 表

```sql
CREATE TABLE collections (
    id              UUID PRIMARY KEY,
    project_id      UUID REFERENCES projects(id) ON DELETE CASCADE,
    collection_title VARCHAR(255),
    description     TEXT,
    collection_type VARCHAR(50),    -- ai_recommended/manual
    clip_ids        JSON,           -- 包含的片段ID列表
    video_path      VARCHAR(500),   -- 合集视频路径
    cover_path      VARCHAR(500),   -- 封面图路径
    status          VARCHAR(50),
    created_at      DATETIME,
    updated_at      DATETIME
);
```

#### tasks 表

```sql
CREATE TABLE tasks (
    id              UUID PRIMARY KEY,
    project_id      UUID REFERENCES projects(id),
    task_type       VARCHAR(50),    -- processing/upload/download
    status          VARCHAR(50),    -- pending/running/success/failed
    progress        FLOAT,          -- 进度 0-100
    current_step    INTEGER,
    step_name       VARCHAR(100),
    result          JSON,
    error_message   TEXT,
    celery_task_id  VARCHAR(255),
    created_at      DATETIME,
    updated_at      DATETIME,
    completed_at    DATETIME
);
```

#### 其他表

| 表名 | 说明 |
|------|------|
| `bilibili_accounts` | B站账号：cookie、登录状态、过期时间 |
| `upload_records` | 上传记录：平台、状态、返回信息、错误日志 |

### 6.2 ORM模型关系

```
+----------+       +----------+       +-------------+
| projects |<----->|  clips   |<----->| collections |
+----------+ 1:N   +----------+  N:M  +-------------+
     | 1:N              | N:1
     v                  v
+----------+       +-------------+
|  tasks   |       | upload_records|
+----------+       +-------------+
```

---

## 7. 配置与部署

### 7.1 环境变量 (.env)

```bash
# 数据库配置
DATABASE_URL=sqlite:///./data/autoclip.db
# DATABASE_URL=postgresql://user:pass@localhost/autoclip

# Redis配置
REDIS_URL=redis://localhost:6379/0

# LLM API配置
API_DASHSCOPE_API_KEY=your_api_key_here
API_MODEL_NAME=qwen-plus
API_MAX_TOKENS=4096
API_TIMEOUT=30

# 处理参数
PROCESSING_CHUNK_SIZE=5000
PROCESSING_MIN_SCORE_THRESHOLD=0.7
PROCESSING_MAX_CLIPS_PER_COLLECTION=5
PROCESSING_MAX_RETRIES=3

# 简化模式（Windows开发推荐，无需Redis）
USE_SIMPLE_TASK_RUNNER=true

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=backend.log

# 环境配置
ENVIRONMENT=development
DEBUG=true
```

### 7.2 Docker Compose部署

```yaml
# docker-compose.yml 服务概览
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  app:
    build: .
    ports: ["8000:8000", "3000:3000"]
    depends_on: [redis]

  celery-worker:
    build: .
    command: celery -A backend.core.celery_app worker --concurrency=2
    depends_on: [redis]

  celery-beat:
    build: .
    command: celery -A backend.core.celery_app beat
    depends_on: [redis]

  flower:  # 可选：Celery监控
    image: mher/flower
    ports: ["5555:5555"]
```

### 7.3 Dockerfile构建

```
三阶段构建：
1. 前端构建 (Node 18)    -> 编译React静态文件
2. 后端依赖 (Python 3.9) -> 安装Python依赖
3. 最终镜像              -> 合并前后端，FFmpeg运行时

安全特性：
- 非root用户运行
- 最小化镜像层
- FFmpeg完整功能
```

### 7.4 本地开发启动

#### 后端启动

```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp env.example .env

# 启动Redis (Linux/macOS/有Redis时)
redis-server

# 启动后端服务
python -m uvicorn backend.main:app --reload --port 8090

# 启动Celery Worker (需要Redis)
celery -A backend.core.celery_app worker --loglevel=info

# 或使用简化任务运行器 (Windows/无Redis)
# USE_SIMPLE_TASK_RUNNER=true 已配置
```

#### 前端启动

```bash
cd frontend
npm install
npm run dev
```

#### 访问服务

| 服务 | URL |
|------|-----|
| 前端界面 | http://localhost:3000 |
| 后端API | http://localhost:8090 |
| API文档 | http://localhost:8090/docs |
| Flower监控 | http://localhost:5555 (Docker) |

---

## 8. API接口

### 8.1 项目接口 (`/api/v1/projects`)

| 方法 | 端点 | 功能 | 请求体/参数 |
|------|------|------|------------|
| POST | `/` | 创建项目 | `{name, source_url, project_type}` |
| GET | `/` | 项目列表 | `?page=1&size=20&status=&search=` |
| GET | `/{id}` | 项目详情 | - |
| PUT | `/{id}` | 更新项目 | `{name, description}` |
| DELETE | `/{id}` | 删除项目 | - |
| POST | `/{id}/process` | 开始处理 | `{settings}` |
| POST | `/{id}/retry` | 重试处理 | - |
| GET | `/{id}/status` | 处理状态 | - |
| POST | `/{id}/sync-data` | 同步数据 | - |
| POST | `/upload` | 上传视频 | `multipart/form-data` |

### 8.2 片段接口 (`/api/v1/clips`)

| 方法 | 端点 | 功能 |
|------|------|------|
| POST | `/` | 创建片段 |
| GET | `/` | 片段列表 (`?project_id=`)
| GET | `/{id}` | 片段详情 |
| PUT | `/{id}` | 更新片段 |
| DELETE | `/{id}` | 删除片段 |
| PATCH | `/{id}/title` | 更新标题 |
| POST | `/{id}/generate-title` | AI生成标题 |

### 8.3 合集接口 (`/api/v1/collections`)

| 方法 | 端点 | 功能 |
|------|------|------|
| POST | `/` | 创建合集 |
| GET | `/` | 合集列表 (`?project_id=`)
| GET | `/{id}` | 合集详情 |
| PUT | `/{id}` | 更新合集 |
| DELETE | `/{id}` | 删除合集 |
| POST | `/{id}/generate-video` | 生成合集视频 |

### 8.4 设置接口 (`/api/v1/settings`)

| 方法 | 端点 | 功能 |
|------|------|------|
| GET | `/` | 获取系统设置 |
| POST | `/` | 更新系统设置 |
| GET | `/secure` | 获取安全配置(密钥掩码) |
| POST | `/test-api-key` | 测试API密钥可用性 |
| GET | `/available-models` | 获取可用模型列表 |

### 8.5 其他接口

| 前缀 | 说明 |
|------|------|
| `/api/v1/youtube/*` | YouTube视频解析与下载 |
| `/api/v1/bilibili/*` | Bilibili视频解析、下载、上传 |
| `/api/v1/tasks/*` | 异步任务状态查询 |
| `/api/v1/health/*` | 服务健康检查 |
| `/api/v1/upload/*` | 文件上传 |
| `/api/v1/files/*` | 文件下载与静态资源 |
| `/api/v1/subtitle-editor/*` | 字幕编辑 |

---

## 9. 依赖关系

### 9.1 Python依赖 (requirements.txt)

共29项核心依赖：

| 类别 | 依赖包 | 用途 |
|------|--------|------|
| **Web框架** | fastapi, uvicorn, websockets | FastAPI应用、WebSocket支持 |
| **数据库** | sqlalchemy, alembic | ORM、数据库迁移 |
| **任务队列** | celery[redis], redis | Celery异步任务、Redis消息代理 |
| **数据校验** | pydantic, pydantic-settings | 数据模型、配置管理 |
| **文件处理** | python-multipart, aiohttp, aiofiles | 文件上传、异步HTTP |
| **视频下载** | yt-dlp | YouTube/Bilibili视频下载 |
| **字幕处理** | pysrt | SRT字幕解析与生成 |
| **AI/ML** | funasr | 语音识别(FunASR) |
| **机器学习** | scikit-learn | 片段聚类(KMeans等) |
| **安全** | python-jose, passlib, cryptography | JWT、密码哈希、加密 |

### 9.2 模块间依赖关系

```
main.py
  ├── core/
  │     ├── config.py       (基础，被所有模块依赖)
  │     ├── database.py     (被models, repositories依赖)
  │     ├── celery_app.py   (被services, tasks依赖)
  │     ├── llm_manager.py  (被services/llm_service依赖)
  │     └── ...
  ├── api/routes/
  │     ├── projects.py  --> services/project_service.py
  │     ├── clips.py     --> services/clip_service.py
  │     ├── settings.py  --> services/settings_service.py
  │     └── ...
  ├── services/
  │     ├── processing_orchestrator.py  --> pipeline/
  │     ├── project_service.py          --> repositories/
  │     ├── llm_service.py              --> utils/llm_client.py
  │     ├── speech_service.py           --> utils/speech_recognition.py
  │     └── video_service.py            --> utils/video_processor.py
  ├── pipeline/
  │     ├── step*.py       --> utils/llm_client.py, utils/scoring_utils.py
  │     ├── fallback.py    --> step*.py
  │     └── pipeline_manager.py --> step*.py
  ├── repositories/
  │     └── *.py          --> models/
  ├── models/
  │     └── *.py          --> core/database.py
  └── utils/
        └── *.py          --> core/config.py
```

---

## 10. 开发指南

### 10.1 目录结构速览

```
autoclip/
├── backend/
│   ├── api/                 # API路由层 (23文件)
│   │   └── routes/
│   ├── core/                # 核心配置层 (10文件)
│   ├── models/              # ORM模型层 (6文件)
│   ├── repositories/        # 数据访问层 (3文件)
│   ├── schemas/             # 数据校验层 (6文件)
│   ├── services/            # 业务服务层 (17文件)
│   ├── pipeline/            # 处理管线层 (9文件)
│   ├── utils/               # 工具函数层 (18文件)
│   ├── prompt/              # 提示词模板 (5文件)
│   └── main.py              # 应用入口
├── frontend/
│   ├── src/
│   │   ├── components/      # React组件 (46个)
│   │   ├── pages/           # 页面组件 (9个)
│   │   ├── services/        # API服务
│   │   ├── store/           # Zustand状态
│   │   ├── stores/          # 辅助状态
│   │   ├── hooks/           # 自定义Hooks (7个)
│   │   └── config/          # 配置文件
│   └── package.json
├── data/                    # 数据目录
│   ├── autoclip.db          # SQLite主数据库
│   ├── settings.json        # 系统设置
│   ├── projects/            # 项目文件存储
│   └── output/              # 输出目录
├── scripts/                 # 工具脚本 (27个)
├── docs/                    # 文档
├── docker-compose.yml       # Docker编排
├── Dockerfile               # 构建镜像
├── requirements.txt         # Python依赖
└── .env                     # 环境变量
```

### 10.2 常用命令

#### 后端开发

```bash
# 启动开发服务器 (带热重载)
python -m uvicorn backend.main:app --reload --port 8090

# 启动Celery Worker
python -m celery -A backend.core.celery_app worker --loglevel=info --concurrency=2

# 启动Celery Beat (定时任务)
python -m celery -A backend.core.celery_app beat --loglevel=info

# 数据库检查
python check_db.py

# 检查项目状态
python check_project_status.py <project_id>

# 修复卡住的项目
python fix_stuck_projects.py
```

#### 前端开发

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 类型检查
npx tsc --noEmit
```

#### Docker操作

```bash
# 启动全部服务
docker-compose up -d

# 查看日志
docker-compose logs -f app
docker-compose logs -f celery-worker

# 重启服务
docker-compose restart app

# 停止全部
docker-compose down
```

### 10.3 脚本工具 (`scripts/`)

| 脚本 | 用途 |
|------|------|
| `verify_all.py` | LLM异常降级完整验证 |
| `check_data_consistency.py` | 数据库与文件系统一致性检查 |
| `migrate_config.py` | 配置格式迁移 |
| `test_full_pipeline.py` | 完整6步流程测试 |
| `view_logs.py` | 格式化查看日志 |
| `start_pending_tasks.py` | 启动待处理任务 |

### 10.4 项目数据目录结构

```
data/
├── autoclip.db                 # SQLite主数据库
├── settings.json               # LLM和处理配置
├── user_config.json            # 用户配置
├── secure_config.json          # 加密配置 (Fernet)
├── product_keywords.yaml       # 产品关键词
└── projects/
    └── {project_id}/
        ├── video.mp4           # 原始视频
        ├── audio.wav           # 提取音频
        ├── subtitle.srt        # 字幕文件
        ├── outline.json        # AI大纲
        ├── timeline.json       # 时间线
        ├── clips/
        │   └── {clip_id}.mp4   # 切片视频
        ├── collections/
        │   └── {collection_id}.mp4  # 合集视频
        └── temp/               # 临时文件
```

### 10.5 视频分类配置

| 分类标识 | 说明 |
|----------|------|
| `default` | 通用视频内容处理 |
| `knowledge` | 科学、技术、历史、文化等知识类 |
| `entertainment` | 游戏、音乐、电影等娱乐内容 |
| `business` | 商业、创业、投资等商业内容 |
| `experience` | 个人经历、生活感悟等经验 |
| `opinion` | 时事评论、观点分析等评论 |
| `speech` | 公开演讲、讲座等演讲内容 |

### 10.6 故障排查

| 问题 | 排查步骤 | 解决方案 |
|------|----------|----------|
| 端口占用 | `netstat -ano \| findstr :8090` | 结束占用进程或修改端口 |
| Redis连接失败 | `redis-cli ping` | 启动Redis或启用`USE_SIMPLE_TASK_RUNNER` |
| FFmpeg未找到 | `ffmpeg -version` | 安装FFmpeg并加入PATH |
| LLM调用失败 | `python test_llm_connection.py` | 检查API密钥和网络 |
| 视频生成失败 | 检查`clip_ids`字段 | 确保合包含`clip_ids` |
| 项目卡住 | `python check_stuck_project.py` | `python fix_stuck_projects.py` |

---

## 附录 A: 标准响应格式

```typescript
// 统一API响应
interface StandardResponse<T> {
  code: number;        // 200成功，其他为错误码
  message: string;     // 提示信息
  data: T;            // 业务数据
}

// 分页响应
interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}
```

## 附录 B: 错误代码

| 错误代码 | 说明 | 解决方案 |
|----------|------|----------|
| `AUTOCLIP_001` | 项目不存在 | 检查项目ID |
| `AUTOCLIP_002` | 视频文件不存在 | 检查视频路径 |
| `AUTOCLIP_003` | 字幕文件不存在 | 检查字幕路径或自动生成 |
| `AUTOCLIP_004` | LLM调用失败 | 检查API密钥和网络 |
| `AUTOCLIP_005` | 视频处理失败 | 检查FFmpeg安装和格式 |
| `AUTOCLIP_006` | 数据库操作失败 | 检查数据库连接和权限 |

---

**文档结束**

> 如有问题，请联系: kxy_1@163.com
