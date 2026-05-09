import requests
import json
import time

print("=== 导入项目处理进度监控 ===\n")

def get_all_projects():
    """获取所有项目并分析状态"""
    try:
        response = requests.get("http://localhost:8000/api/v1/projects/", timeout=10)
        if response.status_code == 200:
            return response.json()['items']
        else:
            print(f"❌ API请求失败: {response.status_code}")
            return []
    except Exception as e:
        print(f"🔴 API连接失败: {e}")
        return []

def format_project_info(project):
    """格式化处理项目信息"""
    status_emoji = {
        'pending': '⏳',
        'processing': '🔄', 
        'completed': '✅',
        'failed': '❌'
    }.get(project['status'], '❓')
    
    # 找出导入中的项目（刚刚上传且片段数仍为0的项目）
    is_importing = (project['status'] in ['pending', 'processing'] and 
                   project['total_clips'] == 0 and
                   'bandicam' in project['name'].lower() or 
                   'clip_001' in project['name'].lower())
    
    return {
        'id': project['id'],
        'name': project['name'][:40] + ('...' if len(project['name']) > 40 else ''),
        'status': project['status'],
        'emoji': status_emoji,
        'clips': project['total_clips'],
        'collections': project['total_collections'],
        'type': project['project_type'],
        'created': project['created_at'],
        'updated': project['updated_at'],
        'is_importing': is_importing
    }

# 等待后端服务启动
print("⏳ 等待后端服务响应...")
for i in range(6):  # 最多等待6次
    projects = get_all_projects()
    if projects:
        print("✅ 后端服务连接成功\n")
        break
    else:
        print(f"等待中 ({i+1}/6)...")
        time.sleep(2)
else:
    print("❌ 无法连接后端服务")
    print("需要启动后端服务:")
    print("  1. 运行: python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000")
    print("  2. 启动Celery: python -c \"from backend.core.celery_app import celery_app; celery_app.worker_main(['worker', '--loglevel=info'])\"")
    exit(1)

# 分析所有项目
projects_info = [format_project_info(p) for p in projects]
projects_info.sort(key=lambda x: x['created'], reverse=True)

print("📋 项目列表:")
print("=" * 120)

importing_projects = []
for i, proj in enumerate(projects_info):
    status_line = f"{proj['emoji']} {proj['name']}"
    status_line += f" | {proj['status']:>10} | {proj['type']:<10} | 片段:{proj['clips']} 合集:{proj['collections']}"
    status_line += f" | 创建:{proj['created'][:19].replace('T', ' ')}"
    if proj['status'] != 'pending':
        status_line += f" | 更新:{proj['updated'][:19].replace('T', ' ')}"
    
    print(status_line)
    
    if proj['is_importing']:
        importing_projects.append(proj)

print("=" * 120)

if importing_projects:
    print(f"\n🎯 检测到 {len(importing_projects)} 个导入中的项目:")
    for proj in importing_projects:
        print(f"   ID: {proj['id']}")
        print(f"   名称: {proj['name']}")
        print(f"   当前状态: {proj['status']}")
        if proj['status'] == 'pending':
            print(f"   💡 说明: 正在队列中等待处理，需要启动或重启Celery Worker")
        elif proj['status'] == 'processing':
            print(f"   💡 说明: 正在处理中，可能是生成缩略图、字幕或AI分析阶段")
else:
    print("\n✅ 没有检测到导入中的项目")

# 检查服务可用性
print(f"\n⚡ 系统状态检查:")
try:
    import sys
    sys.path.append('.')
    from backend.core.celery_app import celery_app
    from celery import current_app
    inspector = current_app.control.inspect()
    
    if inspector.active():
        print("   ✅ Celery Worker: 运行中")
    else:
        print("   ❌ Celery Worker: 空闲或未运行")
        print("   💡 建议: 启动Celery worker: python -c \"from backend.core.celery_app import celery_app; celery_app.worker_main(['worker', '--loglevel=info'])\"")
except Exception as e:
    print(f"   ❌ Celery检查失败: {e}")
    print("   💡 建议: 确保Celery worker正在运行")

print(f"\n📊 统计信息:")
stats = {}
for proj in projects_info:
    status = proj['status']
    stats[status] = stats.get(status, 0) + 1
    
for status, count in sorted(stats.items()):
    emoji = {'pending': '⏳', 'processing': '🔄', 'completed': '✅', 'failed': '❌'}.get(status, '')
    print(f"   {emoji} {status}: {count} 个")