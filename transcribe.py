"""P1：双轨逐字文字稿。

分别转写 mic.wav（标"我"）和 system.wav（标"对方"），
按时间戳合并排序，输出 transcript.md（带说话人标签）和 transcript.txt（纯文本）。

因为两路是物理分开录的，说话人天然可分，无需声纹分离。
本地 faster-whisper，默认 CPU + small 模型，开箱即用。
"""
import os


# 模型加载一次后缓存，避免每次会话重复加载
_MODEL_CACHE = {}


def _fmt_ts(seconds):
    """秒 -> [HH:MM:SS]。"""
    s = int(round(seconds))
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return "{:02d}:{:02d}:{:02d}".format(h, m, s)


def _get_model(model_name, device, compute_type):
    key = (model_name, device, compute_type)
    if key not in _MODEL_CACHE:
        from faster_whisper import WhisperModel
        _MODEL_CACHE[key] = WhisperModel(
            model_name, device=device, compute_type=compute_type)
    return _MODEL_CACHE[key]


def _transcribe_track(model, wav_path, language, speaker, progress=None):
    """转写单轨，返回 [(start, end, speaker, text), ...]。文件不存在或为空则返回空。"""
    if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1024:
        return []
    if progress:
        progress("正在转写「{}」...".format(speaker))
    lang = language if language else None
    segments, _info = model.transcribe(
        wav_path,
        language=lang,
        beam_size=5,
        vad_filter=True,          # 过滤静音段，减少空转写
    )
    rows = []
    for seg in segments:
        text = seg.text.strip()
        if text:
            rows.append((seg.start, seg.end, speaker, text))
    return rows


def transcribe_session(session_dir, cfg, progress=None):
    """转写一个会话目录，生成 transcript.md / transcript.txt，返回 md 路径。

    cfg 取自 config.load_config()，用到 whisper_model / whisper_device /
    whisper_compute / language。progress 是可选回调 progress(str) 给 GUI 显示进度。
    """
    if progress:
        progress("加载语音模型（首次会下载，请稍候）...")
    model = _get_model(
        cfg.get("whisper_model", "small"),
        cfg.get("whisper_device", "cpu"),
        cfg.get("whisper_compute", "int8"),
    )
    language = cfg.get("language", "zh")

    mic_path = os.path.join(session_dir, "mic.wav")
    sys_path = os.path.join(session_dir, "system.wav")

    rows = []
    rows += _transcribe_track(model, sys_path, language, "对方", progress)
    rows += _transcribe_track(model, mic_path, language, "我", progress)

    # 按开始时间排序合并
    rows.sort(key=lambda r: r[0])

    md_path = os.path.join(session_dir, "transcript.md")

    md_lines = ["# 会议逐字稿\n",
                "> 来源目录：`{}`\n".format(os.path.basename(session_dir))]
    if not rows:
        md_lines.append("\n_(未识别到语音内容)_\n")
    else:
        for start, _end, speaker, text in rows:
            ts = _fmt_ts(start)
            md_lines.append("- `[{}]` **{}**：{}".format(ts, speaker, text))

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    # 转写完成后删掉两路分轨，最终只保留 mixed.wav 和 transcript.md
    for name in ("mic.wav", "system.wav"):
        p = os.path.join(session_dir, name)
        try:
            if os.path.exists(p):
                os.remove(p)
        except OSError:
            pass

    if progress:
        progress("转写完成")
    return md_path


if __name__ == "__main__":
    import sys
    from config import load_config
    if len(sys.argv) < 2:
        print("用法：python transcribe.py <会话目录，含 mic.wav/system.wav>")
        raise SystemExit(1)
    out = transcribe_session(sys.argv[1], load_config(), progress=print)
    print("文字稿：", out)
