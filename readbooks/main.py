import configparser
from readbooks.book_reader import BookReader
from readbooks.ai_interaction import AIInteraction

class BookReaderApp:
    def __init__(self, task_id, book_path, question, model_name, max_length, timeout, multi_thread, callback=None):
        self.task_id = task_id
        self.book_path = book_path
        self.question = question
        self.model_name = model_name
        self.max_length = max_length
        self.timeout = timeout
        self.multi_thread = multi_thread
        self.callback = callback
        self.config = self._load_config()
        self.book_reader = BookReader(self.book_path, self.max_length)
        self.ai = AIInteraction(self.task_id, self.config, self.model_name, timeout=self.timeout, multi_thread=self.multi_thread, callback=self.callback)

    def _load_config(self):
        config = configparser.ConfigParser()
        config.read('config.ini', encoding='utf-8')
        return config

    def process_book(self):
        """处理电子书并返回内容"""
        return self.book_reader.process_book_action()
        
    def interact_with_ai(self, content_segmentation):
        """与AI交互获取回答"""
        # 为每个分段添加问题
        if not self.question:
            self.question = self.config['PROMPTS']['Question']

        prompts = [
            f"{self.config['PROMPTS']['Segment_prompt']}\n\n{content}\n\n要求：{self.question}"
            for content in content_segmentation
        ]
        return self.ai.query_ai(prompts)
