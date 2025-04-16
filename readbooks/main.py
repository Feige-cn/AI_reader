import configparser
import json
from readbooks.book_reader import BookReader
from readbooks.ai_interaction import AIInteraction

class BookReaderApp:
    def __init__(self, task_id, book_path, question, model_name, max_length, timeout, multi_thread, book_type=None, callback=None):
        self.task_id = task_id
        self.book_path = book_path
        self.question = question
        self.model_name = model_name
        self.max_length = max_length
        self.timeout = timeout
        self.multi_thread = multi_thread
        self.book_type = book_type
        self.callback = callback
        self.config = self._load_config()
        self.prompts = self._load_prompts()
        self.book_reader = BookReader(self.book_path, self.max_length)
        self.ai = AIInteraction(self.task_id, self.config, self.model_name, timeout=self.timeout, multi_thread=self.multi_thread, callback=self.callback)

    def _load_config(self):
        config = configparser.ConfigParser()
        config.read('config.ini', encoding='utf-8')
        return config

    def _load_prompts(self):
        """加载提示词配置文件"""
        with open('prompts.json', 'r', encoding='utf-8') as f:
            return json.load(f)

    def _get_prompts(self):
        """根据书籍类型获取对应的提示词"""
        if not self.book_type or self.book_type not in self.prompts['BOOK_TYPES']:
            # 使用默认提示词
            return self.prompts['PROMPTS']
        
        # 使用特定类型的提示词
        prompts_section = f'PROMPTS_{self.book_type}'
        return self.prompts[prompts_section]

    def process_book(self):
        """处理电子书并返回内容"""
        return self.book_reader.process_book_action()
        
    def interact_with_ai(self, content_segmentation):
        """与AI交互获取回答"""
        # 获取对应类型的提示词
        prompts = self._get_prompts()
        
        # 为每个分段添加问题
        if not self.question:
            self.question = prompts['Question']

        # 构建更详细的提示词
        segment_prompts = []
        for i, content in enumerate(content_segmentation):
            # 添加章节信息
            chapter_info = f"\n这是第{i+1}部分内容，共{len(content_segmentation)}部分。"
            
            # 构建完整的提示词
            prompt = f"{prompts['Segment_prompt']}{chapter_info}\n\n{content}\n\n要求：{self.question}"
            segment_prompts.append(prompt)
        
        # 获取分段分析结果
        Summary_prompt = prompts['Summary_prompt']
        segment_results = self.ai.query_ai(segment_prompts, Summary_prompt)
        
        return segment_results
