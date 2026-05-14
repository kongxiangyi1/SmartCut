import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, r'e:\ClipProject\autoclip-main1\autoclip-main')

conn = sqlite3.connect(r'e:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db')
cursor = conn.cursor()

print("=" * 60)
print("📊 项目状态概览")
print("=" * 60)

# 首先查看projects表的结构
cursor.execute("PRAGMA table_info(projects)")
columns = cursor.fetchall()
print("\nProjects表结构:")
for col in columns:
    print(f"  {col}")

# 获取所有项目
cursor.execute("""
    SELECT id, name, status, project_type, created_at, updated_at
    FROM projects
    ORDER BY updated_at DESC
    LIMIT 20
""")
projects = cursor.fetchall()

print(f"\n最近项目数: {len(projects)}\n")

for proj in projects:
    project_id, name, status, proj_type, created, updated = proj
    print(f"项目: {name}")
    print(f"  ID: {project_id}")
    print(f"  状态: {status}")
    print(f"  类型: {proj_type}")
    print(f"  创建时间: {created}")
    print(f"  更新时间: {updated}")

    # 获取任务状态
    cursor.execute("""
        SELECT id, name, status, progress, current_step, started_at, completed_at
        FROM tasks WHERE project_id = ?
        ORDER BY started_at DESC
    """, (project_id,))
    task_rows = cursor.fetchall()

    if task_rows:
        print(f"  任务数: {len(task_rows)}")
        for task in task_rows:
            tid, tname, tstatus, tprogress, tstep, tstart, tcomplete = task
            print(f"    任务: {tname}")
            print(f"      状态: {tstatus}")
            print(f"      进度: {tprogress}%")
            print(f"      当前步骤: {tstep}")
            print(f"      开始时间: {tstart}")
            print(f"      完成时间: {tcomplete}")
    else:
        print(f"  任务数: 0")

    # 获取切片数
    cursor.execute("SELECT COUNT(*) FROM clips WHERE project_id = ?", (project_id,))
    clip_count = cursor.fetchone()[0]
    print(f"  切片数: {clip_count}")

    # 获取合集数
    cursor.execute("SELECT COUNT(*) FROM collections WHERE project_id = ?", (project_id,))
    coll_count = cursor.fetchone()[0]
    print(f"  合集数: {coll_count}")

    print()

conn.close()