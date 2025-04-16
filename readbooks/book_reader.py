import os
import mobi
import chardet
from ebooklib import epub
from PyPDF2 import PdfReader
import re
import warnings

warnings.filterwarnings("ignore", category=UserWarning, message="In the future version we will turn default option ignore_ncx to True.")
warnings.filterwarnings("ignore", category=FutureWarning)

class BookReader:
    def __init__(self, book_path, max_length=50000):
        self.book_path = book_path
        self.max_length = max_length

    def process_book_action(self) -> list:
        """处理电子书文件，提取文本内容"""
        if not os.path.exists(self.book_path):
            raise FileNotFoundError(f"文件 {self.book_path} 不存在")
            
        file_ext = os.path.splitext(self.book_path)[1].lower()
        
        try:
            if file_ext == '.epub':
                content = self._process_epub()
            elif file_ext == '.mobi':
                content = self._process_mobi()
            elif file_ext == '.pdf':
                content = self._process_pdf()
            elif file_ext in ['.txt', '.md']:
                content = self._process_text()
            else:
                raise ValueError(f"不支持的电子书格式: {file_ext}")
                
            cleaned_content = self._clean_text(content)
            return self._split_content(cleaned_content)
            
        except Exception as e:
            raise Exception(f"处理电子书时出错: {str(e)}")
            
    def _process_epub(self):
        """处理EPUB格式电子书"""
        book = epub.read_epub(self.book_path)
        text_content = []
        
        for item in book.get_items():
            if isinstance(item, epub.EpubHtml):
                try:
                    content = item.get_content()
                    if content is None:
                        continue
                    if isinstance(content, bytes):
                        text_content.append(content.decode('utf-8'))
                    else:
                        text_content.append(str(content))
                except Exception as e:
                    print(f"Error processing item {item.get_name()}: {str(e)}")
                    continue
                
        full_content = '\n'.join(text_content)
        if not full_content:
            print("Warning: No content extracted from EPUB file")
            return ''
            
        return full_content
        
    def _process_mobi(self):
        """处理MOBI格式电子书"""
        temp_dir, filepath = mobi.extract(self.book_path)
        try:
            # 检测文件编码
            with open(filepath, 'rb') as f:
                raw_data = f.read()
                encoding = chardet.detect(raw_data)['encoding']
                
            with open(filepath, 'r', encoding=encoding or 'utf-8') as f:
                content = f.read()
            return content
        except Exception as e:
            print(f'处理MOBI格式电子书时出错：{str(e)}')
            raise
            
    def _process_pdf(self):
        """处理PDF格式电子书"""
        try:
            reader = PdfReader(self.book_path)
            text_content = []
            
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_content.append(text)
                    
            return '\n'.join(text_content)
        except Exception as e:
            raise Exception(f"PDF处理失败: {str(e)}")

    def _process_text(self):
        """处理纯文本格式电子书"""
        encodings = ['utf-8', 'gbk', 'latin1']
        content = ''
        for enc in encodings:
            try:
                with open(self.book_path, 'r', encoding=enc) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                raise Exception(f"读取文件时发生错误: {e}")
        if content == '':
            raise ValueError("无法解码文件，尝试的编码均失败")
        return content

    def _clean_text(self, text):
        """清理和格式化文本"""
        if not text:
            return text
            
        # 如果输入是列表，先转换为字符串
        if isinstance(text, list):
            text = '\n'.join(text)
            
        # 确保输入是字符串
        if not isinstance(text, str):
            text = str(text)
            
        # 移除多余的空格和换行
        # text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊字符
        # text = re.sub(r'[\x00-\x1F\x7F]', '', text)
        
        # 标准化标点符号
        text = re.sub(r'[“”]', '"', text)
        text = re.sub(r'[‘’]', "'", text)
        
        # 移除重复的标点
        text = re.sub(r'([.,!?])\1+', r'\1', text)
        
        return text.strip()

    def _split_content(self, content):
        """将内容按章节智能分割，如果章节过长则再次分割"""
        if not isinstance(content, str):
            if isinstance(content, list):
                content = '\n'.join(content)
            else:
                content = str(content)

        # 常见的章节标记模式
        chapter_patterns = [
            r'第[一二三四五六七八九十百千]+章',  # 中文数字章节
            r'第\d+章',  # 阿拉伯数字章节
            r'Chapter\s+\d+',  # 英文章节
            r'^\s*\d+\s*$',  # 独立数字作为章节
            r'^\s*[一二三四五六七八九十百千]+\s*$',  # 独立中文数字作为章节
        ]
        
        # 合并所有模式
        pattern = '|'.join(f'({p})' for p in chapter_patterns)
        
        # 按章节分割
        chapters = []
        current_chapter = []
        current_length = 0
        
        lines = content.split('\n')
        for line in lines:
            # 检查是否是新章节的开始
            if re.search(pattern, line, re.IGNORECASE):
                if current_chapter:
                    chapter_content = '\n'.join(current_chapter)
                    # 如果当前章节超过最大长度，需要再次分割
                    if len(chapter_content) > self.max_length:
                        sub_chunks = self._split_by_length(chapter_content)
                        chapters.extend(sub_chunks)
                    else:
                        chapters.append(chapter_content)
                current_chapter = [line]
                current_length = len(line)
            else:
                current_chapter.append(line)
                current_length += len(line)
        
        # 处理最后一个章节
        if current_chapter:
            chapter_content = '\n'.join(current_chapter)
            if len(chapter_content) > self.max_length:
                sub_chunks = self._split_by_length(chapter_content)
                chapters.extend(sub_chunks)
            else:
                chapters.append(chapter_content)
        
        # 如果没有检测到章节标记，则按长度分割
        if not chapters:
            return self._split_by_length(content)
            
        print(f'本书总长度：{len(content)}\t分章数：{len(chapters)}')
        return chapters
        
    def _split_by_length(self, content):
        """按长度分割内容，保持一定的重叠以保证上下文连贯性"""
        overlap_chars = int(self.max_length * 0.1)  # 10%的重叠
        chunks = []
        current_chunk = []
        current_length = 0
        
        paragraphs = content.split('\n')
        
        for para in paragraphs:
            if current_length + len(para) > self.max_length:
                chunks.append('\n'.join(current_chunk))
                # 保留最后一部分作为重叠
                overlap = '\n'.join(current_chunk[-3:])  # 保留最后三段
                current_chunk = [overlap, para]
                current_length = len(overlap) + len(para)
            else:
                current_chunk.append(para)
                current_length += len(para)
                
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
            
        return chunks

