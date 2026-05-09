import sqlite3
from pathlib import Path

# 查询数据库项目状态
db_path = Path('data') / 'autoclip.db'
if not db_path.exists():
    print(f"❌ 数据库不存在: {db_path}")
    exit(1)

print(f"✅ 数据库存在: {db_path}")

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 查询所有项目
cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
projects = cursor.fetchall()

print(f"\n📊 共 {len(projects)} 个项目:\n")

for i, project in enumerate(projects):
    project_id = project['id']
    name = project['name'][:50]
    status = project['status']
    project_type = project['project_type']
    video_path = project['video_path']
    created_at = project['created_at']
    updated_at = project['updated_at']
    
    # 确定是否正在导入中
    is_importing = status in ['pending', 'processing']
    
    status_emoji = {
        'pending': '⏳',
        'processing': '🔄',
        'completed': '✅',
        'failed': '❌'
    }.get(status, '❓')
    
    print(f"{status_emoji} {i+1}. {name}")
    print(f"     ID: {project_id}")
    print(f"     状态: {status}")
    print(f"     类型: {project_type}")
    print(f"     创建时间: {created_at}")
    if status != 'pending':
        print(f"     更新时间: {updated_at}")
    
    if video_path:
        video_file = Path(video_path)
        if video_file.exists():
            size_mb = video_file.stat().st_size / (1024*1024)
            print(f"     📹 视频: {size_mb:.1f} MB")
        else:
            print(f"     ❌ 视频文件不存在")
    
    if is_importing:
        print(f"     🎯 正在导入处理中...")
        if status == 'pending':
            print(f"         💡 任务在队列中等待处理")
        elif status == 'processing':
            print(f"         💡 正在执行处理任务")
    
    print()

conn.close()

# 检查是否有相应的任务记录
print("🔍 检查任务记录...")
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

cursor.execute("SELECT * FROM tasks ORDER BY created_at DESC LIMIT 10")
tasks = cursor.fetchall()

if tasks:
    print(f"📋 最近 {len(tasks)} 个任务:")
    for task in tasks:
        print(f"   ID: {task[0]}, 类型: {task[2]}, 状态: {task[3]}")
        print(f"   项目ID: {task[1]}, 创建时间: {task[6]}")
else:
    print("✅ 没有活跃的任务记录")

conn.close()