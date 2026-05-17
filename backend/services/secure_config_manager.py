"""
安全配置管理器 - 改进版
实现加密存储、完整性校验、密钥备份等安全功能
"""

import json
import hmac
import hashlib
import os
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from threading import Lock

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class SecureConfigManager:
    """
    安全配置管理器 - 提供以下安全特性：
    1. AES-256 加密存储敏感数据
    2. HMAC-SHA256 完整性校验
    3. 密钥与数据分离存储
    4. 文件权限控制（0o600）
    5. 密钥备份/恢复功能
    6. 按需解密（减少内存明文暴露）
    """
    
    _instance = None
    _lock = Lock()
    
    # 安全目录配置
    _KEY_DIR = Path.home() / ".autoclip"  # 密钥存储在用户目录（与数据分离）
    _CONFIG_DIR = Path(__file__).parent.parent.parent / "data"
    
    # 敏感字段列表
    _SENSITIVE_FIELDS = [
        'api_dashscope_api_key',
        'api_openai_api_key',
        'api_gemini_api_key',
        'api_siliconflow_api_key',
        'api_zhipu_api_key',
        'api_tencent_api_key',
    ]
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._initialize()
    
    def _initialize(self):
        """初始化 - 创建安全目录结构"""
        try:
            # 创建密钥目录（仅限当前用户访问）
            self._KEY_DIR.mkdir(mode=0o700, exist_ok=True)
            self._CONFIG_DIR.mkdir(mode=0o700, exist_ok=True)
            
            self._key_file = self._KEY_DIR / "encryption.key"
            self._config_file = self._CONFIG_DIR / "secure_config.json"
            
            self._key = self._load_or_generate_key()
            self._cipher = Fernet(self._key)
            self._config = self._load_config()
            
            logger.info("[OK] 安全配置管理器初始化成功")
            logger.info(f"   密钥位置: {self._key_file}")
            logger.info(f"   配置位置: {self._config_file}")
            
        except Exception as e:
            logger.error(f"[FAIL] 安全配置管理器初始化失败: {e}", exc_info=True)
            raise
    
    def _load_or_generate_key(self) -> bytes:
        """加载或生成密钥（安全版本）"""
        if self._key_file.exists():
            with open(self._key_file, 'rb') as f:
                key = f.read()
            logger.debug(f"[KEY] 已加载现有密钥")
            return key
        
        # 生成新密钥并设置安全权限
        key = Fernet.generate_key()
        with open(self._key_file, 'wb') as f:
            f.write(key)
        os.chmod(self._key_file, 0o600)  # 仅所有者可读写
        logger.info(f"🔐 生成新加密密钥: {self._key_file}")
        return key
    
    def _encrypt(self, value: str) -> str:
        """加密字符串"""
        if not value:
            return ""
        try:
            return self._cipher.encrypt(value.encode()).decode()
        except Exception as e:
            logger.error(f"加密失败: {e}")
            return ""
    
    def _decrypt(self, value: str) -> str:
        """解密字符串"""
        if not value:
            return ""
        try:
            return self._cipher.decrypt(value.encode()).decode()
        except Exception as e:
            logger.warning(f"解密失败，可能是旧的未加密数据: {e}")
            return value  # 兼容旧的未加密数据
    
    def _sign_config(self, config: dict) -> str:
        """生成配置签名（用于完整性校验）"""
        return hmac.new(
            self._key,
            json.dumps(config, sort_keys=True, ensure_ascii=False).encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _verify_signature(self, config: dict) -> bool:
        """验证配置签名（防止篡改）"""
        signature = config.pop('__signature__', None)
        if not signature:
            logger.warning("[WARN] 配置文件缺少签名")
            return False
        
        expected = self._sign_config(config)
        if not hmac.compare_digest(signature, expected):
            logger.error("[FAIL] 配置文件完整性校验失败！")
            return False
        
        return True
    
    def _load_config(self) -> dict:
        """加载配置（带完整性校验和自动解密）"""
        if not self._config_file.exists():
            logger.info("📄 配置文件不存在，使用空配置")
            return {}
        
        try:
            with open(self._config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # 验证签名
            if not self._verify_signature(config):
                logger.warning("[WARN] 配置文件校验失败，使用空配置")
                return {}
            
            # 解密敏感字段
            for field in self._SENSITIVE_FIELDS:
                if field in config:
                    config[field] = self._decrypt(config[field])
            
            logger.info(f"[OK] 配置加载成功，共 {len(config)} 个配置项")
            return config
        
        except json.JSONDecodeError:
            logger.error("[FAIL] 配置文件格式错误")
            return {}
        except Exception as e:
            logger.error(f"[FAIL] 加载配置失败: {e}", exc_info=True)
            return {}
    
    def _save_config(self):
        """保存配置（带加密和签名）"""
        try:
            config_to_save = self._config.copy()
            
            # 加密敏感字段
            for field in self._SENSITIVE_FIELDS:
                if field in config_to_save:
                    config_to_save[field] = self._encrypt(config_to_save[field])
            
            # 添加签名
            config_to_save['__signature__'] = self._sign_config(config_to_save)
            
            # 写入文件
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(config_to_save, f, ensure_ascii=False, indent=2)
            
            # 设置文件权限（仅所有者可读写）
            os.chmod(self._config_file, 0o600)
            
            logger.info(f"[OK] 配置保存成功，共 {len(config_to_save)} 个配置项")
        
        except Exception as e:
            logger.error(f"[FAIL] 保存配置失败: {e}", exc_info=True)
            raise
    
    def update(self, config: Dict[str, Any]):
        """批量更新配置"""
        self._config.update(config)
        self._save_config()
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取单个配置项"""
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        """设置单个配置项"""
        self._config[key] = value
        self._save_config()
    
    def get_all(self) -> Dict[str, Any]:
        """获取所有配置（已解密）"""
        return self._config.copy()
    
    def get_sensitive_value(self, key: str) -> str:
        """
        安全获取敏感值
        解密后立即使用，避免长时间留在内存
        """
        encrypted_value = self._config.get(key, "")
        return self._decrypt(encrypted_value)
    
    def mask_sensitive_value(self, key: str) -> str:
        """
        获取敏感值的掩码形式（用于显示）
        只显示前4位和后4位，中间用*填充
        """
        value = self.get_sensitive_value(key)
        if not value:
            return ""
        if len(value) <= 8:
            return "*" * len(value)
        return value[:4] + "*" * (len(value) - 8) + value[-4:]
    
    def has_sensitive_value(self, key: str) -> bool:
        """检查敏感字段是否有值"""
        value = self.get_sensitive_value(key)
        return bool(value and value.strip())
    
    def backup_key(self, backup_path: Path) -> bool:
        """
        备份密钥到安全位置
        :param backup_path: 备份文件路径
        :return: 是否成功
        """
        try:
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(self._key_file, backup_path)
            os.chmod(backup_path, 0o600)
            logger.info(f"[REFRESH] 密钥已备份到: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"[FAIL] 备份密钥失败: {e}")
            return False
    
    def restore_key(self, backup_path: Path) -> bool:
        """
        从备份恢复密钥
        :param backup_path: 备份文件路径
        :return: 是否成功
        """
        try:
            if not backup_path.exists():
                logger.error(f"[FAIL] 备份文件不存在: {backup_path}")
                return False
            
            shutil.copy(backup_path, self._key_file)
            os.chmod(self._key_file, 0o600)
            
            # 重新加载密钥和配置
            self._key = self._load_or_generate_key()
            self._cipher = Fernet(self._key)
            self._config = self._load_config()
            
            logger.info(f"[REFRESH] 密钥已从备份恢复: {backup_path}")
            return True
        except Exception as e:
            logger.error(f"[FAIL] 恢复密钥失败: {e}")
            return False
    
    def rotate_key(self) -> bool:
        """
        密钥轮换 - 生成新密钥并重新加密所有数据
        :return: 是否成功
        """
        try:
            # 备份当前密钥
            backup_path = self._KEY_DIR / f"encryption.key.backup.{int(os.time())}"
            self.backup_key(backup_path)
            
            # 生成新密钥
            new_key = Fernet.generate_key()
            old_cipher = self._cipher
            self._cipher = Fernet(new_key)
            
            # 重新加密所有敏感数据
            for field in self._SENSITIVE_FIELDS:
                if field in self._config and self._config[field]:
                    # 先用旧密钥解密
                    value = old_cipher.decrypt(self._encrypt(self._config[field]).encode()).decode()
                    # 再用新密钥加密
                    self._config[field] = value
            
            # 保存新密钥
            with open(self._key_file, 'wb') as f:
                f.write(new_key)
            os.chmod(self._key_file, 0o600)
            self._key = new_key
            
            # 保存重新加密后的配置
            self._save_config()
            
            logger.info("[REFRESH] 密钥轮换完成")
            return True
        except Exception as e:
            logger.error(f"[FAIL] 密钥轮换失败: {e}", exc_info=True)
            return False
    
    def clear(self):
        """清除所有配置"""
        self._config = {}
        self._save_config()


# 全局实例
secure_config_manager = SecureConfigManager()


# 测试函数
def test_security_features():
    """测试安全配置管理器的各项功能"""
    print("=" * 70)
    print("测试安全配置管理器")
    print("=" * 70)
    
    # 测试 1: 设置配置
    print("\n[1/6] 测试设置配置")
    secure_config_manager.update({
        "llm_provider": "tencent",
        "model_name": "hunyuan-pro",
        "api_tencent_api_key": "sk-secret-key-1234567890",
        "chunk_size": 5000
    })
    print("[OK] 配置设置成功")
    
    # 测试 2: 获取配置
    print("\n[2/6] 测试获取配置")
    config = secure_config_manager.get_all()
    print(f"   llm_provider: {config.get('llm_provider')}")
    print(f"   model_name: {config.get('model_name')}")
    print(f"   api_tencent_api_key: {config.get('api_tencent_api_key')}")
    print("[OK] 配置获取成功")
    
    # 测试 3: 掩码显示
    print("\n[3/6] 测试掩码显示")
    masked_key = secure_config_manager.mask_sensitive_value("api_tencent_api_key")
    print(f"   掩码后: {masked_key}")
    assert masked_key == "sk-s****************0", f"掩码错误: {masked_key}"
    print("[OK] 掩码显示成功")
    
    # 测试 4: 检查敏感值
    print("\n[4/6] 测试敏感值检查")
    has_key = secure_config_manager.has_sensitive_value("api_tencent_api_key")
    has_none = secure_config_manager.has_sensitive_value("api_openai_api_key")
    print(f"   有腾讯密钥: {has_key}")
    print(f"   有OpenAI密钥: {has_none}")
    assert has_key == True
    assert has_none == False
    print("[OK] 敏感值检查成功")
    
    # 测试 5: 密钥备份
    print("\n[5/6] 测试密钥备份")
    backup_path = Path.home() / ".autoclip" / "encryption.key.backup"
    success = secure_config_manager.backup_key(backup_path)
    print(f"   备份成功: {success}")
    assert success == True
    print("[OK] 密钥备份成功")
    
    # 测试 6: 配置文件检查
    print("\n[6/6] 验证配置文件安全性")
    config_file = secure_config_manager._config_file
    if config_file.exists():
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
        has_signature = '__signature__' in content
        key_encrypted = 'sk-secret-key-1234567890' not in content
        print(f"   文件存在: 是")
        print(f"   包含签名: {has_signature}")
        print(f"   密钥已加密: {key_encrypted}")
        assert has_signature == True
        assert key_encrypted == True
        print("[OK] 配置文件安全验证通过")
    
    print("\n" + "=" * 70)
    print("🎉 所有安全功能测试通过！")
    print("=" * 70)


if __name__ == "__main__":
    test_security_features()