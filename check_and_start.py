
import sqlite3
import os

conn = sqlite3.connect(r'e:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db')
cursor = conn.cursor()

print('=== 项目详情 ===')
cursor.execute("SELECT * FROM projects WHERE name LIKE '%clip_001_product%'")
cols = [desc[0] for desc in cursor.description]
project = cursor.fetchone()
if project:
    project_dict = dict(zip(cols, project))
    for k, v in project_dict.items():
        print(f'{k}: {v}')
    
    project_id = project_dict['id']
    print(f'\n=== 项目目录检查 ===')
    project_dir = os.path.join(r'e:\ClipProject\autoclip-main1\autoclip-main\data\projects', project_id)
    print(f'项目目录: {project_dir}')
    if os.path.exists(project_dir):
        for item in os.listdir(project_dir):
            full_path = os.path.join(project_dir, item)
            if os.path.isdir(full_path):
                print(f'  目录: {item}')
                for subitem in os.listdir(full_path):
                    print(f'    - {subitem}')
            else:
                print(f'  文件: {item}')
    else:
        print('  目录不存在！')
    
    print(f'\n=== 检查任务 ===')
    cursor.execute("SELECT * FROM tasks WHERE project_id = ?", (project_id,))
    cols = [desc[0] for desc in cursor.description]
    task = cursor.fetchone()
    if task:
        for k, v in zip(cols, task):
            print(f'{k}: {v}')
    else:
        print('没有找到相关任务！')

conn.close()
