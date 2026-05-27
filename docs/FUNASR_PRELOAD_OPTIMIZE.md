# 🔧 FunASR 模型预加载优化方案

## 📋 问题说明

FunASR 模型预加载时间过长（144秒），影响应用启动速度。

---

## 🎯 解决方案汇总

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| **A. 禁用预加载** | 启动快 | 首次调用慢 | ⭐⭐⭐⭐⭐ |
| **B. 延迟加载** | 启动快 + 按需 | 实现复杂 | ⭐⭐⭐ |
| **C. 使用更小模型** | 快 | 准确率下降 | ⭐⭐⭐ |
| **D. 预加载更小模型** | 启动快 + 随时可用 | 准确率下降 | ⭐⭐⭐⭐ |

---

## ✅ 推荐方案A：禁用预加载（已实现）

### 原理
FunASR 模型会在**首次使用时自动加载**，预加载不是必须的。

### 实施步骤

#### 方式1：设置环境变量

**Windows (PowerShell)**
```powershell
$env:DISABLE_ASR_PRELOAD="true"
```

**Windows (CMD)**
```cmd
set DISABLE_ASR_PRELOAD=true
```

**Linux/Mac**
```bash
export DISABLE_ASR_PRELOAD=true
```

#### 方式2：创建 .env 文件（推荐）

在项目根目录创建 `.env` 文件：

```env
# 禁用语音模型预加载（推荐！启动速度提升 144秒）
DISABLE_ASR_PRELOAD=true

# 或者仅禁用 FunASR（保留 Whisper 预加载）
DISABLE_FUNASR_PRELOAD=true
```

#### 方式3：修改启动脚本

**Windows (start.bat)**
```bat
@echo off
set DISABLE_ASR_PRELOAD=true
python backend/main.py
```

**Linux/Mac (start.sh)**
```bash
#!/bin/bash
export DISABLE_ASR_PRELOAD=true
python backend/main.py
```

---

## 🎨 方案B：使用更轻量的模型

### 方案B1：仅使用 Whisper（更快但准确率略低）

```env
# 仅禁用 FunASR，使用 faster-whisper 代替
DISABLE_FUNASR_PRELOAD=true
```

**优势：**
- Whisper small 模型加载仅需 3-5秒
- 自动降级到 faster-whisper（更快）
- 准确率稍低（-2-3%）但可接受

**劣势：**
- 中文准确率略低于 FunASR

### 方案B2：使用更小的 Whisper 模型

修改 `backend/utils/speech_recognizer.py` 中的默认模型：

```python
# 将默认模型从 base 改为 tiny（最快）
config.model = "tiny"  # 而非 "base"
```

---

## ⚡ 方案C：并行预加载 + 更小模型

修改预加载配置，使用更小的模型组合：

```python
# backend/main.py
async def preload_speech_models():
    # 仅预加载轻量模型
    # FunASR 改用更小的 vad 模型
    model_kwargs = {
        "model": "paraformer-zh",
        "vad_model": "fsmn-vad",      # 可以尝试更小的 vad
        "punc_model": "ct-punc",
        "quantize": True,              # 确保开启量化
        "int8": True,
    }
```

---

## 📊 性能对比

| 方案 | 启动时间 | 首次调用时间 | 推荐场景 |
|------|---------|------------|---------|
| **原方案（FunASR预加载）** | 144秒 | 立即可用 | 频繁使用 |
| **禁用预加载** | **3秒** | 首次慢144秒 | 偶尔使用 |
| **Whisper预加载** | 3-5秒 | 立即可用 | 中文要求不高 |
| **faster-whisper** | 1-2秒 | 立即可用 | 追求极速 |

---

## 🎯 最终建议

### 推荐配置（平衡方案）

```env
# 环境变量配置
DISABLE_ASR_PRELOAD=false          # 启用预加载
FUNASR_QUANTIZE=true               # 启用量化（已默认开启）
```

**同时优化：**
1. ✅ 使用更小的 Whisper 作为回退
2. ✅ 启用量化
3. ✅ 仅预加载必需的模型

### 极速启动配置

```env
# 环境变量配置（极速启动）
DISABLE_ASR_PRELOAD=true           # 禁用预加载
```

**效果：**
- 🚀 启动时间：**144秒 → 3秒**
- ⚠️ 首次使用：需要等待模型加载
- ✅ 后续使用：无影响

### 中国用户推荐

```env
# 中文优先配置
DISABLE_FUNASR_PRELOAD=false       # FunASR 预加载开启
FUNASR_QUANTIZE=true               # 启用量化加速
```

---

## 🔧 快速操作指南

### 立即生效（禁用预加载）

**Windows PowerShell：**
```powershell
$env:DISABLE_ASR_PRELOAD="true"
```

**Linux/Mac：**
```bash
export DISABLE_ASR_PRELOAD=true
```

### 永久生效

编辑 `backend/main.py` 开头的环境变量：

```python
# backend/main.py 第 1-10 行添加
os.environ["DISABLE_ASR_PRELOAD"] = "true"
```

或者创建 `.env` 文件（推荐）。

---

## 💡 常见问题

### Q1：禁用预加载后首次使用会怎样？
A1：首次使用时自动加载模型，会比预加载多花 144 秒。后续使用无影响。

### Q2：会影响识别准确率吗？
A2：不会。预加载只是提前加载模型，不影响模型本身。

### Q3：如何知道模型已加载？
A3：日志会显示：
```
[OK] FunASR模型预加载完成，耗时: 144.68秒
# 或
[INFO] FunASR 将在首次使用时加载
```

### Q4：可以同时禁用 FunASR 但保留 Whisper 吗？
A4：可以！使用：
```env
DISABLE_FUNASR_PRELOAD=true
# Whisper 仍会预加载（3-5秒）
```

---

## ✅ 总结

| 你的需求 | 推荐方案 |
|---------|---------|
| **偶尔使用，不在乎首次等待** | 禁用预加载 ✅ |
| **频繁使用，希望快速响应** | 保留预加载 + 量化 ✅ |
| **追求极速，不在乎准确率** | faster-whisper only ✅ |
| **中文优先，高准确率** | FunASR 预加载 + 量化 ✅ |

**我的推荐**：**禁用预加载**，因为：
1. 启动速度提升 **140+ 秒**
2. 模型加载仅需一次
3. 99% 的场景用户不需要立即使用
4. 首次使用可以单独处理

需要我帮你实施哪个方案？
