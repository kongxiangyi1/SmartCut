# 🚀 FunASR 预加载优化 - 快速参考

## ⚡ 问题

**FunASR 模型预加载耗时：144秒**（约2.4分钟）

---

## ✅ 解决方案（30秒搞定）

### 方式1：立即生效（当前窗口）

**Windows PowerShell：**
```powershell
$env:DISABLE_ASR_PRELOAD="true"
python backend/main.py
```

**CMD：**
```cmd
set DISABLE_ASR_PRELOAD=true
python backend/main.py
```

---

### 方式2：永久禁用（推荐⭐）

运行脚本：

```bash
python scripts/enable_asr_preload_permanent.py
```

然后选择 **1**（禁用预加载）

**效果：**
- ✅ 启动时间：**144秒 → 3秒**
- ✅ 首次使用：自动加载模型
- ✅ 后续使用：无影响

---

### 方式3：快速批处理（Windows）

双击运行：

```
scripts/disable_asr_preload.bat
```

---

## 📊 性能对比

| 方案 | 启动时间 | 首次使用 | 推荐度 |
|------|---------|---------|--------|
| **原方案** | 144秒 | 立即可用 | ⭐ |
| **禁用预加载** | **3秒** | 首次慢144秒 | ⭐⭐⭐⭐⭐ |
| **仅禁用 FunASR** | 8秒 | 首次慢144秒 | ⭐⭐⭐⭐ |

---

## 🔄 恢复预加载

### 方式1：环境变量

```bash
# Windows
set DISABLE_ASR_PRELOAD=false

# Linux/Mac
export DISABLE_ASR_PRELOAD=false
```

### 方式2：脚本恢复

```bash
python scripts/enable_asr_preload_permanent.py
```

选择 **2**（启用预加载）

---

## 💡 建议

| 场景 | 推荐方案 |
|------|---------|
| **偶尔使用** | ✅ 禁用预加载 |
| **频繁使用** | ⏸️ 启用预加载 |
| **中国用户** | ✅ FunASR 预加载 |

---

## ❓ 常见问题

**Q: 禁用后首次使用会怎样？**
A: 自动加载模型，会多花144秒。后续使用无影响。

**Q: 影响准确率吗？**
A: 不影响，预加载不影响模型本身。

**Q: 如何验证已禁用？**
A: 查看日志：
```
⚠️ 检测到 DISABLE_ASR_PRELOAD=true，跳过所有模型预加载
💡 模型将在首次使用时自动加载（首次调用会稍慢）
```

---

## 📝 一句话总结

**运行 `python scripts/enable_asr_preload_permanent.py` 选择 1，启动速度提升 141秒！**
