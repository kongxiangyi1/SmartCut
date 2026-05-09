# 智谱AI GLM-4-Flash 集成实施文档

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| **版本** | v1.0.0 |
| **创建日期** | 2026-05-06 |
| **适用范围** | AutoClip 智谱AI集成实施 |
| **责任人员** | 技术团队 |

---

## 🎯 目标

本实施文档详细描述了将智谱AI GLM-4-Flash 模型集成到 AutoClip 系统的完整流程，包括：

1. 代码修改清单
2. 配置说明
3. 部署步骤
4. 测试验证
5. 故障排除

---

## 🔧 技术方案

### 1. 集成架构

```
┌─────────────────────────────────────────────────────────────┐
│                    前端配置界面                              │
│  [LLM Provider: 智谱AI] [API Key: *****] [Model: glm-4-flash]│
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   API Route: /api/v1/settings               │
│  - POST /  更新配置                                          │
│  - GET /   获取配置                                          │
│  - POST /test-api-key  测试连接                              │
│  - GET /available-models  获取可用模型                        │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              LLMManager (llm_manager.py)                    │
│  - 环境变量优先获取API Key                                   │
│  - 支持自动降级机制                                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│            LLMProviderFactory (llm_providers.py)            │
│  - ZhipuProvider 新增                                       │
│  - ProviderType.ZHIPU 枚举值                                │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                      智谱AI API                             │
│  Endpoint: https://open.bigmodel.cn/api/paas/v4            │
│  SDK: zhipuai>=4.0.0                                       │
└─────────────────────────────────────────────────────────────┘
```

### 2. 代码修改清单

| 序号 | 文件 | 修改内容 | 状态 |
|------|------|----------|------|
| 1 | `backend/core/llm_providers.py` | 添加 `ProviderType.ZHIPU` 枚举 | ✅ |
| 2 | `backend/core/llm_providers.py` | 添加 `ZhipuProvider` 类 | ✅ |
| 3 | `backend/core/llm_providers.py` | 注册到 `LLMProviderFactory` | ✅ |
| 4 | `backend/core/llm_manager.py` | `_get_api_key_for_provider` 添加ZHIPU | ✅ |
| 5 | `backend/core/llm_manager.py` | `set_provider` 添加ZHIPU | ✅ |
| 6 | `backend/core/llm_manager.py` | `_get_provider_display_name` 添加ZHIPU | ✅ |
| 7 | `backend/core/llm_manager.py` | 添加环境变量API Key获取 | ✅ |
| 8 | `backend/api/v1/settings.py` | `SettingsRequest` 添加 `zhipu_api_key` | ✅ |
| 9 | `backend/api/v1/settings.py` | `load_settings` 添加默认值 | ✅ |
| 10 | `backend/api/v1/settings.py` | `update_settings` 添加处理 | ✅ |

---

## 🚀 部署步骤

### 1. 安装依赖

```bash
# 安装智谱AI SDK
pip install zhipuai>=2.1.5

# 或安装所有LLM依赖
pip install -r requirements.txt
```

### 2. 获取API密钥

1. 访问 [智谱AI开放平台](https://open.bigmodel.cn/)
2. 注册账号并完成实名认证
3. 进入 [API密钥管理](https://bigmodel.cn/usercenter/proj-mgmt/apikeys)
4. 创建或复制API密钥

### 3. 配置方式

#### 方式一：环境变量（推荐）

```bash
# Linux/Mac
export ZHIPU_API_KEY=your_api_key_here

# Windows PowerShell
$env:ZHIPU_API_KEY="your_api_key_here"

# Docker Compose
environment:
  - ZHIPU_API_KEY=your_api_key_here
```

#### 方式二：配置文件

编辑 `data/settings.json`：

```json
{
  "llm_provider": "zhipu",
  "zhipu_api_key": "your_api_key_here",
  "model_name": "glm-4-flash"
}
```

#### 方式三：前端界面配置

1. 访问系统设置页面
2. 选择提供商为"智谱AI"
3. 输入API密钥
4. 选择模型（推荐glm-4-flash）
5. 测试连接并保存

---

## 🧪 测试验证

### 1. 单元测试

```bash
# 运行单元测试
cd backend
python -m pytest tests/test_zhipu_provider.py -v
```

### 2. 集成测试

```bash
# 启动后端服务
python -m uvicorn backend.main:app --reload

# 测试API连接
curl -X POST http://localhost:8000/api/v1/settings/test-api-key \
  -H "Content-Type: application/json" \
  -d '{"provider": "zhipu", "api_key": "your_api_key", "model_name": "glm-4-flash"}'
```

### 3. 功能测试

```bash
# 测试完整Pipeline
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试项目",
    "video_path": "/path/to/video.mp4"
  }'
```

---

## 📊 免费额度说明

| 项目 | 内容 |
|------|------|
| **免费额度** | 2000万Tokens |
| **有效期** | 永久有效 |
| **推荐模型** | glm-4-flash |
| **预计处理量** | 600+个1小时视频 |

---

## 🔍 故障排除

### 常见问题

#### 1. SDK导入错误

**症状**：`ModuleNotFoundError: No module named 'zhipuai'`

**解决方案**：
```bash
pip install zhipuai>=4.0.0
```

#### 2. API密钥无效

**症状**：测试连接失败，提示API Key无效

**解决方案**：
- 检查API密钥是否正确复制
- 确认账号已完成实名认证
- 检查网络连接

#### 3. 模型不可用

**症状**：选择的模型无法使用

**解决方案**：
- 确认使用 `glm-4-flash` 模型
- 检查API密钥权限

#### 4. 网络连接问题

**症状**：连接超时或网络错误

**解决方案**：
- 检查网络连接
- 确认防火墙设置
- 尝试使用国内网络

---

## 📈 性能指标

| 指标 | GLM-4-Flash |
|------|-------------|
| **响应延迟** | <1.5s |
| **上下文长度** | 128K |
| **中文理解** | ⭐⭐⭐⭐⭐ |
| **JSON输出** | ⭐⭐⭐⭐⭐ |

---

## 🎯 最佳实践

1. **使用环境变量**：推荐使用环境变量存储API密钥
2. **监控使用量**：定期检查Token使用情况
3. **选择合适模型**：推荐使用 `glm-4-flash` 平衡性能和成本
4. **备份配置**：定期备份配置文件

---

## 📄 变更记录

| 日期 | 版本 | 变更内容 |
|------|------|----------|
| 2026-05-06 | v1.0.0 | 初始版本 |

---

**注意**: 请妥善保管您的API密钥，不要在代码中硬编码或暴露在公共仓库中。