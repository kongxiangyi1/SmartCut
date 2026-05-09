#!/usr/bin/env python3
"""
启动Celery Worker
"""
import sys
import os

# 设置编码
import io
import sys
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
except:
    pass

print("启动AutoClip Celery Worker...")

# 添加当前目录到Python路径
sys.path.insert(0, os.path.abspath('.'))

print(f"Python路径: {sys.path}")

try:
    # 导入Celery应用
    print("导入Celery应用...")
    from backend.core.celery_app import celery_app
    
    print("Celery应用加载成功!")
    print(f"已发现的任务: {list(celery_app.tasks.keys())}")
    
    print("开始启动worker...")
    
    # 启动worker
    celery_app.worker_main(['worker', '--loglevel=info'])
    
except Exception as e:
    print(f"启动失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)