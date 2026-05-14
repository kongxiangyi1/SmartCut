# 项目打包与部署方案

## 1. 概述

本文档描述AutoClip项目的打包策略，特别是针对FunASR大模型的处理方案。

## 2. 依赖大小分析

### 2.1 核心依赖体积

| 组件 | 大小 | 说明 |
|------|------|------|
| FunASR包 | ~6.74 MB | Python代码 |
| FunASR模型 | **~3.1 GB** | VAD语音检测模型（主要体积来源） |
| 其他依赖 | ~500 MB | librosa、torch、modelscope等 |
| **总计** | **~3.6 GB** | 完整部署所需空间 |

### 2.2 模型存储位置

模型默认缓存路径：
```
Windows: C:\Users\<用户名>\.cache\modelscope
Linux/macOS: ~/.cache/modelscope
```

## 3. 打包策略

### 3.1 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **完整离线包** | 开箱即用、无需网络 | 安装包大（3.6GB+） | 企业内网、离线环境 |
| **轻量安装包** | 安装包小（~50MB） | 首次启动需下载模型 | 个人用户、有网络环境 |
| **预下载模型** | 可控性强、可增量更新 | 部署流程稍复杂 | 多版本维护、定制化部署 |

### 3.2 推荐策略：双版本发布

同时提供两种版本，让客户根据自身环境选择：

#### 方案A：完整离线包

**包结构**：
```
autoclip_full_vX.Y.Z.zip
├── python/           # Python运行环境（可选）
├── packages/         # pip包目录
├── models/           # FunASR模型(3.1GB)
├── app/              # 应用代码
└── start_autoclip.ps1
```

**打包步骤**：
```powershell
# 1. 提前下载模型
python -c "from funasr import AutoModel; model = AutoModel(model='fsmn-vad')"

# 2. 复制模型到项目目录
Copy-Item -Path "$env:USERPROFILE\.cache\modelscope" -Destination ".\models" -Recurse

# 3. 打包
Compress-Archive -Path "backend", "frontend", "models", "start_autoclip.ps1" -DestinationPath "autoclip_full_v1.0.0.zip"
```

#### 方案B：轻量安装包

**包结构**：
```
autoclip_light_vX.Y.Z.zip
├── app/              # 应用代码
├── requirements.txt  # 依赖列表（含funasr>=1.3.0）
└── install.ps1       # 一键安装脚本
```

**install.ps1 示例**：
```powershell
Write-Host "========== AutoClip 安装向导 =========="
Write-Host ""
Write-Host "⚠️ 注意：首次运行会自动下载语音模型(~3GB)"
Write-Host "请确保网络畅通，预计下载时间取决于您的网络速度"
Write-Host ""

# 安装依赖
pip install -r requirements.txt

Write-Host ""
Write-Host "✅ 安装完成！"
Write-Host "运行: .\start_autoclip.ps1"
```

### 3.3 模型路径配置

在 `backend/core/shared_config.py` 中可配置模型路径：

```python
MODEL_CONFIG = {
    "funasr_model": "fsmn-vad",
    "model_cache_dir": None,  # None=自动检测，可指定自定义路径
    "auto_download": True,    # 是否自动下载缺失的模型
}
```

## 4. 部署流程

### 4.1 完整离线包部署

```
1. 解压 autoclip_full_vX.Y.Z.zip
2. 运行 start_autoclip.ps1
3. 等待服务启动（无需额外下载）
4. 访问 http://localhost:3000
```

### 4.2 轻量安装包部署

```
1. 解压 autoclip_light_vX.Y.Z.zip
2. 运行 install.ps1（安装依赖）
3. 首次运行 start_autoclip.ps1（自动下载模型，约3GB）
4. 后续运行直接启动（无需重复下载）
5. 访问 http://localhost:3000
```

## 5. 注意事项

### 5.1 模型更新

```powershell
# 手动更新模型
Remove-Item -Path "$env:USERPROFILE\.cache\modelscope" -Recurse -Force
python -c "from funasr import AutoModel; model = AutoModel(model='fsmn-vad')"
```

### 5.2 网络代理

如果客户网络需要代理：

```powershell
# 设置代理环境变量
$env:HTTP_PROXY = "http://proxy.example.com:8080"
$env:HTTPS_PROXY = "http://proxy.example.com:8080"

# 启动应用
.\start_autoclip.ps1
```

### 5.3 存储空间要求

| 版本 | 安装前 | 安装后 |
|------|--------|--------|
| 完整离线包 | ~3.6GB | ~3.6GB |
| 轻量安装包 | ~50MB | ~3.6GB |

## 6. 客户交付清单

```
├── autoclip_full_vX.Y.Z.zip     # 完整离线包（可选）
├── autoclip_light_vX.Y.Z.zip    # 轻量安装包（必选）
├── README.txt                    # 安装说明
├── install.ps1                   # 安装脚本
└── license.txt                   # 许可证文件
```

## 7. 版本管理

| 版本号 | 说明 |
|--------|------|
| vX.Y.Z-full | 完整版本，包含所有依赖和模型 |
| vX.Y.Z-light | 轻量版本，仅包含代码和安装脚本 |

---

**文档版本**: v1.0  
**创建日期**: 2026-05-13  
**适用项目**: AutoClip
