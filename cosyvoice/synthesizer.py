import os
import configparser
import dashscope
from dashscope.audio.tts_v2 import SpeechSynthesizer
from .callback import TTSCallback

# 读取配置文件中的API密钥
def get_api_key():
    config = configparser.ConfigParser()
    config_file = 'config.ini'
    api_key = None

    # 尝试从配置文件读取API密钥
    if os.path.exists(config_file):
        config.read(config_file)
        if 'API_KEY' in config and 'Qwen' in config['API_KEY']:
            api_key = config['API_KEY']['Qwen']

    # 如果配置文件中没有API密钥，则从环境变量获取
    if not api_key:
        api_key = os.environ.get('COSYVOICE_API_KEY', None)

    return api_key

class CosyVoiceSynthesizer:
    """CosyVoice语音合成器"""
    
    # 可用的音色列表
    AVAILABLE_VOICES = {
        "龙婉": "longwan",
        "龙橙": "longcheng",
        "龙华": "longhua", 
        "龙小淳": "longxiaochun",
        "龙小夏": "longxiaoxia",
        "龙小诚": "longxiaocheng",
        "龙小白": "longxiaobai",
        "龙老铁": "longlaotie",
        "龙书": "longshu",
        "龙硕": "longshuo",
        "龙婧": "longjing",
        "龙妙": "longmiao",
        "龙悦": "longyue",
        "龙媛": "longyuan",
        "龙飞": "longfei",
        "龙杰力豆": "longjielidou",
        "龙彤": "longtong",
        "龙祥": "longxiang",
        "Stella": "loongstella",
        "Bella": "loongbella"
    }
    
    # 支持V2版本的音色
    V2_VOICES = {
        "longcheng": "longcheng_v2",
        "longhua": "longhua_v2",
        "longshu": "longshu_v2",
        "loongbella": "loongbella_v2",
        "longwan": "longwan_v2",
        "longxiaochun": "longxiaochun_v2",
        "longxiaoxia": "longxiaoxia_v2"
    }

    def __init__(self, api_key=None):
        """初始化语音合成器
        
        Args:
            api_key (str, optional): API密钥。如果为None则从环境变量或配置文件获取。
        """
        # 如果没有提供API密钥，则尝试从环境变量或配置文件获取
        if not api_key:
            api_key = get_api_key()
        
        # 检查API密钥是否有效
        if not api_key:
            print("警告: 未配置CosyVoice API密钥，语音合成功能可能无法正常工作")
            print("请在config.ini中配置[API]部分的cosyvoice_key，或设置COSYVOICE_API_KEY环境变量")
        else:
            dashscope.api_key = api_key
            print("CosyVoice API密钥已配置")
            
        self.synthesizer = None
        
    def init_synthesizer(self, voice_name, use_v2=False):
        """初始化合成器
        
        Args:
            voice_name (str): 音色名称
            use_v2 (bool): 是否使用V2版本的音色
        """
        if voice_name not in self.AVAILABLE_VOICES:
            raise ValueError(f"不支持的音色: {voice_name}")
            
        voice = self.AVAILABLE_VOICES[voice_name]
        model = "cosyvoice-v1"
        
        # 如果启用V2且音色支持V2版本
        if use_v2 and voice in self.V2_VOICES:
            voice = self.V2_VOICES[voice]
            model = "cosyvoice-v2"
            
        self.synthesizer = SpeechSynthesizer(
            model=model,
            voice=voice
        )
        
    def synthesize(self, text, output_file, voice_name="龙小淳", use_v2=False):
        """同步方式合成语音
        
        Args:
            text (str): 要合成的文本
            output_file (str): 输出文件路径
            voice_name (str): 音色名称
            use_v2 (bool): 是否使用V2版本的音色
            
        Returns:
            bool: 是否成功
        """
        try:
            self.init_synthesizer(voice_name, use_v2)
            audio = self.synthesizer.call(text)
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            with open(output_file, 'wb') as f:
                f.write(audio)
            return True
            
        except Exception as e:
            print(f"语音合成失败: {str(e)}")
            return False
            
    def synthesize_async(self, text, output_file, voice_name="龙小淳", use_v2=False):
        """异步方式合成语音
        
        Args:
            text (str): 要合成的文本
            output_file (str): 输出文件路径
            voice_name (str): 音色名称
            use_v2 (bool): 是否使用V2版本的音色
            
        Returns:
            bool: 是否成功
        """
        try:
            self.init_synthesizer(voice_name, use_v2)
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            callback = TTSCallback(output_file)
            self.synthesizer.callback = callback
            self.synthesizer.call(text)
            return True
            
        except Exception as e:
            print(f"语音合成失败: {str(e)}")
            return False
            
    def synthesize_stream(self, text_chunks, output_file, voice_name="龙小淳", use_v2=False):
        """流式方式合成语音
        
        Args:
            text_chunks (list): 文本片段列表
            output_file (str): 输出文件路径
            voice_name (str): 音色名称
            use_v2 (bool): 是否使用V2版本的音色
            
        Returns:
            bool: 是否成功
        """
        try:
            self.init_synthesizer(voice_name, use_v2)
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            callback = TTSCallback(output_file)
            self.synthesizer.callback = callback
            
            for chunk in text_chunks:
                self.synthesizer.streaming_call(chunk)
                
            self.synthesizer.streaming_complete()
            return True
            
        except Exception as e:
            print(f"语音合成失败: {str(e)}")
            return False 