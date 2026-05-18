# LLM智能切片异常降级处理方案 - 落地执行计划

---

## 一、执行计划总览

### 1.1 整体节奏（7天迭代）

```
Day 1-2: 准备阶段（基础设施+依赖确认）
Day 3-4: 核心开发（后端枚举+策略基类+本地算法）
Day 5:   前端集成（状态接口+引导弹窗）
Day 6:   测试验证（单元测试+集成测试）
Day 7:   上线部署（灰度发布+监控）
```

### 1.2 团队分工

| 角色 | 负责模块 | 人数建议 |
|------|---------|---------|
| 后端开发 | 枚举定义、策略基类、本地算法、Pipeline改造 | 1人 |
| 前端开发 | 状态接口对接、引导弹窗、结果展示 | 1人 |
| 测试工程师 | 单元测试、集成测试、E2E验证 | 1人 |
| 技术负责人 | 代码Review、方案把控、上线审批 | 1人 |

---

## 二、分阶段落地清单

### Phase 1: 准备阶段（第1-2天）

#### Day 1: 环境与依赖准备

| 序号 | 责任人 | 具体动作 | 验收标准 | 完成标志 |
|------|--------|---------|---------|---------|
| 1.1 | 后端 | 确认 `scikit-learn` 是否已加入 `requirements.txt`，如无则添加 | `pip show scikit-learn` 返回版本信息 | requirements.txt包含sklearn |
| 1.2 | 后端 | 创建 `backend/models/enums.py`，定义枚举类 | 文件存在且可import | `from backend.models.enums import LLMConfigStatus, ProcessMode` 无报错 |
| 1.3 | 后端 | 确认现有项目数据库支持新增字段 | 执行 `alembic revision --autogenerate` 可生成迁移脚本 | migrations目录生成新迁移文件 |
| 1.4 | 后端 | 确认Redis连接配置正确 | `redis-cli ping` 返回PONG | 缓存读写正常 |
| 1.5 | 后端 | 梳理现有Pipeline入口位置 | 找到 `backend/services/simple_pipeline_adapter.py` | 能够清晰画出调用链路图 |

**Day 1 交付物：** `backend/models/enums.py` 枚举文件 + 依赖确认报告

---

#### Day 2: 数据模型与接口设计

| 序号 | 责任人 | 具体动作 | 验收标准 | 完成标志 |
|------|--------|---------|---------|---------|
| 2.1 | 后端 | 设计 `LLMStatus` 响应结构体 | 包含 status/message/provider/model/available_modes 字段 | 接口文档输出 |
| 2.2 | 后端 | 设计 `ProcessMode` 枚举值 | 值为 ai_smart/subtitle_organized/quick_preview/raw_transcript | 与前端对齐枚举字符串 |
| 2.3 | 后端 | 设计 `ProjectSnapshot` 数据模型 | 包含 project_id/mode/llm_config/processing_config/is_locked | SQLAlchemy模型可正常实例化 |
| 2.4 | 后端 | 确认LLM Manager已有方法签名 | 查看 `get_config_status()` 返回结构 | 接口文档输出 |
| 2.5 | 后端 | 确认现有上传接口签名 | 查看 `UploadRequest` 字段定义 | 接口可向后兼容扩展 |

**Day 2 交付物：** 数据模型设计文档 + 接口契约文档

---

### Phase 2: 开发阶段（第3-4天）

#### Day 3: 后端核心开发

##### 3.1 枚举与状态检测接口

| 序号 | 责任人 | 具体动作 | 验收标准 | 完成标志 |
|------|--------|---------|---------|---------|
| 3.1.1 | 后端 | 实现 `LLMConfigStatus` 枚举 | 6个状态值：not_configured/invalid_key/rate_limited/service_unavailable/connection_failed/configured | pytest测试6个枚举值可正常比较 |
| 3.1.2 | 后端 | 实现 `ProcessMode` 枚举 | 4个模式值：ai_smart/subtitle_organized/quick_preview/raw_transcript | pytest测试4个枚举值 |
| 3.1.3 | 后端 | 在 `LLMManager` 新增 `get_config_status()` 方法 | 实际调用API检测连接，返回状态枚举 | 接口单元测试通过 |
| 3.1.4 | 后端 | 在 `settings.py` 新增 `/llm-config-status` GET接口 | 返回 `LLMStatus` 结构 | curl http://localhost:8000/api/v1/settings/llm-config-status 返回JSON |
| 3.1.5 | 后端 | 处理API Key无效的情况 | 捕获401/403错误，返回invalid_key状态 | Mock测试无效Key返回正确状态 |

**验收标准：** `curl http://localhost:8000/api/v1/settings/llm-config-status` 返回正确的status字段

---

##### 3.2 策略模式基类实现

| 序号 | 责任人 | 具体动作 | 验收标准 | 完成标志 |
|------|--------|---------|---------|---------|
| 3.2.1 | 后端 | 创建 `backend/pipeline/strategies/__init__.py` | 空文件，package初始化 | 无报错 |
| 3.2.2 | 后端 | 实现 `PipelineStrategy` 抽象基类 | 定义 `execute()` / `get_capabilities()` / `get_quality_level()` 方法 | 抽象方法子类必须实现 |
| 3.2.3 | 后端 | 实现 `PipelineResult` 数据类 | 包含 status/mode/outputs/warnings/errors/quality_level/is_demo | 可正常序列化JSON |
| 3.2.4 | 后端 | 实现 `AISmartStrategy` 子类 | 调用现有Step1-6流水线 | 单元测试：Mock LLM调用，执行成功 |
| 3.2.5 | 后端 | 实现 `SubtitleOrganizedStrategy` 子类 | 字幕规范化+标点恢复 | 单元测试：输入原始SRT，输出整理后SRT |

**验收标准：** `AISmartStrategy().execute()` 和 `SubtitleOrganizedStrategy().execute()` 均能正常返回 `PipelineResult`

---

##### 3.3 本地降级算法实现

| 序号 | 责任人 | 具体动作 | 验收标准 | 完成标志 |
|------|--------|---------|---------|---------|
| 3.3.1 | 后端 | 实现 `local_scorer.py` 本地评分算法 | 维度：字幕长度适中(20-80字最佳)、音频能量适中(0.3-0.7)、词汇多样性、专业术语检测 | pytest测试：已知输入返回预期分数范围(0-1) |
| 3.3.2 | 后端 | 实现 `local_cluster.py` TF-IDF聚类 | sklearn.TfidfVectorizer + KMeans，fallback简单分组 | pytest测试：3个片段聚成2类，无报错 |
| 3.3.3 | 后端 | 实现 `local_title.py` 简单标题生成 | 策略：取字幕首句/关键词提取/固定前缀 | pytest测试：输入字幕片段，输出非空字符串 |
| 3.3.4 | 后端 | 实现 `QuickPreviewStrategy` 子类 | 仅做字幕整理+基础分段，明确标注is_demo=True | 单元测试：返回结果 `is_demo=True` |
| 3.3.5 | 后端 | 处理sklearn依赖缺失的fallback | try-import sklearn，缺失时使用简单分组 | Mock测试：无sklearn环境执行不报错 |

**验收标准：** 
- `local_scorer.score()` 输入5个字幕片段，返回5个带分数的片段
- `local_cluster.cluster()` 输入10个片段，返回聚类结果（list of lists）
- 无sklearn环境下不抛出ImportError

---

#### Day 4: Pipeline改造与调度器

##### 3.4 统一调度器实现

| 序号 | 责任人 | 具体动作 | 验收标准 | 完成标志 |
|------|--------|---------|---------|---------|
| 3.4.1 | 后端 | 实现 `PipelineDirector` 类 | 注册所有策略，根据模式选择执行 | 单元测试：指定mode返回对应strategy |
| 3.4.2 | 后端 | 实现降级决策逻辑 | 当前策略失败时，自动选择下一级策略 | 集成测试：Mock AI失败，自动降级到字幕模式 |
| 3.4.3 | 后端 | 实现配置快照管理器 `ConfigSnapshotManager` | 创建/读取/验证快照，任务开始时锁定 | 单元测试：快照创建后可读取，内容一致 |
| 3.4.4 | 后端 | 修改 `UploadRequest` 增加 `mode` 字段 | 可选参数，默认 ai_smart | API文档显示新字段 |
| 3.4.5 | 后端 | 修改项目上传接口支持模式选择 | 接收mode参数，传递给Director | curl测试：POST带mode参数，不报错 |

**验收标准：**
- 上传视频时指定 `mode=subtitle_organized`，系统不使用LLM完成处理
- 项目创建后，配置快照已锁定，后续修改LLM配置不影响该项目

---

##### 3.5 异常处理与降级链路

| 序号 | 责任人 | 具体动作 | 验收标准 | 完成标志 |
|------|--------|---------|---------|
| 3.5.1 | 后端 | 实现 `PipelineError` 错误枚举 | 覆盖LLM错误/处理错误/降级失败 | pytest测试枚举值 |
| 3.5.2 | 后端 | 实现 `ErrorHandler` 统一异常处理器 | 错误分类+降级决策+用户提示生成 | 单元测试：给定错误返回正确处理策略 |
| 3.5.3 | 后端 | 实现 `LLMStateMonitor` LLM状态监听器 | 定时检查+状态变化通知+订阅机制 | Mock测试：状态变化触发回调 |
| 3.5.4 | 后端 | 实现 `ResilientPipelineExecutor` 容错执行器 | 多层降级兜底+紧急Fallback | 集成测试：所有策略失败返回友好错误 |
| 3.5.5 | 后端 | 配置定时任务检测LLM状态 | Celery Beat 每5分钟检查一次 | 日志显示定时任务执行 |

**验收标准：**
- 主动关闭LLM服务后，运行中的任务收到降级通知
- AI智能模式执行失败，自动降级到字幕整理模式并继续
- 所有策略失败，返回用户友好的错误信息（非技术堆栈）

---

### Phase 3: 前端集成（第5天）

#### Day 5: 前端开发

##### 4.1 状态检测与接口对接

| 序号 | 责任人 | 具体动作 | 验收标准 | 完成标志 |
|------|--------|---------|---------|---------|
| 4.1.1 | 前端 | 创建 `frontend/src/types/mode.ts` | 定义 `ProcessMode` 枚举 + `ModeInfo` 配置结构 | TypeScript编译通过 |
| 4.1.2 | 前端 | 创建 `useLLMConfig` Hook | 查询 `/llm-config-status`，定时刷新（30s） | 控制台无CORS错误 |
| 4.1.3 | 前端 | 实现模式推荐逻辑 | 根据LLM状态返回推荐模式 | 单元测试：未配置→推荐字幕模式 |
| 4.1.4 | 前端 | 创建 `LLMStatusBadge` 组件 | 显示状态标签：绿(已配置)/橙(未配置)/红(配置无效) | UI正确显示颜色和图标 |
| 4.1.5 | 前端 | 在设置页面集成状态显示 | 设置页显示LLM状态Badge | 页面加载无报错 |

**验收标准：** 设置页面显示正确的LLM配置状态Badge

---

##### 4.2 模式选择引导弹窗

| 序号 | 责任人 | 具体动作 | 验收标准 | 完成标志 |
|------|--------|---------|---------|---------|
| 4.2.1 | 前端 | 设计 `ModeSelectionModal` 组件结构 | 标题+状态提示+模式卡片列表+帮助链接 | 组件可渲染 |
| 4.2.2 | 前端 | 实现模式卡片 `ModeCard` | 显示：图标+名称+描述+能力标签+推荐标识 | 点击卡片触发回调 |
| 4.2.3 | 前端 | 实现演示模式警告样式 | 橙色边框+⚠️图标+警告文案 | Demo模式卡片有明显区分 |
| 4.2.4 | 前端 | 实现模式选择回调 | 选中模式后关闭弹窗，传递mode给上传接口 | 网络请求包含正确mode参数 |
| 4.2.5 | 前端 | 在上传按钮点击时触发检测 | 调用 `useLLMConfig`，根据状态决定是否弹窗 | 流程：点击上传→检测→弹窗/直接打开文件选择器 |

**验收标准：**
- 未配置LLM时点击上传，弹出模式选择框
- 模式选择框显示4种模式，推荐模式置顶
- 选择模式后正常打开文件选择器

---

##### 4.3 结果展示与状态显示

| 序号 | 责任人 | 具体动作 | 验收标准 | 完成标志 |
|------|--------|---------|---------|---------|
| 4.3.1 | 前端 | 创建 `ProcessingResult` 组件 | 显示模式标识+质量星级+警告信息 | Demo模式显示橙色警告 |
| 4.3.2 | 前端 | 创建 `ProcessingStatus` 组件 | 项目详情页显示当前模式+质量指示+降级提示 | 处理中的项目实时更新 |
| 4.3.3 | 前端 | 实现降级状态提示 | 降级时显示警告Alert，解释原因 | 组件接收degraded prop |
| 4.3.4 | 前端 | 修改项目列表卡片显示模式 | 卡片显示当前处理模式标签 | 未配置LLM项目显示"字幕模式" |
| 4.3.5 | 前端 | 添加"了解更多"链接 | 弹窗底部链接到帮助文档 | 链接可点击跳转 |

**验收标准：**
- 项目详情页显示处理模式Badge
- Demo模式输出显示⚠️警告
- 降级处理的项目显示降级原因

---

### Phase 4: 测试验证（第6天）

#### Day 6: 测试执行

##### 5.1 单元测试

| 序号 | 责任人 | 具体动作 | 验收标准 | 测试工具 |
|------|--------|---------|---------|---------|
| 5.1.1 | 后端 | 测试LLMConfigStatus枚举 | 6个枚举值可正确序列化 | pytest |
| 5.1.2 | 后端 | 测试ProcessMode枚举 | 4个枚举值可正确序列化 | pytest |
| 5.1.3 | 后端 | 测试 `get_config_status()` 方法 | Mock API失败/成功/配额耗尽返回正确状态 | pytest + mock |
| 5.1.4 | 后端 | 测试 `local_scorer.score()` | 已知输入返回0-1之间的分数 | pytest |
| 5.1.5 | 后端 | 测试 `local_cluster.cluster()` | 10个片段聚成3类，无sklearn时用fallback | pytest |
| 5.1.6 | 后端 | 测试 `PipelineDirector.decide_mode()` | LLM可用→ai_smart，LLM不可用→subtitle | pytest |
| 5.1.7 | 后端 | 测试配置快照创建和读取 | 创建后读取内容一致 | pytest |
| 5.1.8 | 前端 | 测试 `useLLMConfig` Hook | Mock API返回不同状态，推荐结果正确 | Vitest + msw |

**单元测试覆盖率目标：** 
- 后端核心模块 > 80%
- 前端Hook > 70%

---

##### 5.2 集成测试

| 序号 | 责任人 | 具体动作 | 验收标准 | 测试工具 |
|------|--------|---------|---------|---------|
| 5.2.1 | 后端 | 测试完整AI智能模式Pipeline | 上传视频→执行Step1-6→输出完整结果 | pytest + 真实视频文件 |
| 5.2.2 | 后端 | 测试字幕整理模式Pipeline | 指定mode=subtitle_organized→不调用LLM→输出字幕 | pytest |
| 5.2.3 | 后端 | 测试降级链路 | Mock LLM失败→自动降级→字幕模式完成 | pytest + mock |
| 5.2.4 | 后端 | 测试配置快照锁定 | 任务开始后修改LLM→不影响任务执行 | pytest |
| 5.2.5 | 后端 | 测试错误处理 | LLM失败→降级→再失败→友好错误 | pytest |
| 5.2.6 | 前端 | 测试模式选择流程 | 未配置→弹窗→选择→上传 | Playwright |
| 5.2.7 | 前端 | 测试Demo模式警告显示 | 预览模式结果→显示⚠️警告 | Playwright |
| 5.2.8 | 全栈 | 测试E2E：LLM未配置场景 | 前端检测→弹窗→选字幕模式→处理成功 | Playwright |

**集成测试验收标准：** 所有测试用例通过，代码覆盖率达标

---

### Phase 5: 上线部署（第7天）

#### Day 7: 灰度发布

##### 6.1 上线前检查清单

| 序号 | 责任人 | 具体动作 | 验收标准 | 完成标志 |
|------|--------|---------|---------|---------|
| 6.1.1 | 后端 | 代码Review通过 | 无高危代码问题 | Review记录 |
| 6.1.2 | 后端 | 所有单元测试通过 | `pytest --cov` 覆盖率达标 | 覆盖率报告 |
| 6.1.3 | 后端 | 数据库迁移脚本准备 | `alembic upgrade head` 无报错 | 迁移执行成功 |
| 6.1.4 | 后端 | requirements.txt更新确认 | 包含scikit-learn依赖 | pip install成功 |
| 6.1.5 | 全栈 | API接口文档更新 | /llm-config-status 接口文档完整 | Swagger显示正确 |
| 6.1.6 | 测试 | 测试报告产出 | 覆盖所有关键路径 | 测试报告签字 |
| 6.1.7 | 运维 | 监控告警配置 | LLM异常状态监控+降级触发监控 | 告警规则生效 |

---

##### 6.2 灰度发布步骤

| 序号 | 责任人 | 具体动作 | 验收标准 | 回滚方案 |
|------|--------|---------|---------|---------|
| 6.2.1 | 运维 | 备份数据库 | 执行数据库全量备份 | 可恢复到备份点 |
| 6.2.2 | 运维 | 部署后端到预发布环境 | 新代码部署，无报错 | 代码回滚 |
| 6.2.3 | 运维 | 执行数据库迁移 | `alembic upgrade head` | `alembic downgrade -1` |
| 6.2.4 | 测试 | 预发布环境冒烟测试 | 核心功能验证通过 | 回滚发布 |
| 6.2.5 | 运维 | 灰度10%流量 | 新用户(新注册)使用新功能 | 切回100%旧代码 |
| 6.2.6 | 测试 | 灰度用户反馈收集 | 24小时内无高优Bug | 如有问题继续灰度 |
| 6.2.7 | 运维 | 全量发布 | 100%流量切换 | 回滚脚本准备完成 |

---

##### 6.3 上线后监控

| 序号 | 责任人 | 具体动作 | 验收标准 | 告警阈值 |
|------|--------|---------|---------|---------|
| 6.3.1 | 运维 | 监控LLM配置状态分布 | 统计各状态占比 | 异常状态>20%告警 |
| 6.3.2 | 运维 | 监控降级触发次数 | 统计每日降级次数 | 突增>50%告警 |
| 6.3.3 | 运维 | 监控处理成功率 | 统计各模式成功率 | 成功率<80%告警 |
| 6.3.4 | 运维 | 监控Demo模式使用率 | 统计预览模式占比 | 过高性能问题 |
| 6.3.5 | 运维 | 收集用户反馈 | 收集模式选择偏好 | 优化推荐策略 |

---

## 三、核心坑点及避坑方案

### 坑点1: 前后端枚举不一致 🔴

**问题描述：**
```
后端定义: ProcessMode.AI_SMART = "ai_smart"
前端定义: AI_SMART = "ai_smart" // 可能拼写不同
```

**风险影响：** 模式参数传递错误，导致功能异常

**避坑方案：**
```python
# 方案1: 枚举文件前后端共享（推荐）
# 创建 shared/enums.ts，TypeScript和Python都引用
# backend/models/enums.py 生成 types/enums.ts

# 方案2: 接口协议严格约束
# 接口返回mode字段必须是预定义的枚举字符串
# 前端严格校验，非合法值拒绝处理

# 方案3: 契约测试
# 自动化测试验证前后端枚举一致性
@pytest.fixture
def enum_contract():
    response = requests.get("/api/v1/enums")
    expected_modes = ["ai_smart", "subtitle_organized", "quick_preview", "raw_transcript"]
    assert set(response.json()["process_modes"]) == set(expected_modes)
```

**验收测试：**
```typescript
// frontend/src/__tests__/enumContract.test.ts
import { ProcessMode } from '../types/mode';

it('should have matching enum values with backend', async () => {
  const response = await api.getEnums();
  const backendModes = response.data.process_modes;
  
  Object.values(ProcessMode).forEach(mode => {
    expect(backendModes).toContain(mode);
  });
});
```

---

### 坑点2: sklearn依赖缺失导致ImportError 🔴

**问题描述：**
```python
# 生产环境可能没有安装sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
# ImportError: No module named 'sklearn'
```

**风险影响：** 本地降级算法完全不可用

**避坑方案：**
```python
def local_cluster_clips(clips: List[Dict], n_clusters: int = 3) -> List[List[Dict]]:
    """聚类算法，sklearn不可用时使用简单fallback"""
    
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans
        
        # 正常的TF-IDF聚类逻辑
        ...
        
    except ImportError:
        logger.warning("sklearn不可用，使用简单分组算法")
        return _simple_grouping_fallback(clips, n_clusters)


def _simple_grouping_fallback(clips: List[Dict], n_clusters: int) -> List[List[Dict]]:
    """简单的round-robin分组，作为sklearn缺失时的兜底"""
    
    if not clips:
        return []
    
    result = [[] for _ in range(min(n_clusters, len(clips)))]
    
    for i, clip in enumerate(clips):
        group_index = i % len(result)
        result[group_index].append(clip)
    
    return [group for group in result if group]  # 过滤空组
```

**验收测试：**
```python
# 测试sklearn缺失场景
import sys
original_modules = sys.modules.copy()

# 模拟sklearn不可用
sys.modules['sklearn'] = None
sys.modules['sklearn.feature_extraction'] = None

try:
    from backend.utils.local_cluster import local_cluster_clips
    result = local_cluster_clips(test_clips, 3)
    assert len(result) > 0  # 仍然返回结果
finally:
    # 恢复原始状态
    sys.modules.update(original_modules)
```

---

### 坑点3: 本地评分算法产生误导性结果 🟡

**问题描述：**
```
字幕长 = "内容丰富" → 实际可能是废话
音频能量高 = "激动人心" → 实际可能是噪音
```

**风险影响：** 用户使用预览模式得到低质量切片，误以为是正式输出

**避坑方案：**
```python
def local_score_clips(srt_data: List[Dict], audio_path: Path) -> List[Dict]:
    """
    改进的本地评分算法
    
    核心原则：
    1. 不声称是"精彩片段识别"，而是"字幕片段预览"
    2. 评分逻辑透明，用户可理解
    3. 所有切片都保留，不做筛选
    """
    
    scores = []
    
    for segment in srt_data:
        # 多维度评分，但权重都很低
        score = 0.0
        
        # 1. 字幕长度（适中为佳）
        length = len(segment['text'])
        if 20 <= length <= 80:
            score += 0.25  # 权重降低
        
        # 2. 音频能量（适中为佳）
        energy = get_audio_energy(segment, audio_path)
        if 0.3 <= energy <= 0.7:
            score += 0.25  # 权重降低
        
        # 3. 词汇多样性（重复少=可能更有内容）
        diversity = calculate_diversity(segment['text'])
        score += diversity * 0.25
        
        # 4. 专业术语（可能是重点）
        keywords = detect_keywords(segment['text'])
        score += min(len(keywords) * 0.05, 0.25)
        
        # 5. 不做任何筛选，保留所有片段
        # 用户可以看到所有片段，自行判断
        
        scores.append({
            **segment,
            'score': min(score, 1.0),
            'scoring_method': 'local_preview',  # 明确标注
            'quality_note': '仅供预览，非AI智能识别'  # 明确提示
        })
    
    return scores
```

**前端展示：**
```tsx
// PreviewResultCard.tsx
<div className="preview-mode-indicator">
  <Tag color="orange">⚠️ 预览模式</Tag>
  <span className="quality-note">
    本结果为本地算法模拟，非AI智能识别，仅供参考
  </span>
</div>
```

---

### 坑点4: 前端弹窗阻断用户体验 🟡

**问题描述：**
```
用户行为：快速点击上传 → 弹窗弹出 → 打断操作
预期行为：应该让用户快速完成操作
```

**风险影响：** 用户体验下降，投诉增加

**避坑方案：**
```tsx
const UploadButton: React.FC = () => {
  const { configStatus, shouldShowGuide } = useLLMConfig();
  const [pendingUpload, setPendingUpload] = useState(false);
  
  const handleClick = async () => {
    // 1. 立即打开文件选择器（不阻塞）
    const file = await selectFile();
    
    if (!file) return;  // 用户取消
  
    // 2. 选择文件后，再检测是否需要引导
    const needsGuide = shouldShowGuide();
    
    if (needsGuide) {
      // 3. 有引导需求时，设置为pending状态
      setPendingUpload({ file, needsGuide: true });
    } else {
      // 4. 无引导需求，直接上传
      uploadFile(file, ProcessMode.AI_SMART);
    }
  };
  
  const handleModeSelected = (mode: ProcessMode) => {
    // 用户选择了模式，继续上传
    uploadFile(pendingUpload.file, mode);
    setPendingUpload(null);
  };
  
  return (
    <>
      <Button onClick={handleClick}>上传视频</Button>
      
      {pendingUpload && (
        <ModeSelectionModal
          open={true}
          onSelect={handleModeSelected}
          onCancel={() => setPendingUpload(null)}
        />
      )}
    </>
  );
};
```

---

### 坑点5: 降级链路中状态同步丢失 🟡

**问题描述：**
```
1. 项目开始时快照：mode=ai_smart
2. 处理到Step3时，LLM配额耗尽
3. 系统降级到字幕整理模式
4. 用户看到最终结果，不知道中间降级过
```

**风险影响：** 用户困惑，不知道结果为什么"不完整"

**避坑方案：**
```python
class PipelineDirector:
    async def execute_with_degradation(self, project_id, ...):
        # 记录降级历史
        degradation_history = []
        
        try:
            result = await self._execute_current_strategy(...)
            
            # 检查是否发生了降级
            if result.quality_level < self._initial_quality_level:
                degradation_history.append({
                    'from_level': self._initial_quality_level,
                    'to_level': result.quality_level,
                    'reason': result.errors[-1] if result.errors else 'unknown',
                    'at_step': result.completed_step,
                    'timestamp': datetime.now().isoformat()
                })
            
            # 保存降级历史
            await self._save_degradation_history(project_id, degradation_history)
            
            return result
            
        except Exception as e:
            # 降级失败的处理
            ...
```

**前端展示：**
```tsx
const ProcessingResult: React.FC = ({ result }) => {
  if (result.degradation_history?.length > 0) {
    return (
      <div className="result-with-degradation">
        <Alert
          type="warning"
          message="处理过程中发生了降级"
          description={
            <ul>
              {result.degradation_history.map((d, i) => (
                <li key={i}>
                  Step {d.at_step} 时从 Level{d.from_level} 
                  降级到 Level{d.to_level}：{d.reason}
                </li>
              ))}
            </ul>
          }
        />
        
        {/* 正常显示结果 */}
        {result.content}
      </div>
    );
  }
  
  return <div>{result.content}</div>;
};
```

---

### 坑点6: 配置快照与实际执行环境不一致 🟡

**问题描述：**
```
1. 用户配置了API Key A，项目1开始处理
2. 用户修改为API Key B
3. 项目1在处理中途读取了新的API Key（快照失效）
```

**风险影响：** 结果不一致，历史项目无法复现

**避坑方案：**
```python
class ConfigSnapshotManager:
    async def create_snapshot(self, project_id, mode, llm_status):
        # 1. 加密存储API Key（防止明文泄露）
        encrypted_key = self._encrypt_api_key(llm_status.api_key)
        
        snapshot = ProjectSnapshot(
            project_id=project_id,
            mode=mode,
            llm_api_key_encrypted=encrypted_key,  # 关键：存储加密Key
            llm_provider=llm_status.provider,
            llm_model=llm_status.model,
            processing_config=json.dumps(self._get_current_config()),
            is_locked=True,
            created_at=datetime.now()
        )
        
        self.db.add(snapshot)
        await self.db.commit()
        
        return snapshot
    
    def get_decrypted_config(self, project_id):
        """获取解密后的配置，用于执行"""
        snapshot = self._get_active_snapshot(project_id)
        
        # 每次都从快照解密，不从环境变量读取
        decrypted_key = self._decrypt_api_key(snapshot.llm_api_key_encrypted)
        
        return {
            'api_key': decrypted_key,
            'provider': snapshot.llm_provider,
            'model': snapshot.llm_model,
            'config': json.loads(snapshot.processing_config)
        }
```

---

## 四、上线验证场景清单

### 验证场景 1: LLM未配置场景

| 项目 | 内容 |
|------|------|
| **前置条件** | 后端 `.env` 中 `API_DASHSCOPE_API_KEY` 为空 |
| **操作步骤** | 1. 访问前端首页 2. 点击"上传视频"按钮 3. 观察弹窗 |
| **预期结果** | 弹出模式选择框，显示4种模式，字幕整理模式被推荐 |
| **验收标准** | ✅ 弹窗正常显示 ✅ 推荐模式正确 ✅ 可选择模式继续 |
| **回归检查** | 原有的"静默跳过"行为已消除 |

---

### 验证场景 2: LLM已配置场景

| 项目 | 内容 |
|------|------|
| **前置条件** | 后端配置了有效的 `API_DASHSCOPE_API_KEY` |
| **操作步骤** | 1. 访问首页 2. 点击"上传视频" 3. 选择本地视频上传 |
| **预期结果** | 直接打开文件选择器，不弹窗（LLM可用） |
| **验收标准** | ✅ 无弹窗阻断 ✅ AI智能模式处理 ✅ 完整输出 |

---

### 验证场景 3: AI智能模式完整流程

| 项目 | 内容 |
|------|------|
| **前置条件** | LLM配置正常，配额充足 |
| **操作步骤** | 1. 上传一个5分钟测试视频 2. 选择AI智能模式 3. 等待处理完成 |
| **预期结果** | 输出包含：大纲、时间线、精彩片段(评分>0.7)、智能标题、聚类合集 |
| **验收标准** | ✅ Step1-6全部执行 ✅ outputs包含所有预期字段 ✅ 无报错 |

---

### 验证场景 4: 字幕整理模式流程

| 项目 | 内容 |
|------|------|
| **前置条件** | LLM未配置或配额耗尽 |
| **操作步骤** | 1. 上传测试视频 2. 选择"字幕整理模式" 3. 等待处理 |
| **预期结果** | 输出仅包含整理后的字幕文件，无精彩片段、无标题 |
| **验收标准** | ✅ 字幕文件生成 ✅ outputs只有subtitle字段 ✅ 无LLM调用日志 |

---

### 验证场景 5: 快速预览模式（Demo）

| 项目 | 内容 |
|------|------|
| **前置条件** | 任意LLM状态 |
| **操作步骤** | 1. 上传测试视频 2. 选择"快速预览"模式 3. 查看结果 |
| **预期结果** | 结果显示⚠️警告标签，标注"仅供演示，不可用于正式业务" |
| **验收标准** | ✅ 结果标记is_demo=True ✅ UI显示橙色警告 ✅ 质量星级≤1 |

---

### 验证场景 6: 处理中LLM状态变化（降级触发）

| 项目 | 内容 |
|------|------|
| **前置条件** | 项目处理到Step3时，人为关闭LLM服务 |
| **操作步骤** | 1. 开始处理AI智能模式项目 2. 在Step3时关闭LLM 3. 观察处理结果 |
| **预期结果** | 系统自动降级到字幕整理模式，继续完成处理 |
| **验收标准** | ✅ 项目状态变为"降级中" ✅ 最终结果包含降级历史记录 ✅ 用户看到降级提示 |

---

### 验证场景 7: 所有策略均失败（友好错误）

| 项目 | 内容 |
|------|------|
| **前置条件** | 模拟字幕生成也失败的情况（视频文件损坏） |
| **操作步骤** | 1. 上传损坏的视频文件 2. 尝试处理 3. 观察错误提示 |
| **预期结果** | 返回用户友好的错误信息，说明失败原因和解决建议 |
| **验收标准** | ✅ 无技术堆栈信息泄露 ✅ 错误信息包含解决建议 ✅ 不影响其他项目 |

---

### 验证场景 8: 配置快照锁定验证

| 项目 | 内容 |
|------|------|
| **前置条件** | 项目A使用API Key A开始处理 |
| **操作步骤** | 1. 项目A开始处理(Step1) 2. 修改.env为API Key B 3. 观察项目A的执行 |
| **预期结果** | 项目A继续使用API Key A完成处理，不受后续修改影响 |
| **验收标准** | ✅ 项目A日志显示使用旧Key ✅ 项目A正常完成 ✅ 项目B(新项目)使用新Key |

---

### 验证场景 9: 前端模式选择弹窗交互

| 项目 | 内容 |
|------|------|
| **前置条件** | LLM未配置状态 |
| **操作步骤** | 1. 点击上传按钮 2. 弹窗出现 3. 选择字幕整理模式 4. 继续上传 |
| **预期结果** | 弹窗正常关闭，文件选择器打开，上传携带正确mode参数 |
| **验收标准** | ✅ 弹窗可关闭 ✅ 选择模式后触发正确回调 ✅ 网络请求包含mode字段 |

---

### 验证场景 10: 历史项目不受影响

| 项目 | 内容 |
|------|------|
| **前置条件** | 存在已完成的老项目（无mode字段） |
| **操作步骤** | 1. 查看老项目详情 2. 尝试重新处理老项目 3. 新项目使用新功能 |
| **预期结果** | 老项目正常显示（兼容旧数据），新项目使用新功能 |
| **验收标准** | ✅ 老项目可正常打开 ✅ 老项目字段兼容 ✅ 新功能正常 |

---

## 五、验收checklist

### 上线前必须完成

```markdown
## 技术验收

- [ ] 后端枚举定义完整（LLMConfigStatus 6个值，ProcessMode 4个值）
- [ ] `/llm-config-status` 接口返回正确状态
- [ ] 策略基类 `PipelineStrategy` 所有子类可正常实例化
- [ ] 本地评分算法无sklearn环境可运行（fallback生效）
- [ ] 本地聚类算法无sklearn环境可运行（fallback生效）
- [ ] 降级链路测试：AI→字幕→原始→友好错误
- [ ] 配置快照创建和读取测试通过
- [ ] 前端枚举与后端枚举字符串完全一致
- [ ] 模式选择弹窗可正常显示和交互
- [ ] Demo模式结果有⚠️警告标识
- [ ] 降级历史记录正确保存
- [ ] 所有单元测试通过（覆盖率>80%）
- [ ] 所有集成测试通过

## 功能验收

- [ ] LLM未配置时，点击上传弹窗引导
- [ ] LLM已配置时，无弹窗直接上传
- [ ] AI智能模式完整流程可执行
- [ ] 字幕整理模式不调用LLM
- [ ] 快速预览模式标注Demo警告
- [ ] 处理中途LLM失效，自动降级
- [ ] 所有策略失败返回友好错误
- [ ] 历史项目正常访问

## 性能验收

- [ ] 接口响应时间 < 200ms（状态查询）
- [ ] 降级决策时间 < 1s
- [ ] 前端弹窗加载 < 500ms
- [ ] 无sklearn环境下聚类时间 < 5s（100个片段）

## 安全验收

- [ ] API Key加密存储，不明文保存
- [ ] 错误信息无堆栈泄露
- [ ] 前端无敏感信息打印

## 文档验收

- [ ] API接口文档更新完整
- [ ] 新增接口有使用示例
- [ ] 错误码有对应说明
```

---

## 六、时间线甘特图

```
Day 1     Day 2     Day 3     Day 4     Day 5     Day 6     Day 7
┌─────────┬─────────┬─────────┬─────────┬─────────┬─────────┐
│ 依赖确认  │ 模型设计  │ 枚举实现  │ 调度器   │ 前端集成  │ 测试验证  │ 灰度上线  │
│ +环境准备 │ +接口契约 │ +策略基类 │ +降级链路 │ +弹窗组件 │ +E2E测试  │ +监控配置  │
│          │          │ +本地算法 │          │ +结果展示 │          │          │
└─────────┴─────────┴─────────┴─────────┴─────────┴─────────┴─────────┘
    ↓           ↓           ↓           ↓           ↓           ↓
  交付物      交付物      交付物      交付物      交付物      交付物
 枚举文件     接口文档    核心代码    完整Pipeline  前端组件   测试报告
 依赖报告     模型设计    策略实现    降级链路     弹窗交互    覆盖率报告
```

---

*文档版本: v1.0*
*执行负责人: 技术团队*
*计划周期: 7天*
*状态: 准备执行*
