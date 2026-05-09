#!/usr/bin/env python3
"""
修复Celery任务注册问题
手动验证和重新加载任务
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

try:
    print("开始检查Celery任务...")
    
    # 导入celery应用
    from backend.core.celery_app import celery_app
    
    print(f"Celery配置: ")
    print(f"  - Broker: {celery_app.conf.broker_url}")
    print(f"  - 后端: {celery_app.conf.result_backend}")
    
    print(f"\n自动发现的任务模块: {celery_app._autodiscover_tasks_from_names(['backend.tasks.import_processing', 'backend.tasks.processing'])}")
    
    print(f"\n重新手动发现任务...")
    celery_app.autodiscover_tasks([
        'backend.tasks.import_processing',
        'backend.tasks.processing',
        'backend.tasks.video', 
        'backend.tasks.notification',
        'backend.tasks.maintenance'
    ], force=True)
    
    print(f"\n发现的任务列表: ")
    tasks = list(celery_app.tasks.keys())
    custom_tasks = [t for t in tasks if not t.startswith('celery.')]
    print(f"  自定义任务 ({len(custom_tasks)}个): {custom_tasks[:10]}")
    if len(custom_tasks) > 10:
        print(f"  更多... (共{len(custom_tasks)}个)")
    
    # 特别查找import processing任务
    import_task = None
    for task_name, task_obj in celery_app.tasks.items():
        if 'process_import' in task_name:
            import_task = task_name
            break
    
    if import_task:
        print(f"\n✅ 找到import任务: {import_task}")
        print(f"  任务对象: {celery_app.tasks[import_task]}")
    else:
        print(f"\n❌ 未找到import processing任务")
        
    print(f"\n直接导入import processing模块...")
    from backend.tasks import import_processing
    print(f"  模块导入成功: {import_processing}")
    
    # 查找任务函数
    process_import_task = getattr(import_processing, 'process_import_task', None)
    if process_import_task:
        print(f"  任务函数: {process_import_task}")
        print(f"  是否已注册: {process_import_task.name in celery_app.tasks}")
        if process_import_task.name in celery_app.tasks:
            print(f"  任务注册名: {process_import_task.name}")
    
    # 测试手动提交任务
    print(f"\n测试任务提交...")
    if process_import_task:
        from backend.core.celery_app import celery_app as app
        
        # 先临时切换到内存后端测试
        app.conf.task_always_eager = True  # 同步执行
        
        print("  切换到同步模式测试任务执行...")
        try:
            # 模拟一个基本的项目参数
            test_result = process_import_task(
                project_id="test-87c97a21-6922-4cff-895e-2b821678ee2c",
                video_path="D:/Download/autoclip-main1/autoclip-main/data/projects/87c97a21-6922-4cff-895e-2b821678ee2c/raw/input.mp4",
                srt_file_path=None
            )
            print(f"  静态方法调用结果: {test_result}")
        except Exception as e:
            print(f"  实例调用我们需要绑定: {e}")
        
        # 恢复异步
        app.conf.task_always_eager = False
        
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
    
print("\n检查完成！")