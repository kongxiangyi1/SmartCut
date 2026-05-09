
import sqlite3
import os
import shutil

# 连接数据库
conn = sqlite3.connect(r'e:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db')
cursor = conn.cursor()

# 查找项目
cursor.execute("SELECT id, name, status FROM projects WHERE name LIKE '%clip_001_product%'")
projects = cursor.fetchall()

print('=== 找到的项目 ===')
for row in projects:
    project_id = row[0]
    print(f'ID: {project_id}, Name: {row[1]}, Status: {row[2]}')
    
    # 删除相关任务
    cursor.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))
    print(f'  - 删除了 {cursor.rowcount} 个相关任务')
    
    # 删除项目记录
    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    print(f'  - 删除了项目记录')
    
    # 删除项目目录
    project_dir = os.path.join(r'e:\ClipProject\autoclip-main1\autoclip-main\data\projects', project_id)
    if os.path.exists(project_dir):
        shutil.rmtree(project_dir)
        print(f'  - 删除了项目目录: {project_dir}')

conn.commit()
conn.close()

print('\n=== 删除完成 ===')
