"""
测试后端API是否能正常访问视频文件
"""
import requests
import sys

# 测试项目ID（刚上传的那个）
project_id = "6be285fa-31e4-4487-898a-c26b38753af1"
api_base = "http://localhost:8090/api/v1"

def test_file_access():
    print("Testing file access API...")
    
    # 先测试获取项目列表
    try:
        print(f"\n1. Testing projects list API: {api_base}/projects/")
        response = requests.get(f"{api_base}/projects/", timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            projects = response.json()
            print(f"   Number of projects: {len(projects.get('items', projects))}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # 测试访问项目文件
    try:
        print(f"\n2. Testing raw file access (input.mp4):")
        url = f"{api_base}/projects/{project_id}/files/input.mp4"
        print(f"   URL: {url}")
        
        response = requests.get(url, timeout=30, stream=True)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   Success! File found and accessible")
            print(f"   Content-Type: {response.headers.get('content-type')}")
            print(f"   Content-Length: {response.headers.get('content-length')}")
        elif response.status_code == 404:
            print(f"   404 Not Found - File not found")
            
    except Exception as e:
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
    
    # 先获取项目的所有切片，看看实际的ID是什么
    try:
        print(f"\n3. Getting clips for project:")
        clips_url = f"{api_base}/clips/?project_id={project_id}"
        response = requests.get(clips_url, timeout=10)
        print(f"   Clips API Status: {response.status_code}")
        
        if response.status_code == 200:
            clips = response.json().get('items', response.json())
            print(f"   Found {len(clips)} clips")
            
            if len(clips) > 0:
                for i, clip in enumerate(clips):
                    clip_id = clip.get('id')
                    clip_title = clip.get('title')
                    clip_duration = clip.get('duration')
                    
                    print(f"\n   Clip {i+1}: ID={clip_id}, Title={clip_title}, Duration={clip_duration}s")
                    
                    # 测试访问每个切片
                    print(f"   Testing clip {i+1} video access...")
                    url = f"{api_base}/projects/{project_id}/clips/{clip_id}"
                    
                    response = requests.get(url, timeout=30, stream=True)
                    print(f"   Status: {response.status_code}")
                    
                    if response.status_code == 200:
                        print(f"   Success! Clip found and accessible")
                        print(f"   Content-Type: {response.headers.get('content-type')}")
                        print(f"   Content-Length: {response.headers.get('content-length')}")
                    elif response.status_code == 404:
                        print(f"   404 Not Found - Clip not found")
            
    except Exception as e:
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_file_access()
