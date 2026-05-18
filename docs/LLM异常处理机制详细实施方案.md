# LLM 异常处理机制详细实施方案

---

## 一、背景与目标

### 1.1 问题现状

当前系统存在以下问题：

| 问题 | 描述 | 影响 |
|------|------|------|
| 静默跳过 | LLM 未配置时，后端静默跳过 step1-step5 | 用户不知道发生了什么 |
| 状态模糊 | 前端显示"导入中"，无法区分进行中/完成/失败 | 用户体验差 |
| 输出为空 | 视频处理完成但 step1-step6 输出为空 | 用户困惑 |
| 资源浪费 | 用户等待半天得到空结果 | 用户不满 |

### 1.2 改进目标

1. **前置检测**：上传前检查 LLM 配置状态
2. **明确引导**：未配置时引导用户配置或选择降级模式
3. **降级策略**：无 LLM 时提供本地替代方案
4. **透明反馈**：让用户清楚知道当前处理状态

---

## 二、配置状态定义

### 2.1 LLM 配置状态枚举

```python
class LLMConfigStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"           # 完全未配置
    INVALID_KEY = "invalid_key"                 # API Key 无效
    SERVICE_UNAVAILABLE = "service_unavailable" # 服务不可用
    RATE_LIMITED = "rate_limited"              # 配额用完
    CONNECTION_FAILED = "connection_failed"     # 连接失败
    CONFIGURED = "configured"                 # 正常可用
```

### 2.2 处理模式枚举

```python
class ProcessMode(str, Enum):
    FULL = "full"           # 完整流程（需要LLM）
    LOCAL_ONLY = "local"    # 本地降级（无需LLM）
    SUBTITLE_ONLY = "subtitle"  # 仅字幕模式
```

### 2.3 项目状态枚举

```python
class ProjectStatus(str, Enum):
    PENDING = "pending"          # 待处理
    PROCESSING = "processing"   # 处理中
    COMPLETED = "completed"      # 完全成功
    PARTIAL = "partial"         # 部分成功（降级模式）
    FAILED = "failed"           # 处理失败
```

---

## 三、前置检测机制

### 3.1 后端接口

**接口路径**：`GET /api/v1/settings/llm-config-status`

**响应示例**：

```json
{
  "status": "not_configured",
  "message": "请先配置AI模型才能进行完整处理",
  "required": true,
  "available_modes": ["local", "subtitle"]
}
```

**详细状态响应**：

```json
{
  "status": "configured",
  "message": "AI模型已配置并可用",
  "required": false,
  "provider": "zhipu",
  "model": "glm-4"
}
```

### 3.2 错误状态响应

```json
{
  "status": "invalid_key",
  "message": "您配置的API密钥无效，请重新配置。",
  "required": true,
  "available_modes": ["local", "subtitle"]
}
```

```json
{
  "status": "rate_limited",
  "message": "AI模型配额已用完，请稍后再试。",
  "required": true,
  "available_modes": ["local", "subtitle"],
  "retry_after": 3600
}
```

### 3.3 前端上传前检查流程

```
┌─────────────────────────────────────────────────────────────┐
│                      用户上传视频                            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│            调用 GET /api/v1/settings/llm-config-status       │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   NOT_CONFIGURED         ERROR状态          CONFIGURED
          │                   │                   │
          ▼                   ▼                   ▼
   ┌────────────┐      ┌────────────┐      ┌────────────┐
   │显示引导弹窗│      │显示错误弹窗│      │  正常上传  │
   └────────────┘      └────────────┘      └────────────┘
          │                   │                   │
          ▼                   ▼                   ▼
   ┌────────────┐      ┌────────────┐           结束
   │ 模式选择   │      │ 重新配置   │
   ├────────────┤      └────────────┘
   │完整流程※  │
   │本地降级   │
   │仅字幕模式 │
   └────────────┘
          │
          ▼
   用户选择模式后继续上传
```

### 3.4 前端引导弹窗文案

| 状态 | 标题 | 提示语 | 可选模式 |
|------|------|--------|---------|
| not_configured | 需要配置AI模型 | 上传视频需要AI模型支持才能进行完整处理 | 本地降级、仅字幕 |
| invalid_key | AI模型配置无效 | 您配置的API密钥无效，请重新配置 | 本地降级、仅字幕 |
| rate_limited | AI模型配额用完 | AI模型配额已用完，请稍后再试或使用降级模式 | 本地降级、仅字幕 |
| service_unavailable | AI模型服务不可用 | AI模型服务暂时不可用，请稍后再试 | 本地降级、仅字幕 |

---

## 四、降级策略实现

### 4.1 降级模式选择

| 模式 | 说明 | 适用场景 | LLM依赖 |
|------|------|---------|---------|
| `full` | 完整流程 | 需要完整功能（大纲、时间线、精彩片段） | 必须 |
| `local` | 本地降级 | 无LLM但想要基本分析 | 不依赖 |
| `subtitle` | 仅字幕 | 只需字幕文件 | 不依赖 |

### 4.2 降级模式流程对比

```
【完整流程 - FULL】

FunASR字幕 ──→ Step1大纲 ──→ Step2时间线 ──→ Step3评分 ──→ Step4标题 ──→ Step5聚类 ──→ Step6切割
   LLM         LLM           LLM           LLM          LLM         LLM         LLM

【本地降级 - LOCAL】

FunASR字幕 ──→ 本地分块 ──→ 字幕时间戳 ──→ 本地评分 ──→ 字幕前N字 ──→ TF-IDF聚类 ──→ 按评分切割
   本地         沉默检测     直接使用       音频+长度     简单截取     sklearn     本地算法

【仅字幕 - SUBTITLE】

FunASR字幕 ──→ 结束
   本地
```

### 4.3 本地替代算法详情

| 步骤 | 原算法 | 本地替代 | 算法说明 | 质量 |
|------|--------|---------|---------|------|
| Step 1 | LLM语义分块 | 沉默检测分块 | 基于音频间隙检测切分点 | 中 |
| Step 2 | LLM提取时间点 | 字幕时间戳直接使用 | 每个字幕片段作为一个时间节点 | 高 |
| Step 3 | LLM内容评分 | 音频能量+字幕长度 | 声音大+字幕长=高分 | 中 |
| Step 4 | LLM生成标题 | 字幕前20字 | 直接截取字幕文本 | 低 |
| Step 5 | LLM主题聚类 | TF-IDF聚类 | sklearn K-Means 聚类 | 中 |

---

## 五、核心代码实现

### 5.1 新增枚举定义

**文件**：`backend/models/enums.py`

```python
class LLMConfigStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    INVALID_KEY = "invalid_key"
    SERVICE_UNAVAILABLE = "service_unavailable"
    RATE_LIMITED = "rate_limited"
    CONNECTION_FAILED = "connection_failed"
    CONFIGURED = "configured"


class ProcessMode(str, Enum):
    FULL = "full"
    LOCAL_ONLY = "local"
    SUBTITLE_ONLY = "subtitle"
```

### 5.2 新增接口

**文件**：`backend/api/v1/settings.py`

```python
@router.get("/llm-config-status")
async def get_llm_config_status():
    """获取LLM配置详细状态"""
    manager = get_llm_manager()
    return manager.get_config_status()
```

### 5.3 本地评分算法

**文件**：`backend/utils/local_scorer.py`

```python
def local_score_clips(srt_path: Path, audio_path: Path = None) -> List[Dict]:
    """
    本地评分：基于音频能量 + 字幕长度

    Args:
        srt_path: 字幕文件路径
        audio_path: 音频文件路径（可选）

    Returns:
        带评分的片段列表
    """
    scores = []

    # 1. 音频能量分析
    audio_scores = {}
    if audio_path and audio_path.exists():
        audio_scores = analyze_audio_energy(audio_path)

    # 2. 字幕长度分析
    srt_data = parse_srt(srt_path)

    for i, segment in enumerate(srt_data):
        # 综合评分
        score = 0.5  # 基础分

        # 字幕长度加分（长字幕 = 信息量大）
        text_length = len(segment['text'].replace(' ', ''))
        if text_length > 50:
            score += 0.2
        elif text_length > 30:
            score += 0.1

        # 音频能量加分
        if i in audio_scores and audio_scores[i] > 0.6:
            score += 0.3
        elif i in audio_scores and audio_scores[i] > 0.4:
            score += 0.15

        scores.append({
            'index': i,
            'start': segment['start'],
            'end': segment['end'],
            'text': segment['text'],
            'score': min(score, 1.0),
            'scoring_method': 'local'
        })

    # 按评分排序
    scores.sort(key=lambda x: x['score'], reverse=True)

    return scores
```

### 5.4 本地聚类算法

**文件**：`backend/utils/local_cluster.py`

```python
def local_cluster_clips(clips: List[Dict], n_clusters: int = 3) -> List[List[Dict]]:
    """
    本地聚类：基于 TF-IDF + K-Means
    """
    if len(clips) < n_clusters:
        return [[clip] for clip in clips]

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans

        texts = [clip['text'] for clip in clips]
        vectorizer = TfidfVectorizer(max_features=100)
        tfidf_matrix = vectorizer.fit_transform(texts)
        kmeans = KMeans(n_clusters=min(n_clusters, len(clips)))
        cluster_labels = kmeans.fit_predict(tfidf_matrix)

        result = [[] for _ in range(n_clusters)]
        for clip, label in zip(clips, cluster_labels):
            result[label].append(clip)

        return [group for group in result if group]

    except ImportError:
        return simple_grouping(clips, n_clusters)
```

### 5.5 Pipeline 改造

**文件**：`backend/services/simple_pipeline_adapter.py`

```python
class SimplePipelineAdapter:
    def __init__(self, project_id: str, task_id: str, mode: ProcessMode = ProcessMode.FULL):
        self.project_id = project_id
        self.task_id = task_id
        self.mode = mode

    async def process_project_sync(self, input_video_path: str, input_srt_path: str) -> Dict[str, Any]:
        result = {
            "status": "succeeded",
            "mode": self.mode,
            "warnings": [],
            "failed_steps": []
        }

        # 阶段1: 素材准备
        emit_progress(self.project_id, "INGEST", "素材准备完成")

        # 阶段2: 字幕处理（所有模式都需要）
        subtitle_path = await self._process_subtitle(input_video_path, input_srt_path)
        result["subtitle"] = str(subtitle_path) if subtitle_path else None

        # 根据模式选择处理流程
        if self.mode == ProcessMode.SUBTITLE_ONLY:
            result["status"] = "succeeded"
            result["message"] = "字幕生成完成"
            return result

        elif self.mode == ProcessMode.LOCAL_ONLY:
            return await self._process_local_flow(subtitle_path, input_video_path, result)

        else:
            return await self._process_full_flow(subtitle_path, input_video_path, result)
```

### 5.6 本地降级流程

```python
async def _process_local_flow(self, subtitle_path, input_video_path, result):
    """本地降级流程 - 不需要LLM"""
    from backend.utils.local_scorer import local_score_clips
    from backend.utils.local_cluster import local_cluster_clips
    from backend.utils.local_title import local_generate_titles

    try:
        # Step 1: 本地分块（沉默检测）
        chunks = self._local_chunk_by_silence(subtitle_path)
        emit_progress(self.project_id, "ANALYZE", "分块完成", subpercent=20)

        # Step 2: 直接使用字幕时间戳
        timeline = self._timeline_from_subtitle(subtitle_path)
        emit_progress(self.project_id, "ANALYZE", "时间线生成完成", subpercent=40)

        # Step 3: 本地评分
        scored_clips = local_score_clips(subtitle_path, self._audio_path)
        emit_progress(self.project_id, "ANALYZE", "内容评分完成", subpercent=60)

        # Step 4: 本地标题
        titled_clips = local_generate_titles(scored_clips)
        emit_progress(self.project_id, "HIGHLIGHT", "标题生成完成", subpercent=80)

        # Step 5: TF-IDF聚类
        collections = local_cluster_clips(titled_clips, n_clusters=3)
        emit_progress(self.project_id, "HIGHLIGHT", "主题聚类完成", subpercent=90)

        # Step 6: 视频切割
        video_result = run_step6_video(...)

        return {
            **result,
            "status": "succeeded",
            "mode": "local",
            "warnings": ["使用本地降级算法，结果质量可能不如LLM"],
        }

    except Exception as e:
        return {
            **result,
            "status": "failed",
            "error": f"本地处理失败: {str(e)}",
            "code": "LOCAL_PROCESS_ERROR"
        }
```

---

## 六、接口修改

### 6.1 新增接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/settings/llm-config-status` | 获取LLM配置状态 |

### 6.2 修改上传接口

**文件**：`backend/api/v1/projects.py`

```python
class UploadRequest(BaseModel):
    # ... 现有字段
    mode: ProcessMode = ProcessMode.FULL  # 新增：处理模式
```

---

## 七、前端改造

### 7.1 上传前检查 Hook

```typescript
// hooks/useLLMConfigCheck.ts

export const useLLMConfigCheck = () => {
  const checkBeforeUpload = async () => {
    const response = await api.getLLMConfigStatus();
    return response.data;
  };

  return { checkBeforeUpload };
};
```

### 7.2 上传按钮组件

```typescript
// components/UploadButton.tsx

const UploadButton = () => {
  const { checkBeforeUpload } = useLLMConfigCheck();

  const handleClick = async () => {
    const status = await checkBeforeUpload();

    if (status.status !== 'configured' && status.required) {
      showConfigGuideModal({
        status: status.status,
        message: status.message,
        availableModes: status.available_modes,
        onSelectMode: (mode) => {
          setProcessMode(mode);
        },
        onGoToSettings: () => router.push('/settings'),
      });
      return;
    }

    openFilePicker();
  };

  return <Button onClick={handleClick}>上传视频</Button>;
};
```

### 7.3 配置状态显示组件

```typescript
// components/Settings/LLMStatusBadge.tsx

const LLMStatusBadge = () => {
  const { data: status } = useQuery(['llm-config-status'], api.getLLMConfigStatus);

  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'configured':
        return { color: 'green', text: '已配置', icon: <CheckCircle /> };
      case 'not_configured':
        return { color: 'orange', text: '未配置', icon: <Warning /> };
      case 'invalid_key':
        return { color: 'red', text: '配置无效', icon: <CloseCircle /> };
      default:
        return { color: 'gray', text: '未知', icon: <QuestionCircle /> };
    }
  };

  const config = getStatusConfig(status?.status);

  return (
    <Tag color={config.color} icon={config.icon}>
      {config.text}
    </Tag>
  );
};
```

### 7.4 配置引导弹窗

```typescript
// components/ConfigGuideModal.tsx

interface ConfigGuideModalProps {
  status: LLMConfigStatus;
  message: string;
  availableModes: ProcessMode[];
  onSelectMode: (mode: ProcessMode) => void;
  onGoToSettings: () => void;
  onCancel: () => void;
}

const ConfigGuideModal = ({ status, message, availableModes, onSelectMode, onGoToSettings, onCancel }: ConfigGuideModalProps) => {
  const modeOptions = {
    full: { label: '完整流程（需要配置AI）', description: '生成大纲、时间线、精彩片段等' },
    local: { label: '本地降级处理', description: '使用本地算法，仅生成基础分析' },
    subtitle: { label: '仅生成字幕', description: '仅提取字幕文件，不生成视频片段' }
  };

  return (
    <Modal
      title="需要配置AI模型"
      open={true}
      onCancel={onCancel}
      footer={null}
    >
      <p>{message}</p>

      <div style={{ marginTop: 16 }}>
        {availableModes.map(mode => (
          <div
            key={mode}
            style={{ padding: 12, border: '1px solid #d9d9d9', marginBottom: 8, cursor: 'pointer' }}
            onClick={() => onSelectMode(mode)}
          >
            <div>{modeOptions[mode].label}</div>
            <div style={{ color: '#888', fontSize: 12 }}>{modeOptions[mode].description}</div>
          </div>
        ))}
      </div>

      <Button type="link" onClick={onGoToSettings}>
        去配置AI模型
      </Button>
    </Modal>
  );
};
```

---

## 八、文件修改清单

### 8.1 后端文件

| 文件路径 | 修改类型 | 修改内容 |
|---------|---------|---------|
| `backend/models/enums.py` | 新增枚举 | `ProcessMode`, `LLMConfigStatus` |
| `backend/core/llm_manager.py` | 新增方法 | `get_config_status()` |
| `backend/api/v1/settings.py` | 新增接口 | `/llm-config-status` |
| `backend/api/v1/projects.py` | 修改接口 | `UploadRequest` 添加 `mode` 字段 |
| `backend/services/simple_pipeline_adapter.py` | 重构 | 支持多模式处理 |
| `backend/utils/local_scorer.py` | 新增文件 | 本地评分算法 |
| `backend/utils/local_cluster.py` | 新增文件 | 本地聚类算法 |
| `backend/utils/local_title.py` | 新增文件 | 本地标题生成 |

### 8.2 前端文件

| 文件路径 | 修改类型 | 修改内容 |
|---------|---------|---------|
| `frontend/src/hooks/useLLMConfigCheck.ts` | 新增文件 | LLM配置检查hook |
| `frontend/src/components/UploadButton.tsx` | 修改 | 上传前检查 |
| `frontend/src/components/ConfigGuideModal.tsx` | 新增文件 | 配置引导弹窗 |
| `frontend/src/components/Settings/LLMStatusBadge.tsx` | 新增文件 | 配置状态显示 |

---

## 九、测试计划

### 9.1 单元测试

| 测试用例 | 预期结果 |
|---------|---------|
| `test_llm_config_status_not_configured` | 返回 `not_configured` |
| `test_llm_config_status_invalid_key` | 返回 `invalid_key` |
| `test_llm_config_status_rate_limited` | 返回 `rate_limited` 并包含 `retry_after` |
| `test_local_scorer_basic` | 返回带分数的片段列表 |
| `test_local_scorer_with_audio` | 结合音频能量的评分 |
| `test_local_cluster_basic` | 返回分组结果 |
| `test_local_cluster_insufficient` | 片段不足时每组一个 |
| `test_pipeline_local_mode` | 本地模式完整流程执行成功 |
| `test_pipeline_subtitle_mode` | 仅字幕模式提前结束 |

### 9.2 集成测试

| 测试用例 | 预期结果 |
|---------|---------|
| 上传前未配置LLM | 显示引导弹窗 |
| 选择"本地降级"模式 | 使用本地算法处理 |
| 选择"仅字幕"模式 | 仅生成字幕文件 |
| 配置无效时上传 | 显示错误提示 |
| 配置有效时上传 | 正常完整流程 |
| 配额用完时上传 | 显示配额提示或降级选项 |

### 9.3 质量验证

| 验证项 | 方法 |
|--------|------|
| 本地评分合理性 | 人工对比音频能量和字幕长度与分数关系 |
| 聚类质量 | 人工评估聚类结果的相关性 |
| 降级vs完整对比 | 同一视频两种模式输出对比 |

---

## 十、上线 Checklist

- [ ] 后端接口测试通过
- [ ] 本地评分算法质量验证
- [ ] 本地聚类算法质量验证
- [ ] 前端引导弹窗体验验证
- [ ] 降级模式处理结果验证
- [ ] 完整流程回归测试
- [ ] 文档更新（用户指南）
- [ ] 监控报警配置（如有异常）

---

## 十一、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 本地算法质量差 | 用户体验下降 | 明确告知用户这是降级模式 |
| sklearn 依赖 | 某些环境可能缺失 | 提供 fallback 方案（简单分组） |
| 前端适配成本 | 需要前端团队配合 | 分阶段上线 |
| 状态同步问题 | 配置变更后处理中任务状态不一致 | 任务开始时锁定配置 |
| 用户误选模式 | 用户选了降级但不知道 | 弹窗中明确说明各模式区别 |

---

## 十二、后续优化方向

1. **算法优化**：改进本地评分和聚类算法质量
2. **智能推荐**：根据视频特点推荐最适合的模式
3. **进度优化**：本地模式可以更快完成，可提前告知用户
4. **结果对比**：提供降级模式和完整模式的对比展示
