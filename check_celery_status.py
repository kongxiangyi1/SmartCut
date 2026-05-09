import sys
sys.path.append('.')

from backend.core.celery_app import celery_app
from celery import current_app

try:
    print("检查Celery worker状态...")
    
    # 检查worker状态
    inspector = current_app.control.inspect()
    
    active = inspector.active()
    if active:
        print(f"✅ 找到 {len(active)} 个活跃worker")
        for worker, tasks in active.items():
            print(f"Worker: {worker}")
            for task in tasks:
                print(f"  - 正在执行: {task['name']} (任务ID: {task['id']})")
    else:
        print("❌ 没有活跃的worker")
    
    # 检查等待任务
    scheduled = inspector.scheduled()
    if scheduled:
        print(f"\n⏳ 等待的任务: {len(scheduled)}")
        for worker, tasks in scheduled.items():
            print(f"Worker: {worker}")
            for task in tasks:
                print(f"  - 等待: {task.get('name', '未知任务')} (任务ID: {task.get('request', {}).get('id', '未知')})")
    
    # 检查reserved任务
    reserved = inspector.reserved()
    if reserved:
        print(f"\n📥 Reserved任务: {len(reserved)}")
        for worker, tasks in reserved.items():
            print(f"Worker: {worker}")
            for task in tasks:
                print(f"  - {task['name']} (任务ID: {task['id']})")
    
except Exception as e:
    print(f"❌ 检查Celery状态失败: {e}")
    import traceback
    traceback.print_exc()