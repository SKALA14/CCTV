# YouTube URL 인풋에 대응하는 구현체
# yt-dlp로 직접 스트리밍 URL을 추출한 뒤 cv2로 읽는다.

import cv2
import numpy as np
import yt_dlp

from .base import FrameSource
from ..config import config


def _extract_stream_url(youtube_url: str) -> str:
    ydl_opts = {
        "format": "bestvideo[ext=mp4]/best[ext=mp4]/best",
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        return info["url"]


class YouTubeSource(FrameSource):

    def __init__(self):
        self._cap = None

    def open(self) -> None:
        stream_url = _extract_stream_url(config.YT_URL)
        self._cap = cv2.VideoCapture(stream_url)
        if not self._cap.isOpened():
            raise RuntimeError(f"YouTube 스트림을 열 수 없습니다: {config.YT_URL}")

    def read_frame(self) -> np.ndarray | None:
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    def get_fps(self) -> float:
        return self._cap.get(cv2.CAP_PROP_FPS) or 30.0
