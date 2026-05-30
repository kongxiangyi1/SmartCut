# 视频切片系统优化 - Phase 2 & Phase 3 需求文档

## Overview
- **Summary**: 继续完成视频切片系统的优化工作，包括边界准确率深度优化（Phase 2）和 API/配置集成（Phase 3）
- **Purpose**: 提升边界检测准确率至 96-98%，提供完整的配置管理和 API 支持
- **Target Users**: 系统管理员、开发人员、最终用户

## Goals
- 实现多模态边界检测（文本语义 + 语音停顿 + 视频场景）
- 提升边界准确率至 96-98%
- 提供完整的配置管理系统
- 扩展 API 支持新功能配置

## Non-Goals (Out of Scope)
- 前端界面开发（仅后端 API）
- 机器学习模型训练（使用预训练模型）
- 数据库架构变更

## Background & Context
- Phase 1 已完成：语音识别分层策略、文本纠错、口音处理
- 当前边界准确率约 92%，目标提升至 96-98%
- 需要集成语音停顿分析和视频场景检测

## Functional Requirements
- **FR-1**: 实现语音停顿分析器，检测音频中的停顿区间
- **FR-2**: 实现视频场景检测器，识别镜头切换
- **FR-3**: 实现多模态边界检测器，融合文本、语音、视频特征
- **FR-4**: 实现上下文边界精化器，验证话题完整性
- **FR-5**: 扩展配置管理，支持口音、纠错、边界检测配置
- **FR-6**: 扩展语音识别 API，支持新配置项
- **FR-7**: 规范化边界修正建议接口，减少自由文本解析依赖
- **FR-8**: 引入关键帧/停顿/说话人/场景信号作为边界候选参考
- **FR-9**: 实现 Step1 前文本纠错与语义预处理，减少原始 SRT 错别字和行断句噪声影响

## Non-Functional Requirements
- **NFR-1**: 边界检测延迟 < 200ms（单视频）
- **NFR-2**: 向后兼容，不破坏现有功能
- **NFR-3**: 模块化设计，便于测试和扩展

## Constraints
- **Technical**: Python 3.10+, FastAPI, FunASR VAD
- **Dependencies**: webrtcvad, ffmpeg-python, scikit-learn（可选）

## Assumptions
- FunASR 已安装并可用
- ffmpeg 已安装
- 现有代码结构保持不变

## Acceptance Criteria

### AC-1: 语音停顿分析器
- **Given**: 输入音频文件路径
- **When**: 调用 SpeechPauseAnalyzer.analyze()
- **Then**: 返回停顿区间列表，包含开始时间、结束时间、持续时间、类型
- **Verification**: `programmatic`

### AC-2: 视频场景检测器
- **Given**: 输入视频文件路径
- **When**: 调用 VideoSceneDetector.detect_scene_changes()
- **Then**: 返回场景切换时间点列表，包含时间、置信度
- **Verification**: `programmatic`

### AC-3: 多模态边界检测
- **Given**: 输入字幕数据、音频特征、视频特征
- **When**: 调用 MultimodalBoundaryDetector.detect_boundaries()
- **Then**: 返回加权融合后的边界列表，准确率 >= 96%
- **Verification**: `programmatic`

### AC-4: 上下文边界精化
- **Given**: 输入边界列表和字幕数据
- **When**: 调用 ContextAwareBoundaryRefiner.refine()
- **Then**: 返回精化后的边界，话题完整性 >= 95%
- **Verification**: `programmatic`

### AC-5: 配置管理扩展
- **Given**: 系统配置已更新
- **When**: 访问 /api/v1/settings 接口
- **Then**: 返回包含口音、纠错级别、边界检测配置的完整配置
- **Verification**: `programmatic`

### AC-6: API 扩展
- **Given**: 语音识别 API 已扩展
- **When**: 调用 /api/v1/speech-recognition/status
- **Then**: 返回包含新模式、口音、纠错配置的状态信息
- **Verification**: `programmatic`

### AC-7: 结构化边界建议接口
- **Given**: LLM 返回话题评分与边界建议
- **When**: 解析 boundary_suggestion 字段
- **Then**: 得到结构化调整指令，可直接应用于 segment 边界
- **Verification**: `programmatic`

### AC-8: 多信号候选边界参考
- **Given**: 输入字幕、关键帧、停顿、说话人、场景信号
- **When**: 生成候选边界参考点
- **Then**: Step1/Step2 分析能使用这些信号进行边界判断
- **Verification**: `programmatic`

### AC-9: Step1 前语义预处理
- **Given**: 原始 SRT 字幕文本
- **When**: 运行文本纠错与语义预处理
- **Then**: 返回纠错后文本，话题边界分析更稳健，原始语义基本保持不变
- **Verification**: `programmatic`

## Open Questions
- [ ] 是否需要集成机器学习预测器（会增加依赖）
- [ ] 是否需要提供配置界面的前端组件
