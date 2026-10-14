from dataclasses import dataclass


@dataclass
class Segment:
    start: float  # seconds from the beginning of the video
    end: float
    text: str
    translation: str = ""

    @property
    def duration(self) -> float:
        return max(self.end - self.start, 0.0)
