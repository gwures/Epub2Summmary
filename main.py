import os
import sys
import re
import threading
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QProgressBar, QFileDialog,
    QLabel, QGroupBox, QDialog, QFormLayout, QMessageBox, QMenuBar, QMenu,
    QCheckBox, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont

from epub_handler import EpubHandler
from ai_handler import AIHandler
from config import ConfigManager

class WorkerThread(QThread):
    """工作线程，处理耗时操作"""
    update_log = pyqtSignal(str)
    update_progress = pyqtSignal(int)
    task_complete = pyqtSignal(bool, str)
    
    def __init__(self, epub_path, output_dir, ai_handler, selected_chapters=None, detection_method=1):
        super().__init__()
        self.epub_path = epub_path
        self.output_dir = output_dir
        self.ai_handler = ai_handler
        self.epub_handler = EpubHandler()
        self.selected_chapters = selected_chapters
        self.detection_method = detection_method  # 1: XPath, 2: 正则表达式, 3: TOC
    
    def run(self):
        """执行工作线程"""
        try:
            # 1. 加载Epub文件
            self.update_log.emit(f"正在加载Epub文件: {self.epub_path}")
            self.epub_handler.load_epub(self.epub_path)
            
            # 2. 获取章节（如果没有指定，自动切分）
            if self.selected_chapters:
                chapters = self.selected_chapters
                self.update_log.emit(f"使用用户选择的 {len(chapters)} 个章节")
            else:
                self.update_log.emit("正在切分章节...")
                # 根据选择的检测方法执行相应的章节检测
                detection_methods = {
                    1: 'xpath',
                    2: 'regex',
                    3: 'toc'
                }
                method_name = detection_methods.get(self.detection_method, 'xpath')
                self.update_log.emit(f"使用 {method_name} 方法检测章节")
                chapters = self.epub_handler.split_into_chapters(method_name)
                self.update_log.emit(f"成功切分 {len(chapters)} 个章节")
            
            # 3. 转换为Markdown
            self.update_log.emit("正在转换为Markdown...")
            md_files = []
            for i, chapter in enumerate(chapters):
                # 清理文件名
                safe_title = re.sub(r'[<>:"/\\|?*]', '_', chapter['title'])
                md_path = os.path.join(self.output_dir, f"{safe_title}.md")
                # 写入Markdown文件
                with open(md_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {chapter['title']}\n\n")
                    f.write(chapter['content'])
                md_files.append(md_path)
            self.update_log.emit(f"成功保存 {len(md_files)} 个Markdown文件")
            
            # 4. AI总结
            self.update_log.emit("正在生成AI总结...")
            total_files = len(md_files)
            summary_files = []
            
            for i, md_file in enumerate(md_files):
                try:
                    self.update_log.emit(f"正在处理文件 {i+1}/{total_files}: {os.path.basename(md_file)}")
                    # 生成输出路径
                    base_name = os.path.basename(md_file)
                    output_path = os.path.join(self.output_dir, f"{os.path.splitext(base_name)[0]}_summary.md")
                    # 生成总结
                    with open(md_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    summary = self.ai_handler.generate_summary(content)
                    # 保存总结
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write(f"# {os.path.splitext(base_name)[0]} 总结\n\n")
                        f.write(summary)
                    self.update_log.emit(f"成功生成总结: {os.path.basename(output_path)}")
                    summary_files.append(output_path)
                    # 更新进度
                    self.update_progress.emit(int((i+1) / total_files * 100))
                except Exception as e:
                    self.update_log.emit(f"处理文件失败 {os.path.basename(md_file)}: {str(e)}")
                    continue
            
            # 5. 合并所有总结为summary.md
            if summary_files:
                self.update_log.emit("正在合并所有章节总结...")
                summary_md_path = os.path.join(self.output_dir, "summary.md")
                try:
                    self.ai_handler.merge_summaries(summary_files, summary_md_path)
                    self.update_log.emit(f"成功合并生成总览文件: {os.path.basename(summary_md_path)}")
                except Exception as e:
                    self.update_log.emit(f"合并总结失败: {str(e)}")
            
            self.update_log.emit("所有任务完成！")
            self.update_progress.emit(100)
            self.task_complete.emit(True, "处理完成")
        except Exception as e:
            self.update_log.emit(f"处理失败: {str(e)}")
            self.task_complete.emit(False, str(e))

class ChapterSelectionDialog(QDialog):
    """章节选择对话框"""
    def __init__(self, epub_handler, detection_method='toc'):
        super().__init__()
        self.epub_handler = epub_handler
        self.detection_method = detection_method
        self.setWindowTitle("章节选择")
        self.setMinimumSize(600, 400)
        self.selected_chapters = []
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 获取所有章节
        self.chapters = self.epub_handler.get_all_chapters(self.detection_method)
        
        # 标题
        title_label = QLabel(f"共 {len(self.chapters)} 章")
        layout.addWidget(title_label)
        
        # 全选/取消全选
        select_layout = QHBoxLayout()
        self.select_all_checkbox = QCheckBox("全选")
        self.select_all_checkbox.setChecked(True)
        self.select_all_checkbox.stateChanged.connect(self.toggle_select_all)
        select_layout.addWidget(self.select_all_checkbox)
        layout.addLayout(select_layout)
        
        # 章节列表
        self.chapter_list_layout = QVBoxLayout()
        self.chapter_checkboxes = []
        
        for chapter in self.chapters:
            checkbox = QCheckBox(chapter['title'])
            checkbox.setChecked(True)
            self.chapter_checkboxes.append(checkbox)
            self.chapter_list_layout.addWidget(checkbox)
        
        # 添加滚动区域
        scroll_widget = QWidget()
        scroll_widget.setLayout(self.chapter_list_layout)
        
        scroll_area = QScrollArea()
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 确定按钮
        self.ok_button = QPushButton("确定")
        self.ok_button.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_button)
        
        # 取消按钮
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def toggle_select_all(self, state):
        """全选/取消全选"""
        for checkbox in self.chapter_checkboxes:
            checkbox.setChecked(state == Qt.CheckState.Checked)
    
    def accept(self):
        """确认选择"""
        self.selected_chapters = []
        for i, checkbox in enumerate(self.chapter_checkboxes):
            if checkbox.isChecked():
                self.selected_chapters.append(self.chapters[i])
        super().accept()
    
    def get_selected_chapters(self):
        """获取选中的章节"""
        return self.selected_chapters

class SettingsDialog(QDialog):
    """设置对话框"""
    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.setWindowTitle("设置")
        self.setFixedSize(500, 300)
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout()
        
        # 表单布局
        form_layout = QFormLayout()
        
        # API Base URL
        self.api_base_edit = QLineEdit()
        self.api_base_edit.setText(self.config_manager.get('api_base'))
        form_layout.addRow("API Base URL:", self.api_base_edit)
        
        # API Key
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setText(self.config_manager.get('api_key'))
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("API Key:", self.api_key_edit)
        
        # Model Name
        self.model_name_edit = QLineEdit()
        self.model_name_edit.setText(self.config_manager.get('model_name'))
        form_layout.addRow("模型名称:", self.model_name_edit)
        
        # System Prompt
        self.system_prompt_edit = QTextEdit()
        self.system_prompt_edit.setFixedHeight(100)
        self.system_prompt_edit.setText(self.config_manager.get('system_prompt'))
        form_layout.addRow("提示词:", self.system_prompt_edit)
        
        layout.addLayout(form_layout)
        
        # 按钮布局
        button_layout = QHBoxLayout()
        
        # 保存按钮
        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(self.save_button)
        
        # 取消按钮
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def save_settings(self):
        """保存设置"""
        config = {
            'api_base': self.api_base_edit.text().strip(),
            'api_key': self.api_key_edit.text().strip(),
            'model_name': self.model_name_edit.text().strip(),
            'system_prompt': self.system_prompt_edit.toPlainText().strip()
        }
        
        if self.config_manager.update(config):
            QMessageBox.information(self, "成功", "设置已保存")
            self.accept()
        else:
            QMessageBox.critical(self, "错误", "保存设置失败")

class MainWindow(QMainWindow):
    """主窗口"""
    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.ai_handler = AIHandler(self.config_manager.config)
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        # 设置窗口标题和大小
        self.setWindowTitle("Epub2Summary")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建菜单栏
        self.create_menu_bar()
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 文件选择区域
        file_group = QGroupBox("文件选择")
        file_layout = QHBoxLayout()
        
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("选择Epub文件")
        file_layout.addWidget(self.file_path_edit)
        
        self.browse_button = QPushButton("浏览")
        self.browse_button.clicked.connect(self.browse_file)
        file_layout.addWidget(self.browse_button)
        
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)
        
        # 输出目录区域
        output_group = QGroupBox("输出目录")
        output_layout = QHBoxLayout()
        
        self.output_dir_edit = QLineEdit()
        default_output = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
        self.output_dir_edit.setText(default_output)
        output_layout.addWidget(self.output_dir_edit)
        
        self.browse_output_button = QPushButton("浏览")
        self.browse_output_button.clicked.connect(self.browse_output_dir)
        output_layout.addWidget(self.browse_output_button)
        
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)
        
        # 章节检测方案选择区域
        detection_group = QGroupBox("章节检测方案")
        detection_layout = QHBoxLayout()
        
        # 创建单选按钮组
        from PyQt6.QtWidgets import QRadioButton, QButtonGroup
        self.detection_group = QButtonGroup()
        
        # XPath 选项
        self.xpath_radio = QRadioButton("XPath")
        self.xpath_radio.setChecked(True)  # 默认选中XPath
        detection_layout.addWidget(self.xpath_radio)
        self.detection_group.addButton(self.xpath_radio, 1)
        
        # 正则表达式 选项
        self.regex_radio = QRadioButton("正则表达式")
        detection_layout.addWidget(self.regex_radio)
        self.detection_group.addButton(self.regex_radio, 2)
        
        # TOC 选项
        self.toc_radio = QRadioButton("TOC目录")
        detection_layout.addWidget(self.toc_radio)
        self.detection_group.addButton(self.toc_radio, 3)
        
        detection_group.setLayout(detection_layout)
        main_layout.addWidget(detection_group)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.start_button = QPushButton("开始处理")
        self.start_button.clicked.connect(self.start_processing)
        self.start_button.setFixedHeight(40)
        button_layout.addWidget(self.start_button)
        
        main_layout.addLayout(button_layout)
        
        # 日志和进度区域
        log_group = QGroupBox("处理日志")
        log_layout = QVBoxLayout()
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        log_layout.addWidget(self.progress_bar)
        
        # 日志显示
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)
        
    def create_menu_bar(self):
        """创建菜单栏"""
        menu_bar = self.menuBar()
        
        # 设置菜单
        settings_menu = menu_bar.addMenu("设置")
        
        # 配置设置
        config_action = settings_menu.addAction("配置")
        config_action.triggered.connect(self.open_settings)
        
    def open_settings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self.config_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # 更新AI处理器的配置
            self.ai_handler.update_config(self.config_manager.config)
    
    def browse_file(self):
        """浏览选择Epub文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择Epub文件",
            "",
            "Epub文件 (*.epub)"
        )
        if file_path:
            self.file_path_edit.setText(file_path)
    
    def browse_output_dir(self):
        """浏览选择输出目录"""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            ""
        )
        if dir_path:
            self.output_dir_edit.setText(dir_path)
    
    def start_processing(self):
        """开始处理"""
        # 检查输入
        epub_path = self.file_path_edit.text().strip()
        output_dir = self.output_dir_edit.text().strip()
        
        if not epub_path:
            QMessageBox.warning(self, "警告", "请选择Epub文件")
            return
        
        if not os.path.exists(epub_path):
            QMessageBox.warning(self, "警告", "所选Epub文件不存在")
            return
        
        if not output_dir:
            QMessageBox.warning(self, "警告", "请选择输出目录")
            return
        
        # 预加载Epub文件以获取章节列表
        self.append_log("正在加载Epub文件以获取章节列表...")
        
        try:
            # 创建临时的EpubHandler实例来获取章节
            temp_epub_handler = EpubHandler()
            temp_epub_handler.load_epub(epub_path)
            
            # 获取用户选择的章节检测方法
            detection_method = self.detection_group.id(self.detection_group.checkedButton())
            detection_methods = {
                1: 'xpath',
                2: 'regex',
                3: 'toc'
            }
            method_name = detection_methods.get(detection_method, 'toc')
            
            # 显示章节选择对话框，传递检测方法
            dialog = ChapterSelectionDialog(temp_epub_handler, method_name)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                selected_chapters = dialog.get_selected_chapters()
                
                if not selected_chapters:
                    QMessageBox.warning(self, "警告", "请至少选择一个章节")
                    return
                
                # 禁用按钮
                self.start_button.setEnabled(False)
                self.browse_button.setEnabled(False)
                self.browse_output_button.setEnabled(False)
                
                # 清空日志和进度
                self.log_text.clear()
                self.progress_bar.setValue(0)
                
                # 记录用户选择的检测方法
                detection_methods = {
                    1: 'XPath',
                    2: '正则表达式',
                    3: 'TOC目录'
                }
                method_name = detection_methods.get(detection_method, 'TOC目录')
                self.append_log(f"已选择 {method_name} 作为章节检测方案")
                
                # 创建工作线程，传入用户选择的章节和检测方法
                self.worker_thread = WorkerThread(epub_path, output_dir, self.ai_handler, selected_chapters, detection_method)
                self.worker_thread.update_log.connect(self.append_log)
                self.worker_thread.update_progress.connect(self.update_progress)
                self.worker_thread.task_complete.connect(self.on_task_complete)
                self.worker_thread.start()
        except Exception as e:
            QMessageBox.critical(self, "错误", f"加载Epub文件失败: {str(e)}")
            return
    
    def append_log(self, message):
        """添加日志信息"""
        self.log_text.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}")
        # 自动滚动到底部
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())
    
    def update_progress(self, value):
        """更新进度条"""
        self.progress_bar.setValue(value)
    
    def on_task_complete(self, success, message):
        """任务完成处理"""
        if success:
            QMessageBox.information(self, "成功", "处理完成！")
        else:
            QMessageBox.critical(self, "错误", f"处理失败: {message}")
        
        # 启用按钮
        self.start_button.setEnabled(True)
        self.browse_button.setEnabled(True)
        self.browse_output_button.setEnabled(True)

if __name__ == "__main__":
    import time
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())