import sqlite3

db_path = 'data/autoclip.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print('检查表结构...')
cursor.execute('PRAGMA table_info(projects)')
columns = cursor.fetchall()
for col in columns:
    print(f'列: {col[1]}, 类型: {col[2]}, 默认值: {col[4]}')

print()
print('检查数据...')
cursor.execute('SELECT id, status, project_type FROM projects')
rows = cursor.fetchall()
for row in rows:
    print(f'ID: {row[0][:8]}..., status: [{row[1]}], type: [{row[2]}]')

conn.close()