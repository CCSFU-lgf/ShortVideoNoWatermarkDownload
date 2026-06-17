"""
B站视频下载模块
使用 API 接口获取视频信息，支持多分P下载
"""

import os
import re
import subprocess
import time
from datetime import datetime
from typing import Optional

import requests


# 请求头配置
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com",
}

# API 端点
VIDEO_INFO_API = "https://api.bilibili.com/x/web-interface/view"
PLAY_URL_API = "https://api.bilibili.com/x/player/playurl"

# 下载配置
CHUNK_SIZE = 1024 * 1024  # 1MB 分块
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒

# 视频质量标识映射
QUALITY_MAP = {
    127: "超高清8K",
    126: "杜比视界",
    125: "HDR真彩",
    120: "超清4K",
    116: "高帧率1080P60",
    112: "高码率1080P",
    80:  "高清1080P",
    74:  "高清720P60",
    64:  "高清720P",
    32:  "清晰480P",
    16:  "流畅360P",
}

# 音频质量标识映射
AUDIO_QUALITY_MAP = {
    30280: "320kbps",
    30232: "128kbps",
    30216: "64kbps",
}


class BiliAPI:
    """B站 API 接口"""

    @staticmethod
    def extract_bvid(url: str) -> Optional[str]:
        """从 URL 或 BV 号字符串中提取 BV ID"""
        match = re.search(r"(BV[\w]{10})", url)
        return match.group(1) if match else None

    @staticmethod
    def extract_avid(url: str) -> Optional[int]:
        """从 URL 中提取 AV ID"""
        match = re.search(r"av(\d+)", url, re.IGNORECASE)
        return int(match.group(1)) if match else None

    @staticmethod
    def parse_input(user_input: str) -> dict:
        """解析用户输入，返回标准化的视频标识"""
        bvid = BiliAPI.extract_bvid(user_input)
        if bvid:
            return {"bvid": bvid}

        avid = BiliAPI.extract_avid(user_input)
        if avid:
            return {"avid": avid}

        raise ValueError(
            f"无法识别输入: {user_input}\n"
            "支持的格式:\n"
            "  - B站视频链接: https://www.bilibili.com/video/BVxxxxxx\n"
            "  - BV号: BVxxxxxx\n"
            "  - AV号: avxxxxxx"
        )

    @staticmethod
    def get_video_info(bvid=None, avid=None) -> dict:
        """获取视频基本信息"""
        params = {}
        if bvid:
            params["bvid"] = bvid
        elif avid:
            params["aid"] = avid
        else:
            raise ValueError("必须提供 bvid 或 avid")

        resp = requests.get(VIDEO_INFO_API, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f"获取视频信息失败: {data.get('message', '未知错误')}")

        info = data["data"]
        pages = [
            {"cid": p["cid"], "part": p["part"], "page": p["page"]}
            for p in info.get("pages", [])
        ]

        return {
            "title": info["title"],
            "owner": info["owner"]["name"],
            "bvid": info["bvid"],
            "aid": info["aid"],
            "cid": info["cid"],
            "pages": pages,
        }

    @staticmethod
    def get_play_url(bvid=None, avid=None, cid=None, qn=127, fnval=4048) -> dict:
        """获取视频播放地址 (DASH 格式)"""
        if not cid:
            raise ValueError("必须提供 cid")

        params = {
            "cid": cid,
            "qn": qn,
            "fnval": fnval,
            "fourk": 1,
            "voice_balance": 1,
        }
        if bvid:
            params["bvid"] = bvid
        elif avid:
            params["aid"] = avid
        else:
            raise ValueError("必须提供 bvid 或 avid")

        resp = requests.get(PLAY_URL_API, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f"获取播放地址失败: {data.get('message', '未知错误')}")

        dash = data["data"].get("dash")
        if not dash:
            raise RuntimeError("未获取到 DASH 流信息，可能需要登录或该视频受限")

        video_streams = []
        for s in dash.get("video", []):
            video_streams.append({
                "id": s["id"],
                "codec": s.get("codecs", ""),
                "width": s.get("width", 0),
                "height": s.get("height", 0),
                "bandwidth": s.get("bandwidth", 0),
                "url": s.get("baseUrl") or s.get("base_url", ""),
                "backup_url": s.get("backupUrl") or s.get("backup_url", []),
            })

        audio_streams = []
        for s in dash.get("audio", []):
            audio_streams.append({
                "id": s["id"],
                "codec": s.get("codecs", ""),
                "bandwidth": s.get("bandwidth", 0),
                "url": s.get("baseUrl") or s.get("base_url", ""),
                "backup_url": s.get("backupUrl") or s.get("backup_url", []),
            })

        return {
            "video_streams": video_streams,
            "audio_streams": audio_streams,
            "quality": data["data"].get("quality", 0),
        }


class BiliDownloader:
    """B站视频下载器"""

    def __init__(self, save_dir=None):
        self.save_dir = save_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "output"
        )
        os.makedirs(self.save_dir, exist_ok=True)
        self.api = BiliAPI()

    def check_ffmpeg(self) -> bool:
        """检查 ffmpeg 是否可用"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def download_video_stream(self, url: str, save_path: str, desc: str = "",
                              progress_callback=None) -> bool:
        """下载单个流文件"""
        referer_headers = {**HEADERS, "Origin": "https://www.bilibili.com"}

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.get(
                    url, headers=referer_headers, stream=True, timeout=30
                )
                resp.raise_for_status()

                total_size = int(resp.headers.get("content-length", 0))
                downloaded = 0

                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0 and progress_callback:
                                percent = int(downloaded * 100 / total_size)
                                progress_callback(percent, downloaded, total_size)
                return True

            except (requests.RequestException, IOError) as e:
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    return False

        return False

    def merge_av(self, video_path: str, audio_path: str, output_path: str) -> bool:
        """使用 ffmpeg 合并视频和音频流"""
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "copy",
            output_path,
        ]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def download(self, bvid: str, cid: int, title: str, page_num: int = 1,
                 part_name: str = "", progress_callback=None) -> Optional[str]:
        """下载并合并视频和音频

        Args:
            bvid: BV号
            cid: 分P的cid
            title: 视频标题
            page_num: 分P序号
            part_name: 分P名称
            progress_callback: 进度回调

        Returns:
            成功时返回输出文件路径，失败返回 None
        """
        try:
            play_data = self.api.get_play_url(bvid=bvid, cid=cid)
            v_streams = play_data["video_streams"]
            a_streams = play_data["audio_streams"]

            if not v_streams or not a_streams:
                return None

            # 优先选最高分辨率，同分辨率选最高码率
            best_v = max(v_streams, key=lambda x: (x.get("height", 0), x["bandwidth"]))
            best_a = max(a_streams, key=lambda x: x["bandwidth"])

            # 构建文件名
            safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:100]
            if part_name:
                filename = f"{safe_title}_P{page_num}_{part_name}"
            else:
                filename = safe_title

            os.makedirs(self.save_dir, exist_ok=True)
            temp_video = os.path.join(self.save_dir, f".temp_video_{os.getpid()}.m4s")
            temp_audio = os.path.join(self.save_dir, f".temp_audio_{os.getpid()}.m4s")
            output_path = os.path.join(self.save_dir, f"{filename}.mp4")

            try:
                # 下载视频流
                if progress_callback:
                    progress_callback(0, 0, 0, "下载视频流...")
                success = self.download_video_stream(
                    best_v["url"], temp_video, "视频",
                    lambda p, d, t: progress_callback(p * 0.45, d, t, "下载视频流...") if progress_callback else None
                )
                if not success and best_v.get("backup_url"):
                    for backup in best_v["backup_url"]:
                        success = self.download_video_stream(backup, temp_video, "视频(备用)")
                        if success:
                            break
                if not success:
                    return None

                # 下载音频流
                if progress_callback:
                    progress_callback(45, 0, 0, "下载音频流...")
                success = self.download_video_stream(
                    best_a["url"], temp_audio, "音频",
                    lambda p, d, t: progress_callback(45 + p * 0.45, d, t, "下载音频流...") if progress_callback else None
                )
                if not success and best_a.get("backup_url"):
                    for backup in best_a["backup_url"]:
                        success = self.download_video_stream(backup, temp_audio, "音频(备用)")
                        if success:
                            break
                if not success:
                    return None

                # 合并
                if progress_callback:
                    progress_callback(90, 0, 0, "合并音视频...")
                if self.merge_av(temp_video, temp_audio, output_path):
                    if progress_callback:
                        progress_callback(100, 0, 0, "下载完成")
                    return output_path
                else:
                    return None

            finally:
                for temp in (temp_video, temp_audio):
                    if os.path.exists(temp):
                        try:
                            os.remove(temp)
                        except OSError:
                            pass

        except Exception as e:
            raise Exception(f"下载失败: {str(e)}")
