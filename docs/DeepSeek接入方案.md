# DeepSeek AI模型提供商接入方案（v2，已更新为V4模型）

> **更新说明**：DeepSeek V4 系列已于 2026-04-24 发布，旧版 deepseek-chat / deepseek-reasoner 将于 2026-07-24 停用。本方案直接使用 V4 原生模型ID。

## 概述

新增 **DeepSeek** 作为独立的LLM提供商选项。DeepSeek V4 系列提供 OpenAI 兼容的 API 接口，具备 **1M tokens 上下文**和纯国产算力（昇腾910B/C）支持，价格约为通义千问的 1/3。

---

## 1. 支持模型

| 模型ID | 显示名称 | 上下文 | 特点 | 建议用途 |
|--------|---------|--------|------|---------|
| `deepseek-v4-flash` | DeepSeek V4 Flash | **1M tokens** | V4标准版，性价比之王 | **Step1边界识别、Step2评分（默认）** |
| `deepseek-v4-pro` | DeepSeek V4 Pro | **1M tokens** | V4旗舰版，最强性能 | 复杂边界判断、高精度场景 |

> **默认推荐**：`deepseek-v4-flash`（对标 qwen-plus，价格更低、上下文更大）。
> **不再使用**：`deepseek-chat` 和 `deepseek-reasoner`（2026-07-24 停用）。

### 关于1M上下文的战略意义

V4的1M上下文对SmartCut有直接影响：
- 一个45min视频的全量SRT文本通常 ≤ 20K tokens
- **窗口化Step1（C阶段）在V4下可能不再必要** — 全量SRT可直接单次提交给DeepSeek
- 这降低了C1滑动窗口的紧迫性，但仍保留作为非DeepSeek场景的备用方案

---

## 2. 技术可行性分析

### 2.1 API兼容性

DeepSeek 使用 **OpenAI 兼容格式**：

```
Base URL: https://api.deepseek.com/v1
```

请求/响应格式与已有 Provider 完全一致（OpenAIProvider、SiliconFlowProvider、TencentProvider、OllamaProvider、LMStudioProvider），可完全复用相同实现模板。

### 2.2 依赖

**无需新增依赖**。项目中 `openai` 库已安装。

---

## 3. 需要修改的文件（共7个）

### 3.1 后端改动（4个文件）

#### [backend/core/llm_providers.py](file:///e:/ClipProject/autoclip-main1/autoclip-main/backend/core/llm_providers.py)

**改动1：`ProviderType` 枚举增加 DEEPSEEK**

```python
class ProviderType(Enum):
    DASHSCOPE = "dashscope"
    OPENAI = "openai"
    GEMINI = "gemini"
    SILICONFLOW = "siliconflow"
    ZHIPU = "zhipu"
    TENCENT = "tencent"
    DEEPSEEK = "deepseek"        # ← 新增
    OLLAMA = "ollama"
    LMSTUDIO = "lmstudio"
```

**改动2：新增 `DeepSeekProvider` 类**（在 `TencentProvider` 之后、`OllamaProvider` 之前）

```python
class DeepSeekProvider(LLMProvider):
    """DeepSeek 大模型提供商（OpenAI 兼容接口），使用 V4 系列模型"""

    def __init__(self, api_key: str, model_name: str = "deepseek-v4-flash", **kwargs):
        super().__init__(api_key, model_name, **kwargs)
        try:
            import openai
            self.client = openai.OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com/v1"
            )
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

    def call(self, prompt: str, input_data: Any = None, **kwargs) -> LLMResponse:
        """调用 DeepSeek API（OpenAI 兼容接口）"""
        try:
            messages = self._build_chat_messages(prompt, input_data)

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                **kwargs
            )

            content = response.choices[0].message.content
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None

            return LLMResponse(
                content=content,
                usage=usage,
                model=self.model_name,
                finish_reason=response.choices[0].finish_reason
            )

        except Exception as e:
            logger.error(f"DeepSeek调用失败: {str(e)}")
            raise

    def test_connection(self) -> bool:
        """测试 DeepSeek 连接"""
        try:
            response = self.call("请回复'测试成功'")
            return "测试成功" in response.content or "success" in response.content.lower()
        except Exception as e:
            logger.error(f"DeepSeek连接测试失败: {e}")
            return False

    @staticmethod
    def get_available_models() -> List[ModelInfo]:
        """获取 DeepSeek 可用模型（V4 系列）"""
        return [
            ModelInfo(
                name="deepseek-v4-flash",
                display_name="DeepSeek V4 Flash",
                provider=ProviderType.DEEPSEEK,
                max_tokens=1_000_000,
                description="DeepSeek V4标准版，1M上下文，性价比极高"
            ),
            ModelInfo(
                name="deepseek-v4-pro",
                display_name="DeepSeek V4 Pro",
                provider=ProviderType.DEEPSEEK,
                max_tokens=1_000_000,
                description="DeepSeek V4旗舰版，1M上下文，最强性能"
            ),
        ]
```

**改动3：`LLMProviderFactory._providers` 注册 DeepSeek**

```python
class LLMProviderFactory:
    _providers = {
        ProviderType.DASHSCOPE: DashScopeProvider,
        ProviderType.OPENAI: OpenAIProvider,
        ProviderType.GEMINI: GeminiProvider,
        ProviderType.SILICONFLOW: SiliconFlowProvider,
        ProviderType.ZHIPU: ZhipuProvider,
        ProviderType.TENCENT: TencentProvider,
        ProviderType.DEEPSEEK: DeepSeekProvider,   # ← 新增
        ProviderType.OLLAMA: OllamaProvider,
        ProviderType.LMSTUDIO: LMStudioProvider,
    }
```

---

#### [backend/core/llm_manager.py](file:///e:/ClipProject/autoclip-main1/autoclip-main/backend/core/llm_manager.py)

**改动1：默认 settings 增加 DeepSeek 密钥字段**

```python
default_settings = {
    ...
    "siliconflow_api_key": "",
    "zhipu_api_key": "",
    "tencent_api_key": "",
    "deepseek_api_key": "",       # ← 新增
    "ollama_api_key": "",
    ...
}
```

**改动2：`_get_api_key_for_provider` 增加 DeepSeek 映射**

```python
key_mapping = {
    ...
    ProviderType.TENCENT: "tencent_api_key",
    ProviderType.DEEPSEEK: "deepseek_api_key",     # ← 新增
    ProviderType.OLLAMA: "ollama_api_key",
    ...
}
```

**改动3：`set_provider` 的 `key_mapping` 同步增加**

```python
key_mapping = {
    ...
    ProviderType.TENCENT: "tencent_api_key",
    ProviderType.DEEPSEEK: "deepseek_api_key",     # ← 新增
    ProviderType.OLLAMA: "ollama_api_key",
    ...
}
```

**改动4：`_get_provider_display_name` 增加 DeepSeek**

```python
display_names = {
    ...
    ProviderType.TENCENT: "腾讯混元",
    ProviderType.DEEPSEEK: "DeepSeek",              # ← 新增
    ProviderType.OLLAMA: "本地Ollama",
    ...
}
```

---

#### [backend/api/v1/settings.py](file:///e:/ClipProject/autoclip-main1/autoclip-main/backend/api/v1/settings.py)

**改动1：`provider_key_map` 在所有出现的地方增加 DeepSeek**

共需要修改 **5处** 相同的 `provider_key_map`（在不同API端点中重复出现）：

```python
provider_key_map = {
    ...
    'tencent': 'api_tencent_api_key',
    'deepseek': 'api_deepseek_api_key',     # ← 新增
    'ollama': 'api_ollama_api_key',
    ...
}
```

**改动2：`provider_names`（在`/current-provider`中）增加 DeepSeek**

```python
provider_names = {
    ...
    "tencent": "腾讯混元",
    "deepseek": "DeepSeek",
    "ollama": "本地Ollama",
    ...
}
```

**改动3：`GET /secure` 端点增加 DeepSeek 相关字段**

```python
result = {
    ...
    "api_tencent_api_key": secure_manager.mask_sensitive_value('api_tencent_api_key'),
    "api_deepseek_api_key": secure_manager.mask_sensitive_value('api_deepseek_api_key'),   # ← 新增
    "api_ollama_api_key": secure_manager.mask_sensitive_value('api_ollama_api_key'),
    ...
    # 无 api_ 前缀格式兼容
    "tencent_api_key": secure_manager.mask_sensitive_value('api_tencent_api_key'),
    "deepseek_api_key": secure_manager.mask_sensitive_value('api_deepseek_api_key'),       # ← 新增
    "ollama_api_key": secure_manager.mask_sensitive_value('api_ollama_api_key'),
    ...
    # has_* 标记
    "has_tencent_key": secure_manager.has_sensitive_value('api_tencent_api_key'),
    "has_deepseek_key": secure_manager.has_sensitive_value('api_deepseek_api_key'),        # ← 新增
    "has_ollama_key": secure_manager.has_sensitive_value('api_ollama_api_key'),
    ...
}
```

**改动4：`GET /settings` 端点增加 DeepSeek 密钥回显**

```python
"api_tencent_api_key": secure_manager.get_sensitive_value('api_tencent_api_key'),
"api_deepseek_api_key": secure_manager.get_sensitive_value('api_deepseek_api_key'),  # ← 新增
"api_ollama_api_key": secure_manager.get_sensitive_value('api_ollama_api_key'),
...
# 无 api_ 前缀
"tencent_api_key": secure_manager.get_sensitive_value('api_tencent_api_key'),
"deepseek_api_key": secure_manager.get_sensitive_value('api_deepseek_api_key'),      # ← 新增
"ollama_api_key": secure_manager.get_sensitive_value('api_ollama_api_key'),
```

**改动5：`POST /settings` 的 `field_mapping` 增加 DeepSeek**

```python
field_mapping = {
    ...
    'tencent_api_key': 'api_tencent_api_key',
    'deepseek_api_key': 'api_deepseek_api_key',     # ← 新增
    'ollama_api_key': 'api_ollama_api_key',
    ...
}
```

**改动6：`GET /available-models` 增加 DeepSeek 模型列表**

```python
"tencent": [...],
"deepseek": [
    {"name": "deepseek-v4-flash", "display_name": "DeepSeek V4 Flash", "max_tokens": 1000000, "description": "DeepSeek V4标准版，1M上下文，性价比极高"},
    {"name": "deepseek-v4-pro", "display_name": "DeepSeek V4 Pro", "max_tokens": 1000000, "description": "DeepSeek V4旗舰版，1M上下文，最强性能"}
],
```

---

#### [backend/core/config.py](file:///e:/ClipProject/autoclip-main1/autoclip-main/backend/core/config.py)

**改动：新增 `api_deepseek_api_key` 环境变量**

```python
api_dashscope_api_key: str = Field(default='', ...)
api_deepseek_api_key: str = Field(default='', validation_alias=AliasChoices('API_DEEPSEEK_API_KEY'))    # ← 新增
api_model_name: str = Field(default='qwen-plus', ...)
```

---

### 3.2 前端改动（2个文件）

#### [SettingsPage.tsx](file:///e:/ClipProject/autoclip-main1/autoclip-main/frontend/src/pages/SettingsPage.tsx)

**改动1：`providerConfig` 增加 DeepSeek 配置**

在 `tencent` 和 `ollama` 之间插入：

```typescript
deepseek: {
    name: 'DeepSeek',
    icon: <RobotOutlined />,
    color: '#4FC08D',           // DeepSeek 品牌浅绿色
    description: 'DeepSeek V4大模型，1M上下文，OpenAI兼容，性价比极高',
    apiKeyField: 'deepseek_api_key',
    placeholder: '请输入DeepSeek API密钥',
    secretKeyField: undefined,
    secretKeyPlaceholder: ''
},
```

**改动2：`defaultModels` 增加 DeepSeek 模型列表**

```typescript
tencent: [
    { name: 'hunyuan-pro', display_name: '混元大模型Pro' },
    ...
],
deepseek: [
    { name: 'deepseek-v4-flash', display_name: 'DeepSeek V4 Flash' },
    { name: 'deepseek-v4-pro', display_name: 'DeepSeek V4 Pro' }
],
ollama: [],
```

#### [secure_config_manager.py](file:///e:/ClipProject/autoclip-main1/autoclip-main/backend/services/secure_config_manager.py)

检查 `SENSITIVE_FIELDS` 集合中是否已有 `api_deepseek_api_key`，没有则新增。

---

## 4. 工作量估算

| 文件 | 改动类型 | 行数 | 复杂度 |
|------|---------|------|--------|
| `llm_providers.py` | 加枚举+新增类+注册工厂 | ~70行 | 低（复用现有模式） |
| `llm_manager.py` | 4处映射添加 | ~10行 | 低 |
| `settings.py` | 6处密钥/模型列表添加 | ~30行 | 低（模式化操作） |
| `config.py` | 1个环境变量 | ~2行 | 低 |
| `secure_config_manager.py` | 检查SENSITIVE_FIELDS | ~1行 | 低 |
| `SettingsPage.tsx` | providerConfig + defaultModels | ~25行 | 低 |
| **合计** | | **~138行** | **低** |

**工作量**：约 **0.5天**（纯编码+单元测试）

---

## 5. 测试方案

### 5.1 单元测试

| 测试项 | 方法 | 验证点 |
|-------|------|--------|
| ProviderType枚举 | 验证 `ProviderType.DEEPSEEK.value == "deepseek"` | 枚举值正确 |
| DeepSeekProvider实例化 | 创建实例，验证client.base_url | 确认指向 `https://api.deepseek.com/v1` |
| get_available_models | 返回列表中包含deepseek-v4-flash和deepseek-v4-pro | 模型列表完整 |
| 工厂注册 | `LLMProviderFactory.create_provider(ProviderType.DEEPSEEK, "key", "deepseek-v4-flash")` 不抛异常 | 工厂注册正确 |
| 配置读写 | settings API的deepseek_api_key字段读写 | 密钥可保存和回显 |

### 5.2 集成测试（手动）

| 测试项 | 步骤 | 预期 |
|-------|------|------|
| 前端展示 | 打开设置页面，提供商下拉出现"DeepSeek" | 选择后显示API Key输入框和模型选择 |
| API Key保存 | 输入有效DeepSeek Key并保存 | 保存成功，刷新后Key保持 |
| 连接测试 | 设置页面点击"测试连接" | 返回"API密钥验证通过" |
| 模型切换 | 选择deepseek-v4-flash并运行一个处理任务 | 流水线使用DeepSeek完成全部Step |
| 结果与qwen-plus对比 | 同一视频分别用deepseek-v4-flash和qwen-plus处理 | 切片质量可比较，无明显退化 |

---

## 6. Prompt适配说明（重要）

### 6.1 基础判断：prompt文本是否需要改？

**不需要。** 当前7个prompt文件都是模型无关的中文通用prompt：

| Prompt文件 | DeepSeek兼容性 | 说明 |
|-----------|---------------|------|
| `funclip_step1_boundary.txt` | ✅ 完全兼容 | 中文规则+JSON输出，DeepSeek处理良好 |
| `funclip_step2_batch_score.txt` | ✅ 完全兼容 | 同上 |
| `funclip_step3_batch_title.txt` | ✅ 完全兼容 | 同上 |
| `funclip_step1_5_gapfill.txt` | ✅ 完全兼容 | 同上 |
| `funclip_merged.txt` | ✅ 完全兼容 | 同上 |
| `funclip_clip_only.txt` | ✅ 完全兼容 | 同上 |
| `funclip_title.txt` | ✅ 完全兼容 | 同上 |

**prompt文件不改一行。** 这是统一LLM架构的设计优势。

### 6.2 需要改的辅助逻辑（截断感知provider）

虽然prompt不需要改，但 **代码中的输入截断逻辑** 需要适配DeepSeek的1M上下文。

#### 问题描述

`_smart_truncate_srt_for_scoring` 函数（funclip_style.py L480-508）**硬编码3000字符截断**：

```python
def _smart_truncate_srt_for_scoring(
    srt_text: str, segments,
    *, max_chars: int = 3000,    # 为qwen-plus 32K上下文设计
    head_lines: int = 40,
    tail_lines: int = 30,
    boundary_window: int = 20,
) -> str:
```

这对 qwen-plus（32K上下文）是合理的压缩，但对 DeepSeek V4 Flash（**1M上下文**）白白丢弃了有用信息。带话题上下文的完整SRT有利于Step2更准确地评分和判断边界。

#### 改进方案

**改进1**：在 `llm_manager.py` 增加长上下文检测方法

```python
def supports_long_context(self, min_tokens: int = 100_000) -> bool:
    """当前模型是否支持长上下文（>= min_tokens）"""
    if not self.current_provider:
        return False
    model_name = self.settings.get("model_name", "")
    for provider_type, models in LLMProviderFactory.get_all_available_models().items():
        for model in models:
            if model.name == model_name:
                return model.max_tokens >= min_tokens
    # 无法获取模型信息时保守返回False
    return False
```

**改进2**：在 `_prepare_step2_input` 中使用provider感知的判断

```python
# 在 FunClipStyleProcessor 类中
def _prepare_step2_input(self, topics: List[Dict], srt_entries: List[Dict]) -> List[Dict]:
    """构建Step2输入，根据provider上下文长度决定是否截断"""
    use_full_context = self._is_long_context_provider()
    
    topics_data = []
    for topic in topics:
        srt_text = _extract_srt_for_topic(topic, srt_entries)
        if not use_full_context:
            srt_text = _smart_truncate_srt_for_scoring(srt_text, topic.get('segments', []))
        
        duration = _calc_topic_duration(topic)
        entry = {
            "id": topic.get('id', ''),
            "outline": topic.get('outline', ''),
            "topic_type": topic.get('topic_type', 'knowledge'),
            "total_duration_seconds": duration,
            "srt_text": srt_text,
        }
        topics_data.append(entry)
    return topics_data


def _is_long_context_provider(self) -> bool:
    """当前provider是否支持长上下文（≥100K tokens则无需截断）"""
    try:
        return self.llm_manager.supports_long_context(100_000)
    except Exception:
        return False
```

**改进3**（可选）：为DeepSeek设置更低的temperature

当前代码中有些LLM调用没有显式传递 `temperature`，使用provider默认值。对于DeepSeek，JSON任务推荐 0.3-0.5（比默降低）。

```python
# 在 LlmManager 中增加推荐温度获取
def get_recommended_temperature(self) -> float:
    """获取当前模型推荐的temperature值"""
    model_name = self.settings.get("model_name", "")
    if model_name.startswith("deepseek-"):
        return 0.3
    return 0.7  # 默认值
```

#### 改动汇总

| 改动项 | 文件 | 行数 | 必要性 |
|-------|------|------|--------|
| 新增 `supports_long_context()` | `llm_manager.py` | ~15行 | 高 |
| 新增 `_is_long_context_provider()` | `funclip_style.py` | ~6行 | 高 |
| 修改 `_prepare_step2_input` | `funclip_style.py` | ~3行 | 高 |
| 新增 `get_recommended_temperature()` | `llm_manager.py` | ~6行 | 低（可选） |

### 6.3 不改有什么影响？

| 不改的项目 | 影响 | 严重程度 |
|-----------|------|---------|
| 截断逻辑不感知provider | Step2评分时SRT被截断到3000字符，1M上下文优势浪费，评分精度可能下降 | 🟡 中 |
| temperature不调整 | 输出风格略有差异，JSON质量不受影响 | 🟢 低 |

### 6.4 总结

> **prompt文件不改一行**。需要改的是代码中一段截断逻辑（约24行代码），让它感知当前模型是否支持长上下文。这是发挥DeepSeek 1M上下文优势的投入产出比最高的优化。

---

## 7. 风险与注意事项

| 风险 | 影响 | 缓解 |
|------|------|------|
| DeepSeek API国内访问不稳定 | 处理任务中断 | OpenAI兼容接口，用户可自由切换回其他提供商 |
| 密钥存储：检查 `SENSITIVE_FIELDS` 是否包含 `api_deepseek_api_key` | 密钥可能明文存储 | 确认 `secure_config_manager` 已有自动化注册机制 |
| 截断逻辑未感知provider时浪费1M上下文 | Step2输入被截断到3000字符 | 按6.2节方案改造 `_smart_truncate_srt_for_scoring` 调用 |

### 关于V4模型的特殊说明

V4 Flash 和 V4 Pro 都是标准的 chat 模型，**不会输出 `reasoning_content`**（与旧版 deepseek-reasoner 不同），因此不存在JSON解析干扰问题。V4 Pro 只是能力更强，输出格式与 Flash 完全一致。

---

## 8. 实施步骤

```
Step 1: llm_providers.py — 添加 DeepSeekProvider 类 + 工厂注册    (~70行)
Step 2: llm_manager.py — 4处密钥映射 + display_name 添加          (~10行)
Step 3: config.py — 新增 api_deepseek_api_key 环境变量              (~2行)
Step 4: settings.py — 6处密钥/模型列表添加                         (~30行)
Step 5: secure_config_manager.py — 检查 SENSITIVE_FIELDS           (~1行)
Step 6: SettingsPage.tsx — providerConfig + defaultModels           (~25行)
Step 7: 重启后端 → 验证前端可选中DeepSeek → 输入API Key → 测试连接 → 运行处理
```

**总耗时估计**：0.5天（含单元测试）

---

## 9. 与已有Provider的对比

| 维度 | DeepSeek V4 Flash | 通义千问 (DashScope) | 硅基流动 (SiliconFlow) | 说明 |
|------|------------------|--------------------|---------------------|------|
| API兼容 | OpenAI格式 | DashScope原生 | OpenAI格式 | DeepSeek复用现有openai SDK |
| 推荐模型 | deepseek-v4-flash | qwen-plus | Qwen2.5-32B | — |
| 上下文 | **1,000K** | 32K | 32K | DeepSeek优势极其明显 |
| 输入价格 | ¥1/M tokens | ¥2/M tokens | ¥1.5/M tokens | DeepSeek最低 |
| 输出价格 | ¥2/M tokens | ¥6/M tokens | ¥4/M tokens | DeepSeek最低 |
| 国内可访问 | ✅ 昇腾国产算力 | ✅ | ✅ | 均可用 |
| 额外依赖 | 无（复用openai） | dashscope SDK | 无（复用openai） | DeepSeek零新增依赖 |
| 配置复杂度 | 低（仅API Key） | 低 | 低 | 三者相当 |

**结论**：DeepSeek V4 Flash 在上下文（1M vs 32K）、成本（1/3）、依赖（零新增）三维度均领先，建议作为第二提供商首选接入，并考虑在长视频场景下免去C1滑动窗口。

---

## 10. 设计决策记录

1. **直接使用 V4 原生模型ID**：`deepseek-v4-flash` 和 `deepseek-v4-pro`，不使用已弃用的 `deepseek-chat` / `deepseek-reasoner`
2. **不作为 SiliconFlow 的模型列表扩展**：DeepSeek 已有独立品牌和API，独立成 Provider 更清晰
3. **OpenAI 兼容实现**：复用现有 openai SDK，零新增依赖
4. **不添加自定义 base_url 配置**：DeepSeek 只有 `https://api.deepseek.com/v1` 一个入口
5. **默认推荐 V4 Flash**：性价比最优，1M上下文对SmartCut场景已远超需求
6. **V4 Pro 不需特殊处理**：标准 chat 模型，无 reasoning_content 干扰