"""Recoder GUI 入口（Windows 11，tkinter）。

一个小窗口完成：选设备 -> 开始/停止双向录音 -> 自动出双轨文字稿。
运行：在 Windows 终端执行  python app.py
"""
import os
import threading
import queue
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox

import config
import recorder

DEFAULT_LABEL = "（系统默认）"


class RecoderApp:
    def __init__(self, root):
        self.root = root
        self.cfg = config.load_config()
        self.rec = recorder.DualRecorder(samplerate=self.cfg.get("samplerate", 48000))
        self.last_session = None
        self.msg_q = queue.Queue()  # 后台线程 -> UI 的消息

        root.title("Recoder · 双向会议录音")
        root.geometry("460x340")
        root.resizable(False, False)

        self._build_ui()
        self._load_devices()
        self._poll()  # 启动周期刷新

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI ----------

    def _build_ui(self):
        pad = {"padx": 12, "pady": 6}
        frm = ttk.Frame(self.root)
        frm.pack(fill="both", expand=True, padx=8, pady=8)

        # 设备选择
        ttk.Label(frm, text="麦克风（我）").grid(row=0, column=0, sticky="w", **pad)
        self.mic_cb = ttk.Combobox(frm, state="readonly", width=34)
        self.mic_cb.grid(row=0, column=1, **pad)

        ttk.Label(frm, text="系统回环（对方）").grid(row=1, column=0, sticky="w", **pad)
        self.loop_cb = ttk.Combobox(frm, state="readonly", width=34)
        self.loop_cb.grid(row=1, column=1, **pad)

        refresh = ttk.Button(frm, text="刷新设备", command=self._load_devices)
        refresh.grid(row=2, column=1, sticky="e", padx=12)

        # 电平条
        ttk.Label(frm, text="麦克风电平").grid(row=3, column=0, sticky="w", **pad)
        self.mic_level = ttk.Progressbar(frm, maximum=100, length=240)
        self.mic_level.grid(row=3, column=1, **pad)

        ttk.Label(frm, text="对方电平").grid(row=4, column=0, sticky="w", **pad)
        self.sys_level = ttk.Progressbar(frm, maximum=100, length=240)
        self.sys_level.grid(row=4, column=1, **pad)

        # 计时
        self.timer_var = tk.StringVar(value="00:00:00")
        ttk.Label(frm, textvariable=self.timer_var,
                  font=("Segoe UI", 18, "bold")).grid(row=5, column=0, columnspan=2,
                                                      pady=(8, 2))

        # 开始/停止
        self.btn = ttk.Button(frm, text="● 开始录音", command=self._toggle)
        self.btn.grid(row=6, column=0, columnspan=2, pady=4, ipadx=12, ipady=2)

        # 状态
        self.status_var = tk.StringVar(value="就绪")
        status = ttk.Label(frm, textvariable=self.status_var, foreground="#555")
        status.grid(row=7, column=0, columnspan=2, pady=(4, 0))

        # 打开上次结果
        self.open_btn = ttk.Button(frm, text="打开上次录音文件夹",
                                   command=self._open_last, state="disabled")
        self.open_btn.grid(row=8, column=0, columnspan=2, pady=4)

    def _load_devices(self):
        try:
            mics = recorder.list_microphones()
            loops = recorder.list_loopbacks()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("设备枚举失败", str(e))
            return

        mic_names = [DEFAULT_LABEL] + [m.name for m in mics]
        loop_names = [DEFAULT_LABEL] + [m.name for m in loops]
        self.mic_cb["values"] = mic_names
        self.loop_cb["values"] = loop_names

        self.mic_cb.set(self._pick(self.cfg.get("mic_device", ""), mic_names))
        self.loop_cb.set(self._pick(self.cfg.get("loopback_device", ""), loop_names))

    @staticmethod
    def _pick(saved_name, names):
        if saved_name and saved_name in names:
            return saved_name
        return DEFAULT_LABEL

    @staticmethod
    def _name_of(cb):
        v = cb.get()
        return "" if v == DEFAULT_LABEL else v

    # ---------- 录音控制 ----------

    def _toggle(self):
        if self.rec.is_recording:
            self._stop()
        else:
            self._start()

    def _start(self):
        mic_name = self._name_of(self.mic_cb)
        loop_name = self._name_of(self.loop_cb)
        try:
            self.rec.start(mic_name, loop_name)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("无法开始录音", str(e))
            return
        # 记住选择
        self.cfg["mic_device"] = mic_name
        self.cfg["loopback_device"] = loop_name
        config.save_config(self.cfg)

        self.btn.config(text="■ 停止录音")
        self.status_var.set("录音中…")
        self.mic_cb.config(state="disabled")
        self.loop_cb.config(state="disabled")
        self.open_btn.config(state="disabled")

    def _stop(self):
        self.status_var.set("保存中…")
        self.root.update_idletasks()
        session = self.rec.stop()
        self.btn.config(text="● 开始录音")
        self.mic_cb.config(state="readonly")
        self.loop_cb.config(state="readonly")
        self.mic_level["value"] = 0
        self.sys_level["value"] = 0

        if self.rec.error:
            messagebox.showwarning("录音过程出现问题", self.rec.error)
        if not session:
            self.status_var.set("就绪")
            return

        self.last_session = session
        self.open_btn.config(state="normal")
        self.status_var.set("已保存：{}".format(os.path.basename(session)))

        if self.cfg.get("auto_transcribe", True):
            self._start_transcribe(session)

    # ---------- P1 转写（后台线程） ----------

    def _start_transcribe(self, session):
        self.btn.config(state="disabled")

        def worker():
            try:
                import transcribe
                transcribe.transcribe_session(
                    session, self.cfg,
                    progress=lambda s: self.msg_q.put(("status", s)))
                self.msg_q.put(("done", session))
            except Exception as e:  # noqa: BLE001
                self.msg_q.put(("error", str(e)))

        threading.Thread(target=worker, daemon=True).start()

    # ---------- 周期刷新 ----------

    def _poll(self):
        # 电平 + 计时
        if self.rec.is_recording:
            ml, sl = self.rec.get_levels()
            self.mic_level["value"] = ml * 100
            self.sys_level["value"] = sl * 100
            self.timer_var.set(self._fmt(self.rec.elapsed()))

        # 处理后台转写消息
        try:
            while True:
                kind, payload = self.msg_q.get_nowait()
                if kind == "status":
                    self.status_var.set(payload)
                elif kind == "done":
                    self.status_var.set("文字稿已生成 ✓")
                    self.btn.config(state="normal")
                elif kind == "error":
                    self.btn.config(state="normal")
                    messagebox.showerror("转写失败", payload)
                    self.status_var.set("转写失败（录音文件已保存）")
        except queue.Empty:
            pass

        self.root.after(100, self._poll)

    @staticmethod
    def _fmt(seconds):
        s = int(seconds)
        h, s = divmod(s, 3600)
        m, s = divmod(s, 60)
        return "{:02d}:{:02d}:{:02d}".format(h, m, s)

    # ---------- 其它 ----------

    def _open_last(self):
        if self.last_session and os.path.isdir(self.last_session):
            webbrowser.open(self.last_session)

    def _on_close(self):
        if self.rec.is_recording:
            if not messagebox.askyesno("正在录音", "录音还在进行，确定退出并保存吗？"):
                return
            self.rec.stop()
        config.save_config(self.cfg)
        self.root.destroy()


def main():
    root = tk.Tk()
    RecoderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
