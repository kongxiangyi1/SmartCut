"""修复卡住的项目状态"""
import sqlite3
from pathlib import Path

db_path = Path("data") / "autoclip.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=== 当前项目状态 ===")
cursor.execute("SELECT id, name, status, created_at FROM projects")
projects = cursor.fetchall()
for p in projects:
    print(f"ID: {p[0]}")
    print(f"  Name: {p[1]}")
    print(f"  Status: {p[2]}")
    print(f"  Created: {p[3]}")
    print()

print("\n=== 检查项目目录 ===")
projects_dir = Path("data") / "projects"
fixed_count = 0

for p in projects:
    project_id = p[0]
    status = p[2]
    project_dir = projects_dir / project_id
    
    if project_dir.exists():
        # 检查是否有处理结果
        metadata_dir = project_dir / "metadata"
        has_outline = (metadata_dir / "step1_outline.json").exists()
        has_timeline = (metadata_dir / "step2_timeline.json").exists()
        has_clips = (metadata_dir / "step3_high_score_clips.json").exists()
        has_titles = (metadata_dir / "step4_titles.json").exists()
        has_collections = (metadata_dir / "step5_collections.json").exists()
        
        print(f"项目 {project_id}:")
        print(f"  目录存在: 是")
        print(f"  有大纲: {has_outline}")
        print(f"  有时间线: {has_timeline}")
        print(f"  有评分剪辑: {has_clips}")
        print(f"  有标题: {has_titles}")
        print(f"  有合集: {has_collections}")
        
        # 判断是否应该更新状态
        should_update = False
        new_status = status
        
        if status == "processing" and has_outline:
            # 如果正在处理中但已经有处理结果，说明处理已完成
            new_status = "completed"
            should_update = True
        elif status == "pending":
            # 如果是pending状态但有处理结果，说明处理已完成
            if has_outline and has_timeline:
                new_status = "completed"
                should_update = True
        
        if should_update:
            print(f"  状态更新: {status} -> {new_status}")
            cursor.execute(
                "UPDATE projects SET status = ? WHERE id = ?",
                (new_status, project_id)
            )
            fixed_count += 1
        else:
            print(f"  状态无需更新")
        print()

conn.commit()
conn.close()

print(f"\n=== 修复完成 ===")
print(f"已修复 {fixed_count} 个项目")