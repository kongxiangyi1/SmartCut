# 视频切片系统优化开发计划

## 一、研究结论

### 1.1 项目现状

* 项目采用前后端分离架构，使用 Python 后端 + React 前端

* 已有语音识别功能，支持 BCUT\_ASR、FunASR、Whisper 等多种引擎

* 已有基本的语义分析和边界定位流程（step1\_outline.py、step2\_timeline.py）

* 已有视频处理和字幕提取功能

* 缺少口音处理、高级纠错、多模态边界检测等功能

### 1.2 核心文件结构

```
backend/
├── utils/
│   ├── speech_recognizer.py       # 语音识别工具
│   ├── video_processor.py         # 视频处理工具
│   └── text_processor.py          # 文本处理工具
├── pipeline/
│   ├── step1_outline.py           # 大纲提取
│   ├── step2_timeline.py          # 时间线定位
│   └── step6_video.py             # 视频处理
└── api/
    └── v1/
        └── speech_recognition.py  # 语音识别API
```

***

## 二、开发内容与文件修改

### 2.1 新增文件

| 文件路径                                            | 说明        |
| ----------------------------------------------- | --------- |
| `backend/utils/accent_detector.py`              | 口音检测器     |
| `backend/utils/sishui_accent_processor.py`      | 山东泗水口音处理器 |
| `backend/utils/text_corrector.py`               | 高级文本纠错器   |
| `backend/utils/speech_pause_analyzer.py`        | 语音停顿分析器   |
| `backend/utils/video_scene_detector.py`         | 视频场景检测器   |
| `backend/utils/multimodal_boundary_detector.py` | 多模态边界检测器  |
| `backend/utils/ml_boundary_predictor.py`        | 机器学习边界预测器 |
| `backend/utils/context_boundary_refiner.py`     | 上下文边界精化器  |

### 2.2 修改文件

| 文件路径                                   | 修改内容                               |
| -------------------------------------- | ---------------------------------- |
| `backend/utils/speech_recognizer.py`   | 1. 集成口音检测；2. 实现分层策略；3. 添加口音自适应     |
| `backend/utils/text_processor.py`      | 集成 pycorrector 纠错                  |
| `backend/pipeline/step2_timeline.py`   | 1. 集成多模态边界检测；2. 添加上下文精化；3. 集成ML预测器 |
| `backend/core/shared_config.py`        | 添加新功能的配置项                          |
| `backend/api/v1/speech_recognition.py` | 添加口音选择、纠错级别配置等API                  |

***

## 三、开发步骤

### Phase 1: 基础功能优化（P0优先级）

#### Step 1: 完善语音识别分层策略

* **文件**：`backend/utils/speech_recognizer.py`

* **内容**：

  1. 实现 `IntelligentASRStrategy` 类
  2. 添加 preview/production/offline 三种模式切换
  3. 完善 BCUT\_ASR 和 FunASR 的自动回退机制
  4. 添加配置参数支持

#### Step 2: 集成 pycorrector 文本纠错

* **文件**：`backend/utils/text_corrector.py`（新增）、`backend/utils/text_processor.py`（修改）

* **内容**：

  1. 创建 `TextCorrector` 类
  2. 实现三层纠错机制（规则级/统计级/语义级）
  3. 集成到现有的 text\_processor 中
  4. 添加领域词汇表支持

#### Step 3: 实现口音检测基础功能

* **文件**：`backend/utils/accent_detector.py`（新增）

* **内容**：

  1. 创建 `AccentDetector` 类
  2. 实现山东口音、四川口音等检测模式
  3. 添加口音特征提取和匹配逻辑

#### Step 4: 实现山东泗水口音规则

* **文件**：`backend/utils/sishui_accent_processor.py`（新增）

* **内容**：

  1. 创建 `SishuiAccentProcessor` 类
  2. 实现泗水口音的发音映射规则
  3. 添加口音到标准普通话的转换逻辑

***

### Phase 2: 边界准确率深度优化（P0-P1优先级）

#### Step 5: 实现语音停顿分析器

* **文件**：`backend/utils/speech_pause_analyzer.py`（新增）

* **内容**：

  1. 创建 `SpeechPauseAnalyzer` 类
  2. 集成 VAD 检测功能
  3. 实现停顿类型分类（短/中/长停顿）
  4. 计算停顿置信度

#### Step 6: 实现视频场景检测器

* **文件**：`backend/utils/video_scene_detector.py`（新增）

* **内容**：

  1. 创建 `VideoSceneDetector` 类
  2. 使用 ffmpeg 提取帧差异
  3. 实现场景切换检测算法
  4. 添加自适应阈值机制

#### Step 7: 实现多模态边界检测器

* **文件**：`backend/utils/multimodal_boundary_detector.py`（新增）

* **内容**：

  1. 创建 `MultimodalBoundaryDetector` 类
  2. 实现文本语义边界检测
  3. 实现语音停顿边界检测
  4. 实现视频场景边界检测
  5. 实现加权融合算法

#### Step 8: 实现上下文边界精化器

* **文件**：`backend/utils/context_boundary_refiner.py`（新增）

* **内容**：

  1. 创建 `ContextAwareBoundaryRefiner` 类
  2. 实现话题完整性检查
  3. 实现连贯性验证
  4. 实现边界位置微调

#### Step 9: 集成到时间线定位流程

* **文件**：`backend/pipeline/step2_timeline.py`（修改）

* **内容**：

  1. 集成多模态边界检测
  2. 添加上下文精化步骤
  3. 保留原有的 LLM 分析作为补充
  4. 添加边界质量评分

***

### Phase 3: API与配置集成（P1-P2优先级）

#### Step 10: 添加配置管理

* **文件**：`backend/core/shared_config.py`（修改）

* **内容**：

  1. 添加口音处理配置
  2. 添加纠错级别配置
  3. 添加边界检测权重配置
  4. 添加多模态融合开关

#### Step 11: 扩展语音识别API

* **文件**：`backend/api/v1/speech_recognition.py`（修改）

* **内容**：

  1. 添加口音选择接口
  2. 添加纠错级别设置接口
  3. 添加边界检测模式切换接口
  4. 更新状态查询接口，包含新功能状态

#### Step 12: 前端配置界面（可选，视需要）

* **文件**：`frontend/src/components/Settings.tsx`（如需要）

* **内容**：

  1. 添加语音识别引擎选择
  2. 添加口音处理选项
  3. 添加纠错级别设置
  4. 添加边界检测配置

***

## 四、潜在依赖与考虑

### 4.1 依赖包

* `pycorrector` - 文本纠错

* `webrtcvad` - 语音活动检测

* `scikit-learn` / `xgboost` - ML边界预测（可选）

* `numpy` - 数值计算

* `opencv-python` - 视频处理（可选，如需要更精细的场景检测）

### 4.2 性能考虑

* 视频场景检测会增加处理时间，建议默认关闭或仅在需要时启用

* ML预测器首次加载模型会有延迟，建议预加载

* 建议添加缓存机制，避免重复处理相同内容

### 4.3 兼容性考虑

* 保持与现有代码的向后兼容

* 新功能默认设为可选开关

* 提供降级方案，在依赖不可用时使用原有逻辑

### 4.4 数据安全

* 避免敏感音频数据泄露

* 离线处理优先，云端服务仅在用户明确授权时使用

***

## 五、风险处理

| 风险         | 影响 | 缓解措施                                     |
| ---------- | -- | ---------------------------------------- |
| 新增依赖安装失败   | 中  | 1. 提供清晰的安装文档；2. 实现降级逻辑；3. 依赖设为可选         |
| 多模态处理太慢    | 中  | 1. 添加进度反馈；2. 提供开关选项；3. 实现并行处理            |
| 边界检测效果不如预期 | 高  | 1. 保留原有流程作为备选；2. 添加用户手动调整功能；3. 持续收集反馈优化  |
| 口音检测不准确    | 中  | 1. 提供手动选择口音选项；2. 收集用户反馈迭代规则；3. 不影响基础识别功能 |
| 前端集成复杂度    | 低  | 1. 后端API先完成，前端可以分阶段；2. 提供默认配置，简化用户选择     |

***

## 六、验证与测试

### 6.1 测试计划

1. **单元测试** - 为每个新增模块编写单元测试
2. **集成测试** - 验证完整流程的正确性
3. **对比测试** - 对比优化前后的边界准确率
4. **性能测试** - 评估新增功能对处理时间的影响

### 6.2 验收标准

* 边界准确率提升至 96%+

* 错别字率降至 0.3% 以下

* 带口音普通话识别准确率提升 18%+

* 处理时间不超过原有时间的 1.5 倍

***

## 七、开发顺序与交付

### 推荐开发顺序

1. Phase 1（基础功能）：分层策略 + 纠错 + 口音处理
2. Phase 2（边界优化）：语音停顿 + 多模态融合 + 上下文精化
3. Phase 3（集成）：配置管理 + API扩展

### 交付物

1. 所有新增/修改的代码文件
2. 单元测试文件
3. 更新的文档（使用说明、API文档）
4. 演示视频或效果对比

