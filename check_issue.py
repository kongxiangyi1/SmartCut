
import sqlite3

conn = sqlite3.connect(r'e:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db')
cursor = conn.cursor()

print('=== 卡住的任务详情 ===')
cursor.execute("SELECT * FROM tasks WHERE id = '3f535022-125b-42bb-a177-86ec0393abf9'")
cols = [desc[0] for desc in cursor.description]
task = cursor.fetchone()
if task:
    for k, v in zip(cols, task):
        if k == 'result_data' and v:
            print(f'{k}: (有数据, {len(v)} chars)')
        elif k == 'error_message' and v:
            print(f'{k}: {v}')
        else:
            print(f'{k}: {v}')

print('\n=== 对应项目 ===')
cursor.execute("SELECT * FROM projects WHERE id = '108c1056-fe23-4d56-8599-640bea390a37'")
cols = [desc[0] for desc in cursor.description]
project = cursor.fetchone()
if project:
    for k, v in zip(cols, project):
        print(f'{k}: {v}')

conn.close()
