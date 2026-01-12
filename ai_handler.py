import os
import requests
import json
import time

class AIHandler:
    def __init__(self, config):
        self.config = config
        self.api_base = config.get('api_base', '')
        self.api_key = config.get('api_key', '')
        self.model_name = config.get('model_name', 'gpt-3.5-turbo')
        self.system_prompt = config.get('system_prompt', '请总结以下小说章节的核心剧情，保留关键人物和冲突。')
    
    def update_config(self, config):
        """更新配置"""
        self.config = config
        self.api_base = config.get('api_base', '')
        self.api_key = config.get('api_key', '')
        self.model_name = config.get('model_name', 'gpt-3.5-turbo')
        self.system_prompt = config.get('system_prompt', '请总结以下小说章节的核心剧情，保留关键人物和冲突。')
    
    def generate_summary(self, text, max_retries=3):
        """调用AI API生成总结"""
        for retry in range(max_retries):
            try:
                # 构建请求体
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text}
                ]
                
                data = {
                    "model": self.model_name,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 1000
                }
                
                # 发送请求
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
                
                response = requests.post(
                    f"{self.api_base}/v1/chat/completions",
                    headers=headers,
                    json=data,
                    timeout=30
                )
                
                # 处理响应
                if response.status_code == 200:
                    result = response.json()
                    return result['choices'][0]['message']['content'].strip()
                else:
                    raise Exception(f"API请求失败，状态码: {response.status_code}, 响应: {response.text}")
            except Exception as e:
                if retry < max_retries - 1:
                    # 重试前等待
                    wait_time = 2 ** retry
                    time.sleep(wait_time)
                else:
                    raise Exception(f"生成总结失败: {str(e)}")
    
    def summarize_file(self, file_path, output_path):
        """读取文件内容并生成总结"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 生成总结
            summary = self.generate_summary(content)
            
            # 保存总结
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# {os.path.basename(file_path).replace('.md', '')} 总结\n\n")
                f.write(summary)
            
            return True
        except Exception as e:
            raise Exception(f"处理文件 {file_path} 失败: {str(e)}")
    
    def summarize_files(self, file_list, output_dir):
        """批量生成总结"""
        import os
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        results = []
        summary_files = []
        
        for file_path in file_list:
            try:
                # 生成输出文件名
                base_name = os.path.basename(file_path)
                output_path = os.path.join(output_dir, f"{os.path.splitext(base_name)[0]}_summary.md")
                
                # 生成并保存总结
                success = self.summarize_file(file_path, output_path)
                results.append((file_path, output_path, success))
                if success:
                    summary_files.append(output_path)
            except Exception as e:
                results.append((file_path, None, False, str(e)))
        
        return results, summary_files
    
    def merge_summaries(self, summary_files, output_path):
        """将所有章节的总结合并为一个summary.md文件"""
        import os
        import re
        
        # 检查是否有文件名包含数字编号
        has_numbering = any(re.search(r'\d+', os.path.basename(f)) for f in summary_files)
        
        if has_numbering:
            # 如果有数字编号，按编号排序
            def sort_key(file_path):
                # 提取文件名中的数字部分
                file_name = os.path.basename(file_path)
                match = re.search(r'(\d+)', file_name)
                if match:
                    return int(match.group(1))
                return 0
            
            # 复制列表并排序，避免修改原始列表
            sorted_files = sorted(summary_files, key=sort_key)
        else:
            # 如果没有数字编号，保持原始顺序
            sorted_files = summary_files
        
        with open(output_path, 'w', encoding='utf-8') as merged_file:
            # 写入标题
            merged_file.write("# 全书总览\n\n")
            
            # 写入目录
            merged_file.write("## 目录\n\n")
            for i, summary_file in enumerate(sorted_files):
                chapter_title = os.path.basename(summary_file).replace('_summary.md', '').replace('_', ' ')
                merged_file.write(f"{i+1}. [{chapter_title}](#{i+1})\n")
            
            merged_file.write("\n")
            
            # 写入各个章节的总结内容
            for i, summary_file in enumerate(sorted_files):
                try:
                    with open(summary_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 提取章节标题
                    chapter_title = os.path.basename(summary_file).replace('_summary.md', '').replace('_', ' ')
                    
                    # 写入章节标题和内容
                    merged_file.write(f"## {i+1}. {chapter_title}\n\n")
                    
                    # 跳过原始文件的标题行，直接写入总结内容
                    lines = content.split('\n')
                    content_lines = [line for line in lines if not line.strip().startswith('#')]
                    merged_file.write('\n'.join(content_lines).strip() + '\n\n')
                    
                except Exception as e:
                    merged_file.write(f"## {i+1}. {os.path.basename(summary_file)}\n\n")
                    merged_file.write(f"读取总结内容失败: {str(e)}\n\n")
        
        return True