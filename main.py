"""
短视频下载器 - 统一界面
支持抖音和B站视频下载
"""

import sys
import os
import json
import subprocess
import platform
import threading
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar, QComboBox,
    QFileDialog, QMessageBox, QFrame, QStackedWidget, QTextEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from platforms.douyin import DouyinParser, DouyinDownloader
from platforms.bilibili import BiliAPI, BiliDownloader


# ── 跨平台工具 ──────────────────────────────────────────
def open_folder(path):
    """跨平台打开文件夹"""
    system = platform.system()
    if system == "Windows":
        os.startfile(path)
    elif system == "Darwin":  # macOS
        subprocess.call(["open", path])
    else:  # Linux
        subprocess.call(["xdg-open", path])


# ── 配置文件 ──────────────────────────────────────────
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config():
    """加载配置文件"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_config(config):
    """保存配置文件"""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ── 主题配置 ──────────────────────────────────────────
THEME = {
    "bg": "#1a1a2e",
    "bg_secondary": "#16213e",
    "bg_card": "#0f3460",
    "accent": "#e94560",
    "accent_hover": "#c73e54",
    "accent_pressed": "#a83248",
    "bili_pink": "#fb7299",
    "bili_pink_hover": "#e85d84",
    "text": "#e0e0e0",
    "text_dim": "#888888",
    "text_info": "#aaaaaa",
    "border": "#0f3460",
    "progress_bg": "#16213e",
    "success": "#4ade80",
    "error": "#ef4444",
}


# ── 工作线程 ──────────────────────────────────────────
class DouyinParseThread(QThread):
    """抖音解析线程"""
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            parser = DouyinParser()
            info = parser.parse(self.url)
            self.finished.emit(info)
        except Exception as e:
            self.error.emit(str(e))


class DouyinDownloadThread(QThread):
    """抖音下载线程"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, video_url, save_path):
        super().__init__()
        self.video_url = video_url
        self.save_path = save_path

    def run(self):
        try:
            downloader = DouyinDownloader()
            downloader.download(
                self.video_url,
                self.save_path,
                lambda p, d, t: self.progress.emit(p)
            )
            self.finished.emit(self.save_path)
        except Exception as e:
            self.error.emit(str(e))


class BiliParseThread(QThread):
    """B站解析线程"""
    finished = pyqtSignal(dict, dict)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            api = BiliAPI()
            vid = api.parse_input(self.url)
            info = api.get_video_info(**vid)
            play_data = api.get_play_url(bvid=info["bvid"], cid=info["cid"])
            self.finished.emit(info, play_data)
        except Exception as e:
            self.error.emit(str(e))


class BiliDownloadThread(QThread):
    """B站下载线程"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, bvid, cid, title, page_num, part_name, save_dir):
        super().__init__()
        self.bvid = bvid
        self.cid = cid
        self.title = title
        self.page_num = page_num
        self.part_name = part_name
        self.save_dir = save_dir

    def run(self):
        try:
            downloader = BiliDownloader(self.save_dir)
            result = downloader.download(
                bvid=self.bvid,
                cid=self.cid,
                title=self.title,
                page_num=self.page_num,
                part_name=self.part_name,
                progress_callback=lambda p, d, t, msg: self.progress.emit(int(p), msg)
            )
            if result:
                self.finished.emit(result)
            else:
                self.error.emit("下载失败")
        except Exception as e:
            self.error.emit(str(e))


# ── 平台选择按钮 ──────────────────────────────────────
class PlatformButton(QPushButton):
    """平台选择按钮"""
    def __init__(self, text, icon, color, parent=None):
        super().__init__(f"{icon}  {text}", parent)
        self.color = color
        self.setCheckable(True)
        self.setFixedHeight(96)
        self.setCursor(Qt.PointingHandCursor)
        self._update_style(False)

    def _update_style(self, checked):
        if checked:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.color};
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 30px;
                    font-weight: bold;
                    padding: 0 48px;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {THEME['bg_secondary']};
                    color: {THEME['text_dim']};
                    border: 2px solid {THEME['border']};
                    border-radius: 8px;
                    font-size: 30px;
                    font-weight: bold;
                    padding: 0 48px;
                }}
                QPushButton:hover {{
                    border-color: {self.color};
                    color: {self.color};
                }}
            """)

    def setChecked(self, checked):
        super().setChecked(checked)
        self._update_style(checked)


# ── 抖音下载组件 ──────────────────────────────────────
class DouyinWidget(QWidget):
    """抖音下载界面"""

    CONFIG_KEY = "douyin_save_dir"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_info = None
        config = load_config()
        self.save_dir = config.get(self.CONFIG_KEY, os.path.join(os.path.expanduser("~"), "Videos", "Douyin"))
        os.makedirs(self.save_dir, exist_ok=True)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)

        # 输入区
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("粘贴抖音分享链接 ...")
        self.url_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME['bg_secondary']};
                color: {THEME['text']};
                border: 2px solid {THEME['border']};
                border-radius: 16px;
                padding: 20px 28px;
                font-size: 28px;
            }}
            QLineEdit:focus {{
                border-color: {THEME['accent']};
            }}
        """)
        input_layout.addWidget(self.url_input)

        self.parse_btn = QPushButton("解析")
        self.parse_btn.setFixedWidth(160)
        self.parse_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['accent']};
                color: white;
                border: none;
                border-radius: 16px;
                padding: 20px 40px;
                font-size: 28px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {THEME['accent_hover']}; }}
            QPushButton:pressed {{ background-color: {THEME['accent_pressed']}; }}
            QPushButton:disabled {{ background-color: #555; color: #999; }}
        """)
        self.parse_btn.clicked.connect(self._on_parse)
        input_layout.addWidget(self.parse_btn)
        layout.addLayout(input_layout)

        # 视频信息区
        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME['bg_secondary']};
                border-radius: 20px;
                padding: 24px;
            }}
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(28, 20, 28, 20)

        self.info_label = QLabel("等待解析...")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(f"color: {THEME['text_info']}; font-size: 26px;")
        self.info_label.setMinimumHeight(120)
        self.info_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self.info_label)
        layout.addWidget(info_frame)

        # 保存目录
        dir_layout = QHBoxLayout()
        dir_label = QLabel("保存目录:")
        dir_label.setStyleSheet(f"color: {THEME['text']}; font-size: 26px;")
        dir_label.setFixedWidth(140)
        dir_layout.addWidget(dir_label)

        self.dir_input = QLineEdit(self.save_dir)
        self.dir_input.setReadOnly(True)
        self.dir_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME['bg_secondary']};
                color: {THEME['text']};
                border: 2px solid {THEME['border']};
                border-radius: 16px;
                padding: 16px 24px;
                font-size: 24px;
            }}
        """)
        dir_layout.addWidget(self.dir_input)

        dir_btn = QPushButton("选择")
        dir_btn.setFixedWidth(140)
        dir_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_card']};
                color: {THEME['text']};
                border: none;
                border-radius: 16px;
                padding: 16px;
                font-size: 24px;
            }}
            QPushButton:hover {{ background-color: #1a4a8a; }}
        """)
        dir_btn.clicked.connect(self._choose_dir)
        dir_layout.addWidget(dir_btn)
        layout.addLayout(dir_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid {THEME['border']};
                border-radius: 16px;
                text-align: center;
                color: {THEME['text']};
                background-color: {THEME['progress_bg']};
                height: 44px;
                font-size: 24px;
            }}
            QProgressBar::chunk {{
                background-color: {THEME['accent']};
                border-radius: 12px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # 按钮区
        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("下载视频")
        self.download_btn.setEnabled(False)
        self.download_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['accent']};
                color: white;
                border: none;
                border-radius: 16px;
                padding: 20px 48px;
                font-size: 28px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {THEME['accent_hover']}; }}
            QPushButton:disabled {{ background-color: #555; color: #999; }}
        """)
        self.download_btn.clicked.connect(self._on_download)
        btn_layout.addWidget(self.download_btn)

        self.open_dir_btn = QPushButton("打开目录")
        self.open_dir_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_card']};
                color: {THEME['text']};
                border: none;
                border-radius: 16px;
                padding: 20px 48px;
                font-size: 28px;
            }}
            QPushButton:hover {{ background-color: #1a4a8a; }}
        """)
        self.open_dir_btn.clicked.connect(self._open_dir)
        btn_layout.addWidget(self.open_dir_btn)
        layout.addLayout(btn_layout)

        # 状态
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 22px;")
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _on_parse(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入抖音分享链接")
            return

        self.parse_btn.setEnabled(False)
        self.parse_btn.setText("解析中...")
        self.info_label.setText("正在启动浏览器解析，请稍候（约10-20秒）...")
        self.download_btn.setEnabled(False)
        self.status_label.setText("正在解析...")

        self.parse_thread = DouyinParseThread(url)
        self.parse_thread.finished.connect(self._on_parse_finished)
        self.parse_thread.error.connect(self._on_parse_error)
        self.parse_thread.start()

    def _on_parse_finished(self, info):
        self.video_info = info
        self.parse_btn.setEnabled(True)
        self.parse_btn.setText("解析")

        desc = info.get("desc", "无标题")
        author = info.get("author", "未知作者")
        video_id = info.get("video_id", "")
        duration = info.get("duration", 0)
        duration_str = f"{duration // 1000 // 60}:{duration // 1000 % 60:02d}" if duration else "未知"

        info_text = (
            f"  作者: {author}\n"
            f"  标题: {desc}\n"
            f"  视频ID: {video_id}\n"
            f"  时长: {duration_str}"
        )
        self.info_label.setText(info_text)
        self.download_btn.setEnabled(True)
        self.status_label.setText("解析完成，可以下载了")

    def _on_parse_error(self, msg):
        self.parse_btn.setEnabled(True)
        self.parse_btn.setText("解析")
        self.info_label.setText(f"  解析失败: {msg}")
        self.status_label.setText("解析失败")
        QMessageBox.warning(self, "解析错误", msg)

    def _on_download(self):
        if not self.video_info:
            return

        downloader = DouyinDownloader(self.save_dir)
        save_path = downloader.get_save_path(self.video_info)

        self.download_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("正在下载...")

        self.download_thread = DouyinDownloadThread(
            self.video_info["video_url"], save_path
        )
        self.download_thread.progress.connect(
            lambda p: self.progress_bar.setValue(p)
        )
        self.download_thread.finished.connect(self._on_download_finished)
        self.download_thread.error.connect(self._on_download_error)
        self.download_thread.start()

    def _on_download_finished(self, path):
        self.download_btn.setEnabled(True)
        self.progress_bar.setValue(100)
        self.status_label.setText(f"下载完成: {os.path.basename(path)}")
        QMessageBox.information(self, "下载完成", f"视频已保存到:\n{path}")

    def _on_download_error(self, msg):
        self.download_btn.setEnabled(True)
        self.status_label.setText("下载失败")
        QMessageBox.warning(self, "下载错误", msg)

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择保存目录", self.save_dir)
        if d:
            self.save_dir = d
            self.dir_input.setText(d)
            config = load_config()
            config[self.CONFIG_KEY] = d
            save_config(config)

    def _open_dir(self):
        open_folder(self.save_dir)


# ── B站下载组件 ──────────────────────────────────────
class BiliWidget(QWidget):
    """B站下载界面"""

    CONFIG_KEY = "bili_save_dir"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.video_info = None
        self.play_data = None
        config = load_config()
        self.save_dir = config.get(self.CONFIG_KEY, os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "output"
        ))
        os.makedirs(self.save_dir, exist_ok=True)
        self._init_ui()
        self._check_env()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(24)

        # 环境状态
        env_layout = QHBoxLayout()
        self.env_label = QLabel("检查中...")
        self.env_label.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 22px;")
        env_layout.addStretch()
        env_layout.addWidget(self.env_label)
        layout.addLayout(env_layout)

        # 输入区
        input_layout = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("输入B站链接 / BV号 / AV号 ...")
        self.url_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME['bg_secondary']};
                color: {THEME['text']};
                border: 2px solid {THEME['border']};
                border-radius: 16px;
                padding: 20px 28px;
                font-size: 28px;
            }}
            QLineEdit:focus {{
                border-color: {THEME['bili_pink']};
            }}
        """)
        input_layout.addWidget(self.url_input)

        self.parse_btn = QPushButton("解析")
        self.parse_btn.setFixedWidth(160)
        self.parse_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bili_pink']};
                color: white;
                border: none;
                border-radius: 16px;
                padding: 20px 40px;
                font-size: 28px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {THEME['bili_pink_hover']}; }}
            QPushButton:disabled {{ background-color: #555; color: #999; }}
        """)
        self.parse_btn.clicked.connect(self._on_parse)
        input_layout.addWidget(self.parse_btn)
        layout.addLayout(input_layout)

        # 视频信息区
        info_frame = QFrame()
        info_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME['bg_secondary']};
                border-radius: 20px;
                padding: 24px;
            }}
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(28, 20, 28, 20)

        self.info_label = QLabel("等待解析...")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(f"color: {THEME['text_info']}; font-size: 26px;")
        self.info_label.setMinimumHeight(120)
        self.info_label.setAlignment(Qt.AlignCenter)
        info_layout.addWidget(self.info_label)
        layout.addWidget(info_frame)

        # 分P选择
        page_layout = QHBoxLayout()
        page_label = QLabel("分P:")
        page_label.setStyleSheet(f"color: {THEME['text']}; font-size: 26px;")
        page_label.setFixedWidth(80)
        page_layout.addWidget(page_label)

        self.page_combo = QComboBox()
        self.page_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {THEME['bg_secondary']};
                color: {THEME['text']};
                border: 2px solid {THEME['border']};
                border-radius: 16px;
                padding: 16px 24px;
                font-size: 26px;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background-color: {THEME['bg_secondary']};
                color: {THEME['text']};
                selection-background-color: {THEME['bili_pink']};
            }}
        """)
        page_layout.addWidget(self.page_combo)
        layout.addLayout(page_layout)

        # 保存目录
        dir_layout = QHBoxLayout()
        dir_label = QLabel("保存:")
        dir_label.setStyleSheet(f"color: {THEME['text']}; font-size: 26px;")
        dir_label.setFixedWidth(80)
        dir_layout.addWidget(dir_label)

        self.dir_input = QLineEdit(self.save_dir)
        self.dir_input.setReadOnly(True)
        self.dir_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {THEME['bg_secondary']};
                color: {THEME['text']};
                border: 2px solid {THEME['border']};
                border-radius: 16px;
                padding: 16px 24px;
                font-size: 24px;
            }}
        """)
        dir_layout.addWidget(self.dir_input)

        dir_btn = QPushButton("浏览")
        dir_btn.setFixedWidth(140)
        dir_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_card']};
                color: {THEME['text']};
                border: none;
                border-radius: 16px;
                padding: 16px;
                font-size: 24px;
            }}
            QPushButton:hover {{ background-color: #1a4a8a; }}
        """)
        dir_btn.clicked.connect(self._choose_dir)
        dir_layout.addWidget(dir_btn)
        layout.addLayout(dir_layout)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 2px solid {THEME['border']};
                border-radius: 16px;
                text-align: center;
                color: {THEME['text']};
                background-color: {THEME['progress_bg']};
                height: 44px;
                font-size: 24px;
            }}
            QProgressBar::chunk {{
                background-color: {THEME['bili_pink']};
                border-radius: 12px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # 按钮区
        btn_layout = QHBoxLayout()
        self.download_btn = QPushButton("开始下载")
        self.download_btn.setEnabled(False)
        self.download_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bili_pink']};
                color: white;
                border: none;
                border-radius: 16px;
                padding: 20px 48px;
                font-size: 28px;
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {THEME['bili_pink_hover']}; }}
            QPushButton:disabled {{ background-color: #555; color: #999; }}
        """)
        self.download_btn.clicked.connect(self._on_download)
        btn_layout.addWidget(self.download_btn)

        self.open_dir_btn = QPushButton("打开目录")
        self.open_dir_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['bg_card']};
                color: {THEME['text']};
                border: none;
                border-radius: 16px;
                padding: 20px 48px;
                font-size: 28px;
            }}
            QPushButton:hover {{ background-color: #1a4a8a; }}
        """)
        self.open_dir_btn.clicked.connect(self._open_dir)
        btn_layout.addWidget(self.open_dir_btn)
        layout.addLayout(btn_layout)

        # 状态
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 22px;")
        layout.addWidget(self.status_label)

        layout.addStretch()

    def _check_env(self):
        def _check():
            downloader = BiliDownloader()
            if downloader.check_ffmpeg():
                self.env_label.setText("✓ ffmpeg 就绪")
                self.env_label.setStyleSheet(f"color: {THEME['success']}; font-size: 22px;")
            else:
                self.env_label.setText("✗ ffmpeg 未安装")
                self.env_label.setStyleSheet(f"color: {THEME['error']}; font-size: 22px;")
        threading.Thread(target=_check, daemon=True).start()

    def _on_parse(self):
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "提示", "请输入视频链接或BV号")
            return

        self.parse_btn.setEnabled(False)
        self.parse_btn.setText("解析中...")
        self.info_label.setText("正在获取视频信息...")
        self.download_btn.setEnabled(False)
        self.status_label.setText("正在解析...")

        self.parse_thread = BiliParseThread(url)
        self.parse_thread.finished.connect(self._on_parse_finished)
        self.parse_thread.error.connect(self._on_parse_error)
        self.parse_thread.start()

    def _on_parse_finished(self, info, play_data):
        self.video_info = info
        self.play_data = play_data
        self.parse_btn.setEnabled(True)
        self.parse_btn.setText("解析")

        v_streams = play_data["video_streams"]
        a_streams = play_data["audio_streams"]
        best_v = play_data.get("quality", 0)
        best_v_name = {80: "1080P", 64: "720P", 32: "480P"}.get(best_v, f"{best_v}P")

        info_text = (
            f"  标题: {info['title']}\n"
            f"  UP主: {info['owner']}\n"
            f"  BV号: {info['bvid']}\n"
            f"  分P数: {len(info['pages'])}  |  "
            f"视频流: {len(v_streams)} 条  |  音频流: {len(a_streams)} 条"
        )
        self.info_label.setText(info_text)

        # 更新分P下拉框
        self.page_combo.clear()
        pages = info["pages"]
        if len(pages) > 1:
            for p in pages:
                self.page_combo.addItem(f"P{p['page']}: {p['part']}", p)
        else:
            self.page_combo.addItem(f"P1: {pages[0]['part']}", pages[0])

        self.download_btn.setEnabled(True)
        self.status_label.setText("解析完成，可以下载了")

    def _on_parse_error(self, msg):
        self.parse_btn.setEnabled(True)
        self.parse_btn.setText("解析")
        self.info_label.setText(f"  解析失败: {msg}")
        self.status_label.setText("解析失败")
        QMessageBox.warning(self, "解析错误", msg)

    def _on_download(self):
        if not self.video_info or not self.play_data:
            return

        # 获取选中的分P
        current_index = self.page_combo.currentIndex()
        if current_index < 0:
            return
        page_info = self.page_combo.itemData(current_index)

        self.download_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText("正在下载...")

        self.download_thread = BiliDownloadThread(
            bvid=self.video_info["bvid"],
            cid=page_info["cid"],
            title=self.video_info["title"],
            page_num=page_info["page"],
            part_name=page_info["part"],
            save_dir=self.save_dir
        )
        self.download_thread.progress.connect(self._on_progress)
        self.download_thread.finished.connect(self._on_download_finished)
        self.download_thread.error.connect(self._on_download_error)
        self.download_thread.start()

    def _on_progress(self, percent, msg):
        self.progress_bar.setValue(percent)
        self.status_label.setText(msg)

    def _on_download_finished(self, path):
        self.download_btn.setEnabled(True)
        self.progress_bar.setValue(100)
        self.status_label.setText(f"下载完成: {os.path.basename(path)}")
        QMessageBox.information(self, "下载完成", f"视频已保存到:\n{path}")

    def _on_download_error(self, msg):
        self.download_btn.setEnabled(True)
        self.status_label.setText("下载失败")
        QMessageBox.warning(self, "下载错误", msg)

    def _choose_dir(self):
        d = QFileDialog.getExistingDirectory(self, "选择保存目录", self.save_dir)
        if d:
            self.save_dir = d
            self.dir_input.setText(d)
            config = load_config()
            config[self.CONFIG_KEY] = d
            save_config(config)

    def _open_dir(self):
        open_folder(self.save_dir)


# ── 主窗口 ──────────────────────────────────────────
class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("短视频下载器")
        self.setFixedSize(1360, 1160)
        self.setStyleSheet(f"QMainWindow {{ background-color: {THEME['bg']}; }}")

        self._init_ui()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(48, 40, 48, 40)
        layout.setSpacing(32)

        # 标题
        title = QLabel("短视频下载器")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            font-size: 48px;
            font-weight: bold;
            color: {THEME['text']};
            margin-bottom: 4px;
        """)
        layout.addWidget(title)

        subtitle = QLabel("支持抖音和B站视频下载")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(f"font-size: 24px; color: {THEME['text_dim']}; margin-bottom: 16px;")
        layout.addWidget(subtitle)

        # 平台选择
        platform_layout = QHBoxLayout()
        platform_layout.setSpacing(24)

        self.douyin_btn = PlatformButton("抖音", "🎵", THEME['accent'])
        self.douyin_btn.setChecked(True)
        self.douyin_btn.clicked.connect(lambda: self._switch_platform(0))
        platform_layout.addWidget(self.douyin_btn)

        self.bili_btn = PlatformButton("B站", "📺", THEME['bili_pink'])
        self.bili_btn.clicked.connect(lambda: self._switch_platform(1))
        platform_layout.addWidget(self.bili_btn)

        layout.addLayout(platform_layout)

        # 内容区
        self.stack = QStackedWidget()

        self.douyin_widget = DouyinWidget()
        self.bili_widget = BiliWidget()

        self.stack.addWidget(self.douyin_widget)
        self.stack.addWidget(self.bili_widget)

        layout.addWidget(self.stack)

    def _switch_platform(self, index):
        self.stack.setCurrentIndex(index)
        self.douyin_btn.setChecked(index == 0)
        self.bili_btn.setChecked(index == 1)


# ── 入口 ──────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    # 跨平台字体选择
    system = platform.system()
    if system == "Darwin":
        font = QFont("PingFang SC", 20)
    elif system == "Windows":
        font = QFont("Microsoft YaHei", 20)
    else:
        font = QFont("Noto Sans CJK SC", 20)
    app.setFont(font)

    # 设置 QMessageBox 样式，文字居中左对齐
    app.setStyleSheet("""
        QMessageBox {
            font-size: 16px;
        }
        QMessageBox QLabel {
            font-size: 20px;
            min-width: 360px;
            qproperty-alignment: AlignLeft;
        }
        QMessageBox QPushButton {
            font-size: 16px;
            padding: 8px 24px;
            min-width: 80px;
        }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
