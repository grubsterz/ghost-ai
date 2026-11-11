"""Optional local speech-to-text (faster-whisper + sounddevice).

Recording only starts after an explicit user click and stops on the next click or after
`max_seconds`. Audio stays in memory and is discarded after transcription."""

from __future__ import annotations

import importlib.util
import logging
import threading
from typing import Any

log = logging.getLogger(__name__)

SAMPLE_RATE = 16_000


def voice_available() -> tuple[bool, str]:
    missing = [m for m in ("faster_whisper", "sounddevice", "numpy") if importlib.util.find_spec(m) is None]
    if missing:
        return False, "missing:" + ",".join(missing)
    return True, ""


class VoiceRecorder:
    def __init__(self, model_size: str = "small", max_seconds: float = 30.0) -> None:
        self.model_size = model_size
        self.max_seconds = max_seconds
        self._frames: list[Any] = []
        self._stream = None
        self._lock = threading.Lock()
        self._model = None

    @property
    def recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        import numpy as np  # noqa: F401
        import sounddevice as sd

        self._frames = []

        def cb(indata, _frames, _time, status):  # noqa: ANN001
            if status:
                log.debug("audio status %s", status)
            with self._lock:
                if len(self._frames) * len(indata) < self.max_seconds * SAMPLE_RATE:
                    self._frames.append(indata.copy())

        self._stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32", callback=cb)
        self._stream.start()

    def stop(self):
        import numpy as np

        if self._stream is None:
            return np.zeros(0, dtype="float32")
        self._stream.stop()
        self._stream.close()
        self._stream = None
        with self._lock:
            audio = np.concatenate(self._frames).flatten() if self._frames else np.zeros(0, dtype="float32")
            self._frames = []
        return audio

    def transcribe(self, audio, language: str | None) -> str:
        from faster_whisper import WhisperModel

        if len(audio) < SAMPLE_RATE // 4:
            return ""
        if self._model is None:
            # CPU int8 works everywhere; no GPU required.
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        segments, _info = self._model.transcribe(audio, language=language, vad_filter=True)
        return " ".join(s.text.strip() for s in segments).strip()
