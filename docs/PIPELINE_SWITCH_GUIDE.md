
# AutoClip 流水线切换说明

## 快速开始

### 查看当前流水线模式
```bash
curl http://localhost:8090/api/v1/pipeline/status
```

### 切换到FunClip快速方案
```bash
curl -X POST http://localhost:8090/api/v1/pipeline/switch \
  -H "Content-Type: application/json" \
  -d '{"mode": "funclip"}'
```

### 切换回原6步方案（推荐用于2小时直播）
```bash
curl -X POST http://localhost:8090/api/v1/pipeline/switch \
  -H "Content-Type: application/json" \
  -d '{"mode": "legacy"}'
```

## 两种方案对比

| 特性 | 原6步方案 (legacy) | FunClip方案 (funclip) |
|------|---------------------|----------------------|
| LLM调用次数 | 10-15次 | 1次 |
| 处理速度 | 基准 | 提升90% |
| 适合场景 | 2小时直播、复杂内容 | 短视频、快速处理 |
| 稳定性 | 高（已验证） | 中（新方案） |

## 推荐使用策略

### 对于2小时直播
```bash
# 使用原6步方案
curl -X POST http://localhost:8090/api/v1/pipeline/switch \
  -H "Content-Type: application/json" \
  -d '{"mode": "legacy"}'
```

### 对于短视频测试
```bash
# 使用FunClip快速方案
curl -X POST http://localhost:8090/api/v1/pipeline/switch \
  -H "Content-Type: application/json" \
  -d '{"mode": "funclip"}'
```

### A/B测试模式
```bash
curl -X POST http://localhost:8090/api/v1/pipeline/switch \
  -H "Content-Type: application/json" \
  -d '{"mode": "ab_test", "ab_test_ratio": 0.1}'
```

## 验证新方案

```bash
curl http://localhost:8090/api/v1/pipeline/validate
```

## 核心文件说明

```
backend/pipeline/
├── funclip_style.py          # FunClip风格单步处理方案（新增）
├── pipeline_selector.py       # 流水线选择器（更新）
└── legacy/                    # 原6步方案（保留）
    ├── step1_outline.py
    ├── step2_timeline.py
    ├── step3_scoring.py
    ├── step4_title.py
    ├── step5_clustering.py
    └── step6_video.py
```

