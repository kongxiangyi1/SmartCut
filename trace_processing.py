import requests
import json
import time

BASE_URL = "http://localhost:8000"

# 更新为正确的项目ID
project_id = "ab0dd81f-1d16-4bde-b60e-21295e58d7ed"

print("=" * 70)
print("🚀 启动项目处理流程跟踪")
print("=" * 70)

# 1. 检查服务是否正常运行
print("\n1. 检查后端服务状态...")
try:
    resp = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
    if resp.status_code == 200:
        print("✅ 后端服务健康检查通过")
    else:
        print(f"❌ 健康检查失败: {resp.status_code}")
        exit(1)
except Exception as e:
    print(f"❌ 无法连接后端服务: {e}")
    exit(1)

# 2. 获取项目详情
print("\n2. 获取项目详情...")
try:
    resp = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}", timeout=10)
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        project = resp.json()
        print(f"项目名称: {project.get('name')}")
        print(f"项目状态: {project.get('status')}")
        print(f"项目类型: {project.get('project_type')}")
        print(f"文件路径: {project.get('video_path')}")
        print(f"封面路径: {project.get('cover_path')}")
    else:
        print(f"响应: {resp.text}")
except Exception as e:
    print(f"错误: {e}")

# 3. 启动处理流程
print("\n3. 启动项目处理流程...")
try:
    resp = requests.post(f"{BASE_URL}/api/v1/projects/{project_id}/process", timeout=30)
    print(f"状态码: {resp.status_code}")
    if resp.status_code == 200:
        result = resp.json()
        print(f"✅ 处理流程启动成功!")
        print(f"任务ID: {result.get('task_id')}")
        task_id = result.get('task_id')
    else:
        print(f"❌ 启动失败: {resp.text}")
        exit(1)
except Exception as e:
    print(f"❌ 启动异常: {e}")
    exit(1)

# 4. 跟踪处理进度
print("\n4. 跟踪处理进度...")
print("-" * 70)
max_checks = 60
for i in range(max_checks):
    try:
        # 获取项目状态
        resp = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}", timeout=10)
        if resp.status_code == 200:
            project = resp.json()
            status = project.get('status')
            progress = project.get('progress', 0)
            
            # 获取任务状态
            resp_task = requests.get(f"{BASE_URL}/api/v1/tasks/{task_id}", timeout=10)
            task_info = {}
            if resp_task.status_code == 200:
                task_info = resp_task.json()
            
            current_step = task_info.get('current_step', 'N/A')
            task_status = task_info.get('status', 'N/A')
            task_progress = task_info.get('progress', 0)
            
            print(f"[{i+1:2d}] 项目状态: {status:10s} | 项目进度: {progress:3d}% | "
                  f"任务状态: {task_status:10s} | 任务进度: {task_progress:3d}% | "
                  f"当前步骤: {current_step}")
            
            if status in ['completed', 'failed']:
                print("\n🎉 处理流程结束!")
                break
        else:
            print(f"获取状态失败: {resp.status_code}")
        
    except Exception as e:
        print(f"检查进度时出错: {e}")
    
    time.sleep(5)

print("\n" + "=" * 70)
print("📊 最终状态报告")
print("=" * 70)

# 最终状态检查
try:
    resp = requests.get(f"{BASE_URL}/api/v1/projects/{project_id}", timeout=10)
    if resp.status_code == 200:
        project = resp.json()
        print(f"项目名称: {project.get('name')}")
        print(f"最终状态: {project.get('status')}")
        print(f"最终进度: {project.get('progress', 0)}%")
        
        # 获取生成的切片数
        resp_clips = requests.get(f"{BASE_URL}/api/v1/clips?project_id={project_id}", timeout=10)
        if resp_clips.status_code == 200:
            clips_data = resp_clips.json()
            print(f"生成切片数: {len(clips_data.get('items', []))}")
        
        # 获取生成的合集数
        resp_collections = requests.get(f"{BASE_URL}/api/v1/collections?project_id={project_id}", timeout=10)
        if resp_collections.status_code == 200:
            coll_data = resp_collections.json()
            print(f"生成合集数: {len(coll_data.get('items', []))}")
except Exception as e:
    print(f"获取最终状态失败: {e}")

print("\n" + "=" * 70)