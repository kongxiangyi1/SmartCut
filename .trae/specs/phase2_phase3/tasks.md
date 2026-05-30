# 视频切片系统优化 - Phase 2 & Phase 3 实现计划

## [x] Task 1: 实现语音停顿分析器 ✅ 已完成
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 创建 `speech_pause_analyzer.py` 文件
  - 使用 FunASR VAD 检测语音区间
  - 识别停顿区间并分类（短/中/长停顿）
  - 计算停顿置信度
- **Acceptance Criteria Addressed**: AC-1
- **Test Requirements**:
  - `programmatic` TR-1.1: 分析 1 分钟音频，正确识别 >= 90% 的停顿区间
  - `programmatic` TR-1.2: 停顿类型分类准确率 >= 85%
- **Notes**: 依赖 FunASR VAD 模型

## [x] Task 2: 实现视频场景检测器 ✅ 已完成
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 创建 `video_scene_detector.py` 文件
  - 使用 ffmpeg 提取帧差异
  - 实现场景切换检测算法
  - 添加自适应阈值机制
- **Acceptance Criteria Addressed**: AC-2
- **Test Requirements**:
  - `programmatic` TR-2.1: 检测 1 分钟视频，正确识别 >= 80% 的场景切换
  - `programmatic` TR-2.2: 检测延迟 < 500ms
- **Notes**: 依赖 ffmpeg-python

## [x] Task 3: 实现多模态边界检测器 ✅ 已完成
- **Priority**: P0
- **Depends On**: Task 1, Task 2
- **Description**: 
  - 创建 `multimodal_boundary_detector.py` 文件
  - 实现文本语义边界检测
  - 实现语音停顿边界检测
  - 实现视频场景边界检测
  - 实现加权融合算法（权重可配置）
- **Acceptance Criteria Addressed**: AC-3
- **Test Requirements**:
  - `programmatic` TR-3.1: 边界检测准确率 >= 96%
  - `programmatic` TR-3.2: 延迟 < 200ms
- **Notes**: 需要集成前两个任务的输出

## [x] Task 4: 实现上下文边界精化器 ✅ 已完成
- **Priority**: P1
- **Depends On**: Task 3
- **Description**: 
  - 创建 `context_boundary_refiner.py` 文件
  - 实现话题完整性检查
  - 实现连贯性验证
  - 实现边界位置微调
- **Acceptance Criteria Addressed**: AC-4
- **Test Requirements**:
  - `programmatic` TR-4.1: 话题完整性 >= 95%
  - `human-judgment` TR-4.2: 边界位置合理，不切断完整话题
- **Notes**: 需要访问字幕数据进行上下文分析

## [x] Task 5: 集成到时间线定位流程 ✅ 已完成
- **Priority**: P1
- **Depends On**: Task 3, Task 4
- **Description**: 
  - 修改 `step2_timeline.py`
  - 集成多模态边界检测
  - 添加上下文精化步骤
  - 保留原有 LLM 分析作为补充
- **Acceptance Criteria Addressed**: AC-3, AC-4
- **Test Requirements**:
  - `programmatic` TR-5.1: 端到端边界准确率 >= 96%
  - `programmatic` TR-5.2: 与现有功能兼容
- **Notes**: 需要仔细处理原有逻辑和新逻辑的融合

## [x] Task 6: 扩展配置管理 ✅ 已完成
- **Priority**: P1
- **Depends On**: None
- **Description**: 
  - 修改 `shared_config.py`
  - 添加口音处理配置
  - 添加纠错级别配置
  - 添加边界检测权重配置
  - 添加多模态融合开关
- **Acceptance Criteria Addressed**: AC-5
- **Test Requirements**:
  - `programmatic` TR-6.1: 配置项可正确读取和修改
  - `programmatic` TR-6.2: 默认配置合理
- **Notes**: 保持向后兼容

## [ ] Task 7: 扩展语音识别 API
- **Priority**: P2
- **Depends On**: Task 6
- **Description**: 
  - 修改 `speech_recognition.py` API
  - 添加口音选择接口
  - 添加纠错级别设置接口
  - 添加边界检测模式切换接口
  - 更新状态查询接口
- **Acceptance Criteria Addressed**: AC-6
- **Test Requirements**:
  - `programmatic` TR-7.1: API 响应状态码正确（200/400/500）
  - `programmatic` TR-7.2: 返回数据格式符合规范
- **Notes**: 需要编写 API 测试

## [ ] Task 8: 更新配置界面（可选）
- **Priority**: P2
- **Depends On**: Task 7
- **Description**: 
  - 更新前端设置页面（如果需要）
  - 添加语音识别引擎选择
  - 添加口音处理选项
  - 添加纠错级别设置
- **Acceptance Criteria Addressed**: AC-5, AC-6
- **Test Requirements**:
  - `human-judgment` TR-8.1: UI 布局合理，操作流畅
  - `human-judgment` TR-8.2: 配置项完整，易于理解
- **Notes**: 此任务可选，根据需求决定是否实施

## [ ] Task 9: 编写单元测试
- **Priority**: P1
- **Depends On**: 所有功能任务
- **Description**: 
  - 为每个新模块编写单元测试
  - 测试边界检测准确率
  - 测试配置管理功能
  - 测试 API 接口
- **Acceptance Criteria Addressed**: 所有 AC
- **Test Requirements**:
  - `programmatic` TR-9.1: 单元测试覆盖率 >= 80%
  - `programmatic` TR-9.2: 所有测试通过
- **Notes**: 使用 pytest 框架

## [ ] Task 10: 集成测试和验证
- **Priority**: P0
- **Depends On**: 所有任务
- **Description**: 
  - 运行完整测试套件
  - 验证端到端流程
  - 验证边界准确率达到目标（>= 96%）
  - 验证性能指标（延迟 < 200ms）
- **Acceptance Criteria Addressed**: 所有 AC
- **Test Requirements**:
  - `programmatic` TR-10.1: 端到端测试通过
  - `programmatic` TR-10.2: 边界准确率 >= 96%
  - `programmatic` TR-10.3: 延迟 < 200ms
- **Notes**: 需要真实视频样本进行测试

## [ ] Task 11: 强化话题切分边界结构化与建议接口
- **Priority**: P1
- **Depends On**: Task 5, Task 6
- **Description**:
  - 将 `boundary_suggestion` 输出规范化为结构化字段
  - 增强 Step1 结果解析与降级处理逻辑
  - 使边界调整建议可直接映射为 `extend_start`/`shrink_end`/`remove_segment` 等操作
  - 减少依赖自由文本解析，提高边界修正稳定性
- **Acceptance Criteria Addressed**: AC-4, AC-5
- **Test Requirements**:
  - `programmatic` TR-11.1: Step1 LLM 响应解析成功率 >= 98%（历史样本）
  - `programmatic` TR-11.2: 结构化边界建议应用后错误调整率 < 5%
- **Notes**: 重点改造 `backend/pipeline/funclip_style.py` 和相关 prompt

## [ ] Task 12: 引入多信号边界辅助与动态阈值优化
- **Priority**: P1
- **Depends On**: Task 3, Task 4, Task 6
- **Description**:
  - 将关键帧/停顿/说话人/场景切换信号提前用于话题边界候选
  - 在 Step1 之前生成边界候选点供 LLM 参考
  - 添加话题时长与数量的动态阈值策略
  - 强化跨段同一话题合并规则，增加语义相似度判断
- **Acceptance Criteria Addressed**: AC-3, AC-4, AC-5
- **Test Requirements**:
  - `programmatic` TR-12.1: 混合内容中边界候选覆盖率提升 >= 10%
  - `programmatic` TR-12.2: 相同语义跨段合并准确率提升
- **Notes**: 重点改造 `backend/pipeline/step2_timeline.py`、`backend/pipeline/topic_postprocess.py` 和配置项

## [ ] Task 13: Step1 前文本纠错与语义预处理
- **Priority**: P1
- **Depends On**: Task 6
- **Description**:
  - 实现 SRT 文本纠错与语义归一化模块
  - 将说话人、停顿、断句、话题候选信息融入 Step1 输入
  - 在 Step1 前将原始字幕转换为更符合语义的片段
  - 保留原始 SRT 作为回退依据
- **Subtasks**:
  - Task 13.1: 设计 `TextCorrector` 模块与纠错接口（0.5d）
  - Task 13.2: 实现规则级/统计级/语义级三层纠错策略（1.0d）
  - Task 13.3: 实现说话人/停顿信息的语义断句与片段生成（1.0d）
  - Task 13.4: 修改 `backend/pipeline/funclip_style.py`，让 Step1 使用预处理结果（0.5d）
  - Task 13.5: 添加纠错元数据输出与回退机制（0.5d）
- **Implementation Plan**:
  1. Day 1: 定义 `TextCorrector` 接口，完成词典与同音词规则
     - 产出：`TextCorrector` 类草案、`correct_text()` 返回格式、词典结构
     - 验收：接口文档明确，示例输入输出 OK
  2. Day 2: 集成 `pycorrector` 统计纠错，构建语义一致性校验
     - 产出：规则级纠错 + `pycorrector` 纠错模块、纠错元数据收集
     - 验收：对 10 条常见错别字测试样例纠错正确
  3. Day 3: 开发说话人/停顿断句模块，生成语义片段
     - 产出：语义片段生成函数、说话人合并与停顿断句规则
     - 验收：同一说话人连续语句合并，长停顿处切分正确
  4. Day 4: 修改 Step1 输入逻辑，增加回退与元数据输出
     - 产出：`funclip_style.py` 中 Step1 输入改造、回退逻辑、原始文本备份
     - 验收：Step1 入参包含纠错结果并可回退至原文本
  5. Day 5: 编写单元测试、回归测试并验证效果
     - 产出：`test_text_corrector.py`、`test_funclip_preprocessing.py`
     - 验收：测试通过、Step1 边界稳定性对比报告
- **Acceptance Criteria Addressed**: AC-4, AC-5, AC-7
- **Test Requirements**:
  - `programmatic` TR-13.1: 纠错后输入文本与原始 SRT 语义一致
  - `programmatic` TR-13.2: Step1 话题边界稳定性提升
  - `programmatic` TR-13.3: 纠错模块对常见同音词的校正率 >= 90%
- **Notes**: 重点改造 `backend/utils/text_corrector.py`、`backend/utils/text_processor.py`、`backend/pipeline/funclip_style.py`
- **Key Functions**:
  - `TextCorrector.correct_text`
  - `TextCorrector._apply_rule_corrections`
  - `TextCorrector._apply_pycorrector_correction`
  - `TextCorrector._validate_semantic_correction`
  - `SemanticPreprocessor.generate_semantic_chunks`
  - `SemanticPreprocessor._merge_speaker_segments`
  - `SemanticPreprocessor._split_by_pause`
  - `FunclipStyle._prepare_step1_input`
  - `FunclipStyle._build_step1_prompt_input`
