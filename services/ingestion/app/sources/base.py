# 입력 프레임 추상 클래스
# 모든 영상 소스(파일, RTSP 등)는 이 클래스를 상속해 구현한다.

from abc import ABC, abstractmethod
import numpy as np

class FrameSource(ABC):

    @abstractmethod
    def open(self) -> None:
        pass

    @abstractmethod
    def read_frame(self) -> np.ndarray | None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def get_fps(self) -> float:
        pass

