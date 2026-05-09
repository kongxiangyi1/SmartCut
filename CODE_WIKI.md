# AutoClip Code Wiki - AI视频智能切片系统

## 目录
1. [项目概述](#项目概述)
2. [系统架构](#系统架构)
3. [主要模块](#主要模块)
4. [数据模型](#数据模型)
5. [处理流水线](#处理流水线)
6. [依赖关系](#依赖关系)
7. [API说明](#api说明)
8. [运行方式](#运行方式)
9. [开发指南](#开发指南)

---

## 项目概述

### 简介
AutoClip是一个基于AI的智能视频切片处理系统，能够自动从YouTube、B站等平台下载视频，通过AI分析提取精彩片段，并智能生成合集。系统采用现代化的前后端分离架构，提供直观的Web界面和强大的后端处理能力。

### 核心特性
- 🎬 **多平台支持**：YouTube、B站视频一键下载，支持本地文件上传
- 🤖 **AI智能分析**：基于通义千问大语言模型的视频内容理解
- ✂️ **自动切片**：智能识别精彩片段并自动切割，支持多种视频分类
- 📚 **智能合集**：AI推荐和手动创建视频合集，支持拖拽排序
- 🚀 **实时处理**：异步任务队列，实时进度反馈，WebSocket通信
- 🎨 **现代界面**：React + TypeScript + Ant Design，响应式设计
- 📱 **移动端支持**（开发中）：响应式设计，正在完善移动端体验
- 🔐 **账号管理**（开发中）：支持B站多账号管理，自动健康检查
- 📊 **数据统计**：完整的项目管理和数据统计功能
- 🛠️ **易于部署**：一键启动脚本，Docker支持，详细文档
- 📤 **B站上传**（开发中）：自动上传切片视频到B站
- ✏️ **字幕编辑**（开发中）：可视化字幕编辑和同步功能

---

## 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户界面层                                 │
│                        (React + TypeScript)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │  首页        │  │ 项目详情页   │  │ 设置页      │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
│         │                  │                  │                   │
│         └──────────────────┴──────────────────┘                   │
│                            │                                       │
└────────────────────────────┼───────────────────────────────────────┘
                             │ HTTP/WebSocket
┌────────────────────────────┼───────────────────────────────────────┐
│                        后端服务层                                  │
│                       (FastAPI + Python)                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐   │
│  │    API路由      │  │    服务层        │  │  数据存储    │   │
│  └──────────────────┘  └──────────────────┘  └──────────────┘   │
│         │                      │                    │            │
│         └──────────────────────┼────────────────────┘            │
└────────────────────────────────┼─────────────────────────────────┘
                                 │
┌────────────────────────────────┼─────────────────────────────────┐
│                          任务处理层                              │
│                      (Celery + Redis)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │  处理队列    │  │  视频处理    │  │  AI分析      │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
└────────────────────────────────┼─────────────────────────────────┘
                                 │
┌────────────────────────────────┼─────────────────────────────────┐
│                         AI服务层                                │
│              (通义千问LLM + 语音识别模型)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │  大纲提取    │  │  时间线分析  │  │  内容评分    │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
└────────────────────────────────┼─────────────────────────────────┘
                                 │
┌────────────────────────────────┼─────────────────────────────────┐
│                         数据存储层                               │
│              (SQLite + 文件系统 + Redis)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │  项目数据    │  │  切片数据    │  │  合集数据    │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
└───────────────────────────────────────────────────────────────────┘
```

### 目录结构

```
autoclip/
├── backend/                      # 后端代码
│   ├── api/                     # API路由
│   │   └── v1/                  # API v1版本
│   │       ├── projects.py      # 项目管理API
│   │       ├── clips.py         # 视频片段API
│   │       ├── collections.py   # 合集管理API
│   │       ├── youtube.py       # YouTube下载API
│   │       ├── bilibili.py      # B站下载API
│   │       └── ...              # 其他API模块
│   ├── core/                    # 核心配置
│   │   ├── config.py            # 系统配置
│   │   ├── database.py          # 数据库配置
│   │   ├── celery_app.py        # Celery配置
│   │   ├── path_utils.py        # 路径工具
│   │   └── websocket_manager.py # WebSocket管理
│   ├── models/                  # 数据模型
│   │   ├── base.py              # 基础模型
│   │   ├── project.py           # 项目模型
│   │   ├── clip.py              # 切片模型
│   │   ├── collection.py        # 合集模型
│   │   ├── task.py              # 任务模型
│   │   └── bilibili.py          # B站账号模型
│   ├── services/                # 业务逻辑层
│   │   ├── project_service.py   # 项目服务
│   │   ├── clip_service.py      # 切片服务
│   │   ├── collection_service.py# 合集服务
│   │   ├── processing_service.py# 处理服务
│   │   └── ...                  # 其他服务
│   ├── pipeline/                # 处理流水线
│   │   ├── step1_outline.py     # 大纲提取
│   │   ├── step2_timeline.py    # 时间线提取
│   │   ├── step3_scoring.py     # 内容评分
│   │   ├── step4_title.py       # 标题生成
│   │   ├── step5_clustering.py  # 内容聚类
│   │   └── step6_video.py       # 视频生成
│   ├── utils/                   # 工具函数
│   │   ├── llm_client.py        # LLM客户端
│   │   ├── text_processor.py    # 文本处理
│   │   ├── video_processor.py   # 视频处理
│   │   ├── speech_recognizer.py # 语音识别
│   │   └── ...                  # 其他工具
│   ├── tasks/                   # Celery任务
│   │   ├── processing.py        # 处理任务
│   │   ├── import_processing.py # 导入任务
│   │   └── ...                  # 其他任务
│   ├── schemas/                 # Pydantic模式
│   ├── repositories/            # 数据仓储
│   └── main.py                  # 应用入口
├── frontend/                    # 前端代码
│   ├── src/
│   │   ├── components/          # React组件
│   │   ├── pages/               # 页面组件
│   │   ├── services/            # API服务
│   │   ├── stores/              # 状态管理(Zustand)
│   │   └── App.tsx
│   └── package.json
├── prompt/                      # 提示词模板
├── docs/                        # 文档
├── data/                        # 数据存储
│   ├── projects/                # 项目数据
│   ├── uploads/                 # 上传文件
│   ├── temp/                    # 临时文件
│   └── output/                  # 输出文件
├── docker-compose.yml           # Docker编排
├── requirements.txt             # Python依赖
└── README.md
```

---

## 主要模块

### 1. 后端模块

#### FastAPI应用入口 (`backend/main.py`)

**职责**：
- 创建FastAPI应用实例
- 配置CORS中间件
- 注册API路由
- 管理启动和关闭事件
- 提供静态文件服务（前端构建产物）

**核心功能**：
```python
# 关键端点
GET /api/v1/video-categories  # 获取视频分类
GET /docs                      # Swagger UI
GET /redoc                     # Redoc UI
```

#### 配置管理 (`backend/core/config.py`)

**职责**：
- 集中管理应用所有配置项
- 环境变量加载
- 路径管理
- 配置验证

**关键配置类**：
- `Settings`: 主应用设置（基于Pydantic）
- 数据库配置（SQLite）
- Redis配置
- LLM API配置（通义千问）
- 处理配置（分块大小、评分阈值等）

**关键函数**：
- `get_project_root()`: 获取项目根目录
- `get_data_directory()`: 获取数据目录
- `get_uploads_directory()`: 获取上传目录
- `get_api_key()`: 获取API密钥

#### 数据库管理 (`backend/core/database.py`)

**职责**：
- SQLAlchemy引擎创建
- Session工厂管理
- 数据库表创建
- 依赖注入

**技术栈**：
- SQLAlchemy ORM
- SQLite（默认，可升级到PostgreSQL）

#### WebSocket管理 (`backend/core/websocket_manager.py`)

**职责**：
- WebSocket连接管理
- 实时消息推送
- 连接状态跟踪
- 广播功能

#### 路径工具 (`backend/core/path_utils.py`)

**职责**：
- 统一路径管理
- 项目目录结构创建
- 路径验证和规范化

---

### 2. 数据模型模块

#### 基础模型 (`backend/models/base.py`)

**职责**：
- 提供基础模型类
- 统一ID、时间戳字段
- 通用工具方法

**字段**：
- `id`: UUID主键
- `created_at`: 创建时间
- `updated_at`: 更新时间

#### 项目模型 (`backend/models/project.py`)

**核心实体**：

```python
class Project(BaseModel):
    """项目模型"""
    # 基本信息
    name: str                    # 项目名称
    description: Optional[str]   # 项目描述
    
    # 状态信息
    status: str                  # 项目状态：pending/processing/completed/failed
    
    # 项目类型
    project_type: str            # 项目类型：default/knowledge/entertainment/business等
    
    # 文件路径
    video_path: Optional[str]    # 视频文件路径
    subtitle_path: Optional[str] # 字幕文件路径
    video_duration: Optional[int]# 视频时长（秒）
    thumbnail: Optional[str]     # 缩略图（base64）
    
    # 配置和元数据
    processing_config: Optional[JSON]  # 处理配置
    project_metadata: Optional[JSON]   # 项目元数据
    completed_at: Optional[datetime]   # 完成时间
    
    # 关系
    clips: List[Clip]            # 关联切片
    collections: List[Collection]# 关联合集
    tasks: List[Task]            # 关联任务
```

**ProjectType枚举**：
- `default`: 默认类型
- `knowledge`: 知识科普
- `entertainment`: 娱乐内容
- `business`: 商业内容
- `experience`: 经验分享
- `opinion`: 观点评论
- `speech`: 演讲内容
- `content_review`: 内容解说

**ProjectStatus枚举**：
- `pending`: 等待处理
- `processing`: 处理中
- `completed`: 已完成
- `failed`: 处理失败

#### 切片模型 (`backend/models/clip.py`)

**核心实体**：

```python
class Clip(BaseModel):
    """切片模型"""
    # 基本信息
    title: str                   # 切片标题
    description: Optional[str]   # 切片描述
    
    # 状态
    status: ClipStatus           # 状态：pending/processing/completed/failed
    
    # 时间信息
    start_time: int              # 开始时间（秒）
    end_time: int                # 结束时间（秒）
    duration: int                # 时长（秒）
    
    # 评分
    score: Optional[float]       # 精彩度评分（0-1）
    recommendation_reason: Optional[str] # 推荐理由
    
    # 文件
    video_path: Optional[str]    # 切片视频路径
    thumbnail_path: Optional[str]# 缩略图路径
    
    # 元数据
    processing_step: Optional[int] # 当前处理步骤
    tags: Optional[List[str]]     # 标签
    clip_metadata: Optional[JSON]  # 完整元数据
    
    # 关系
    project_id: str              # 所属项目ID
    project: Project             # 所属项目
    collections: List[Collection]# 所属合集（多对多）
```

#### 合集模型 (`backend/models/collection.py`)

**核心实体**：

```python
class Collection(BaseModel):
    """合集模型"""
    # 基本信息
    name: str                    # 合集名称
    description: Optional[str]   # 合集描述
    
    # 关系
    project_id: str              # 所属项目ID
    project: Project             # 所属项目
    clips: List[Clip]            # 包含切片（多对多）
    
    # 元数据
    collection_metadata: Optional[JSON] # 合集元数据
    export_path: Optional[str]   # 导出视频路径
    thumbnail_path: Optional[str]# 缩略图路径
```

#### 任务模型 (`backend/models/task.py`)

**核心实体**：

```python
class Task(BaseModel):
    """任务模型"""
    # 基本信息
    task_type: str               # 任务类型
    status: TaskStatus           # 任务状态
    
    # 进度
    progress: float              # 进度（0-100）
    current_step: Optional[int]  # 当前步骤
    step_name: Optional[str]     # 步骤名称
    
    # 关联
    project_id: str              # 所属项目ID
    project: Project             # 所属项目
    
    # 元数据
    task_metadata: Optional[JSON]# 任务元数据
    error_message: Optional[str] # 错误信息
```

---

### 3. 服务层模块

#### 项目服务 (`backend/services/project_service.py`)

**职责**：
- 项目CRUD操作
- 项目创建和更新
- 项目状态管理
- 项目删除（含文件清理）
- 项目查询和分页

**核心方法**：
```python
create_project(project_data: ProjectCreate) -> Project
update_project(project_id: str, project_data: ProjectUpdate) -> Optional[Project]
get_project_with_stats(project_id: str) -> Optional[ProjectResponse]
get_projects_paginated(pagination: PaginationParams, filters: Optional[ProjectFilter]) -> ProjectListResponse
start_project_processing(project_id: str) -> bool
complete_project(project_id: str) -> bool
delete_project_with_files(project_id: str) -> bool
```

#### 处理服务 (`backend/services/processing_service.py`)

**职责**：
- 视频处理流程协调
- 步骤执行和状态跟踪
- 进度更新和通知
- 错误处理和重试

**核心方法**：
```python
start_processing(project_id: str, input_video: Path, input_srt: Optional[Path])
get_processing_status(project_id: str, task_id: str)
resume_processing(project_id: str, start_step: str)
```

#### 切片服务 (`backend/services/clip_service.py`)

**职责**：
- 切片CRUD操作
- 切片元数据管理
- 切片查询和过滤

#### 合集服务 (`backend/services/collection_service.py`)

**职责**：
- 合集CRUD操作
- 合集切片管理
- 拖拽排序支持
- 合集视频生成

---

### 4. API路由模块

#### 项目API (`backend/api/v1/projects.py`)

**主要端点**：

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | /api/v1/projects/upload | 上传视频创建项目 |
| POST | /api/v1/projects | 创建新项目 |
| GET | /api/v1/projects | 获取项目列表（分页） |
| GET | /api/v1/projects/{project_id} | 获取项目详情 |
| PUT | /api/v1/projects/{project_id} | 更新项目 |
| DELETE | /api/v1/projects/{project_id} | 删除项目 |
| POST | /api/v1/projects/{project_id}/process | 开始处理项目 |
| POST | /api/v1/projects/{project_id}/retry | 重试处理项目 |
| GET | /api/v1/projects/{project_id}/status | 获取处理状态 |
| POST | /api/v1/projects/{project_id}/sync-data | 同步项目数据 |

#### 切片API (`backend/api/v1/clips.py`)

**主要端点**：

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | /api/v1/clips | 获取切片列表 |
| GET | /api/v1/clips/{clip_id} | 获取切片详情 |
| PUT | /api/v1/clips/{clip_id} | 更新切片 |
| GET | /api/v1/projects/{project_id}/clips/{clip_id} | 获取切片视频 |

#### 合集API (`backend/api/v1/collections.py`)

**主要端点**：

| 方法 | 端点 | 描述 |
|------|------|------|
| GET | /api/v1/collections | 获取合集列表 |
| POST | /api/v1/collections | 创建合集 |
| GET | /api/v1/collections/{collection_id} | 获取合集详情 |
| PUT | /api/v1/collections/{collection_id} | 更新合集 |
| DELETE | /api/v1/collections/{collection_id} | 删除合集 |
| PATCH | /api/v1/collections/{collection_id}/reorder | 重新排序合集切片 |
| POST | /api/v1/collections/{collection_id}/generate | 生成合集视频 |

#### YouTube API (`backend/api/v1/youtube.py`)

**主要端点**：

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | /api/v1/youtube/parse | 解析YouTube视频信息 |
| POST | /api/v1/youtube/download | 下载YouTube视频 |

#### B站API (`backend/api/v1/bilibili.py`)

**主要端点**：

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | /api/v1/bilibili/parse | 解析B站视频信息 |
| POST | /api/v1/bilibili/download | 下载B站视频 |

---

### 5. 前端模块

#### 前端技术栈

**核心依赖**：
- React 18.2: UI框架
- TypeScript 5.2: 类型安全
- Ant Design 5.12: UI组件库
- React Router 6.20: 路由管理
- Zustand 4.4: 状态管理
- Axios 1.6: HTTP客户端
- React Player 2.13: 视频播放器
- React Beautiful DND 13.1: 拖拽排序

#### 页面组件

1. **首页** (`frontend/src/pages/HomePage.tsx`)
   - 项目列表展示
   - 新建项目入口
   - 项目搜索和过滤

2. **项目详情页** (`frontend/src/pages/ProjectDetailPage.tsx`)
   - 项目信息展示
   - 切片列表
   - 合集管理
   - 视频播放器
   - 处理进度显示

3. **设置页** (`frontend/src/pages/SettingsPage.tsx`)
   - 系统配置
   - B站账号管理
   - API密钥配置

#### 核心组件

- `ProjectCard`: 项目卡片组件
- `ClipCard`: 切片卡片组件
- `CollectionCard`: 合集卡片组件
- `UploadModal`: 上传模态框
- `RealTimeStatus`: 实时状态组件
- `UnifiedStatusBar`: 统一状态栏

#### 状态管理 (`frontend/src/stores/`)

使用Zustand进行状态管理：
- 项目状态
- 处理进度状态
- 用户界面状态

#### API服务 (`frontend/src/services/api.ts`)

封装Axios调用，提供类型安全的API访问：
- 项目API
- 切片API
- 合集API
- 处理API

---

## 数据模型

### 实体关系图

```
┌──────────┐    1:N    ┌──────────┐
│ Project  ├──────────>│   Clip   │
└─────┬────┘           └────┬─────┘
      │                     │
      │ 1:N                 │ N:M
      │                     │
      v                     v
┌──────────┐           ┌──────────────┐
│  Task    │           │  Collection  │
└──────────┘           └──────────────┘
                              ↑
                              │ 1:N
                              │
                      ┌──────────┐
                      │Bilibili  │
                      │  Account │
                      └──────────┘
```

### 数据库表结构

#### projects表
| 字段 | 类型 | 约束 | 描述 |
|------|------|------|------|
| id | VARCHAR(36) | PRIMARY KEY | UUID主键 |
| name | VARCHAR(255) | NOT NULL | 项目名称 |
| description | TEXT | NULLABLE | 项目描述 |
| status | VARCHAR(50) | NOT NULL DEFAULT 'pending' | 项目状态 |
| project_type | VARCHAR(50) | NOT NULL DEFAULT 'default' | 项目类型 |
| video_path | VARCHAR(500) | NULLABLE | 视频文件路径 |
| subtitle_path | VARCHAR(500) | NULLABLE | 字幕文件路径 |
| video_duration | INTEGER | NULLABLE | 视频时长（秒） |
| thumbnail | TEXT | NULLABLE | 缩略图（base64） |
| processing_config | JSON | NULLABLE | 处理配置 |
| project_metadata | JSON | NULLABLE | 项目元数据 |
| completed_at | DATETIME | NULLABLE | 完成时间 |
| created_at | DATETIME | NOT NULL | 创建时间 |
| updated_at | DATETIME | NOT NULL | 更新时间 |

#### clips表
| 字段 | 类型 | 约束 | 描述 |
|------|------|------|------|
| id | VARCHAR(36) | PRIMARY KEY | UUID主键 |
| title | VARCHAR(255) | NOT NULL | 切片标题 |
| description | TEXT | NULLABLE | 切片描述 |
| status | VARCHAR(50) | NOT NULL DEFAULT 'pending' | 切片状态 |
| start_time | INTEGER | NOT NULL | 开始时间（秒） |
| end_time | INTEGER | NOT NULL | 结束时间（秒） |
| duration | INTEGER | NOT NULL | 时长（秒） |
| score | FLOAT | NULLABLE | 精彩度评分 |
| recommendation_reason | TEXT | NULLABLE | 推荐理由 |
| video_path | VARCHAR(500) | NULLABLE | 切片视频路径 |
| thumbnail_path | VARCHAR(500) | NULLABLE | 缩略图路径 |
| processing_step | INTEGER | NULLABLE | 当前处理步骤 |
| tags | JSON | NULLABLE | 标签 |
| clip_metadata | JSON | NULLABLE | 切片元数据 |
| project_id | VARCHAR(36) | FOREIGN KEY | 所属项目ID |
| created_at | DATETIME | NOT NULL | 创建时间 |
| updated_at | DATETIME | NOT NULL | 更新时间 |

#### collections表
| 字段 | 类型 | 约束 | 描述 |
|------|------|------|------|
| id | VARCHAR(36) | PRIMARY KEY | UUID主键 |
| name | VARCHAR(255) | NOT NULL | 合集名称 |
| description | TEXT | NULLABLE | 合集描述 |
| collection_metadata | JSON | NULLABLE | 合集元数据 |
| export_path | VARCHAR(500) | NULLABLE | 导出视频路径 |
| thumbnail_path | VARCHAR(500) | NULLABLE | 缩略图路径 |
| project_id | VARCHAR(36) | FOREIGN KEY | 所属项目ID |
| created_at | DATETIME | NOT NULL | 创建时间 |
| updated_at | DATETIME | NOT NULL | 更新时间 |

#### clip_collection关联表
| 字段 | 类型 | 约束 | 描述 |
|------|------|------|------|
| clip_id | VARCHAR(36) | FOREIGN KEY | 切片ID |
| collection_id | VARCHAR(36) | FOREIGN KEY | 合集ID |

#### tasks表
| 字段 | 类型 | 约束 | 描述 |
|------|------|------|------|
| id | VARCHAR(36) | PRIMARY KEY | UUID主键 |
| task_type | VARCHAR(50) | NOT NULL | 任务类型 |
| status | VARCHAR(50) | NOT NULL DEFAULT 'pending' | 任务状态 |
| progress | FLOAT | NOT NULL DEFAULT 0.0 | 进度 |
| current_step | INTEGER | NULLABLE | 当前步骤 |
| step_name | VARCHAR(255) | NULLABLE | 步骤名称 |
| task_metadata | JSON | NULLABLE | 任务元数据 |
| error_message | TEXT | NULLABLE | 错误信息 |
| project_id | VARCHAR(36) | FOREIGN KEY | 所属项目ID |
| created_at | DATETIME | NOT NULL | 创建时间 |
| updated_at | DATETIME | NOT NULL | 更新时间 |

---

## 处理流水线

### 六步处理流程

AutoClip采用六步处理流水线，从原始视频到最终切片输出：

```
原始视频 + 字幕
    ↓
[步骤1] 大纲提取 (Outline)
    ↓
[步骤2] 时间线提取 (Timeline)
    ↓
[步骤3] 内容评分 (Scoring)
    ↓
[步骤4] 标题生成 (Title)
    ↓
[步骤5] 内容聚类 (Clustering)
    ↓
[步骤6] 视频生成 (Video)
    ↓
最终切片 + 合集
```

### 步骤详解

#### Step 1: 大纲提取 (`backend/pipeline/step1_outline.py`)

**类名**：`OutlineExtractor`

**职责**：
- 解析SRT字幕文件
- 将字幕按时间智能分块（约30分钟/块）
- 使用LLM从每个文本块中提取视频大纲
- 合并和去重大纲
- 保存到step1_outline.json

**关键方法**：
```python
extract_outline(srt_path: Path) -> List[Dict]
save_outline(outlines: List[Dict], output_path: Optional[Path]) -> Path
load_outline(input_path: Path) -> List[Dict]
```

**输出格式**：
```json
[
  {
    "title": "话题标题",
    "subtopics": ["子话题1", "子话题2"],
    "chunk_index": 0
  }
]
```

#### Step 2: 时间线提取 (`backend/pipeline/step2_timeline.py`)

**类名**：`TimelineExtractor`

**职责**：
- 为每个大纲话题定位具体时间区间
- 多模态边界检测（文本语义 + 语音停顿 + 视频场景）
- 产品介绍模块化（片段类型识别 + 复用价值评估）
- 按时间排序并分配固定ID

**关键方法**：
```python
extract_timeline(outlines: List[Dict]) -> List[Dict]
set_media_paths(video_path: Optional[Path], audio_path: Optional[Path])
save_timeline(timeline_data: List[Dict], output_path: Optional[Path]) -> Path
```

**新特性**：
- 集成多模态边界检测
- 集成产品介绍模块化
- 支持原始LLM响应缓存
- 中间文件保存增强健壮性

**输出格式**：
```json
[
  {
    "id": "1",
    "outline": "话题标题",
    "start_time": "00:00:00,000",
    "end_time": "00:05:30,000",
    "chunk_index": 0,
    "segment_type": "product_intro", // 可选
    "reuse_value": 0.85, // 可选
    "boundary_refined": true // 可选
  }
]
```

#### Step 3: 内容评分 (`backend/pipeline/step3_scoring.py`)

**职责**：
- 对每个时间线片段进行精彩度评分
- 基于内容质量、话题重要性等维度
- 过滤低于评分阈值的片段
- 生成推荐理由

**评分维度**：
- 内容质量
- 话题重要性
- 信息密度
- 表达清晰度
- 情绪热度

#### Step 4: 标题生成 (`backend/pipeline/step4_title.py`)

**职责**：
- 为每个高评分片段生成吸引人的标题
- 基于片段内容和上下文
- 支持多种标题风格

#### Step 5: 内容聚类 (`backend/pipeline/step5_clustering.py`)

**职责**：
- 将相关片段聚类到一起
- 生成推荐合集
- 支持多种聚类策略（主题、时间、风格等）

#### Step 6: 视频生成 (`backend/pipeline/step6_video.py`)

**类名**：`VideoGenerator`

**职责**：
- 根据时间区间批量提取切片视频
- 生成合集视频
- 生成缩略图
- 保存完整元数据

**关键方法**：
```python
generate_clips(clips_with_titles: List[Dict], input_video: Path) -> List[Path]
generate_collections(collections_data: List[Dict]) -> List[Path]
save_clip_metadata(clips_with_titles: List[Dict], output_path: Optional[Path]) -> Path
save_collection_metadata(collections_data: List[Dict], output_path: Optional[Path]) -> Path
```

**输出文件**：
- `clips/{clip_id}_{title}.mp4`: 切片视频
- `collections/{collection_id}_{title}.mp4`: 合集视频
- `clips_metadata.json`: 切片完整元数据
- `collections_metadata.json`: 合集完整元数据

---

## 依赖关系

### 后端依赖 (`requirements.txt`)

#### Web框架
| 依赖 | 版本 | 用途 |
|------|------|------|
| fastapi | latest | 现代Web框架 |
| uvicorn[standard] | latest | ASGI服务器 |
| python-multipart | latest | 文件上传支持 |
| websockets | latest | WebSocket支持 |

#### 数据库和ORM
| 依赖 | 版本 | 用途 |
|------|------|------|
| sqlalchemy | latest | ORM框架 |
| alembic | latest | 数据库迁移 |

#### 任务队列
| 依赖 | 版本 | 用途 |
|------|------|------|
| celery[redis] | latest | 异步任务队列 |
| redis | latest | 消息代理和缓存 |

#### 数据验证
| 依赖 | 版本 | 用途 |
|------|------|------|
| pydantic | latest | 数据验证 |
| pydantic-settings | latest | 设置管理 |

#### LLM和AI
| 依赖 | 版本 | 用途 |
|------|------|------|
| dashscope | latest | 通义千问SDK |
| openai | latest | OpenAI SDK |
| google-generativeai | latest | Google AI SDK |
| pycorrector | latest | 中文文本纠错 |
| pypinyin | latest | 拼音转换 |

#### 语音识别
| 依赖 | 版本 | 用途 |
|------|------|------|
| funasr | latest | 阿里FunASR语音识别 |
| torch | latest | PyTorch深度学习框架 |
| torchaudio | latest | 音频处理库 |
| soundfile | latest | 音频文件读写 |

#### 视频处理
| 依赖 | 版本 | 用途 |
|------|------|------|
| yt-dlp | >=2024.12.13 | YouTube/B站视频下载 |
| pysrt | latest | SRT字幕解析 |

#### HTTP和网络
| 依赖 | 版本 | 用途 |
|------|------|------|
| requests | latest | HTTP客户端 |
| aiohttp | latest | 异步HTTP客户端 |
| aiofiles | latest | 异步文件操作 |

#### 安全
| 依赖 | 版本 | 用途 |
|------|------|------|
| python-jose[cryptography] | latest | JWT令牌 |
| passlib[bcrypt] | latest | 密码哈希 |
| cryptography | latest | 加密工具 |

#### 工具
| 依赖 | 版本 | 用途 |
|------|------|------|
| psutil | latest | 系统资源监控 |
| pytz | latest | 时区处理 |
| qrcode[pil] | latest | 二维码生成 |

#### 测试
| 依赖 | 版本 | 用途 |
|------|------|------|
| pytest | latest | 测试框架 |
| pytest-cov | latest | 测试覆盖率 |
| pytest-mock | latest | Mock工具 |

### 前端依赖 (`frontend/package.json`)

#### 核心框架
| 依赖 | 版本 | 用途 |
|------|------|------|
| react | ^18.2.0 | UI框架 |
| react-dom | ^18.2.0 | DOM渲染 |
| typescript | ^5.2.2 | 类型安全 |

#### UI组件库
| 依赖 | 版本 | 用途 |
|------|------|------|
| antd | ^5.12.8 | Ant Design组件库 |
| @ant-design/icons | ^5.2.6 | 图标库 |

#### 路由和导航
| 依赖 | 版本 | 用途 |
|------|------|------|
| react-router-dom | ^6.20.1 | 路由管理 |

#### 状态管理
| 依赖 | 版本 | 用途 |
|------|------|------|
| zustand | ^4.4.7 | 轻量级状态管理 |

#### HTTP客户端
| 依赖 | 版本 | 用途 |
|------|------|------|
| axios | ^1.6.2 | HTTP客户端 |

#### 媒体处理
| 依赖 | 版本 | 用途 |
|------|------|------|
| react-player | ^2.13.0 | 视频播放器 |
| react-dropzone | ^14.2.3 | 文件拖拽上传 |

#### 交互组件
| 依赖 | 版本 | 用途 |
|------|------|------|
| react-beautiful-dnd | ^13.1.1 | 拖拽排序 |

#### 工具
| 依赖 | 版本 | 用途 |
|------|------|------|
| dayjs | ^1.11.10 | 日期处理 |

#### 构建工具
| 依赖 | 版本 | 用途 |
|------|------|------|
| vite | ^5.0.8 | 构建工具 |
| @vitejs/plugin-react | ^4.2.1 | React插件 |

#### 代码质量
| 依赖 | 版本 | 用途 |
|------|------|------|
| eslint | ^8.55.0 | 代码检查 |
| @typescript-eslint/eslint-plugin | ^6.14.0 | TypeScript ESLint插件 |
| @typescript-eslint/parser | ^6.14.0 | TypeScript解析器 |
| eslint-plugin-react-hooks | ^4.6.0 | React Hooks检查 |
| eslint-plugin-react-refresh | ^0.4.5 | React Refresh检查 |

#### 类型定义
| 依赖 | 版本 | 用途 |
|------|------|------|
| @types/react | ^18.2.43 | React类型 |
| @types/react-dom | ^18.2.17 | React DOM类型 |
| @types/react-beautiful-dnd | ^13.1.8 | DnD类型 |

### 系统依赖

| 依赖 | 用途 |
|------|------|
| FFmpeg | 视频处理（必须安装） |
| Redis 6.0+ | 消息代理和缓存（可选，默认使用简化任务运行器） |
| Python 3.8+ | 后端运行环境 |
| Node.js 16+ | 前端开发环境 |

---

## API说明

### 响应格式

#### 成功响应
```json
{
  "success": true,
  "data": {},
  "message": "操作成功"
}
```

#### 错误响应
```json
{
  "success": false,
  "error": "错误信息",
  "code": "ERROR_CODE"
}
```

### 项目API

#### 上传视频创建项目
```
POST /api/v1/projects/upload
Content-Type: multipart/form-data

Body:
- video_file: File (必填) - 视频文件
- srt_file: File (可选) - 字幕文件
- project_name: string (必填) - 项目名称
- video_category: string (可选) - 视频分类

Response: ProjectResponse
```

#### 获取项目列表
```
GET /api/v1/projects?page=1&size=20&status=pending&project_type=knowledge&search=关键词

Response: ProjectListResponse
```

#### 获取项目详情
```
GET /api/v1/projects/{project_id}?include_clips=true&include_collections=true

Response: ProjectResponse
```

#### 开始处理项目
```
POST /api/v1/projects/{project_id}/process

Response:
{
  "message": "Processing started successfully",
  "project_id": "uuid",
  "task_id": "uuid",
  "status": "processing"
}
```

#### 获取处理状态
```
GET /api/v1/projects/{project_id}/status

Response:
{
  "status": "processing",
  "current_step": 3,
  "total_steps": 6,
  "step_name": "内容评分",
  "progress": 45.5,
  "error_message": null
}
```

### 切片API

#### 获取项目切片列表
```
GET /api/v1/projects/{project_id}/clips

Response: ClipListResponse
```

#### 获取切片视频
```
GET /api/v1/projects/{project_id}/clips/{clip_id}

Response: Video/MP4 stream
```

### 合集API

#### 创建合集
```
POST /api/v1/collections
Content-Type: application/json

Body:
{
  "name": "合集名称",
  "description": "合集描述",
  "project_id": "project_uuid",
  "clip_ids": ["clip1_uuid", "clip2_uuid"]
}

Response: CollectionResponse
```

#### 重新排序合集切片
```
PATCH /api/v1/projects/{project_id}/collections/{collection_id}/reorder
Content-Type: application/json

Body:
{
  "clip_ids": ["clip1_uuid", "clip3_uuid", "clip2_uuid"]
}
```

#### 生成合集视频
```
POST /api/v1/projects/{project_id}/collections/{collection_id}/generate

Response:
{
  "success": true,
  "message": "合集视频生成成功",
  "collection_id": "uuid",
  "output_path": "/path/to/video.mp4",
  "filename": "collection_name.mp4"
}
```

### YouTube/B站API

#### 解析视频信息
```
POST /api/v1/youtube/parse
Content-Type: application/json

Body:
{
  "url": "https://www.youtube.com/watch?v=xxx"
}

Response: VideoInfo
```

#### 下载视频
```
POST /api/v1/youtube/download
Content-Type: application/json

Body:
{
  "url": "https://www.youtube.com/watch?v=xxx",
  "project_name": "我的项目",
  "video_category": "knowledge"
}

Response: DownloadTaskStatus
```

---

## 运行方式

### 方式一：Docker部署（推荐）

#### 前置条件
- Docker 20.10+
- Docker Compose 2.0+
- 至少4GB内存，推荐8GB+
- 至少10GB可用磁盘空间

#### 快速启动

```bash
# 1. 克隆项目
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip

# 2. 配置环境变量
cp env.example .env
# 编辑.env文件，填入API密钥等配置

# 3. 启动所有服务
docker-compose up -d

# 4. 查看服务状态
docker-compose ps

# 5. 查看日志
docker-compose logs -f
```

#### 访问服务

- 前端界面：http://localhost:3000
- 后端API：http://localhost:8000
- API文档：http://localhost:8000/docs
- Flower监控：http://localhost:5555（可选）

#### 开发环境

```bash
# 使用开发环境配置
docker-compose -f docker-compose.dev.yml up -d

# 实时查看日志
docker-compose -f docker-compose.dev.yml logs -f
```

### 方式二：本地部署

#### 前置条件
- Python 3.8+（推荐3.9+）
- Node.js 16+（推荐18+）
- FFmpeg（必须安装）
- Redis 6.0+（可选，默认使用简化任务运行器）

#### 后端设置

```bash
# 1. 创建虚拟环境
python -m venv venv

# 2. 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 3. 安装Python依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp env.example .env
# 编辑.env文件

# 5. 初始化数据库
python -m backend.init_db

# 6. 启动后端服务
python -m backend.main
# 或使用uvicorn
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端设置

```bash
# 1. 进入前端目录
cd frontend

# 2. 安装依赖
npm install

# 3. 启动开发服务器
npm run dev

# 4. 构建生产版本
npm run build
```

#### 任务运行器（可选）

如果需要使用Celery：

```bash
# 启动Celery Worker
celery -A backend.core.celery_app worker --loglevel=info

# 启动Beat调度器
celery -A backend.core.celery_app beat --loglevel=info

# 启动Flower监控
celery -A backend.core.celery_app flower --port=5555
```

默认情况下，系统使用简化任务运行器，无需安装Redis。

### 环境变量配置

创建`.env`文件：

```env
# 数据库配置
DATABASE_URL=sqlite:///./data/autoclip.db

# Redis配置（可选）
REDIS_URL=redis://localhost:6379/0

# AI API配置
API_DASHSCOPE_API_KEY=your_dashscope_api_key_here
API_MODEL_NAME=qwen-plus
API_MAX_TOKENS=4096
API_TIMEOUT=30

# 处理配置
PROCESSING_CHUNK_SIZE=5000
PROCESSING_MIN_SCORE_THRESHOLD=0.7
PROCESSING_MAX_CLIPS_PER_COLLECTION=5
PROCESSING_MAX_RETRIES=3

# 日志配置
LOG_LEVEL=INFO
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
LOG_FILE=backend.log

# 应用配置
ENVIRONMENT=development
DEBUG=true
ENCRYPTION_KEY=your_encryption_key_here

# 路径配置（可选，使用默认值即可）
UPLOAD_DIR=./data/uploads
PROJECT_DIR=./data/projects
OUTPUT_DIR=./data/output

# 任务运行器配置
USE_SIMPLE_TASK_RUNNER=true
```

### 项目数据目录结构

```
data/
├── projects/                # 项目数据
│   └── {project_id}/        # 每个项目一个目录
│       ├── raw/             # 原始文件
│       │   ├── input.mp4    # 原始视频
│       │   └── input.srt    # 原始字幕
│       ├── metadata/        # 元数据
│       │   ├── step1_outline.json
│       │   ├── step2_timeline.json
│       │   ├── step3_scoring.json
│       │   ├── step4_titles.json
│       │   ├── step5_clustering.json
│       │   ├── clips_metadata.json
│       │   └── collections_metadata.json
│       └── output/          # 输出文件
│           ├── clips/       # 切片视频
│           └── collections/ # 合集视频
├── uploads/                 # 上传文件
├── temp/                    # 临时文件
└── autoclip.db              # SQLite数据库
```

---

## 开发指南

### 后端开发

#### 项目结构说明

项目遵循分层架构：
- `api/`: API路由层（FastAPI）
- `services/`: 业务逻辑层
- `repositories/`: 数据访问层
- `models/`: 数据模型层
- `schemas/`: Pydantic模式层
- `pipeline/`: 处理流水线
- `utils/`: 工具函数
- `core/`: 核心配置
- `tasks/`: Celery任务

#### 添加新功能的步骤

1. 在`models/`中定义数据模型
2. 在`schemas/`中定义Pydantic模式
3. 在`repositories/`中实现数据访问
4. 在`services/`中实现业务逻辑
5. 在`api/`中添加API端点
6. 在`tasks/`中添加异步任务（如需要）
7. 编写测试
8. 更新文档

#### 代码规范

- 遵循PEP 8 Python代码规范
- 使用类型注解（Type Hints）
- 编写文档字符串（Docstrings）
- 使用Gitmoji或Conventional Commits规范提交信息

### 前端开发

#### 组件开发规范

- 使用函数组件 + Hooks
- 使用TypeScript类型
- 遵循Ant Design设计规范
- 使用Zustand进行状态管理
- 组件化开发，保持组件单一职责

#### 状态管理

使用Zustand进行状态管理：

```typescript
// 示例状态store
import { create } from 'zustand';

interface ProjectState {
  projects: Project[];
  currentProject: Project | null;
  fetchProjects: () => Promise<void>;
  setCurrentProject: (project: Project) => void;
}

export const useProjectStore = create<ProjectState>((set) => ({
  projects: [],
  currentProject: null,
  fetchProjects: async () => {
    // 获取项目列表
  },
  setCurrentProject: (project) => set({ currentProject: project }),
}));
```

#### 开发流程

```bash
# 1. 启动开发服务器
npm run dev

# 2. 代码检查
npm run lint

# 3. 构建生产版本
npm run build

# 4. 预览生产版本
npm run preview
```

### 测试

#### 后端测试

```bash
# 运行所有测试
pytest

# 运行测试并生成覆盖率报告
pytest --cov=backend

# 运行特定测试文件
pytest backend/tests/test_processing_framework.py
```

#### 前端测试

```bash
# （项目当前未配置前端测试，可添加）
```

### 数据库迁移

使用Alembic进行数据库迁移：

```bash
# 初始化迁移（已完成）
# alembic init alembic

# 创建新迁移
alembic revision --autogenerate -m "description"

# 应用迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

### 常见问题排查

#### 问题1：端口被占用

```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <pid> /F

# Linux/Mac
lsof -i :8000
kill -9 <pid>
```

#### 问题2：FFmpeg未安装

```bash
# Windows
# 下载FFmpeg并添加到PATH

# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg
```

#### 问题3：视频下载失败

- 检查网络连接
- 更新yt-dlp：`pip install --upgrade yt-dlp`
- 尝试使用浏览器Cookie
- 检查视频是否可用或需要登录

#### 问题4：AI处理失败

- 检查API密钥是否正确配置
- 检查网络连接
- 查看日志获取详细错误信息
- 尝试使用不同的模型

#### 问题5：数据不一致

```bash
# 使用同步API
POST /api/v1/projects/{project_id}/sync-data
POST /api/v1/sync-all

# 或使用数据同步服务
```

---

## 附录

### 视频分类说明

| 分类 | 值 | 描述 | 图标 |
|------|-----|------|------|
| 默认 | default | 通用视频内容处理 | 🎬 |
| 知识科普 | knowledge | 科学、技术、历史、文化等知识类内容 | 📚 |
| 娱乐 | entertainment | 游戏、音乐、电影等娱乐内容 | 🎮 |
| 商业 | business | 商业、创业、投资等商业内容 | 💼 |
| 经验分享 | experience | 个人经历、生活感悟等经验内容 | 🌟 |
| 观点评论 | opinion | 时事评论、观点分析等评论内容 | 💭 |
| 演讲 | speech | 公开演讲、讲座等演讲内容 | 🎤 |

### 联系和支持

- 问题反馈：GitHub Issues
- 功能建议：GitHub Discussions
- 邮箱：christine_zhouye@163.com

### 许可证

本项目采用MIT许可证。

---

*文档最后更新：2025-05-05*
