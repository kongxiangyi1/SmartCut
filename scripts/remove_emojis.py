"""
移除代码中的 emoji 字符（用于修复 Windows GBK 编码问题）
"""

import re
from pathlib import Path

# Emoji 替换映射
EMOJI_MAP = {
    '✅': '[OK]',
    '❌': '[FAIL]',
    '⚠️': '[WARN]',
    '🔧': '[TOOL]',
    '📁': '[DIR]',
    '📊': '[STAT]',
    '🎬': '[VIDEO]',
    '🤖': '[AI]',
    '✂️': '[CUT]',
    '📚': '[DOC]',
    '🚀': '[RUN]',
    '🎨': '[STYLE]',
    '🎥': '[CAM]',
    '💡': '[IDEA]',
    '🔍': '[SEARCH]',
    '✨': '[SPARKLE]',
    '💾': '[SAVE]',
    '🎯': '[TARGET]',
    '📝': '[NOTE]',
    '🎙️': '[MIC]',
    '🔊': '[SOUND]',
    '📈': '[CHART]',
    '🎵': '[MUSIC]',
    '👁️': '[EYE]',
    '⚡': '[LIGHTNING]',
    '🔑': '[KEY]',
    '💻': '[COMPUTER]',
    '🌐': '[WEB]',
    '📱': '[PHONE]',
    '🔔': '[BELL]',
    '📋': '[LIST]',
    '⏰': '[CLOCK]',
    '🔄': '[REFRESH]',
    '📌': '[PIN]',
    '🔒': '[LOCK]',
    '📤': '[UPLOAD]',
    '📥': '[DOWNLOAD]',
    '🔎': '[LOOKUP]',
    '✅️': '[OK]',  # 带变体选择符
}


def remove_emojis_in_file(file_path: Path):
    """移除文件中的 emoji 字符"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换所有 emoji
        new_content = content
        for emoji, replacement in EMOJI_MAP.items():
            new_content = new_content.replace(emoji, replacement)
        
        # 如果内容有变化，写回文件
        if new_content != content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"已更新: {file_path}")
            return True
        return False
    except Exception as e:
        print(f"处理失败 {file_path}: {e}")
        return False


def main():
    """主函数"""
    backend_dir = Path(__file__).parent.parent / "backend"
    
    # 需要处理的文件
    files_to_process = [
        backend_dir / "services" / "secure_config_manager.py",
        backend_dir / "services" / "user_config_manager.py",
        backend_dir / "services" / "enhanced_progress_service.py",
        backend_dir / "pipeline" / "concrete_strategies.py",
        backend_dir / "utils" / "local_scorer.py",
        backend_dir / "models" / "enums.py",
        backend_dir / "core" / "shared_config.py",
        backend_dir / "main.py",
        backend_dir / "utils" / "speech_recognizer.py",
        backend_dir / "utils" / "vad_preprocessor.py",
        backend_dir / "api" / "v1" / "youtube_improved.py",
    ]
    
    # 处理所有文件
    updated_count = 0
    for file_path in files_to_process:
        if file_path.exists():
            if remove_emojis_in_file(file_path):
                updated_count += 1
        else:
            print(f"文件不存在: {file_path}")
    
    print(f"\n完成! 已更新 {updated_count} 个文件。")


if __name__ == "__main__":
    main()
