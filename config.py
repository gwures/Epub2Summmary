import os
import json

class ConfigManager:
    def __init__(self):
        self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
        self.default_config = {
            'api_base': 'https://api.openai.com',
            'api_key': '',
            'model_name': 'gpt-3.5-turbo',
            'system_prompt': '请总结以下小说章节的核心剧情，保留关键人物和冲突。'
        }
        self.config = self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 合并默认配置和用户配置
                merged_config = self.default_config.copy()
                merged_config.update(config)
                return merged_config
            else:
                # 如果配置文件不存在，使用默认配置
                self.save_config(self.default_config)
                return self.default_config
        except Exception as e:
            print(f"加载配置失败: {str(e)}")
            return self.default_config
    
    def save_config(self, config):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            self.config = config
            return True
        except Exception as e:
            print(f"保存配置失败: {str(e)}")
            return False
    
    def get(self, key, default=None):
        """获取配置值"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """设置配置值"""
        self.config[key] = value
        return self.save_config(self.config)
    
    def update(self, updates):
        """批量更新配置"""
        self.config.update(updates)
        return self.save_config(self.config)