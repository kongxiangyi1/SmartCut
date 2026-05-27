# AutoClip 流水线优化具体执行方案

## 📋 执行概述

经过多轮验证分析，本方案提供具体的、可执行的优化步骤。

---

## 🎯 优化目标

| 指标 | 当前值 | 目标值 | 提升 |
|------|--------|--------|------|
| LLM 调用次数 | 7-12 次 | 2-3 次 | **-75%** |
| 处理时间 | 基准 | ~30% | **-70%** |
| 中间文件数 | 15+ 个 | 3-4 个 | **-80%** |
| API 成本 | 基准 | ~25% | **-75%** |

---

## 📅 实施阶段

### 阶段 1：创建优化模块（预计 1-2 天）

#### 1.1 创建目录结构
```
backend/pipeline/
├── legacy/                    # 保留现有实现
│   ├── step1_outline.py
│   ├── step2_timeline.py
│   ├── step3_scoring.py
│   ├── step4_title.py
│   ├── step5_clustering.py
│   └── step6_video.py
└── optimized/                 # 新优化实现
    ├── __init__.py
    ├── unified_analyzer.py    # ✅ 已创建
    ├── smart_clustering.py    # ✅ 已创建
    ├── pipeline.py            # ✅ 已创建
    ├── validation_tests.py     # ✅ 已创建
    └── config.py              # 配置文件
```

#### 1.2 创建配置文件
<minimax:tool_call>
<invoke name="Write">
<parameter name="content">"""
优化流水线配置
"""

from pathlib import Path

# 优化流水线开关
OPTIMIZED_PIPELINE_ENABLED = True

# 聚类模式
CLUSTERING_MODE = "keyword"  # "keyword" | "llm" | "hybrid"

# 聚类阈值
CLUSTER_MIN_CLIPS = 2  # 最少2个切片才能形成合集
MAX_CLIPS_PER_COLLECTION = 5  # 每个合集最多切片数

# LLM配置
LLM_MAX_RETRIES = 3
LLM_TIMEOUT = 30

# 分块配置
CHUNK_INTERVAL_MINUTES = 30  # 每块时长
CHUNK_OVERLAP_MINUTES = 2    # 块重叠时长

# 评分阈值
MIN_SCORE_THRESHOLD = 0.0  # 低于此分数的切片将被过滤

# 输出配置
OUTPUT_METADATA_FILE = "clips_metadata.json"
OUTPUT_COLLECTIONS_FILE = "collections_metadata.json"
