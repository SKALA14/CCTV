# YouTube URL 인풋에 대응하는 구현체
# yt-dlp로 직접 스트리밍 URL을 추출한 뒤 cv2로 읽는다.

import cv2
import numpy as np
import yt_dlp

from .base import FrameSource
from ..config import config


def _extract_stream_url(youtube_url: str) -> str:
    ydl_opts = {
        "format": "bestvideo[vcodec^=avc1][ext=mp4]/bestvideo[ext=mp4][vcodec!=av01]/best[ext=mp4][vcodec!=av01]/best[vcodec!=av01]",
        "quiet": False,
        "no_warnings": False,
        "socket_timeout": 15,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)
        return info["url"]


class YouTubeSource(FrameSource):

    def __init__(self):
        self._cap = None

    def open(self, path: str) -> None:
        stream_url = _extract_stream_url(path)
        self._cap = cv2.VideoCapture(stream_url)
        if not self._cap.isOpened():
            raise RuntimeError(f"YouTube 스트림을 열 수 없습니다: {path}")

    def read_frame(self) -> np.ndarray | None:
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        if self._cap:
            self._cap.release()
            self._cap = None

    def get_fps(self) -> float:
        return self._cap.get(cv2.CAP_PROP_FPS) or 30.0
