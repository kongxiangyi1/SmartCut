"""
使用指定的腾讯混元 API Key 进行测试
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from core.llm_providers import ProviderType, LLMProviderFactory

def test_tencent_api_key(api_key: str):
    print(f"正在测试腾讯混元 API Key: {api_key[:10]}...")
    print("=" * 60)
    
    try:
        # 创建腾讯混元提供商实例
        provider = LLMProviderFactory.create_provider(
            ProviderType.TENCENT,
            api_key=api_key,
            model_name="hunyuan-turbos-latest"
        )
        
        print("✅ 提供商实例创建成功")
        
        # 测试连接
        print("正在测试 API 连接...")
        success = provider.test_connection()
        
        if success:
            print("✅ 腾讯混元 API 连接测试成功！")
            print("\n📝 测试响应内容：")
            
            # 调用API获取实际响应
            llm_response = provider.call("请用中文回复一个简单的测试消息")
            content = llm_response.content
            print(f"响应: {content[:100]}...")
            
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
    # 使用用户提供的 API Key
    api_key = "sk-S2XVtNSX55yXTXSGF8TdTkV8y0bCC2XakcM0iEUsmGy9c3EE"
    
    print("🚀 腾讯混元 API Key 测试")
    print("=" * 60)
    
    success = test_tencent_api_key(api_key)
    
    print("=" * 60)
    print("测试结果:", "✅ 成功" if success else "❌ 失败")
    
    sys.exit(0 if success else 1)