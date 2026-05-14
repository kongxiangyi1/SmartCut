#!/usr/bin/env python3
"""
测试处理任务触发脚本
用于验证修复后的任务提交流程
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import asyncio
from backend.utils.simple_task_submitter import get_task_submitter

async def test_process_trigger():
    """测试触发处理任务"""
    print("=" * 70)
    print("测试处理任务触发")
    print("=" * 70)
    
    # 项目ID
    project_id = "74b0a1e1-0093-4329-9ffc-c68ae6c8052a"
    
    # 视频路径
    video_path = f"data/projects/{project_id}/raw/input.mp4"
    
    if not os.path.exists(video_path):
        print(f"❌ 视频文件不存在: {video_path}")
        print("请上传视频文件后再试")
        return
    
    print(f"项目ID: {project_id}")
    print(f"视频路径: {video_path}")
    
    # 获取任务提交器
    task_submitter = get_task_submitter()
    
    # 提交导入任务
    print("\n提交导入任务...")
    result = task_submitter.submit_import_task(
        project_id=project_id,
        video_path=video_path,
        srt_file_path=None
    )
    
    print(f"任务提交结果: {result}")
    
    # 等待任务执行
    import time
    print("\n等待任务执行...")
    for i in range(30):
        task_state = task_submitter.get_task_state(result['task_id'])
        print(f"第 {i+1} 秒 - 任务状态: {task_state.value}")
        
        task_result = task_submitter.get_task_result(result['task_id'])
        if task_result and task_result.progress > 0:
            print(f"        进度: {task_result.progress}%")
        
        if task_state.value in ['SUCCESS', 'FAILURE']:
            break
        
        time.sleep(1)
    
    # 最终结果
    task_result = task_submitter.get_task_result(result['task_id'])
    print(f"\n最终任务结果: {task_result}")

if __name__ == "__main__":
    asyncio.run(test_process_trigger())
