[README.md](https://github.com/user-attachments/files/29037746/README.md)
# 短视频下载器 / Short Video No-Watermark Download

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![PyQt5](https://img.shields.io/badge/GUI-PyQt5-green.svg)](https://pypi.org/project/PyQt5/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

一款简洁优雅的桌面应用，支持抖音和 B 站视频无水印下载。

A clean and elegant desktop application for downloading Douyin and Bilibili videos without watermarks.

---

## 项目简介 / Introduction

**中文：**
短视频下载器是一款基于 Python + PyQt5 开发的桌面工具，支持从抖音和 B 站下载高清无水印视频。采用现代化深色主题 UI，操作简单直观。

**English：**
Short Video No-Watermark Download is a desktop tool built with Python + PyQt5, supporting high-definition watermark-free video downloads from Douyin (TikTok China) and Bilibili. Features a modern dark-themed UI with intuitive operation.

---

## 功能特性 / Features

| 功能 / Feature | 说明 / Description |
|---|---|
| 🎵 抖音下载 / Douyin Download | 支持抖音分享链接、视频链接解析下载 |
| 📺 B站下载 / Bilibili Download | 支持 BV号、AV号、视频链接，多分P选择 |
| 🎬 原画质 / Original Quality | 抖音无水印原画质，B站最高画质 |
| 🔧 音视频合并 / AV Merge | B站自动合并音视频流（需 ffmpeg） |
| 📂 自定义目录 / Custom Directory | 可自由选择视频保存路径 |
| 🌙 深色主题 / Dark Theme | 现代化深色 UI，护眼舒适 |
| ⚡ 多线程下载 / Multi-thread | 解析与下载使用独立线程，界面不卡顿 |

---

## 支持平台 / Supported Platforms

| 平台 / Platform | 链接格式 / URL Format |
|---|---|
| 抖音 / Douyin | `https://v.douyin.com/xxxxx/`、`https://www.douyin.com/video/7xxxxxx` |
| B站 / Bilibili | `https://www.bilibili.com/video/BVxxxxxx`、`BVxxxxxx`、`avxxxxxx` |

---

## 截图 / Screenshots

> 截图占位 — 请在打包运行后补充实际界面截图
>
> Placeholder — add actual screenshots after building and running

---

## 安装与运行 / Installation & Usage

### 方式一：从源码运行 / Run from Source

**环境要求 / Requirements：**
- Python 3.8+
- ffmpeg（B站下载需要，用于合并音视频 / Required for Bilibili downloads）

**步骤 / Steps：**

```bash
# 1. 克隆仓库 / Clone the repository
git clone https://github.com/your-username/ShortVideoNoWatermarkDownload.git
cd ShortVideoNoWatermarkDownload

# 2. 创建虚拟环境 / Create virtual environment
python -m venv pc

# 3. 激活虚拟环境 / Activate virtual environment
# Windows:
pc\Scripts\activate
# macOS / Linux:
source pc/bin/activate

# 4. 安装依赖 / Install dependencies
pip install -r requirements.txt

# 5. 安装 Playwright 浏览器（抖音解析需要）/ Install Playwright browser
playwright install chromium

# 6. 启动程序 / Launch the app
python main.py
```

### 方式二：直接运行 / Run Pre-built

1. 从 [Releases](https://github.com/your-username/ShortVideoNoWatermarkDownload/releases) 页面下载最新版本
2. 解压后双击 `短视频下载器.exe`（Windows）或 `短视频下载器`（macOS）即可启动

1. Download the latest release from the [Releases](https://github.com/your-username/ShortVideoNoWatermarkDownload/releases) page
2. Extract and double-click `短视频下载器.exe` (Windows) or `短视频下载器` (macOS) to launch

---

## 打包构建 / Build from Source

如果你想自己打包可执行文件：

If you want to build the executable yourself:

### Windows

```bash
# 双击运行打包脚本 / Double-click to run the build script
build_windows.bat
```

打包完成后，可执行文件位于 `dist/短视频下载器/` 目录下。

After building, the executable will be in the `dist/短视频下载器/` directory.

### macOS

```bash
# 运行打包脚本 / Run the build script
chmod +x build_mac.sh
./build_mac.sh
```

打包完成后，应用位于 `dist/短视频下载器/` 目录下。

After building, the app will be in the `dist/短视频下载器/` directory.

---

## 依赖 / Dependencies

| 依赖 / Dependency | 用途 / Purpose |
|---|---|
| [PyQt5](https://pypi.org/project/PyQt5/) | GUI 界面框架 |
| [requests](https://pypi.org/project/requests/) | HTTP 网络请求 |
| [playwright](https://pypi.org/project/playwright/) | 浏览器自动化（抖音解析） |
| [ffmpeg](https://ffmpeg.org/) | 音视频合并（B站下载） |

---

## 常见问题 / FAQ

### Q: B站下载提示"ffmpeg 未安装"怎么办？
### Q: What to do if Bilibili download says "ffmpeg not installed"?

需要安装 ffmpeg 并将其添加到系统 PATH 环境变量：
- Windows：从 https://ffmpeg.org/download.html 下载，解压后将 `bin` 目录添加到 PATH
- macOS：`brew install ffmpeg`

You need to install ffmpeg and add it to your system PATH:
- Windows: Download from https://ffmpeg.org/download.html, extract and add the `bin` directory to PATH
- macOS: `brew install ffmpeg`

### Q: 抖音解析失败？
### Q: Douyin parsing failed?

- 确保网络连接正常
- 抖音解析需要 Playwright 浏览器，首次运行请执行 `playwright install chromium`
- 如果视频已删除或设为私密，将无法解析

- Ensure your network connection is working
- Douyin parsing requires Playwright browser. Run `playwright install chromium` on first use
- Videos that are deleted or set to private cannot be parsed

### Q: 下载的视频在哪里？
### Q: Where are the downloaded videos?

默认保存目录：
- 抖音：`~/Videos/Douyin/`
- B站：程序目录下的 `output/`

你可以在界面上点击"选择目录"或"浏览"来更改保存路径。

Default save directories:
- Douyin: `~/Videos/Douyin/`
- Bilibili: `output/` in the program directory

You can change the save path by clicking "选择目录" or "浏览" in the interface.

---

## 免责声明 / Disclaimer

**中文：**
本工具仅供学习和个人使用。请遵守相关平台的服务条款和当地法律法规。下载内容的版权归原作者所有，请勿用于商业用途。使用本工具所产生的一切后果由用户自行承担。

**English：**
This tool is for educational and personal use only. Please comply with the terms of service of the respective platforms and applicable local laws. Copyright of downloaded content belongs to the original authors. Do not use for commercial purposes. Users are solely responsible for any consequences arising from the use of this tool.

---

## 许可证 / License

本项目基于 [MIT License](LICENSE) 开源。

This project is open-source under the [MIT License](LICENSE).
