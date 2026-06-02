"""配置读写：把上次选的设备、采样率、模型等存进 settings.json，下次启动自动回填。"""
import json
import os

# settings.json 与本文件放在同目录
_HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(_HERE, "settings.json")
RECORDINGS_DIR = os.path.join(_HERE, "recordings")

# 默认配置
DEFAULTS = {
    "mic_device": "",          # 麦克风设备名；空=系统默认
    "loopback_device": "",     # 系统回环设备名；空=默认播放设备的 loopback
    "samplerate": 48000,       # 统一采样率，避免两路错位
    "whisper_model": "small",  # faster-whisper 模型：tiny/base/small/medium/large-v3
    "whisper_device": "cpu",   # cpu 或 cuda（GPU 加速，需自行装好 CUDA/cuDNN）
    "whisper_compute": "int8", # int8(CPU) / int8_float16 或 float16(GPU)
    "language": "zh",          # 转写语言；"" 表示自动识别
    "auto_transcribe": True,   # 录完是否自动转写（P1）
}


def load_config():
    """读取配置；缺字段用默认值补齐。"""
    cfg = dict(DEFAULTS)
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                cfg.update({k: saved[k] for k in saved if k in DEFAULTS})
        except (json.JSONDecodeError, OSError):
            # 配置损坏不影响启动，回退默认
            pass
    return cfg


def save_config(cfg):
    """把配置写回 settings.json（只保存已知字段）。"""
    to_save = {k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(to_save, f, ensure_ascii=False, indent=2)


def ensure_recordings_dir():
    """确保 recordings/ 目录存在，返回其路径。"""
    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    return RECORDINGS_DIR
