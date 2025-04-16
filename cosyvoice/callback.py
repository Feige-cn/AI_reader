from datetime import datetime
from dashscope.audio.tts_v2 import ResultCallback

class TTSCallback(ResultCallback):
    def __init__(self, output_file):
        """初始化回调处理类
        
        Args:
            output_file (str): 输出音频文件路径
        """
        self.output_file = output_file
        self.file = None
        
    def get_timestamp(self):
        """获取当前时间戳"""
        now = datetime.now()
        return now.strftime("[%Y-%m-%d %H:%M:%S.%f]")
        
    def on_open(self):
        """WebSocket连接打开时的回调"""
        self.file = open(self.output_file, "wb")
        print(f"{self.get_timestamp()} WebSocket已连接")

    def on_complete(self):
        """语音合成任务完成时的回调"""
        print(f"{self.get_timestamp()} 语音合成任务完成")

    def on_error(self, message: str):
        """发生错误时的回调
        
        Args:
            message (str): 错误信息
        """
        print(f"语音合成任务失败: {message}")

    def on_close(self):
        """WebSocket连接关闭时的回调"""
        print(f"{self.get_timestamp()} WebSocket已关闭")
        if self.file:
            self.file.close()

    def on_event(self, message):
        """事件消息回调"""
        pass

    def on_data(self, data: bytes) -> None:
        """接收音频数据的回调
        
        Args:
            data (bytes): 音频数据
        """
        print(f"{self.get_timestamp()} 收到音频数据长度: {len(data)}")
        if self.file:
            self.file.write(data) 