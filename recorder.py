"""双路录音核心。

同时采集两路声音：
  - 麦克风（"我"）        -> mic.wav
  - 系统回环 Loopback（"对方"）-> system.wav
停止时把两路对齐相加，得到 mixed.wav（整场会议一份能直接听）。

两路统一为 48000Hz 单声道，从源头避免采样率不一致导致的错位。
Windows 专用：依赖 soundcard 的 WASAPI Loopback。
"""
import os
import time
import threading
import datetime

import numpy as np
import soundfile as sf
import soundcard as sc


# ---------- 设备枚举（供 GUI 下拉用） ----------

def list_microphones():
    """真实麦克风输入设备（不含 loopback）。"""
    return sc.all_microphones(include_loopback=False)


def list_loopbacks():
    """系统回环设备（每个扬声器对应一个 loopback）。"""
    return [m for m in sc.all_microphones(include_loopback=True) if m.isloopback]


def default_loopback():
    """当前系统默认播放设备对应的 loopback（插耳机后自动跟随）。"""
    loops = list_loopbacks()
    if not loops:
        return None
    try:
        spk = sc.default_speaker()
        for m in loops:
            if m.name == spk.name or m.id == spk.id:
                return m
    except Exception:
        pass
    return loops[0]


def _get_mic(name):
    if name:
        for m in list_microphones():
            if m.name == name:
                return m
    try:
        return sc.default_microphone()
    except Exception:
        mics = list_microphones()
        return mics[0] if mics else None


def _get_loopback(name):
    if name:
        for m in list_loopbacks():
            if m.name == name:
                return m
    return default_loopback()


def _rms_level(chunk):
    """计算一个音频块的 RMS 电平，归一到 0~1 方便画电平条。"""
    if chunk is None or len(chunk) == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(chunk))))
    # 语音 RMS 通常远小于 1，乘个系数让电平条更直观，并裁剪到 [0,1]
    return min(1.0, rms * 4.0)


class DualRecorder:
    """双路录音器：start() 开始，stop() 停止并保存，返回会话目录。"""

    def __init__(self, samplerate=48000):
        self.samplerate = int(samplerate)
        self._block = max(1, self.samplerate // 20)  # ~50ms 一块
        self._running = False
        self._threads = []
        self._mic_chunks = []
        self._sys_chunks = []
        self._mic_level = 0.0
        self._sys_level = 0.0
        self._start_ts = None
        self.error = None  # 任一采集线程出错时记录异常信息

    # ----- 状态查询（GUI 轮询） -----

    @property
    def is_recording(self):
        return self._running

    def get_levels(self):
        """返回 (麦克风电平, 回环电平)，均为 0~1。"""
        return self._mic_level, self._sys_level

    def elapsed(self):
        """已录秒数。"""
        if self._start_ts is None:
            return 0.0
        return time.time() - self._start_ts

    # ----- 采集 -----

    def _capture(self, device, channels, is_mic):
        """单路采集线程：循环 record，下混单声道，缓存并更新电平。"""
        try:
            with device.recorder(samplerate=self.samplerate,
                                  channels=channels,
                                  blocksize=self._block) as rec:
                while self._running:
                    data = rec.record(numframes=self._block)
                    if data.ndim > 1:
                        mono = data.mean(axis=1)
                    else:
                        mono = data
                    mono = mono.astype(np.float32, copy=False)
                    level = _rms_level(mono)
                    if is_mic:
                        self._mic_chunks.append(mono)
                        self._mic_level = level
                    else:
                        self._sys_chunks.append(mono)
                        self._sys_level = level
        except Exception as e:  # noqa: BLE001 采集出错要让上层看到
            self.error = "{}: {}".format("麦克风" if is_mic else "系统回环", e)
            self._running = False

    def start(self, mic_name="", loop_name=""):
        """开始录音。mic_name/loop_name 为空则用默认设备。"""
        if self._running:
            return
        mic = _get_mic(mic_name)
        loop = _get_loopback(loop_name)
        if mic is None:
            raise RuntimeError("找不到可用的麦克风设备")
        if loop is None:
            raise RuntimeError("找不到系统回环设备（请确认有默认播放设备/已插耳机）")

        self._mic_chunks = []
        self._sys_chunks = []
        self._mic_level = 0.0
        self._sys_level = 0.0
        self.error = None
        self._running = True
        self._start_ts = time.time()

        # 麦克风通常单声道，loopback 通常立体声；各自按 2 声道录再下混最稳
        self._threads = [
            threading.Thread(target=self._capture, args=(mic, 1, True), daemon=True),
            threading.Thread(target=self._capture, args=(loop, 2, False), daemon=True),
        ]
        for t in self._threads:
            t.start()

    def stop(self):
        """停止录音并保存三份 wav，返回会话目录路径。"""
        if not self._running and not self._threads:
            return None
        self._running = False
        for t in self._threads:
            t.join(timeout=3.0)
        self._threads = []
        self._mic_level = 0.0
        self._sys_level = 0.0
        return self._save()

    # ----- 保存 -----

    def _save(self):
        from config import ensure_recordings_dir
        base = ensure_recordings_dir()
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        session_dir = os.path.join(base, stamp)
        os.makedirs(session_dir, exist_ok=True)

        mic = (np.concatenate(self._mic_chunks)
               if self._mic_chunks else np.zeros(0, dtype=np.float32))
        sysaud = (np.concatenate(self._sys_chunks)
                  if self._sys_chunks else np.zeros(0, dtype=np.float32))

        mic_path = os.path.join(session_dir, "mic.wav")
        sys_path = os.path.join(session_dir, "system.wav")
        mixed_path = os.path.join(session_dir, "mixed.wav")

        sf.write(mic_path, mic, self.samplerate)
        sf.write(sys_path, sysaud, self.samplerate)

        # 对齐相加 -> 混音
        n = max(len(mic), len(sysaud))
        mic_p = np.pad(mic, (0, n - len(mic)))
        sys_p = np.pad(sysaud, (0, n - len(sysaud)))
        mixed = mic_p + sys_p
        peak = float(np.max(np.abs(mixed))) if n else 0.0
        if peak > 1.0:  # 防削顶
            mixed = mixed / peak * 0.99
        sf.write(mixed_path, mixed.astype(np.float32), self.samplerate)

        return session_dir


if __name__ == "__main__":
    # 无 GUI 自测：录 5 秒，确认三份 wav 都生成
    print("可用麦克风：", [m.name for m in list_microphones()])
    print("可用回环：", [m.name for m in list_loopbacks()])
    print("默认回环：", default_loopback())
    rec = DualRecorder()
    print("开始录音 5 秒，请对麦克风说话并播放一段有声视频...")
    rec.start()
    for _ in range(50):
        time.sleep(0.1)
        ml, sl = rec.get_levels()
        print("\r麦克风 {:.2f} | 回环 {:.2f}".format(ml, sl), end="")
    out = rec.stop()
    print("\n保存到：", out, "错误：", rec.error)
