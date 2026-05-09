"""
测试步骤1：大纲提取
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from pathlib import Path
from pipeline.step1_outline import run_step1_outline
from core.shared_config import METADATA_DIR

def test_step1_outline():
    print("正在测试步骤1：大纲提取...")
    
    # 检查SRT文件是否存在
    srt_path = METADATA_DIR / "step1_srt_chunks" / "chunk_0.json"
    print(f"SRT文件路径: {srt_path}")
    if not srt_path.exists():
        print("❌ SRT文件不存在")
        return False
        
    print("✅ SRT文件存在")
    
    # 读取SRT内容
    with open(srt_path, 'r', encoding='utf-8') as f:
        srt_data = json.load(f)
    print(f"SRT条目数量: {len(srt_data)}")
    
    # 创建临时输入SRT文件
    temp_srt = METADATA_DIR / "test_input.srt"
    print(f"创建临时SRT文件: {temp_srt}")
    
    try:
        with open(temp_srt, 'w', encoding='utf-8') as f:
            for i, item in enumerate(srt_data, 1):
                start = item['start_time'].replace(',', ' --> ')
                end = item['end_time']
                f.write(f"{i}\n")
                f.write(f"{start}{end}\n")
                f.write(f"{item['text']}\n\n")
        
        print("✅ 临时SRT文件创建成功")
        
        # 运行步骤1
        print("正在运行步骤1：大纲提取...")
        outlines = run_step1_outline(temp_srt, METADATA_DIR)
        
        print(f"大纲提取结果数量: {len(outlines)}")
        
        if outlines:
            print("✅ 大纲提取成功！")
            for outline in outlines:
                print(f"  - {outline.get('title', '无标题')}")
        else:
            print("❌ 大纲提取失败，结果为空")
            
        return len(outlines) > 0
        
    finally:
        # 清理临时文件
        if temp_srt.exists():
            temp_srt.unlink()

if __name__ == "__main__":
    success = test_step1_outline()
    sys.exit(0 if success else 1)