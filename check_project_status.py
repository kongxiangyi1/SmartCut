"""检查项目状态 - 简化版本"""
import sqlite3
from pathlib import Path

# 找到数据库文件
db_path = Path("data") / "autoclip.db"
if not db_path.exists():
    db_path = Path(".") / "data" / "autoclip.db"

print(f"数据库路径: {db_path}")
print(f"数据库存在: {db_path.exists()}")

if db_path.exists():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n=== 表结构 ===")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    for table in tables:
        table_name = table[0]
        print(f"\n表: {table_name}")
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
    
    print("\n=== 项目列表 ===")
    cursor.execute("SELECT * FROM projects")
    columns = [desc[0] for desc in cursor.description]
    projects = cursor.fetchall()
    for p in projects:
        print(f"记录: {dict(zip(columns, p))}")
        print()
    
    print("\n=== 任务列表 ===")
    cursor.execute("SELECT * FROM tasks")
    columns = [desc[0] for desc in cursor.description]
    tasks = cursor.fetchall()
    for t in tasks:
        print(f"记录: {dict(zip(columns, t))}")
        print()
    
    conn.close()
else:
    print("数据库文件不存在")