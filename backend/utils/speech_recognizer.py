"""
语音识别工具 - 支持多种语音识别服务
支持本地Whisper、OpenAI API、Azure Speech Services等多种语音识别服务
"""
import logging
import subprocess
import json
import os
import asyncio
import shutil
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from enum import Enum
import requests
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# FunASR模型缓存（按设备类型缓存）
_FUNASR_MODEL_CACHE = {}

def _detect_compute_device() -> str:
    """
    自动检测可用的计算设备
    
    优先级:
    1. 环境变量 SPEECH_DEVICE
    2. CUDA (NVIDIA GPU)
    3. MPS (Apple Silicon GPU)
    4. CPU
    
    Returns:
        设备类型字符串: "cuda", "mps", 或 "cpu"
    """
    # 检查环境变量手动指定
    env_device = os.environ.get("SPEECH_DEVICE", "").lower()
    if env_device in ["cuda", "mps", "cpu"]:
        logger.info(f"使用环境变量指定的设备: {env_device}")
        return env_device
    
    # 检查CUDA
    try:
        import torch
        if torch.cuda.is_available():
            logger.info("检测到CUDA设备，使用GPU加速")
            return "cuda"
        elif torch.backends.mps.is_available():
            logger.info("检测到MPS设备，使用Apple Silicon GPU")
            return "mps"
    except ImportError:
        logger.debug("PyTorch未安装，无法检测GPU")
    
    logger.info("未检测到可用GPU，使用CPU")
    return "cpu"

# 尝试导入bcut-asr
try:
    from bcut_asr import BcutASR
    from bcut_asr.orm import ResultStateEnum
    BCUT_ASR_AVAILABLE = True
except ImportError:
    BCUT_ASR_AVAILABLE = False
    logger.warning("bcut-asr未安装，将跳过bcut-asr方法")

def _auto_install_bcut_asr():
    """自动安装bcut-asr"""
    try:
        import subprocess
        import sys
        from pathlib import Path
        
        # 获取安装脚本路径
        script_path = Path(__file__).parent.parent.parent / "scripts" / "install_bcut_asr.py"
        
        if not script_path.exists():
            logger.error("安装脚本不存在，请手动安装bcut-asr")
            _show_manual_install_guide()
            return False
        
        logger.info("开始自动安装bcut-asr...")
        
        # 运行安装脚本
        result = subprocess.run([
            sys.executable, str(script_path)
        ], capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=600)  # 10分钟超时
        
        if result.returncode == 0:
            logger.info("[OK] bcut-asr自动安装成功")
            return True
        else:
            logger.error(f"[FAIL] bcut-asr自动安装失败: {result.stderr}")
            _show_manual_install_guide()
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("[FAIL] bcut-asr安装超时")
        _show_manual_install_guide()
        return False
    except Exception as e:
        logger.error(f"[FAIL] bcut-asr自动安装失败: {e}")
        _show_manual_install_guide()
        return False

def _show_manual_install_guide():
    """显示手动安装指导"""
    logger.info("[LIST] 手动安装指导:")
    logger.info("1. 安装 ffmpeg:")
    logger.info("   macOS: brew install ffmpeg")
    logger.info("   Ubuntu: sudo apt install ffmpeg")
    logger.info("   Windows: winget install ffmpeg")
    logger.info("2. 安装 bcut-asr:")
    logger.info("   git clone https://github.com/SocialSisterYi/bcut-asr.git")
    logger.info("   cd bcut-asr && pip install .")
    logger.info("3. 运行手动安装脚本:")
    logger.info("   python scripts/manual_install_guide.py")

def _ensure_bcut_asr_available():
    """确保bcut-asr可用，如果不可用则尝试自动安装"""
    global BCUT_ASR_AVAILABLE
    
    if BCUT_ASR_AVAILABLE:
        return True
    
    logger.info("bcut-asr不可用，尝试自动安装...")
    
    if _auto_install_bcut_asr():
        # 重新尝试导入
        try:
            from bcut_asr import BcutASR
            from bcut_asr.orm import ResultStateEnum
            BCUT_ASR_AVAILABLE = True
            logger.info("[OK] bcut-asr安装成功，现在可以使用")
            return True
        except ImportError:
            logger.error("[FAIL] bcut-asr安装后仍无法导入")
            return False
    else:
        logger.warning("[WARN] bcut-asr自动安装失败，将使用其他方法")
        return False


class SpeechRecognitionMethod(str, Enum):
    """语音识别方法枚举"""
    BCUT_ASR = "bcut_asr"
    WHISPER_LOCAL = "whisper_local"
    FUNASR = "funasr"
    OPENAI_API = "openai_api"
    AZURE_SPEECH = "azure_speech"
    GOOGLE_SPEECH = "google_speech"
    ALIYUN_SPEECH = "aliyun_speech"


class LanguageCode(str, Enum):
    """支持的语言代码"""
    # 中文
    CHINESE_SIMPLIFIED = "zh"
    CHINESE_TRADITIONAL = "zh-TW"
    # 英文
    ENGLISH = "en"
    ENGLISH_US = "en-US"
    ENGLISH_UK = "en-GB"
    # 日文
    JAPANESE = "ja"
    # 韩文
    KOREAN = "ko"
    # 法文
    FRENCH = "fr"
    # 德文
    GERMAN = "de"
    # 西班牙文
    SPANISH = "es"
    # 俄文
    RUSSIAN = "ru"
    # 阿拉伯文
    ARABIC = "ar"
    # 葡萄牙文
    PORTUGUESE = "pt"
    # 意大利文
    ITALIAN = "it"
    # 自动检测
    AUTO = "auto"


@dataclass
class SpeechRecognitionConfig:
    """语音识别配置"""
    method: SpeechRecognitionMethod = SpeechRecognitionMethod.FUNASR
    language: LanguageCode = LanguageCode.AUTO
    model: str = "base"  # Whisper模型大小
    timeout: int = 0  # 超时时间（秒），0表示无限制
    output_format: str = "srt"  # 输出格式
    enable_timestamps: bool = True  # 是否启用时间戳
    enable_punctuation: bool = True  # 是否启用标点符号
    enable_speaker_diarization: bool = False  # 是否启用说话人分离
    enable_fallback: bool = True  # 是否启用回退机制
    fallback_method: SpeechRecognitionMethod = SpeechRecognitionMethod.WHISPER_LOCAL  # 回退方法
    hotwords: str = ""  # 热词列表（空格分隔），帮助ASR准确识别特定词汇
    
    def __post_init__(self):
        """验证配置参数"""
        # 验证方法
        if not isinstance(self.method, SpeechRecognitionMethod):
            try:
                self.method = SpeechRecognitionMethod(self.method)
            except ValueError:
                raise ValueError(f"不支持的语音识别方法: {self.method}")

        # 验证语言
        if not isinstance(self.language, LanguageCode):
            try:
                self.language = LanguageCode(self.language)
            except ValueError:
                raise ValueError(f"不支持的语言代码: {self.language}")

        # 自动调整模型（当 model 为默认值 "base" 时，根据方法选择正确的默认模型）
        if self.model == "base":
            if self.method == SpeechRecognitionMethod.FUNASR:
                self.model = "iic/SenseVoiceSmall"
            elif self.method == SpeechRecognitionMethod.WHISPER_LOCAL:
                self.model = "small"
            # 其他方法使用默认的 "base"（bcut-asr 等不需要 model 参数）

        # 验证模型（根据不同方法使用不同的验证规则）
        if self.method == SpeechRecognitionMethod.WHISPER_LOCAL:
            valid_models = ["tiny", "base", "small", "medium", "large"]
            if self.model not in valid_models:
                raise ValueError(f"不支持的Whisper模型: {self.model}")
        elif self.method == SpeechRecognitionMethod.FUNASR:
            valid_models = ["iic/SenseVoiceSmall", "paraformer-zh", "paraformer-en", "paraformer-zh-16k", "euro", "fa", "ms", "asr", "ct-punc", "fsmn-vad"]
            if self.model not in valid_models:
                raise ValueError(f"不支持的FunASR模型: {self.model}")
        # bcut-asr 和其他云服务不需要验证 model 参数
        
        # 验证超时时间
        if self.timeout < 0:
            raise ValueError("超时时间不能为负数")
        
        # 验证输出格式
        valid_formats = ["srt", "vtt", "txt", "json"]
        if self.output_format not in valid_formats:
            raise ValueError(f"不支持的输出格式: {self.output_format}")


class SpeechRecognitionError(Exception):
    """语音识别错误"""
    pass


class SpeechRecognizer:
    """语音识别器，支持多种语音识别服务"""
    
    def __init__(self, config: Optional[SpeechRecognitionConfig] = None):
        self.config = config or SpeechRecognitionConfig()
        self.available_methods = self._check_available_methods()
    
    def _check_available_methods(self) -> Dict[SpeechRecognitionMethod, bool]:
        """检查可用的语音识别方法（按优先级顺序检查）"""
        methods = {}
        
        # 检查FunASR（优先级最高，完全离线，中文识别准确率高）
        methods[SpeechRecognitionMethod.FUNASR] = self._check_funasr_availability()
        
        # 检查bcut-asr（优先级次之，云服务但准确率高）
        methods[SpeechRecognitionMethod.BCUT_ASR] = self._check_bcut_asr_availability()
        
        # 检查本地Whisper（优先级较低，需要安装较大模型）
        methods[SpeechRecognitionMethod.WHISPER_LOCAL] = self._check_whisper_availability()
        
        # 检查OpenAI API
        methods[SpeechRecognitionMethod.OPENAI_API] = self._check_openai_availability()
        
        # 检查Azure Speech Services
        methods[SpeechRecognitionMethod.AZURE_SPEECH] = self._check_azure_speech_availability()
        
        # 检查Google Speech-to-Text
        methods[SpeechRecognitionMethod.GOOGLE_SPEECH] = self._check_google_speech_availability()
        
        # 检查阿里云语音识别
        methods[SpeechRecognitionMethod.ALIYUN_SPEECH] = self._check_aliyun_speech_availability()
        
        # 输出优先级摘要
        available = [m.value for m, v in methods.items() if v]
        if available:
            logger.info(f"可用语音识别方法（按优先级）: {', '.join(available)}")
        else:
            logger.warning("没有可用的语音识别方法，请安装 FunASR、Whisper 或配置 API 密钥")
        
        return methods
    
    def _check_bcut_asr_availability(self) -> bool:
        """检查bcut-asr是否可用，如果不可用则尝试自动安装"""
        if BCUT_ASR_AVAILABLE:
            return True
        
        # 尝试自动安装
        logger.info("bcut-asr不可用，尝试自动安装...")
        if _ensure_bcut_asr_available():
            return True
        
        logger.warning("bcut-asr不可用且自动安装失败")
        return False
    
    def _check_whisper_availability(self) -> bool:
        """检查本地Whisper是否可用"""
        try:
            # 优先尝试导入whisper库
            import whisper
            logger.info("[OK] 本地Whisper已安装")
            return True
        except ImportError:
            try:
                # 如果导入失败，再尝试命令行
                result = subprocess.run(['whisper', '--help'], 
                                      capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=5)
                if result.returncode == 0:
                    logger.info("[OK] Whisper命令行工具可用")
                    return True
                return False
            except (subprocess.TimeoutExpired, FileNotFoundError):
                # Whisper 不可用，但这是正常的，不算严重问题
                logger.debug("本地Whisper未安装（可选）")
                return False
    
    def _check_funasr_availability(self) -> bool:
        """检查FunASR是否可用"""
        try:
            from funasr import AutoModel
            logger.info("[OK] FunASR已安装，可用")
            return True
        except ImportError:
            logger.warning("FunASR未安装或不可用")
            return False
    
    def _check_openai_availability(self) -> bool:
        """检查OpenAI API是否可用"""
        api_key = os.getenv("OPENAI_API_KEY")
        return api_key is not None and len(api_key.strip()) > 0
    
    def _check_azure_speech_availability(self) -> bool:
        """检查Azure Speech Services是否可用"""
        api_key = os.getenv("AZURE_SPEECH_KEY")
        region = os.getenv("AZURE_SPEECH_REGION")
        return api_key is not None and region is not None
    
    def _check_google_speech_availability(self) -> bool:
        """检查Google Speech-to-Text是否可用"""
        # 检查Google Cloud凭证文件
        cred_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_file and Path(cred_file).exists():
            return True
        
        # 检查API密钥
        api_key = os.getenv("GOOGLE_SPEECH_API_KEY")
        return api_key is not None
    
    def _check_aliyun_speech_availability(self) -> bool:
        """检查阿里云语音识别是否可用"""
        access_key = os.getenv("ALIYUN_ACCESS_KEY_ID")
        secret_key = os.getenv("ALIYUN_ACCESS_KEY_SECRET")
        app_key = os.getenv("ALIYUN_SPEECH_APP_KEY")
        return access_key is not None and secret_key is not None and app_key is not None
    
    def _extract_audio_from_video(self, video_path: Path, output_dir: Path) -> Path:
        """
        从视频文件中提取音频
        
        Args:
            video_path: 视频文件路径
            output_dir: 输出目录
            
        Returns:
            提取的音频文件路径
        """
        try:
            # 检查ffmpeg是否可用 - 使用shutil.which查找完整路径避免PATH问题
            ffmpeg_path = shutil.which('ffmpeg')
            if not ffmpeg_path:
                raise SpeechRecognitionError("ffmpeg不可用，请安装ffmpeg")
            
            # 生成音频文件路径
            audio_filename = f"{video_path.stem}_audio.wav"
            audio_path = output_dir / audio_filename
            
            # 如果音频文件已存在，直接返回
            if audio_path.exists():
                logger.info(f"音频文件已存在: {audio_path}")
                return audio_path
            
            logger.info(f"正在从视频提取音频: {video_path} -> {audio_path}")
            
            # 使用ffmpeg提取音频（使用完整路径避免PATH问题）
            cmd = [
                ffmpeg_path,
                '-i', str(video_path),
                '-vn',  # 不处理视频流
                '-acodec', 'pcm_s16le',  # 使用PCM 16位编码
                '-ar', '16000',  # 采样率16kHz
                '-ac', '1',  # 单声道
                '-af', 'afftdn=nf=-25,volume=2.0',  # 降噪+自动增益
                '-y',  # 覆盖输出文件
                str(audio_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=300)
            
            if result.returncode != 0:
                raise SpeechRecognitionError(f"音频提取失败: {result.stderr}")
            
            if not audio_path.exists():
                raise SpeechRecognitionError("音频提取失败，输出文件不存在")
            
            logger.info(f"音频提取成功: {audio_path}")
            return audio_path
            
        except subprocess.TimeoutExpired:
            raise SpeechRecognitionError("音频提取超时")
        except Exception as e:
            raise SpeechRecognitionError(f"音频提取失败: {e}")
    
    def generate_subtitle(self, video_path: Path, output_path: Optional[Path] = None, 
                         config: Optional[SpeechRecognitionConfig] = None) -> Path:
        """
        生成字幕文件
        
        Args:
            video_path: 视频文件路径
            output_path: 输出字幕文件路径
            config: 语音识别配置
            
        Returns:
            生成的字幕文件路径
            
        Raises:
            SpeechRecognitionError: 语音识别失败
        """
        if not video_path.exists():
            raise SpeechRecognitionError(f"视频文件不存在: {video_path}")
        
        # 使用传入的配置或默认配置
        config = config or self.config
        
        # 确定输出路径
        if output_path is None:
            output_path = video_path.parent / f"{video_path.stem}.{config.output_format}"
        
        # 根据配置的方法选择识别服务，支持回退机制
        try:
            if config.method == SpeechRecognitionMethod.BCUT_ASR:
                return self._generate_subtitle_bcut_asr(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.WHISPER_LOCAL:
                return self._generate_subtitle_whisper_local(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.FUNASR:
                return self._generate_subtitle_funasr(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.OPENAI_API:
                return self._generate_subtitle_openai_api(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.AZURE_SPEECH:
                return self._generate_subtitle_azure_speech(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.GOOGLE_SPEECH:
                return self._generate_subtitle_google_speech(video_path, output_path, config)
            elif config.method == SpeechRecognitionMethod.ALIYUN_SPEECH:
                return self._generate_subtitle_aliyun_speech(video_path, output_path, config)
            else:
                raise SpeechRecognitionError(f"不支持的语音识别方法: {config.method}")
        except SpeechRecognitionError as e:
            # 如果启用了回退机制且当前方法不是回退方法，则尝试回退
            if (config.enable_fallback and 
                config.method != config.fallback_method and 
                self.available_methods.get(config.fallback_method, False)):
                
                logger.warning(f"主方法 {config.method} 失败: {e}")
                logger.info(f"尝试回退到 {config.fallback_method}")
                
                # 创建回退配置
                fallback_config = SpeechRecognitionConfig(
                    method=config.fallback_method,
                    language=config.language,
                    model=config.model,
                    timeout=config.timeout,
                    output_format=config.output_format,
                    enable_timestamps=config.enable_timestamps,
                    enable_punctuation=config.enable_punctuation,
                    enable_speaker_diarization=config.enable_speaker_diarization,
                    enable_fallback=False  # 避免无限回退
                )
                
                return self.generate_subtitle(video_path, output_path, fallback_config)
            else:
                raise
    
    def _generate_subtitle_bcut_asr(self, video_path: Path, output_path: Path, 
                                   config: SpeechRecognitionConfig) -> Path:
        """使用bcut-asr生成字幕"""
        # 确保bcut-asr可用
        if not _ensure_bcut_asr_available():
            raise SpeechRecognitionError(
                "bcut-asr不可用且自动安装失败，请手动安装:\n"
                "1. 运行: python scripts/install_bcut_asr.py\n"
                "2. 或手动安装: git clone https://github.com/SocialSisterYi/bcut-asr.git\n"
                "3. 同时确保已安装ffmpeg:\n"
                "   macOS: brew install ffmpeg\n"
                "   Ubuntu: sudo apt install ffmpeg\n"
                "   Windows: winget install ffmpeg"
            )
        
        try:
            logger.info(f"开始使用bcut-asr生成字幕: {video_path}")
            
            # 检查视频文件是否存在
            if not video_path.exists():
                raise SpeechRecognitionError(f"视频文件不存在: {video_path}")
            
            # 检查视频文件大小
            file_size = video_path.stat().st_size
            if file_size == 0:
                raise SpeechRecognitionError(f"视频文件为空: {video_path}")
            
            # 检查文件格式，如果是视频文件需要先提取音频
            audio_path = self._extract_audio_from_video(video_path, output_path.parent)
            
            # 创建BcutASR实例，使用音频文件
            asr = BcutASR(str(audio_path))
            
            # 上传文件
            logger.info("正在上传文件到bcut-asr...")
            asr.upload()
            
            # 创建任务
            logger.info("正在创建识别任务...")
            asr.create_task()
            
            # 轮询检查结果
            logger.info("正在等待识别结果...")
            max_attempts = 60  # 最多等待5分钟（每5秒检查一次）
            attempt = 0
            
            while attempt < max_attempts:
                result = asr.result()
                
                # 判断识别成功
                if result.state == ResultStateEnum.COMPLETE:
                    logger.info("bcut-asr识别完成")
                    break
                elif result.state == ResultStateEnum.FAILED:
                    raise SpeechRecognitionError("bcut-asr识别失败")
                
                # 等待5秒后重试
                import time
                time.sleep(5)
                attempt += 1
                logger.info(f"等待识别结果... ({attempt}/{max_attempts})")
            else:
                raise SpeechRecognitionError("bcut-asr识别超时")
            
            # 解析字幕内容
            subtitle = result.parse()
            
            # 判断是否存在字幕
            if not subtitle.has_data():
                raise SpeechRecognitionError("bcut-asr未识别到有效字幕内容")
            
            # 根据输出格式保存字幕
            if config.output_format == "srt":
                subtitle_content = subtitle.to_srt()
            elif config.output_format == "json":
                subtitle_content = subtitle.to_json()
            elif config.output_format == "lrc":
                subtitle_content = subtitle.to_lrc()
            elif config.output_format == "txt":
                subtitle_content = subtitle.to_txt()
            else:
                # 默认使用srt格式
                subtitle_content = subtitle.to_srt()
            
            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(subtitle_content)
            
            logger.info(f"bcut-asr字幕生成成功: {output_path}")
            return output_path
            
        except Exception as e:
            error_msg = f"bcut-asr生成字幕时发生错误: {e}\n"
            error_msg += "可能的原因:\n"
            error_msg += "1. 网络连接问题\n"
            error_msg += "2. 文件格式不支持\n"
            error_msg += "3. 文件过大\n"
            error_msg += "4. bcut-asr服务暂时不可用"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def _generate_subtitle_whisper_local(self, video_path: Path, output_path: Path, 
                                       config: SpeechRecognitionConfig) -> Path:
        """使用本地Whisper生成字幕（优先用Python API）"""
        if not self.available_methods[SpeechRecognitionMethod.WHISPER_LOCAL]:
            raise SpeechRecognitionError(
                "本地Whisper不可用，请安装whisper: pip install openai-whisper\n"
                "同时确保已安装ffmpeg:\n"
                "  macOS: brew install ffmpeg\n"
                "  Ubuntu: sudo apt install ffmpeg\n"
                "  Windows: 下载ffmpeg并添加到PATH"
            )
        
        try:
            logger.info(f"开始使用本地Whisper生成字幕: {video_path}")
            
            # 检查视频文件是否存在
            if not video_path.exists():
                raise SpeechRecognitionError(f"视频文件不存在: {video_path}")
            
            # 检查视频文件大小
            file_size = video_path.stat().st_size
            if file_size == 0:
                raise SpeechRecognitionError(f"视频文件为空: {video_path}")
            
            try:
                # 优先尝试使用Python API（更可靠）
                import whisper
                logger.info(f"加载Whisper模型: {config.model}")
                model = whisper.load_model(config.model)
                
                # 识别参数
                transcribe_kwargs = {
                    "verbose": True
                }
                if config.language != LanguageCode.AUTO:
                    transcribe_kwargs["language"] = config.language.value
                
                logger.info("开始转录...")
                result = model.transcribe(str(video_path), **transcribe_kwargs)
                
                logger.info(f"转录完成，生成SRT: {output_path}")
                
                # 生成SRT文件
                with open(output_path, 'w', encoding='utf-8') as f:
                    for i, segment in enumerate(result['segments'], start=1):
                        start = segment['start']
                        end = segment['end']
                        
                        # 格式化时间 (HH:MM:SS,mmm)
                        def format_time(seconds):
                            hours = int(seconds // 3600)
                            minutes = int((seconds % 3600) // 60)
                            secs = seconds % 60
                            return f"{hours:02}:{minutes:02}:{secs:06.3f}".replace('.', ',')
                        
                        f.write(f"{i}\n")
                        f.write(f"{format_time(start)} --> {format_time(end)}\n")
                        f.write(f"{segment['text'].strip()}\n\n")
                
                logger.info(f"[OK] Whisper字幕生成成功: {output_path}")
                return output_path
                
            except Exception as e:
                logger.warning(f"Python API失败，尝试命令行: {e}")
                
                # 回退到命令行方式
                cmd = [
                    'whisper',
                    str(video_path),
                    '--output_dir', str(output_path.parent),
                    '--output_format', config.output_format,
                    '--model', config.model
                ]
                
                if config.language != LanguageCode.AUTO:
                    cmd.extend(['--language', config.language.value])
                
                logger.info(f"执行Whisper命令: {' '.join(cmd)}")
                
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', cwd=str(video_path.parent))
                
                if result.returncode == 0:
                    if output_path.exists():
                        return output_path
                    else:
                        possible_outputs = list(output_path.parent.glob(f"{video_path.stem}*.{config.output_format}"))
                        if possible_outputs:
                            return possible_outputs[0]
                        else:
                            raise SpeechRecognitionError("Whisper执行成功但未找到输出文件")
                else:
                    raise SpeechRecognitionError(f"Whisper命令失败: {result.stderr}")
                    
        except Exception as e:
            error_msg = f"Whisper生成字幕时发生错误: {e}"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    # ---------- ASR热词管理 ----------
    
    def _collect_asr_hotwords(self, config: 'SpeechRecognitionConfig') -> str:
        """收集所有来源的热词（多源合并去重）"""
        hotword_list = []
        
        # 来源1：用户配置
        if config.hotwords:
            hotword_list.extend(config.hotwords.strip().split())
        
        # 来源2：环境变量
        env_hw = os.environ.get("FUNASR_HOTWORDS", "").strip()
        if env_hw:
            hotword_list.extend(env_hw.split())
        
        # 来源3：历史积累的热词（自动学习）
        persisted = self._load_asr_hotwords()
        hotword_list.extend(persisted)
        
        # 去重保序
        seen = set()
        result = []
        for w in hotword_list:
            w = w.strip()
            if w and w not in seen and len(w) >= 2:
                seen.add(w)
                result.append(w)
        
        return " ".join(result)
    
    def _load_asr_hotwords(self) -> list:
        """加载历史积累的热词"""
        path = Path.home() / ".cache" / "autoclip" / "asr_hotwords.json"
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载历史热词失败: {e}")
        return []
    
    def _save_asr_hotwords(self, srt_path: Path):
        """从ASR结果提取高频词，积累到热词库"""
        try:
            if not srt_path.exists():
                return
            
            # 解析SRT文件提取文本
            texts = []
            with open(srt_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if (line and not line.isdigit() 
                        and '-->' not in line 
                        and len(line) >= 2):
                        texts.append(line)
            
            all_text = ' '.join(texts)
            
            # 提取2字以上的中文词，统计频率
            import re
            words = re.findall(r'[\u4e00-\u9fff]{2,}', all_text)
            from collections import Counter
            counter = Counter(words)
            
            # 停用词
            stopwords = {'的', '是', '在', '了', '和', '与', '了', '我', '你', '他', 
                        '这', '那', '我们', '你们', '他们', '这个', '那个', 
                        '什么', '怎么', '为什么', '因为', '所以', '但是', 
                        '而且', '然后', '还是', '就是', '也是',
                        '啊', '吧', '呢', '吗', '呀', '哦', '嗯',
                        '大家', '可以', '没有', '不是', '一个', '有没',
                        '就是', '还是', '只是', '但是', '因为', '所以'}
            
            # 提取出现3次以上的高频词作为热词
            new_hotwords = [
                word for word, count in counter.most_common(50) 
                if count >= 3 and word not in stopwords and len(word) >= 2
            ]
            
            if not new_hotwords:
                return
            
            # 合并到现有热词库
            existing = self._load_asr_hotwords()
            merged = list(set(existing + new_hotwords))
            
            # 保存（只保留最近200个）
            cache_dir = Path.home() / ".cache" / "autoclip"
            cache_dir.mkdir(parents=True, exist_ok=True)
            with open(cache_dir / "asr_hotwords.json", 'w', encoding='utf-8') as f:
                json.dump(merged[:200], f, ensure_ascii=False, indent=2)
            
            logger.info(f"热词库已更新: {len(merged)} 个热词")
        except Exception as e:
            logger.warning(f"保存热词失败: {e}")
    
    def _generate_subtitle_funasr(self, video_path: Path, output_path: Path,
                                   config: SpeechRecognitionConfig) -> Path:
        """使用FunASR生成字幕（支持GPU加速和模型量化）"""
        if not self.available_methods[SpeechRecognitionMethod.FUNASR]:
            raise SpeechRecognitionError(
                "FunASR不可用，请安装: pip install funasr"
            )

        try:
            logger.info(f"开始使用FunASR生成字幕: {video_path}")

            if not video_path.exists():
                raise SpeechRecognitionError(f"视频文件不存在: {video_path}")

            file_size = video_path.stat().st_size
            if file_size == 0:
                raise SpeechRecognitionError(f"视频文件为空: {video_path}")

            audio_path = self._extract_audio_from_video(video_path, output_path.parent)

            # 自动检测计算设备
            device = _detect_compute_device()
            logger.info(f"使用计算设备: {device}")

            logger.info(f"加载FunASR模型...")
            from funasr import AutoModel
            global _FUNASR_MODEL_CACHE
            
            # 检查是否启用量化（通过环境变量控制）
            use_quantize = os.environ.get("FUNASR_QUANTIZE", "true").lower() == "true"
            
            # 使用缓存的模型（按设备类型缓存）
            cache_key = f"{device}_{'quantized' if use_quantize else 'full'}"
            
            if cache_key not in _FUNASR_MODEL_CACHE:
                logger.info(f"初始化FunASR模型（首次加载，{cache_key}）...")
                
                model_kwargs = {
                    "model": "iic/SenseVoiceSmall",
                    "vad_model": "fsmn-vad",
                    "punc_model": "ct-punc",
                    "device": device,
                    "disable_update": True,
                    "cache_dir": str(Path.home() / ".cache" / "funasr"),
                }
                
                # 启用模型量化（减少内存占用，提升推理速度）
                if use_quantize:
                    model_kwargs.update({
                        "quantize": True,
                        "int8": True,
                    })
                    logger.info("启用模型量化(INT8)")
                
                _FUNASR_MODEL_CACHE[cache_key] = AutoModel(**model_kwargs)
                logger.info("FunASR模型加载完成")
            else:
                logger.info(f"使用缓存的FunASR模型 ({cache_key})")
            
            model = _FUNASR_MODEL_CACHE[cache_key]

            logger.info("开始FunASR转录...")
            # 设置return_timestamp=True以获取带时间戳的分段结果
            # 收集热词：用户配置 + 环境变量 + 历史积累
            generate_kwargs = {"input": str(audio_path), "return_timestamp": True}
            hotwords = self._collect_asr_hotwords(config)
            if hotwords:
                generate_kwargs["hotword"] = hotwords
                logger.info(f"FunASR热词: {hotwords[:100]}...")
            result = model.generate(**generate_kwargs)

            logger.info(f"转录完成，生成SRT: {output_path}")
            
            # 调试：打印结果格式
            logger.info(f"FunASR返回结果类型: {type(result)}")
            if result:
                logger.info(f"FunASR返回结果示例: {str(result[0])[:300]}...")

            def format_time(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = seconds % 60
                return f"{hours:02}:{minutes:02}:{secs:06.3f}".replace('.', ',')

            funasr_vad_segments = []
            for seg in result:
                if isinstance(seg, dict):
                    ts = seg.get('timestamp', seg.get('time_stamp', []))
                    if isinstance(ts, list) and len(ts) > 0 and isinstance(ts[0], list):
                        funasr_vad_segments.append({'start': ts[0][0] / 1000.0, 'end': ts[-1][1] / 1000.0})

            import json as _json
            vad_path = output_path.with_suffix('.vad.json')
            with open(vad_path, 'w', encoding='utf-8') as vf:
                _json.dump(funasr_vad_segments, vf)
            logger.info(f"FunASR VAD 数据已保存: {vad_path} ({len(funasr_vad_segments)} 段语音)")

            def split_text_by_punctuation(text):
                sentences = []
                current = ""
                for char in text:
                    current += char
                    if char in '。！？；\n':
                        sentences.append(current.strip())
                        current = ""
                if current.strip():
                    sentences.append(current.strip())
                return sentences

            def align_timestamps_with_sentences(sentences, timestamps, text):
                if not sentences or not timestamps:
                    return []

                total_text_len = len(text)
                ts_start_ms = timestamps[0][0]
                ts_end_ms = timestamps[-1][1]
                total_ts_duration = ts_end_ms - ts_start_ms

                aligned = []
                char_pos = 0

                for sentence in sentences:
                    sentence_len = len(sentence)
                    char_end = char_pos + sentence_len

                    start_ratio = char_pos / total_text_len if total_text_len > 0 else 0
                    end_ratio = char_end / total_text_len if total_text_len > 0 else 1

                    start_ms = ts_start_ms + start_ratio * total_ts_duration
                    end_ms = ts_start_ms + end_ratio * total_ts_duration

                    end_ms = max(end_ms, start_ms + 100)

                    aligned.append({
                        'start': start_ms / 1000.0,
                        'end': end_ms / 1000.0,
                        'text': sentence
                    })

                    char_pos = char_end

                return aligned

            with open(output_path, 'w', encoding='utf-8') as f:
                segment_index = 1

                for segment in result:
                    if isinstance(segment, dict):
                        text = segment.get('text', segment.get('value', '')).strip()
                        timestamps = segment.get('timestamp', segment.get('time_stamp', []))

                        if isinstance(timestamps, list) and len(timestamps) > 0 and isinstance(timestamps[0], list):
                            sentences = split_text_by_punctuation(text)

                            if sentences:
                                aligned = align_timestamps_with_sentences(sentences, timestamps, text)
                                for item in aligned:
                                    if item['text']:
                                        f.write(f"{segment_index}\n")
                                        f.write(f"{format_time(item['start'])} --> {format_time(item['end'])}\n")
                                        f.write(f"{item['text']}\n\n")
                                        segment_index += 1
                            else:
                                if text:
                                    start = timestamps[0][0] / 1000.0
                                    end = timestamps[-1][1] / 1000.0
                                    f.write(f"{segment_index}\n")
                                    f.write(f"{format_time(start)} --> {format_time(end)}\n")
                                    f.write(f"{text}\n\n")
                                    segment_index += 1

                        elif isinstance(timestamps, list) and len(timestamps) >= 2:
                            start = float(timestamps[0]) / 1000.0
                            end = float(timestamps[1]) / 1000.0

                            f.write(f"{segment_index}\n")
                            f.write(f"{format_time(start)} --> {format_time(end)}\n")
                            f.write(f"{text}\n\n")
                            segment_index += 1

                        else:
                            start = float(segment.get('start', segment.get('start_time', 0))) / 1000.0
                            end = float(segment.get('end', segment.get('end_time', 0))) / 1000.0

                            if text:
                                f.write(f"{segment_index}\n")
                                f.write(f"{format_time(start)} --> {format_time(end)}\n")
                                f.write(f"{text}\n\n")
                                segment_index += 1

            logger.info(f"[OK] FunASR字幕生成成功: {output_path}")
            
            # 从SRT提取高频词，自动积累热词库（供下次ASR使用）
            self._save_asr_hotwords(output_path)
            
            return output_path

        except SpeechRecognitionError:
            raise
        except Exception as e:
            error_msg = f"FunASR生成字幕时发生错误: {e}"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def _generate_subtitle_openai_api(self, video_path: Path, output_path: Path, 
                                    config: SpeechRecognitionConfig) -> Path:
        """使用OpenAI API生成字幕"""
        if not self.available_methods[SpeechRecognitionMethod.OPENAI_API]:
            raise SpeechRecognitionError("OpenAI API不可用，请设置OPENAI_API_KEY环境变量")
        
        try:
            logger.info(f"开始使用OpenAI API生成字幕: {video_path}")
            
            # 这里需要实现OpenAI API调用
            # 由于需要额外的依赖，这里先抛出异常
            raise SpeechRecognitionError("OpenAI API功能暂未实现，请使用本地Whisper")
            
        except Exception as e:
            error_msg = f"OpenAI API生成字幕时发生错误: {e}"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def _generate_subtitle_azure_speech(self, video_path: Path, output_path: Path, 
                                      config: SpeechRecognitionConfig) -> Path:
        """使用Azure Speech Services生成字幕"""
        if not self.available_methods[SpeechRecognitionMethod.AZURE_SPEECH]:
            raise SpeechRecognitionError("Azure Speech Services不可用，请设置AZURE_SPEECH_KEY和AZURE_SPEECH_REGION环境变量")
        
        try:
            logger.info(f"开始使用Azure Speech Services生成字幕: {video_path}")
            
            # 这里需要实现Azure Speech Services调用
            raise SpeechRecognitionError("Azure Speech Services功能暂未实现，请使用本地Whisper")
            
        except Exception as e:
            error_msg = f"Azure Speech Services生成字幕时发生错误: {e}"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def _generate_subtitle_google_speech(self, video_path: Path, output_path: Path, 
                                       config: SpeechRecognitionConfig) -> Path:
        """使用Google Speech-to-Text生成字幕"""
        if not self.available_methods[SpeechRecognitionMethod.GOOGLE_SPEECH]:
            raise SpeechRecognitionError("Google Speech-to-Text不可用，请设置GOOGLE_APPLICATION_CREDENTIALS或GOOGLE_SPEECH_API_KEY环境变量")
        
        try:
            logger.info(f"开始使用Google Speech-to-Text生成字幕: {video_path}")
            
            # 这里需要实现Google Speech-to-Text调用
            raise SpeechRecognitionError("Google Speech-to-Text功能暂未实现，请使用本地Whisper")
            
        except Exception as e:
            error_msg = f"Google Speech-to-Text生成字幕时发生错误: {e}"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def _generate_subtitle_aliyun_speech(self, video_path: Path, output_path: Path, 
                                       config: SpeechRecognitionConfig) -> Path:
        """使用阿里云语音识别生成字幕"""
        if not self.available_methods[SpeechRecognitionMethod.ALIYUN_SPEECH]:
            raise SpeechRecognitionError("阿里云语音识别不可用，请设置ALIYUN_ACCESS_KEY_ID、ALIYUN_ACCESS_KEY_SECRET和ALIYUN_SPEECH_APP_KEY环境变量")
        
        try:
            logger.info(f"开始使用阿里云语音识别生成字幕: {video_path}")
            
            # 这里需要实现阿里云语音识别调用
            raise SpeechRecognitionError("阿里云语音识别功能暂未实现，请使用本地Whisper")
            
        except Exception as e:
            error_msg = f"阿里云语音识别生成字幕时发生错误: {e}"
            logger.error(error_msg)
            raise SpeechRecognitionError(error_msg)
    
    def get_available_methods(self) -> Dict[SpeechRecognitionMethod, bool]:
        """获取可用的语音识别方法"""
        return self.available_methods.copy()
    
    def get_supported_languages(self) -> List[LanguageCode]:
        """获取支持的语言列表"""
        return list(LanguageCode)
    
    def get_whisper_models(self) -> List[str]:
        """获取可用的Whisper模型列表"""
        return ["tiny", "base", "small", "medium", "large"]


def generate_subtitle_for_video(video_path: Path, output_path: Optional[Path] = None,
                               method: str = "auto", language: str = "auto",
                               model: str = "base", enable_fallback: bool = True) -> Path:
    """
    为视频生成字幕文件的便捷函数

    Args:
        video_path: 视频文件路径
        output_path: 输出字幕文件路径
        method: 生成方法 ("auto", "funasr", "bcut_asr", "whisper_local", "openai_api", "azure_speech", "google_speech", "aliyun_speech")
        language: 语言代码
        model: 模型名称（FunASR用paraformer-zh，Whisper用small等）
        enable_fallback: 是否启用回退机制

    Returns:
        生成的字幕文件路径

    Raises:
        SpeechRecognitionError: 语音识别失败
    """
    if method == "auto":
        effective_method = SpeechRecognitionMethod.FUNASR
    else:
        effective_method = SpeechRecognitionMethod(method)

    if effective_method == SpeechRecognitionMethod.FUNASR:
        default_model = "iic/SenseVoiceSmall"
    elif effective_method == SpeechRecognitionMethod.WHISPER_LOCAL:
        default_model = "small"
    else:
        default_model = model

    final_model = model if model != "base" else default_model

    # 创建配置
    config = SpeechRecognitionConfig(
        method=effective_method,
        language=LanguageCode(language),
        model=final_model,
        enable_fallback=enable_fallback
    )

    recognizer = SpeechRecognizer()
    
    if method == "auto":
        # 自动选择最佳方法
        available_methods = recognizer.get_available_methods()
        
        # 按优先级选择方法（FunASR优先，因为准确率高且完全离线）
        priority_methods = [
            SpeechRecognitionMethod.FUNASR,
            SpeechRecognitionMethod.BCUT_ASR,
            SpeechRecognitionMethod.WHISPER_LOCAL,
            SpeechRecognitionMethod.OPENAI_API,
            SpeechRecognitionMethod.AZURE_SPEECH,
            SpeechRecognitionMethod.GOOGLE_SPEECH,
            SpeechRecognitionMethod.ALIYUN_SPEECH
        ]
        
        for priority_method in priority_methods:
            if available_methods.get(priority_method, False):
                config.method = priority_method
                break
        else:
            raise SpeechRecognitionError("没有可用的语音识别服务，请安装whisper或配置API密钥")
    
    return recognizer.generate_subtitle(video_path, output_path, config)


def get_available_speech_recognition_methods() -> Dict[str, bool]:
    """
    获取可用的语音识别方法
    
    Returns:
        可用方法字典
    """
    recognizer = SpeechRecognizer()
    available_methods = recognizer.get_available_methods()
    
    return {
        method.value: available 
        for method, available in available_methods.items()
    }


def get_supported_languages() -> List[str]:
    """
    获取支持的语言列表
    
    Returns:
        支持的语言代码列表
    """
    return [lang.value for lang in LanguageCode]


def get_whisper_models() -> List[str]:
    """
    获取可用的Whisper模型列表
    
    Returns:
        Whisper模型列表
    """
    return ["tiny", "base", "small", "medium", "large"]
