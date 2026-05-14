import sqlite3

conn = sqlite3.connect(r'e:\ClipProject\autoclip-main1\autoclip-main\data\autoclip.db')
cursor = conn.cursor()

print("=" * 70)
print("查看 projects 表结构")
print("=" * 70)

cursor.execute("PRAGMA table_info(projects)")
columns = cursor.fetchall()
for col in columns:
    print(f"{col[1]}: {col[2]}")

conn.close()

print("\n" + "=" * 70)
