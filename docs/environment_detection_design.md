# 环境自动检测方案设计文档

## 1. 方案概述

### 1.1 设计目标

本方案旨在实现**运行环境自动检测**，根据检测结果自动选择最优配置策略，实现：

- **本地部署优化**：充分利用本地SSD高性能存储和多核CPU
- **服务器部署兼容**：保守配置确保云服务器稳定运行
- **硬件自适应**：自动检测SSD/HDD并调整IO策略
- **零配置部署**：无需手动配置，开箱即用

### 1.2 适用场景

| 场景 | 环境特征 | 推荐策略 |
|------|---------|---------|
| 本地开发 | Windows + SSD | 高性能配置 |
| 本地测试 | Windows + HDD | IO保护配置 |
| 云服务器 | Linux + 云盘 | 稳定配置 |
| Docker容器 | /.dockerenv | 稳定配置 |

---

## 2. 技术方案

### 2.1 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    环境检测层                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 本地检测 │  │ SSD检测  │  │ CPU检测  │  │ 内存检测 │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │             │          │
└───────┼─────────────┼─────────────┼─────────────┼──────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                    配置生成层                               │
│                    EnvironmentDetector                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  get_optimal_config() → 根据检测结果生成最优配置       │   │
│  └──────────────────────────────────────────────────────┘   │
└───────┬─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                    应用层                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ 文件上传 │  │ 视频切片 │  │ 数据同步 │  │ 任务调度 │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 检测方法

#### 2.2.1 本地环境检测

| 优先级 | 检测方法 | 说明 |
|--------|---------|------|
| 1 | 环境变量 `ENVIRONMENT` | 手动设置最高优先级 |
| 2 | 容器检测 `/.dockerenv` | 存在则为服务器环境 |
| 3 | 操作系统检测 | Windows = 本地 |
| 4 | 网络延迟检测 | ping 127.0.0.1 |

#### 2.2.2 SSD检测

| 方法 | 实现方式 | 适用平台 |
|------|---------|---------|
| IO速度检测 | `psutil.disk_io_counters()` | 跨平台 |
| 磁盘型号检测 | `wmic diskdrive get model` | Windows |
| 旋转标志检测 | `/sys/block/sda/queue/rotational` | Linux |

### 2.3 配置参数说明

| 参数 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `environment` | str | 环境类型: `local`/`server` | - |
| `has_ssd` | bool | 是否SSD存储 | - |
| `cpu_count` | int | CPU核心数 | 4 |
| `available_memory_gb` | float | 可用内存(GB) | 4.0 |
| `chunk_size_bytes` | int | 文件读写块大小 | 1MB |
| `max_workers` | int | 并行线程数 | 4 |
| `use_streaming_write` | bool | 是否使用流式写入 | True |
| `use_streaming_slice` | bool | 是否使用流式切片 | True |
| `use_hardlink` | bool | 是否使用硬链接 | False |
| `io_delay_seconds` | float | IO操作间隔(秒) | 0.0 |

---

## 3. 配置策略矩阵

### 3.1 配置策略对比

| 环境类型 | chunk_size | max_workers | use_hardlink | io_delay |
|---------|------------|-------------|--------------|----------|
| **本地SSD** | 8MB | max(4, min(cpu, mem/2)) | True | 0s |
| **本地HDD** | 512KB | min(2, cpu) | True | 0.1s |
| **服务器** | 2MB | min(4, cpu) | False | 0.05s |

### 3.2 策略选择逻辑

```python
if is_local and has_ssd:
    # 本地SSD: 最大化性能
    config = high_performance_config
elif is_local and not has_ssd:
    # 本地HDD: IO保护
    config = io_protection_config
else:
    # 服务器: 稳定优先
    config = server_stable_config
```

---

## 4. 实现细节

### 4.1 文件结构

```
backend/
└── utils/
    ├── environment_detector.py   # 环境检测器核心类
    └── __init__.py               # 模块导出
```

### 4.2 核心类设计

#### 4.2.1 EnvironmentDetector 类

**静态方法列表**：

| 方法 | 功能 | 返回值 |
|------|------|--------|
| `is_local()` | 判断是否本地环境 | bool |
| `has_ssd()` | 判断是否SSD | bool |
| `get_cpu_count()` | 获取CPU核心数 | int |
| `get_available_memory_gb()` | 获取可用内存 | float |
| `get_disk_space_gb()` | 获取可用磁盘空间 | float |
| `get_optimal_config()` | 获取最优配置 | dict |
| `get_environment_summary()` | 获取环境摘要 | str |
| `test_environment_detection()` | 运行测试套件 | dict |

#### 4.2.2 缓存机制

```python
# 使用类变量缓存检测结果
_detection_cache: Dict[str, any] = {}

# 检测前先检查缓存
if 'is_local' in _detection_cache:
    return _detection_cache['is_local']

# 检测后保存到缓存
_detection_cache['is_local'] = result
```

**缓存优点**：
- 减少重复检测开销
- 保证同一进程内检测结果一致
- 可通过 `_reset_cache()` 手动刷新

---

## 5. 应用集成方案

### 5.1 文件上传优化

```python
# backend/api/v1/projects.py

from backend.utils.environment_detector import EnvironmentDetector

async def upload_files(video_file: UploadFile = File(...)):
    # 获取最优配置
    config = EnvironmentDetector.get_optimal_config()
    chunk_size = config["chunk_size_bytes"]
    
    # 流式写入
    video_path = raw_dir / "input.mp4"
    with open(video_path, "wb") as f:
        while True:
            chunk = await video_file.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
    
    # 硬链接优化（本地环境）
    if config["use_hardlink"]:
        # 尝试硬链接替代复制
        pass
```

### 5.2 视频切片优化

```python
# backend/utils/video_processor.py

def batch_extract_clips_parallel(input_video: Path, clips_data: List[Dict]):
    config = EnvironmentDetector.get_optimal_config()
    max_workers = config["max_workers"]
    io_delay = config["io_delay_seconds"]
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for clip_data in clips_data:
            executor.submit(extract_single_clip, clip_data)
            if io_delay > 0:
                time.sleep(io_delay)
```

### 5.3 启动时检测

```python
# backend/main.py

from backend.utils.environment_detector import EnvironmentDetector

@app.on_event("startup")
async def startup_event():
    # 打印环境检测报告
    logger.info("\n" + EnvironmentDetector.get_environment_summary())
    
    # 初始化最优配置
    config = EnvironmentDetector.get_optimal_config()
    app.state.environment_config = config
```

---

## 6. 验证方案

### 6.1 测试脚本

运行测试脚本验证功能：

```bash
python test_environment_detection.py
```

### 6.2 测试用例

| 测试项 | 预期结果 |
|--------|---------|
| 本地环境检测 | Windows返回True，Linux返回False |
| SSD检测 | SSD返回True，HDD返回False |
| CPU计数 | 返回正确核心数 |
| 内存检测 | 返回正确可用内存 |
| 配置生成 | 根据环境生成对应配置 |
| 环境变量覆盖 | ENVIRONMENT=local强制返回True |

### 6.3 手动验证

```python
from backend.utils.environment_detector import EnvironmentDetector

# 打印环境摘要
print(EnvironmentDetector.get_environment_summary())

# 获取配置
config = EnvironmentDetector.get_optimal_config()
print(f"推荐线程数: {config['max_workers']}")
print(f"使用硬链接: {config['use_hardlink']}")
```

---

## 7. 兼容性说明

### 7.1 操作系统兼容

| 系统 | 本地检测 | SSD检测 | CPU检测 | 内存检测 |
|------|---------|---------|---------|---------|
| Windows 10/11 | ✅ | ✅ | ✅ | ✅ |
| Linux (Ubuntu/CentOS) | ✅ | ✅ | ✅ | ✅ |
| macOS | ✅ | ⚠️ | ✅ | ✅ |

### 7.2 依赖说明

| 依赖 | 用途 | 安装方式 |
|------|------|---------|
| `psutil` | 系统信息获取 | `pip install psutil` |

---

## 8. 性能影响

| 影响维度 | 评估 | 说明 |
|----------|------|------|
| 启动时间 | 可忽略 | 检测耗时 < 100ms |
| 内存占用 | 可忽略 | 缓存仅存储少量布尔/整数值 |
| CPU占用 | 可忽略 | 检测操作非CPU密集 |

---

## 9. 安全考虑

### 9.1 环境变量注入

- **风险**：恶意用户可能通过设置 `ENVIRONMENT` 环境变量影响配置
- **缓解**：生产环境应通过容器编排工具统一管理环境变量

### 9.2 路径遍历

- **风险**：硬链接功能可能被利用进行路径遍历攻击
- **缓解**：
  1. 限制硬链接目标目录
  2. 验证路径合法性
  3. 仅允许在项目数据目录内创建硬链接

---

## 10. 扩展计划

### 10.1 未来优化方向

| 功能 | 描述 | 优先级 |
|------|------|--------|
| GPU检测 | 检测NVIDIA/AMD GPU，启用硬件加速 | 中 |
| 网络检测 | 检测网络延迟，优化远程存储访问 | 低 |
| 配置热更新 | 运行时动态调整配置 | 低 |
| 多磁盘支持 | 检测多个磁盘，选择最优存储位置 | 中 |

---

## 附录：配置示例

### 本地SSD环境配置

```python
{
    "environment": "local",
    "has_ssd": true,
    "cpu_count": 8,
    "available_memory_gb": 15.8,
    "chunk_size_bytes": 8388608,  # 8MB
    "max_workers": 8,
    "use_streaming_write": true,
    "use_streaming_slice": true,
    "use_hardlink": true,
    "io_delay_seconds": 0.0,
    "description": "本地SSD环境 - 高性能配置"
}
```

### 服务器环境配置

```python
{
    "environment": "server",
    "has_ssd": false,
    "cpu_count": 4,
    "available_memory_gb": 7.2,
    "chunk_size_bytes": 2097152,  # 2MB
    "max_workers": 4,
    "use_streaming_write": true,
    "use_streaming_slice": true,
    "use_hardlink": false,
    "io_delay_seconds": 0.05,
    "description": "服务器环境 - 稳定配置"
}
```
