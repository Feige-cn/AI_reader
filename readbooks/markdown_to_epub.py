from ebooklib import epub
import markdown

class MK_to_EPUB:
    def __init__(self, md_file, epub_file, title, author):
        self.md_file = md_file
        self.epub_file = epub_file
        self.title = title
        self.author = author
        self.book = epub.EpubBook()
        self.chapters = []
        self.lang = 'zh'

    def initialize_book(self):
        """初始化EPUB书籍的元数据"""
        self.book.set_title(self.title)
        self.book.set_language(self.lang)
        self.book.add_author(self.author)

    def read_markdown(self):
        """读取Markdown文件内容"""
        with open(self.md_file, 'r', encoding='utf-8') as f:
            return f.read()

    def split_markdown_into_chapters(self, md_text):
        """
        将Markdown文本按标题拆分为多个章节。
        返回一个列表，每个元素是一个元组 (标题, 内容)。
        """
        chapters = []
        sections = md_text.split('\n# ')
        for i, section in enumerate(sections):
            if i == 0:
                # 第一个部分可能是没有标题的引言
                if section.strip():
                    chapters.append(('介绍', section))
            else:
                # 提取标题和内容
                lines = section.split('\n')
                title = lines[0].strip()
                content = '\n'.join(lines[1:]).strip()
                if content:
                    chapters.append((title, content))
        return chapters

    def create_chapter(self, title, content, index):
        """创建单个EPUB章节"""
        html_content = markdown.markdown(content)
        chapter = epub.EpubHtml(
            title=title,
            file_name=f'chap_{index}.xhtml',
            lang=self.lang
        )
        chapter.content = f'<h1>{title}</h1>\n{html_content}'
        return chapter

    def add_chapters_to_book(self, chapters):
        """将所有章节添加到书籍中"""
        for index, (title, content) in enumerate(chapters):
            chapter = self.create_chapter(title, content, index + 1)
            self.book.add_item(chapter)
            self.chapters.append(chapter)

    def set_book_structure(self):
        """设置书籍的目录结构和阅读顺序"""
        # 设置目录
        self.book.toc = tuple((epub.Link(chapter.file_name, chapter.title, chapter.file_name) for chapter in self.chapters))
        # 设置阅读顺序
        self.book.spine = ['nav'] + self.chapters

    def add_metadata(self):
        """添加书籍的元数据和样式"""
        # 添加默认的NCX和Nav文件
        self.book.add_item(epub.EpubNcx())
        self.book.add_item(epub.EpubNav())
        # 添加样式
        style = '''
        BODY {
            font-family: "SimSun", serif; /* 使用宋体 */
            line-height: 1.6;
        }
        h1, h2, h3 {
            font-family: "SimHei", sans-serif; /* 使用黑体 */
        }
        '''
        nav_css = epub.EpubItem(uid="style_nav", file_name="style/nav.css", media_type="text/css", content=style)
        self.book.add_item(nav_css)

    def generate_epub(self):
        """生成EPUB文件"""
        epub.write_epub(self.epub_file, self.book, {})

    def convert(self):
        """执行转换流程"""
        self.initialize_book()
        md_text = self.read_markdown()
        chapters = self.split_markdown_into_chapters(md_text)
        self.add_chapters_to_book(chapters)
        self.set_book_structure()
        self.add_metadata()
        self.generate_epub()

# 使用示例
if __name__ == '__main__':
    converter = MK_to_EPUB('api/故事.md', 'api/故事.epub', '龙龙与魔法代码', '爸爸')
    converter.convert()