"""
检查服务器使用的文件路径
"""
import requests
import json

# 发送一个测试请求，并检查服务器返回的额外信息
response = requests.post(
    "http://localhost:8000/api/v1/settings/test-api-key",
    json={
        "provider": "tencent",
        "api_key": "test-key",
        "model_name": "test-model"
    }
)

print(f"响应状态码: {response.status_code}")
print(f"响应内容: {response.text}")

# 检查可用模型，看看是否能获取更多信息
try:
    models_response = requests.get("http://localhost:8000/api/v1/settings/available-models")
    print(f"\n可用模型响应: {models_response.text[:500]}...")
except Exception as e:
    print(f"获取可用模型失败: {e}")