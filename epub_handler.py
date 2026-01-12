import os
import re
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from lxml import etree

class EpubHandler:
    def __init__(self):
        self.chapter_regex = r'^(?:(.+[ 　]+)|())(第[一二三四五六七八九十零〇百千万两0123456789]+[章卷]|卷[一二三四五六七八九十零〇百千万两0123456789]+|chap(?:ter)\.?|vol(?:ume)?\.?|book|bk)(?:[ 　]+(?:\S.*)?)?[ 　]*$'
        self.soup = None
    
    def load_epub(self, epub_path):
        """加载Epub文件"""
        try:
            self.book = epub.read_epub(epub_path)
            return True
        except Exception as e:
            raise Exception(f"加载Epub文件失败: {str(e)}")
    
    def extract_text_from_html(self, html_content):
        """从HTML内容中提取纯文本"""
        self.soup = BeautifulSoup(html_content, 'html.parser')
        # 移除脚本和样式
        for script in self.soup(['script', 'style']):
            script.decompose()
        # 获取文本并清理空白
        text = self.soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        return text
    
    def extract_all_text(self):
        """提取Epub中的所有文本内容"""
        all_text = []
        for item in self.book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                html_content = item.get_content().decode('utf-8')
                text = self.extract_text_from_html(html_content)
                if text:
                    all_text.append(text)
        return '\n'.join(all_text)
    
    def split_by_regex(self, text):
        """使用正则表达式切分章节"""
        chapters = []
        lines = text.split('\n')
        current_chapter = None
        current_content = []
        
        for line in lines:
            match = re.match(self.chapter_regex, line, re.IGNORECASE)
            if match:
                # 保存当前章节
                if current_chapter:
                    chapters.append({
                        'title': current_chapter,
                        'content': '\n'.join(current_content)
                    })
                # 开始新章节
                current_chapter = line.strip()
                current_content = []
            else:
                if current_chapter:
                    current_content.append(line)
        
        # 添加最后一章
        if current_chapter:
            chapters.append({
                'title': current_chapter,
                'content': '\n'.join(current_content)
            })
        
        return chapters
    
    def split_by_xpath(self, html_content):
        """使用XPath表达式检测章节"""
        chapters = []
        try:
            # 创建lxml解析器
            parser = etree.HTMLParser()
            tree = etree.fromstring(html_content, parser)
            
            # 注册正则表达式命名空间
            ns = {'re': 'http://exslt.org/regular-expressions'}
            
            # 使用提供的XPath表达式查找章节节点
            chapter_nodes = tree.xpath("//*[((name()='h1' or name()='h2') and re:test(., '\s*((chapter|book|section|part)\s+)|((prolog|prologue|epilogue)(\s+|$))', 'i')) or @class = 'chapter']", namespaces=ns)
            
            if not chapter_nodes:
                return chapters
            
            # 提取章节内容
            for i, chapter_node in enumerate(chapter_nodes):
                # 获取章节标题
                title = chapter_node.text_content().strip()
                
                # 获取章节内容（当前章节节点到下一个章节节点之间的内容）
                content_elements = []
                next_sibling = chapter_node.getnext()
                
                while next_sibling is not None:
                    # 检查是否是下一个章节节点
                    is_next_chapter = False
                    try:
                        is_next_chapter = next_sibling.xpath("self::*[((name()='h1' or name()='h2') and re:test(., '\s*((chapter|book|section|part)\s+)|((prolog|prologue|epilogue)(\s+|$))', 'i')) or @class = 'chapter']", namespaces=ns)
                    except:
                        pass
                    
                    if is_next_chapter:
                        break
                    
                    # 添加当前兄弟节点的文本
                    content_elements.append(next_sibling.text_content())
                    next_sibling = next_sibling.getnext()
                
                # 合并内容并清理
                content = '\n'.join(content_elements)
                lines = (line.strip() for line in content.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                content = '\n'.join(chunk for chunk in chunks if chunk)
                
                if title and content:
                    chapters.append({
                        'title': title,
                        'content': content
                    })
            
        except Exception as e:
            print(f"XPath解析错误: {str(e)}")
        
        return chapters
    
    def get_toc_chapters(self, include_all=False):
        """从TOC中获取章节"""
        chapters = []
        
        def process_toc_item(item, level=0):
            if level > 2:  # 只处理到二级目录
                return
            
            if hasattr(item, 'href'):
                # 获取章节内容
                content_item = self.book.get_item_with_href(item.href)
                if content_item:
                    html_content = content_item.get_content().decode('utf-8')
                    text = self.extract_text_from_html(html_content)
                    chapters.append({
                        'title': item.title,
                        'content': text,
                        'href': item.href,
                        'level': level
                    })
            
            # 处理子项
            if hasattr(item, 'items') and item.items:
                for subitem in item.items:
                    process_toc_item(subitem, level + 1)
        
        # 遍历TOC
        for toc_item in self.book.toc:
            process_toc_item(toc_item)
        
        # 如果是获取所有可选择章节（用于人工选择），且TOC为空，则返回正则切分的章节
        if include_all and not chapters:
            all_text = self.extract_all_text()
            regex_chapters = self.split_by_regex(all_text)
            for i, chapter in enumerate(regex_chapters):
                chapters.append({
                    'title': chapter['title'],
                    'content': chapter['content'],
                    'href': f'chapter_{i}.html',
                    'level': 0
                })
        
        return chapters
    
    def get_all_chapters(self, detection_method='toc'):
        """获取所有可选择的章节（用于人工选择）"""
        chapters = []
        
        # 根据指定的检测方法获取章节
        if detection_method == 'xpath':
            # 使用XPath方法获取章节
            for item in self.book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    html_content = item.get_content().decode('utf-8')
                    xpath_chapters = self.split_by_xpath(html_content)
                    if xpath_chapters:
                        chapters.extend(xpath_chapters)
        elif detection_method == 'regex':
            # 使用正则表达式获取章节
            all_text = self.extract_all_text()
            chapters = self.split_by_regex(all_text)
        elif detection_method == 'toc':
            # 使用TOC获取章节
            chapters = self.get_toc_chapters(include_all=True)
        
        # 如果获取不到章节，尝试其他方法
        if not chapters:
            # 先尝试TOC
            chapters = self.get_toc_chapters(include_all=True)
            if not chapters:
                # 再尝试正则表达式
                all_text = self.extract_all_text()
                chapters = self.split_by_regex(all_text)
        
        # 为每个章节添加必要的属性
        for i, chapter in enumerate(chapters):
            if 'href' not in chapter:
                chapter['href'] = f'chapter_{i}.html'
            if 'level' not in chapter:
                chapter['level'] = 0
        
        return chapters
    
    def split_into_chapters(self, detection_method='xpath'):
        """将Epub内容切分为章节"""
        chapters = []
        
        # 根据指定的检测方法执行相应的逻辑
        if detection_method == 'xpath':
            # 使用XPath方法检测章节
            self._split_by_xpath(chapters)
        elif detection_method == 'regex':
            # 使用正则表达式检测章节
            self._split_by_regex(chapters)
        elif detection_method == 'toc':
            # 使用TOC检测章节
            self._split_by_toc(chapters)
        else:
            # 默认使用XPath优先的检测方式
            self._split_by_xpath(chapters)
            if not chapters:
                self._split_by_regex(chapters)
            if not chapters:
                self._split_by_toc(chapters)
        
        return chapters
    
    def _split_by_xpath(self, chapters):
        """使用XPath方法检测章节"""
        for item in self.book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                html_content = item.get_content().decode('utf-8')
                xpath_chapters = self.split_by_xpath(html_content)
                if xpath_chapters:
                    chapters.extend(xpath_chapters)
    
    def _split_by_regex(self, chapters):
        """使用正则表达式检测章节"""
        all_text = self.extract_all_text()
        regex_chapters = self.split_by_regex(all_text)
        if regex_chapters:
            chapters.extend(regex_chapters)
    
    def _split_by_toc(self, chapters):
        """使用TOC检测章节"""
        toc_chapters = self.get_toc_chapters()
        if toc_chapters:
            chapters.extend(toc_chapters)
    
    def save_chapters_to_md(self, chapters, output_dir):
        """将章节保存为Markdown文件"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        saved_files = []
        for i, chapter in enumerate(chapters):
            # 清理文件名
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', chapter['title'])
            md_path = os.path.join(output_dir, f"{safe_title}.md")
            # 写入Markdown文件
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(f"# {chapter['title']}\n\n")
                f.write(chapter['content'])
            saved_files.append(md_path)
        
        return saved_files