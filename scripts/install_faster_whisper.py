#!/usr/bin/env python3
"""
faster-whisper 快速安装与测试脚本
帮助用户快速体验 faster-whisper 在 autoclip 中的集成
"""

import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def run_command(cmd, description=""):
    """运行命令并返回结果"""
    if description:
        logger.info(f"▶️  {description}...")
    logger.debug(f"执行命令: {cmd}")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        if result.returncode != 0:
            logger.warning(f"命令执行有警告:\n{result.stderr}")
        return result.returncode == 0
    except Exception as e:
        logger.error(f"命令执行失败: {e}")
        return False

def check_python_version():
    """检查 Python 版本"""
    logger.info("=" * 60)
    logger.info("检查环境...")
    logger.info("=" * 60)
    
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    logger.info(f"✅ Python 版本: {py_version}")
    
    if sys.version_info < (3, 8):
        logger.error("❌ Python 版本过低，需要 3.8+")
        return False
    return True

def check_ffmpeg():
    """检查 ffmpeg 是否安装"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            logger.info(f"✅ FFmpeg 已安装: {version_line}")
            return True
    except Exception:
        pass
    
    logger.warning("⚠️  FFmpeg 未安装，这是必需的！")
    logger.info("   安装方式:")
    logger.info("   - Windows: winget install ffmpeg")
    logger.info("   - macOS: brew install ffmpeg")
    logger.info("   - Ubuntu: sudo apt install ffmpeg")
    return False

def install_faster_whisper():
    """安装 faster-whisper"""
    logger.info("=" * 60)
    logger.info("安装 faster-whisper...")
    logger.info("=" * 60)
    
    packages = [
        "faster-whisper",
        "torch torchaudio --index-url https://download.pytorch.org/whl/cpu"
    ]
    
    for pkg in packages:
        logger.info(f"📦 安装: {pkg}")
        if not run_command(f"pip install {pkg}", f"安装 {pkg}"):
            logger.warning(f"⚠️  安装 {pkg} 可能失败，请检查")
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("验证安装...")
    logger.info("=" * 60)
    
    try:
        import faster_whisper
        logger.info(f"✅ faster-whisper 安装成功 (版本: {faster_whisper.__version__})")
        return True
    except ImportError:
        logger.error("❌ faster-whisper 导入失败！")
        return False

def test_integration():
    """测试与 autoclip 的集成"""
    logger.info("=" * 60)
    logger.info("测试 autoclip 集成...")
    logger.info("=" * 60)
    
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from backend.utils.speech_recognizer import SpeechRecognizer
        
        logger.info("✅ autoclip 模块导入成功")
        
        # 测试初始化
        recognizer = SpeechRecognizer()
        available = recognizer.get_available_methods()
        
        logger.info(f"📊 可用方法: {available}")
        
        if available.get('whisper_faster'):
            logger.info("✅ faster-whisper 已准备就绪！")
        else:
            logger.warning("⚠️  faster-whisper 在系统中检测失败")
        
        return True
    except Exception as e:
        logger.error(f"❌ 集成测试失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False

def main():
    """主函数"""
    print("🚀 faster-whisper 安装向导")
    print("=" * 60)
    
    checks = [
        check_python_version(),
        check_ffmpeg(),
        install_faster_whisper(),
        test_integration(),
    ]
    
    all_passed = all(checks)
    
    logger.info("=" * 60)
    
    if all_passed:
        logger.info("🎉 安装成功！")
        logger.info("")
        logger.info("📖 使用方法:")
        logger.info("   # 在代码中直接调用")
        logger.info("   from backend.utils.speech_recognizer import generate_subtitle_for_video")
        logger.info("   result = generate_subtitle_for_video('video.mp4', method='whisper_faster')")
        logger.info("")
        logger.info("   # 或使用 auto 模式（会自动选择最佳方案）")
        logger.info("   result = generate_subtitle_for_video('video.mp4', method='auto')")
    else:
        logger.warning("⚠️  安装过程有警告，请检查上方日志")
    
    logger.info("=" * 60)
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
