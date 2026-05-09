"""
测试后端 API /settings/test-api-key 接口
"""
import requests
import json

print("🚀 测试 API Key 接口")
print("=" * 60)
print("正在测试 /settings/test-api-key 接口...")

url = "http://localhost:8080/api/v1/settings/test-api-key"
data = {
    "provider": "tencent",
    "api_key": "sk-S2XVtNSX55yXTXSGF8TdTkV8y0bCC2XakcM0iEUsmGy9c3EE",
    "model_name": "hunyuan-turbos-latest"
}

print(f"发送请求到: {url}")
print(f"请求数据: {data}")

try:
    response = requests.post(url, json=data)
    print(f"响应状态码: {response.status_code}")
    print(f"响应内容: {response.text}")
    
    if response.status_code == 200:
        result = response.json()
        if result.get("success"):
            print("✅ API 接口测试成功！")
        else:
            print(f"❌ API 接口测试失败: {result.get('error')}")
    else:
        print(f"❌ 请求失败，状态码: {response.status_code}")
        
except Exception as e:
    print(f"❌ 请求异常: {e}")

print("=" * 60)
print("测试结果:", "✅ 成功" if response.status_code == 200 and response.json().get("success") else "❌ 失败")