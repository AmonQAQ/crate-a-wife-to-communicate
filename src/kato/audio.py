"""音频播放：提示音、快捷音、语音。"""
import os

from PySide6.QtCore import QObject, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class AudioPlayer(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._players = []

    def play(self, file_path, volume=1.0):
        if not file_path or not os.path.exists(file_path):
            return
        # 清理已停止的播放器，防止引用堆积
        self._players = [p for p in self._players
                         if p[0].playbackState() != QMediaPlayer.PlaybackState.StoppedState]
        player = QMediaPlayer(self)
        out = QAudioOutput(self)
        out.setVolume(float(volume))
        player.setAudioOutput(out)
        player.setSource(QUrl.fromLocalFile(file_path))
        self._players.append((player, out))
        player.play()
