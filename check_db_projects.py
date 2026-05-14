
import sqlite3

# 连接数据库
conn = sqlite3.connect(r'E:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db')
cursor = conn.cursor()

# 查询所有项目
cursor.execute("SELECT id, status, created_at, completed_at FROM projects ORDER BY created_at DESC")
projects = cursor.fetchall()

print("数据库中的项目列表:")
print("-" * 80)
for project in projects:
    project_id, status, created_at, completed_at = project
    print(f"项目ID: {project_id}")
    print(f"状态: {status}")
    print(f"创建时间: {created_at}")
    print(f"完成时间: {completed_at}")
    print("-" * 80)

# 查询任务
cursor.execute("SELECT project_id, task_name, status, created_at, completed_at FROM tasks ORDER BY created_at DESC")
tasks = cursor.fetchall()

print("\n最近的任务:")
print("-" * 80)
for task in tasks[:10]:
    project_id, task_name, status, created_at, completed_at = task
    print(f"项目ID: {project_id[:10]}...")
    print(f"任务名称: {task_name}")
    print(f"状态: {status}")
    print(f"创建时间: {created_at}")
    print(f"完成时间: {completed_at}")
    print("-" * 80)

conn.close()
