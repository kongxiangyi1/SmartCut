# AutoClip 紧急启动指南

## 🚨 问题诊断

根据诊断结果，当前系统状态：
- ✅ 前端服务: 运行正常
- ✅ 数据库: 正常，5个项目
- ✅ Celery worker: 运行正常
- ❌ **后端API服务**: **未启动** - 这是前端报错的主因！
- ✅ 项目结构: 完整

## 🔧 紧急恢复步骤

### 第一步：启动后端服务

```powershell
# PowerShell 中执行
$env:PYTHONPATH="$env:PYTHONPATH;$pwd"
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 第二步：验证后端启动

```powershell
# 新窗口执行
curl http://localhost:8000/docs
# 应该返回 200 OK

curl "http://localhost:8000/api/v1/projects/" 
# 应该返回项目列表 JSON
```

### 第三步：重启Celery worker（如果需要）

```powershell
# 如果需要重启worker
python -c "from backend.core.celery_app import celery_app; celery_app.worker_main(['worker', '--loglevel=info'])"
```

## 📝 检查清单

✅ **后端API**: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`  
✅ **前端服务**: `cd frontend && npx vite --port 3000`  
✅ **Celery worker**: `python start_worker.py`  
✅ **环境变量**: `PYTHONPATH=$PYTHONPATH;$pwd`  
✅ **API密钥**: `.env 文件配置正确`  

## 🌐 正常访问地址

- **前端界面**: http://localhost:3000
- **API文档**: http://localhost:8000/docs  
- **项目API**: http://localhost:8000/api/v1/projects/

## ❓ 常见问题

### Q: 启动后端时报错？
A: 可能需要安装依赖
```powershell
pip install -r requirements.txt
```

### Q: 端口被占用？
A: 杀死占用进程
```powershell
taskkill /F /IM python.exe
```

### Q: 前端仍报错？
A: 检查浏览器控制台，可能是CORS问题，需要确保：
1. 后端API正常运行 
2. 前端配置的后端地址正确
3. 清除浏览器缓存

## 🔄 自动恢复脚本

```python
# save as emergency_restart.py
import os
import subprocess
import time

print("🚀 AutoClip 紧急恢复...")

# 步骤1: 杀死所有Python进程
os.system('taskkill /F /IM python.exe')
time.sleep(2)

# 步骤2: 启动后端
print("启动后端API...")
os.system('start python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000')
time.sleep(5)

# 步骤3: 启动Celery
print("启动Celery worker...") 
os.system('start python start_worker.py')

time.sleep(3)
print("✅ 系统已重启完成")
print("访问: http://localhost:3000")
```

## 📞 帮助支持

如果按照以上步骤仍无法解决：

1. **检查日志**: 查看各服务的错误输出
2. **端口检查**: 确认8000和3000端口未被占用 
3. **依赖检查**: 运行 `pip install -r requirements.txt`
4. **配置检查**: 确认 `.env` 文件存在且配置正确

---

**当前问题**: 后端API服务未启动导致前端无法获取数据
**解决方案**: 按上述步骤1启动后端服务
**预期结果**: 前端恢复正常，可以显示和操作项目

🚀 **重启后你将看到**: 正常的AutoClip界面、项目列表、上传功能！