"""
抖音视频下载模块
使用 Playwright 浏览器自动化，支持原画质无水印下载
"""

import os
import re
import json
import time
import requests
from datetime import datetime


MAX_RETRIES = 3
RETRY_DELAY = 2


class DouyinParser:
    """抖音视频解析器"""

    def __init__(self):
        self.video_info = None

    def extract_url(self, text):
        """从文本中提取URL"""
        text = text.strip()
        match = re.search(r'https?://[^\s<>"\']+', text)
        if match:
            text = match.group(0)
        text = re.sub(r'[一-鿿]+$', '', text)
        return text.strip()

    def extract_video_id(self, url):
        """从URL中提取视频ID"""
        for pattern in [
            r'modal_id=(\d+)',
            r'/video/(\d+)',
            r'/note/(\d+)',
            r'aweme_id=(\d+)',
            r'(\d{15,})',
        ]:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def parse(self, url):
        """解析抖音视频，返回视频信息（带重试）"""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                clean_url = self.extract_url(url)
                video_id = self.extract_video_id(clean_url)
                if not video_id:
                    raise ValueError(
                        "无法从链接中提取视频ID\n\n"
                        "支持的格式：\n"
                        "  - https://v.douyin.com/xxxxx/\n"
                        "  - https://www.douyin.com/video/7xxxxxx\n"
                        "  - https://www.douyin.com/user/xxx?modal_id=7xxxxxx"
                    )
                info = self._fetch_with_browser(video_id)
                self.video_info = info
                return info
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)
        raise Exception(f"解析失败（已重试{MAX_RETRIES}次）: {str(last_error)}")

    def _fetch_with_browser(self, video_id):
        """使用 Playwright 获取视频信息"""
        from playwright.sync_api import sync_playwright

        page_url = f"https://www.douyin.com/video/{video_id}"
        result = {
            "video_id": video_id,
            "video_url": "",
            "desc": "",
            "author": "",
            "cover_url": "",
            "duration": 0,
        }

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/137.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="zh-CN",
                extra_http_headers={
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                },
            )

            # 注入反检测脚本，隐藏 webdriver 标记
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                window.chrome = { runtime: {} };
            """)

            page = context.new_page()

            try:
                page.goto(page_url, wait_until="domcontentloaded", timeout=30000)

                # 等待页面充分加载：优先等 video 元素，否则等到最长 20 秒
                try:
                    page.wait_for_selector("video", timeout=20000)
                except Exception:
                    pass

                # 给 SPA 额外时间渲染动态内容
                page.wait_for_timeout(8000)

                # ── 方法 A：从 DOM <video> 元素提取源地址 ──
                sources = page.evaluate("""() => {
                    const videos = document.querySelectorAll('video');
                    const urls = new Set();
                    videos.forEach(v => {
                        if (v.src && !v.src.startsWith('blob:')) urls.add(v.src);
                        if (v.currentSrc && !v.currentSrc.startsWith('blob:')) urls.add(v.currentSrc);
                        v.querySelectorAll('source').forEach(s => {
                            if (s.src && !s.src.startsWith('blob:')) urls.add(s.src);
                        });
                    });
                    return [...urls];
                }""")

                # ── 方法 B：从 RENDER_DATA 提取视频地址和元数据 ──
                render_info = page.evaluate("""() => {
                    const el = document.getElementById('RENDER_DATA');
                    if (!el) return null;
                    try { return decodeURIComponent(el.textContent); }
                    catch(e) { return null; }
                }""")

                # ── 方法 C：从 __NEXT_DATA__ 或 SSR 数据提取（新版页面可能用此结构）──
                next_data = page.evaluate("""() => {
                    const el = document.getElementById('__NEXT_DATA__');
                    if (el) {
                        try { return el.textContent; } catch(e) { return null; }
                    }
                    return null;
                }""")

                # ── 方法 D：拦截网络请求中常见的视频 API 响应 ──
                # 通过分析页面脚本标签获取内嵌的视频数据
                script_data = page.evaluate("""() => {
                    const scripts = document.querySelectorAll('script');
                    for (const s of scripts) {
                        const text = s.textContent || '';
                        if (text.includes('playApi') || text.includes('play_addr')) {
                            return text.substring(0, 50000);
                        }
                    }
                    return null;
                }""")

                page_title = page.title()
                browser.close()

            except Exception:
                try:
                    browser.close()
                except Exception:
                    pass
                raise

        # ── 解析 RENDER_DATA ──
        if render_info:
            self._parse_render_data(render_info, sources, result)

        # ── 解析 __NEXT_DATA__ ──
        if next_data and not sources:
            self._parse_next_data(next_data, sources, result)

        # ── 解析内嵌脚本数据 ──
        if script_data and not sources:
            self._parse_script_data(script_data, sources, result)

        # ── 从页面标题获取描述 ──
        if not result["desc"] and page_title:
            title = page_title.replace(" - 抖音", "").replace("抖音", "").strip()
            if title and len(title) > 1:
                result["desc"] = title

        # ── 选择最佳视频地址 ──
        video_url = self._pick_best_url(sources)
        if not video_url:
            raise Exception(
                "未能获取视频地址，可能原因：\n"
                "  - 视频已删除或设为私密\n"
                "  - 网络连接问题\n"
                "  - 需要登录才能查看\n"
                "  - 抖音页面结构已更新，请联系作者更新"
            )
        result["video_url"] = video_url

        if not result["desc"]:
            result["desc"] = f"抖音视频_{video_id}"

        return result

    def _parse_render_data(self, render_info, sources, result):
        """从 RENDER_DATA JSON 中解析视频信息"""
        try:
            data = json.loads(render_info)
            data_str = json.dumps(data, ensure_ascii=False)

            desc_matches = re.findall(r'"desc"\s*:\s*"([^"]*)"', data_str)
            if desc_matches:
                # 取最长的描述（通常是完整描述）
                result["desc"] = max(desc_matches, key=len)

            author_matches = re.findall(r'"nickname"\s*:\s*"([^"]*)"', data_str)
            if author_matches:
                result["author"] = author_matches[0]

            cover_matches = re.findall(
                r'"origin_cover".*?"url_list"\s*:\s*\["([^"]+)"', data_str
            )
            if cover_matches:
                result["cover_url"] = cover_matches[0].replace("\\u002F", "/")

            dur_matches = re.findall(r'"duration"\s*:\s*(\d+)', data_str)
            if dur_matches:
                result["duration"] = int(dur_matches[0])

            # 从 playApi 获取视频地址
            if not sources:
                play_matches = re.findall(r'"playApi"\s*:\s*"([^"]+)"', data_str)
                if play_matches:
                    for u in play_matches:
                        u = u.replace("\\u002F", "/")
                        if u.startswith("//"):
                            u = "https:" + u
                        if u.startswith("http"):
                            sources.append(u)

            # 从 play_addr 中提取视频地址（新版可能用此字段）
            if not sources:
                addr_matches = re.findall(
                    r'"play_addr".*?"url_list"\s*:\s*\[([^\]]+)\]', data_str
                )
                for match in addr_matches:
                    urls_in_addr = re.findall(r'"([^"]+)"', match)
                    for u in urls_in_addr:
                        u = u.replace("\\u002F", "/")
                        if u.startswith("//"):
                            u = "https:" + u
                        if u.startswith("http") and "douyinvod" in u:
                            sources.append(u)

        except (json.JSONDecodeError, Exception):
            pass

    def _parse_next_data(self, next_data, sources, result):
        """从 __NEXT_DATA__ 中解析视频信息"""
        try:
            data = json.loads(next_data)
            data_str = json.dumps(data, ensure_ascii=False)

            desc_matches = re.findall(r'"desc"\s*:\s*"([^"]*)"', data_str)
            if desc_matches and not result["desc"]:
                result["desc"] = max(desc_matches, key=len)

            play_matches = re.findall(r'"playApi"\s*:\s*"([^"]+)"', data_str)
            for u in play_matches:
                u = u.replace("\\u002F", "/")
                if u.startswith("//"):
                    u = "https:" + u
                if u.startswith("http"):
                    sources.append(u)
        except (json.JSONDecodeError, Exception):
            pass

    def _parse_script_data(self, script_data, sources, result):
        """从内嵌脚本标签中提取视频地址"""
        try:
            play_matches = re.findall(r'"playApi"\s*:\s*"([^"]+)"', script_data)
            for u in play_matches:
                u = u.replace("\\u002F", "/")
                if u.startswith("//"):
                    u = "https:" + u
                if u.startswith("http"):
                    sources.append(u)

            addr_matches = re.findall(
                r'"play_addr".*?"url_list"\s*:\s*\[([^\]]+)\]', script_data
            )
            for match in addr_matches:
                urls_in_addr = re.findall(r'"([^"]+)"', match)
                for u in urls_in_addr:
                    u = u.replace("\\u002F", "/")
                    if u.startswith("//"):
                        u = "https:" + u
                    if u.startswith("http"):
                        sources.append(u)
        except Exception:
            pass

    def _pick_best_url(self, urls):
        """从候选 URL 中选择最佳视频地址"""
        # 过滤掉 blob: 和非 http 地址
        filtered = [u for u in urls if u.startswith("http")]
        filtered = [
            u for u in filtered
            if "douyinstatic" not in u and "media-audio" not in u and "media-video" not in u
        ]
        if not filtered:
            filtered = [u for u in urls if "douyinstatic" not in u]

        # 优先选择 douyinvod CDN（通常是无水印原画质）
        for u in filtered:
            if "douyinvod" in u and "media-" not in u:
                return u

        # 其次选择 aweme 播放接口
        for u in filtered:
            if "aweme/v1/play" in u:
                return u

        # 再次选择包含 v1/play 的地址
        for u in filtered:
            if "v1/play" in u or "play" in u.lower():
                return u

        return filtered[0] if filtered else None


class DouyinDownloader:
    """抖音视频下载器"""

    def __init__(self, save_dir=None):
        self.save_dir = save_dir or os.path.join(os.path.expanduser("~"), "Videos", "Douyin")
        os.makedirs(self.save_dir, exist_ok=True)

    def download(self, video_url, save_path, progress_callback=None):
        """下载视频文件（带重试）

        Args:
            video_url: 视频URL
            save_path: 保存路径
            progress_callback: 进度回调函数，参数为 (percent, downloaded, total)

        Returns:
            保存路径
        """
        if not video_url or not video_url.startswith("http"):
            raise Exception("视频地址无效，可能是浏览器临时链接(blob:)，请重新解析")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.douyin.com/",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(
                    video_url,
                    headers=headers,
                    stream=True,
                    timeout=60,
                    allow_redirects=True,
                )
                resp.raise_for_status()

                total = int(resp.headers.get("content-length", 0))
                downloaded = 0

                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0 and progress_callback:
                                percent = int(downloaded * 100 / total)
                                progress_callback(percent, downloaded, total)

                return save_path

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY)

        raise Exception(f"下载失败（已重试{MAX_RETRIES}次）: {str(last_error)}")

    def get_save_path(self, info):
        """根据视频信息生成保存路径"""
        desc = info.get("desc", "video")
        safe_desc = re.sub(r'[\\/:*?"<>|\n\r]', '_', desc)[:60]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_desc}_{timestamp}.mp4"
        return os.path.join(self.save_dir, filename)
