"""
测试腾讯混元 API 连接（模拟前端调用）
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from core.llm_manager import get_llm_manager
from core.llm_providers import ProviderType

def test_tencent_connection():
    print("正在测试腾讯混元 API 连接...")
    
    # 从配置文件读取 API key
    from pathlib import Path
    import json
    
    settings_file = Path("data/settings.json")
    if not settings_file.exists():
        print("❌ 配置文件不存在")
        return False
        
    with open(settings_file, 'r', encoding='utf-8') as f:
        settings = json.load(f)
    
    api_key = settings.get('tencent_api_key', '')
    model_name = settings.get('model_name', 'hunyuan-turbos-latest')
    
    if not api_key:
        print("❌ API Key 未配置")
        return False
        
    print(f"使用 API Key: {api_key[:10]}...")
    print(f"使用模型：{model_name}")
    
    try:
        llm_manager = get_llm_manager()
        
        # 模拟前端调用，传入 secret_key=None
        print("正在调用 test_provider_connection...")
        success = llm_manager.test_provider_connection(
            ProviderType.TENCENT,
            api_key,
            model_name,
            secret_key=None  # 模拟前端传入的 secret_key
        )
        
        if success:
            print("✅ 腾讯混元 API 连接测试成功！")
            return True
        else:
            print("❌ 腾讯混元 API 连接测试失败")
            return False
            
    except Exception as e:
        print(f"❌ 测试过程中出现异常：{str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_tencent_connection()
    sys.exit(0 if success else 1)