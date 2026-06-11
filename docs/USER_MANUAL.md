# AutoClip 用户手册

---

## 📖 目录

1. [项目介绍](#项目介绍)
2. [快速开始](#快速开始)
3. [功能使用指南](#功能使用指南)
4. [系统配置](#系统配置)
5. [API接口说明](#api接口说明)
6. [本地AI模型配置（LM Studio / Ollama）](#6-本地ai模型配置lm-studio--ollama)
7. [故障排除](#故障排除)
   - [端口被占用](#711-端口被占用)
   - [Redis连接失败](#712-redis连接失败)
   - [YouTube下载失败](#713-youtube下载失败)
   - [B站下载失败](#714-b站下载失败)
   - [AI处理速度慢](#715-ai处理速度慢)
   - [前端构建失败](#716-前端构建失败)
   - [数据库连接失败](#717-数据库连接失败)
   - [日志查看](#72-日志查看)
   - [系统状态检查](#73-系统状态检查)
8. [常见问题](#常见问题)
   - [安装和启动问题](#81-安装和启动问题)
   - [功能使用问题](#82-功能使用问题)
   - [性能优化](#83-性能优化)

---

## 1. 项目介绍

### 1.1 项目概述

AutoClip是一个基于AI的智能视频切片处理系统，能够自动从YouTube、B站等平台下载视频，通过AI分析提取精彩片段，并智能生成合集。

### 1.2 核心特性

| 特性 | 描述 |
|------|------|
| 🎬 **多平台支持** | YouTube、B站视频一键下载，支持本地文件上传 |
| 🤖 **AI智能分析** | 基于通义千问大语言模型的视频内容理解 |
| ✂️ **自动切片** | 智能识别精彩片段并自动切割，支持多种视频分类 |
| 📚 **智能合集** | AI推荐和手动创建视频合集，支持拖拽排序 |
| 🚀 **实时处理** | 异步任务队列，实时进度反馈，WebSocket通信 |
| 🎨 **现代界面** | React + TypeScript + Ant Design，响应式设计 |
| 📱 **移动端支持** | 响应式设计，支持移动端访问 |
| 🔐 **账号管理** | 支持B站多账号管理，自动健康检查 |
| 📊 **数据统计** | 完整的项目管理和数据统计功能 |
| 🛠️ **易于部署** | 一键启动脚本，Docker支持 |
| 📤 **B站上传** | 自动上传切片视频到B站 |
| ✏️ **字幕编辑** | 可视化字幕编辑和同步功能 |

### 1.3 系统架构

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   前端 (React)   │◄──►│   后端 (FastAPI) │◄──►│   文件系统      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                     ┌─────────────────┐
                     │   数据库 (SQLite) │
                     └─────────────────┘
                              │
                     ┌─────────────────┐
                     │   Redis + Celery │
                     └─────────────────┘
```

---

## 2. 快速开始

### 2.1 环境要求

| 环境 | 版本要求 |
|------|----------|
| Docker | 20.10+ |
| Docker Compose | 2.0+ |
| Python | 3.8+ (本地部署) |
| Node.js | 16+ (本地部署) |
| Redis | 6.0+ |
| FFmpeg | 必需 |
| 内存 | 最少4GB，推荐8GB+ |
| 存储 | 最少10GB可用空间 |

### 2.2 Docker部署（推荐）

```bash
# 克隆项目
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip

# 配置环境变量
cp env.example .env
# 编辑 .env 文件，填入API密钥等配置

# Docker一键启动
./docker-start.sh

# 停止服务
./docker-stop.sh

# 检查服务状态
./docker-status.sh
```

### 2.3 本地部署

```bash
# 克隆项目
git clone https://github.com/zhouxiaoka/autoclip.git
cd autoclip

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 安装Python依赖
pip install -r requirements.txt

# 安装前端依赖
cd frontend && npm install && cd ..

# 安装Redis
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt update && sudo apt install redis-server
sudo systemctl start redis-server

# 安装FFmpeg
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# 配置环境变量
cp env.example .env
# 编辑 .env 文件，填入API密钥等配置

# 启动服务
./start_autoclip.sh
```

### 2.4 访问服务

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:3000 |
| 后端API | http://localhost:8000 |
| API文档 | http://localhost:8000/docs |
| Flower监控 | http://localhost:5555 |

---

## 3. 功能使用指南

### 3.1 项目管理

#### 3.1.1 创建新项目

1. 登录系统后，点击首页的"新建项目"按钮
2. 填写项目信息：
   - **项目名称**: 输入项目的名称
   - **项目类型**: 选择视频类型（知识科普、商业财经、观点评论等）
   - **描述**: 可选，输入项目描述
3. 点击"创建"按钮

#### 3.1.2 项目列表

项目列表页面展示所有项目，支持：
- **搜索筛选**: 通过项目名称搜索
- **状态筛选**: 按状态（待处理、处理中、已完成、失败）筛选
- **批量操作**: 支持批量删除项目
- **状态标识**: 不同颜色标识项目状态

#### 3.1.3 项目状态说明

| 状态 | 描述 | 颜色 |
|------|------|------|
| pending | 待处理 | 灰色 |
| processing | 处理中 | 蓝色 |
| completed | 已完成 | 绿色 |
| failed | 处理失败 | 红色 |
| cancelled | 已取消 | 橙色 |

### 3.2 视频上传

#### 3.2.1 YouTube视频下载

1. 在项目详情页点击"上传视频"
2. 选择"YouTube链接"
3. 粘贴视频URL
4. 选择浏览器Cookie（可选，用于访问受限视频）
5. 点击"开始下载"

#### 3.2.2 B站视频下载

1. 在项目详情页点击"上传视频"
2. 选择"B站链接"
3. 粘贴视频URL
4. 选择登录账号（需提前配置B站账号）
5. 点击"开始下载"

#### 3.2.3 本地文件上传

1. 在项目详情页点击"上传视频"
2. 选择"文件上传"
3. 拖拽或选择视频文件
4. 可选上传字幕文件（SRT格式）
5. 点击"开始处理"

### 3.3 智能处理流程

系统自动执行以下6步处理流程：

| 步骤 | 名称 | 描述 |
|------|------|------|
| Step 1 | 大纲提取 | AI分析视频内容，提取视频大纲 |
| Step 2 | 时间定位 | 识别话题时间区间 |
| Step 3 | 精彩评分 | 对每个片段进行AI评分 |
| Step 4 | 标题生成 | 为精彩片段生成吸引人标题 |
| Step 5 | 主题聚类 | AI推荐视频合集组合 |
| Step 6 | 视频切割 | 生成切片视频和合集视频 |

### 3.4 结果管理

#### 3.4.1 查看切片

1. 进入项目详情页
2. 在"切片"标签页查看所有生成的视频片段
3. 点击片段卡片预览视频
4. 查看片段评分、时长等信息

#### 3.4.2 编辑切片信息

1. 点击片段卡片的"编辑"按钮
2. 修改标题、描述等信息
3. 点击"保存"按钮

#### 3.4.3 创建合集

**方式一：AI推荐合集**
1. 进入项目详情页的"合集"标签页
2. 点击"AI推荐合集"
3. 系统自动生成推荐的合集组合
4. 点击"确认创建"

**方式二：手动创建合集**
1. 进入项目详情页的"合集"标签页
2. 点击"新建合集"
3. 选择要加入合集的切片
4. 调整切片顺序（拖拽排序）
5. 设置合集名称和描述
6. 点击"创建"按钮

#### 3.4.4 下载导出

1. 选择要下载的切片或合集
2. 点击"下载"按钮
3. 选择导出格式和分辨率
4. 等待下载完成

### 3.5 B站上传（开发中）

1. 在项目详情页点击"B站上传"
2. 选择要上传的切片
3. 选择B站账号
4. 设置视频标题、描述、标签等信息
5. 选择分区
6. 点击"开始上传"

### 3.6 字幕编辑（开发中）

1. 在切片详情页点击"编辑字幕"
2. 在字幕编辑器中查看和编辑字幕
3. 调整字幕时间轴
4. 支持多语言字幕
5. 点击"保存"按钮

### 3.7 系统设置

#### 3.7.1 处理参数配置

1. 点击顶部导航的"设置"按钮
2. 在"处理参数"标签页配置：
   - **最小评分阈值**: 设置切片的最低评分要求
   - **每合集最大切片数**: 设置每个合集的最大切片数量
   - **并发处理数**: 设置同时处理的任务数

#### 3.7.2 API密钥管理

1. 在"API配置"标签页配置：
   - 输入通义千问API密钥
   - 选择AI模型
   - 设置最大token数
   - 设置超时时间

#### 3.7.3 B站账号管理

1. 在"B站账号"标签页管理账号：
   - 点击"添加账号"
   - 选择登录方式（Cookie导入、账号密码、二维码）
   - 系统自动管理账号健康状态

#### 3.7.4 系统监控

1. 在"系统监控"标签页查看：
   - 任务队列状态
   - 系统资源使用情况
   - 错误统计
   - 处理成功率

---

## 4. 系统配置

### 4.1 环境变量配置

创建 `.env` 文件：

```bash
# 数据库配置
DATABASE_URL=sqlite:///./data/autoclip.db

# Redis配置
REDIS_URL=redis://localhost:6379/0

# AI API配置
API_DASHSCOPE_API_KEY=your_dashscope_api_key
API_MODEL_NAME=qwen-plus
API_MAX_TOKENS=4096
API_TIMEOUT=30

# 处理配置
PROCESSING_CHUNK_SIZE=5000
PROCESSING_MIN_SCORE_THRESHOLD=0.7
PROCESSING_MAX_CLIPS_PER_COLLECTION=5
PROCESSING_MAX_RETRIES=3

# 路径配置
PATH_PROJECT_ROOT=./data
PATH_UPLOADS_DIR=./data/uploads
PATH_TEMP_DIR=./data/temp
PATH_OUTPUT_DIR=./data/output

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=backend.log

# 环境配置
ENVIRONMENT=development
DEBUG=true
```

### 4.2 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| DATABASE_URL | 数据库连接URL | sqlite:///./data/autoclip.db |
| REDIS_URL | Redis连接URL | redis://localhost:6379/0 |
| API_DASHSCOPE_API_KEY | 通义千问API密钥 | 必需 |
| API_MODEL_NAME | AI模型名称 | qwen-plus |
| API_MAX_TOKENS | 最大token数 | 4096 |
| API_TIMEOUT | API超时时间（秒） | 30 |
| PROCESSING_CHUNK_SIZE | 文本分块大小 | 5000 |
| PROCESSING_MIN_SCORE_THRESHOLD | 最小评分阈值 | 0.7 |
| PROCESSING_MAX_CLIPS_PER_COLLECTION | 每合集最大切片数 | 5 |
| PROCESSING_MAX_RETRIES | 最大重试次数 | 3 |
| LOG_LEVEL | 日志级别 | INFO |
| ENVIRONMENT | 运行环境 | development |
| DEBUG | 是否开启调试 | true |

---

## 5. API接口说明

### 5.1 项目管理

#### 5.1.1 获取项目列表

```
GET /api/v1/projects
```

**请求参数**:

| 参数 | 类型 | 是否必需 | 描述 |
|------|------|----------|------|
| page | integer | 否 | 页码，默认1 |
| size | integer | 否 | 每页数量，默认20 |
| status | string | 否 | 状态筛选 |
| project_type | string | 否 | 项目类型筛选 |

**响应示例**:

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "projects": [
      {
        "id": "project_id",
        "name": "项目名称",
        "status": "completed",
        "project_type": "knowledge",
        "video_duration": 3600,
        "created_at": "2024-01-01 12:00:00",
        "updated_at": "2024-01-01 12:30:00"
      }
    ],
    "total": 100,
    "page": 1,
    "size": 20
  }
}
```

#### 5.1.2 创建项目

```
POST /api/v1/projects
```

**请求参数**:

| 参数 | 类型 | 是否必需 | 描述 |
|------|------|----------|------|
| name | string | 是 | 项目名称 |
| description | string | 否 | 项目描述 |
| project_type | string | 是 | 项目类型 |
| processing_config | object | 否 | 处理配置 |

**请求示例**:

```json
{
  "name": "知识科普视频处理",
  "project_type": "knowledge",
  "processing_config": {
    "min_score_threshold": 0.7,
    "max_clips_per_collection": 5
  }
}
```

**响应示例**:

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "project_id",
    "name": "知识科普视频处理",
    "status": "pending",
    "project_type": "knowledge",
    "created_at": "2024-01-01 12:00:00"
  }
}
```

#### 5.1.3 获取项目详情

```
GET /api/v1/projects/{project_id}
```

**路径参数**:

| 参数 | 类型 | 描述 |
|------|------|------|
| project_id | string | 项目ID |

**响应示例**:

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "project_id",
    "name": "项目名称",
    "description": "项目描述",
    "status": "completed",
    "project_type": "knowledge",
    "video_path": "/data/projects/project_id/raw/video.mp4",
    "video_duration": 3600,
    "processing_config": {...},
    "project_metadata": {...},
    "created_at": "2024-01-01 12:00:00",
    "updated_at": "2024-01-01 12:30:00",
    "completed_at": "2024-01-01 12:30:00"
  }
}
```

#### 5.1.4 更新项目

```
PUT /api/v1/projects/{project_id}
```

**请求参数**:

| 参数 | 类型 | 是否必需 | 描述 |
|------|------|----------|------|
| name | string | 否 | 项目名称 |
| description | string | 否 | 项目描述 |
| processing_config | object | 否 | 处理配置 |

#### 5.1.5 删除项目

```
DELETE /api/v1/projects/{project_id}
```

### 5.2 视频处理

#### 5.2.1 上传视频文件

```
POST /api/v1/projects/{project_id}/upload
```

**请求参数**:

| 参数 | 类型 | 是否必需 | 描述 |
|------|------|----------|------|
| video_file | file | 是 | 视频文件 |
| srt_file | file | 否 | 字幕文件 |

#### 5.2.2 开始处理项目

```
POST /api/v1/projects/{project_id}/process
```

**请求参数**:

| 参数 | 类型 | 是否必需 | 描述 |
|------|------|----------|------|
| processing_steps | array | 否 | 指定处理步骤 |
| priority | integer | 否 | 任务优先级 |

**响应示例**:

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "task_id": "task_id",
    "project_id": "project_id",
    "status": "running",
    "progress": 0.0,
    "current_step": "step1_outline",
    "started_at": "2024-01-01 12:00:00"
  }
}
```

#### 5.2.3 获取处理状态

```
GET /api/v1/projects/{project_id}/status
```

**响应示例**:

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "task_id": "task_id",
    "status": "running",
    "progress": 45.5,
    "current_step": "step3_scoring",
    "message": "正在进行精彩评分...",
    "estimated_remaining": 120
  }
}
```

### 5.3 切片管理

#### 5.3.1 获取切片列表

```
GET /api/v1/projects/{project_id}/clips
```

**响应示例**:

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "id": "clip_id",
      "title": "片段标题",
      "description": "片段描述",
      "start_time": 120.0,
      "end_time": 180.0,
      "duration": 60.0,
      "score": 0.85,
      "video_path": "/data/output/clips/project_id/clip_id.mp4",
      "thumbnail_path": "/data/output/clips/project_id/clip_id.jpg"
    }
  ]
}
```

#### 5.3.2 更新切片信息

```
PUT /api/v1/clips/{clip_id}
```

**请求参数**:

| 参数 | 类型 | 是否必需 | 描述 |
|------|------|----------|------|
| title | string | 否 | 切片标题 |
| description | string | 否 | 切片描述 |

### 5.4 合集管理

#### 5.4.1 获取合集列表

```
GET /api/v1/projects/{project_id}/collections
```

**响应示例**:

```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "id": "collection_id",
      "name": "合集名称",
      "description": "合集描述",
      "total_clips": 5,
      "total_duration": 300.0,
      "clip_ids": ["clip1", "clip2", "clip3", "clip4", "clip5"]
    }
  ]
}
```

#### 5.4.2 创建合集

```
POST /api/v1/projects/{project_id}/collections
```

**请求参数**:

| 参数 | 类型 | 是否必需 | 描述 |
|------|------|----------|------|
| name | string | 是 | 合集名称 |
| description | string | 否 | 合集描述 |
| clip_ids | array | 是 | 切片ID列表 |

#### 5.4.3 更新合集

```
PUT /api/v1/collections/{collection_id}
```

**请求参数**:

| 参数 | 类型 | 是否必需 | 描述 |
|------|------|----------|------|
| name | string | 否 | 合集名称 |
| description | string | 否 | 合集描述 |
| clip_ids | array | 否 | 切片ID列表（更新顺序） |

#### 5.4.4 删除合集

```
DELETE /api/v1/collections/{collection_id}
```

### 5.5 WebSocket实时进度

```
WS /api/v1/ws/{project_id}
```

**消息格式**:

```json
{
  "type": "progress_update",
  "data": {
    "task_id": "task_id",
    "progress": 45.5,
    "current_step": "step3_scoring",
    "message": "正在进行精彩评分...",
    "estimated_remaining": 120
  }
}
```

---

## 6. 本地AI模型配置（LM Studio / Ollama）

### 6.1 概述

AutoClip 支持接入本地部署的大语言模型作为 AI 分析引擎，适用于：
- 数据隐私要求较高，不希望将视频内容发送到云端 API
- 需要离线运行，无网络环境
- 使用自有硬件资源，节省 API 调用费用

支持的本地模型提供商：
- **[LM Studio](https://lmstudio.ai/)**：Windows / macOS 桌面应用，提供 OpenAI 兼容接口
- **[Ollama](https://ollama.com/)**：跨平台命令行工具，也提供 OpenAI 兼容接口

### 6.2 LM Studio 配置步骤

#### 6.2.1 安装 LM Studio

1. 访问 [https://lmstudio.ai/](https://lmstudio.ai/) 下载对应操作系统的安装包
2. 安装后启动 LM Studio

#### 6.2.2 下载并加载模型

1. 在 LM Studio 左侧导航栏点击 **🔍 Search**（搜索图标）
2. 搜索框输入你想要的模型，例如 `Qwen2.5-7B-Instruct` 或 `deepseek-v4-flash`
3. 点击模型卡片上的 **Download** 按钮下载模型
4. 下载完成后，点击左侧 **💬 Chat**（聊天图标）
5. 在顶部的模型选择下拉框中，选择刚才下载的模型

#### 6.2.3 ⚠️ 配置 Context Length（关键步骤）

Context Length（上下文长度）决定了模型一次性可处理的文本量。加载模型后**必须**按以下步骤配置：

1. 在 **💬 Chat** 页面中，点击顶部模型选择框右侧的 **⚙️ 设置图标**（或齿轮图标），打开模型加载参数面板
2. 找到 **Context Length（上下文长度）** 或 **n_ctx** 输入框
3. 根据你的硬件配置和视频长度，选择适当的值：

| 视频时长 | 推荐 Context Length | 显存需求（7B模型） |
|----------|-------------------|-----------------|
| 短（<5分钟） | 8192 (8K) | ~6GB |
| 中（5-15分钟） | 16384 (16K) | ~8GB |
| 长（15-30分钟） | 32768 (32K) | ~12GB |
| 超长（>30分钟） | 65536 (64K) | ~16GB+ |

4. **重新加载模型**：修改参数后，需要点击 **Reload Model**（重新加载模型）按钮使配置生效
5. 确认右侧状态栏显示 `n_ctx: 16384`（或你设置的值），表示配置已生效

> **⚠️ 重要**：Context Length 过低（如默认的 4096）会导致流水线处理失败，日志中出现 `n_keep: XXXX >= n_ctx: 4096` 错误。此时需按上述步骤增大 Context Length 并重新加载模型。

#### 6.2.4 启动本地 API 服务

1. 在 LM Studio 左侧点击 **💻 Developer**（开发者模式）图标
2. 在 **Server** 标签页中：
   - 确认模型选择器中已选中你要使用的模型
   - 确认 **Port** 填写为 `1234`（默认值）
   - 确认 **CORS Origin** 填写为 `*`（或 `http://localhost:3000`）
3. 点击 **Start Server** 按钮，启动 API 服务
4. 当状态变为 **Running** 时，API 服务已就绪，地址为 `http://localhost:1234/v1`

#### 6.2.5 在 AutoClip 中配置 LM Studio

1. 在 AutoClip 前端页面，点击顶部的 **设置** 按钮
2. 进入 **API 配置** 标签页
3. 在 AI 提供商下拉框中选择 **LM Studio**
4. 配置以下参数：

| 参数 | 说明 | 填写值 |
|------|------|--------|
| API Key | LM Studio 不验证 API Key | 任意值（如 `lmstudio`） |
| 模型名称 | 你在 LM Studio 中加载的模型名 | 例如 `qwen2.5-7b-instruct` |
| 基础URL | LM Studio API 服务地址 | `http://localhost:1234/v1` |
| 最大Token数 | 单次生成的最大输出长度 | `4096`（一般保持默认） |

5. 点击 **测试连接** 按钮，确认显示"连接成功"
6. 点击 **保存设置**

#### 6.2.6 验证配置

配置完成后，创建一个新的视频处理项目进行验证。关注后端日志中是否有以下信息：

```
LM Studio 模型预热完成，上下文窗口: 16384
```

如果出现 `n_ctx: 4096` 或警告日志，说明 Context Length 配置未生效，请返回 6.2.3 重新配置并重新加载模型。

### 6.3 Ollama 配置步骤

#### 6.3.1 安装 Ollama

1. 访问 [https://ollama.com/](https://ollama.com/) 下载安装包
2. 安装后，打开终端验证：
   ```bash
   ollama --version
   ```
   
#### 6.3.2 下载并运行模型

```bash
# 下载并运行 Qwen2.5 7B（推荐）
ollama run qwen2.5

# 其他可选模型
ollama run qwen2.5:7b    # 7B 参数版
ollama run qwen2.5:14b   # 14B 参数版（需要更多显存）

# 模型下载完成后，Ollama 自动启动 API 服务
# 默认地址: http://localhost:11434
```

#### 6.3.3 配置 Context Length

Ollama 默认的 Context Length 为 2048，需要手动修改：

```bash
# 方式一：通过环境变量设置（推荐）
# 在启动 AutoClip 前设置
set OLLAMA_CONTEXT_LENGTH=16384    # Windows PowerShell
# 或
export OLLAMA_CONTEXT_LENGTH=16384  # Linux/macOS

# 方式二：通过 Modelfile 设置
# 创建 Modelfile
echo "FROM qwen2.5
PARAMETER num_ctx 16384" > Modelfile

# 创建自定义模型
ollama create my-model -f Modelfile

# 运行自定义模型
ollama run my-model
```

> **⚠️ 注意**：Context Length 越大，占用的显存越多。普通 7B 模型建议 16384，14B 模型建议 8192。

#### 6.3.4 在 AutoClip 中配置 Ollama

1. 在 AutoClip 设置页面的 **API 配置** 标签页
2. 在 AI 提供商下拉框中选择 **Ollama**
3. 配置以下参数：

| 参数 | 说明 | 填写值 |
|------|------|--------|
| API Key | Ollama 不验证 API Key | 任意值（如 `ollama`） |
| 模型名称 | Ollama 中的模型名 | 例如 `qwen2.5` 或 `my-model` |
| 基础URL | Ollama API 服务地址 | `http://localhost:11434/v1` |
| 最大Token数 | 单次生成的最大输出长度 | `4096` |

4. 点击 **测试连接** 确认成功
5. 点击 **保存设置**

### 6.4 本地模型配置检查清单

使用本地 AI 模型时，请逐项确认：

- [ ] LM Studio / Ollama 已安装并运行
- [ ] 模型已下载并加载成功
- [ ] Context Length 已设置为 16384 或更大（根据视频时长）
- [ ] 修改 Context Length 后已重新加载模型（LM Studio）或重新创建模型（Ollama）
- [ ] API 服务已启动（LM Studio 需手动点击 Start Server）
- [ ] AutoClip 设置中的基础 URL 正确指向本地 API 地址
- [ ] 测试连接成功

### 6.5 常见错误及解决

| 错误日志 | 原因 | 解决方案 |
|---------|------|---------|
| `n_keep: XXXX >= n_ctx: 4096` | Context Length 过小 | 增大至 16384+ 并重新加载模型 |
| `Connection refused` | LM Studio / Ollama 未启动 | 检查 API 服务是否已运行 |
| `model not found` | 模型名称不匹配 | 确认 LM Studio 或 Ollama 中已加载该模型 |
| `Context size has been exceeded` | 输入文本超出模型窗口 | 增大 Context Length 或缩短视频 |

---

## 7. 故障排除

### 7.1 常见问题

#### 7.1.1 端口被占用

**问题**: 启动服务时提示端口被占用

**解决方案**:

```bash
# 检查端口占用
lsof -i :8000  # 后端端口
lsof -i :3000  # 前端端口

# 停止占用进程
kill -9 <PID>
```

#### 7.1.2 Redis连接失败

**问题**: Celery无法连接到Redis

**解决方案**:

```bash
# 检查Redis状态
redis-cli ping

# 启动Redis服务
brew services start redis  # macOS
sudo systemctl start redis  # Linux
```

#### 7.1.3 YouTube下载失败

**问题**: 无法下载YouTube视频

**解决方案**:
1. 检查网络连接
2. 更新yt-dlp版本：`pip install --upgrade yt-dlp`
3. 尝试使用浏览器Cookie
4. 检查视频是否可用或需要登录

#### 7.1.4 B站下载失败

**问题**: 无法下载B站视频

**解决方案**:
1. 检查账号登录状态
2. 更新账号Cookie
3. 检查视频权限设置
4. 尝试使用其他账号

#### 7.1.5 AI处理速度慢

**问题**: AI分析处理时间过长

**解决方案**:
1. 检查API密钥配置
2. 调整处理参数（减少chunk_size）
3. 检查网络连接
4. 考虑使用更快的AI模型

#### 7.1.6 前端构建失败

**问题**: npm run build 失败

**解决方案**:

```bash
cd frontend
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

#### 7.1.7 数据库连接失败

**问题**: 无法连接到数据库

**解决方案**:
1. 检查数据库文件是否存在
2. 确认数据库权限设置
3. 检查数据库连接字符串

### 7.2 日志查看

```bash
# 查看所有日志
tail -f logs/*.log

# 查看特定服务日志
tail -f logs/backend.log    # 后端日志
tail -f logs/frontend.log   # 前端日志
tail -f logs/celery.log     # 任务队列日志
```

### 7.3 系统状态检查

```bash
# 详细状态检查
./status_autoclip.sh

# 手动检查服务
curl http://localhost:8000/api/v1/health/  # 后端健康检查
curl http://localhost:3000/                # 前端访问测试
redis-cli ping                             # Redis连接测试
```

---

## 8. 常见问题

### 8.1 安装和启动问题

**Q: 启动时提示端口被占用怎么办？**

**A:** 使用以下命令检查并停止占用端口的进程：

```bash
# 检查端口占用
lsof -i :8000  # 后端端口
lsof -i :3000  # 前端端口

# 停止进程
kill -9 <PID>
```

**Q: Redis连接失败怎么办？**

**A:** 确保Redis服务正在运行：

```bash
# 检查Redis状态
redis-cli ping

# 启动Redis服务
brew services start redis  # macOS
sudo systemctl start redis-server  # Linux
```

**Q: 前端依赖安装失败怎么办？**

**A:** 尝试清理缓存后重新安装：

```bash
cd frontend
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

### 8.2 功能使用问题

**Q: YouTube视频下载失败怎么办？**

**A:**
1. 检查网络连接
2. 更新yt-dlp：`pip install --upgrade yt-dlp`
3. 尝试使用浏览器Cookie
4. 检查视频是否可用或需要登录

**Q: B站视频下载失败怎么办？**

**A:**
1. 检查账号登录状态
2. 更新账号Cookie
3. 检查视频权限设置
4. 尝试使用其他账号

**Q: AI处理速度慢怎么办？**

**A:**
1. 检查API密钥配置
2. 调整处理参数（减少chunk_size）
3. 检查网络连接
4. 考虑使用更快的AI模型

**Q: B站上传功能什么时候可以使用？**

**A:** B站上传功能正在开发中，预计在下一个版本中发布。该功能将支持：
- 自动上传切片视频到B站
- 多账号管理和切换
- 批量上传和队列管理
- 上传进度监控

**Q: 字幕编辑功能什么时候可以使用？**

**A:** 字幕编辑功能正在开发中，预计在下一个版本中发布。该功能将支持：
- 可视化字幕编辑器
- 字幕时间轴同步
- 多语言字幕支持
- 字幕格式转换

### 8.3 性能优化

**Q: 如何提高处理速度？**

**A:**
1. 增加Celery Worker并发数
2. 使用SSD存储
3. 增加系统内存
4. 优化视频质量设置

**Q: 如何减少存储空间占用？**

**A:**
1. 定期清理临时文件
2. 压缩输出视频
3. 删除不需要的项目
4. 使用外部存储

---

## 📞 支持与反馈

### 获取帮助

- **问题反馈**: [GitHub Issues](https://github.com/zhouxiaoka/autoclip/issues)
- **功能建议**: [GitHub Discussions](https://github.com/zhouxiaoka/autoclip/discussions)
- **Bug报告**: 请使用GitHub Issues模板
- **文档**: [项目文档](docs/)

### 联系方式

- 发送邮件至：[kxy_1@163.com](mailto:kxy_1@163.com)

---

**文档版本**: 1.0  
**创建日期**: 2024年12月  
**最后更新**: 2024年12月

---

⭐ 如果觉得有用，请给个Star支持一下！