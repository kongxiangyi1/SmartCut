import sqlite3
conn = sqlite3.connect('data/autoclip.db')
cursor = conn.cursor()
cursor.execute("SELECT id, name, status FROM projects WHERE status = 'pending' ORDER BY created_at DESC LIMIT 5")
rows = cursor.fetchall()
if rows:
    for r in rows:
        print(f'Pending: {r[0]} - {r[1]}')
else:
    print('无pending项目')
conn.close()
