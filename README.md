# Recoder · 双向会议录音工具

线上会议时同时录下**对方的声音**（系统播放）和**我的声音**（麦克风），合成一份完整录音，
并自动生成区分"我 / 对方"的逐字文字稿。Windows 11 桌面小工具。

## 解决的痛点
普通录音软件只能录一路：要么只录到麦克风（只有我），要么只录到系统声（只有对方）。主流会议软件又有音频转文字的用量限制。
Recoder 同时抓两路：

- **对方的声音** = 系统回环录音（WASAPI Loopback，抓操作系统播放流）
- **我的声音** = 麦克风录音

> 戴「带麦克风的耳机」也完全没问题，效果反而更好：对方声音只进你耳朵、不会被麦克风回收，
> 所以"我 / 对方"两轨分得更干净。

## 功能
- **双向录音**：选设备 → 开始/停止 → 实时电平条确认两路都有声
- **逐字文字稿**：录完自动用本地 [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
  分别转写两轨，合并成带说话人标签的 `transcript.md`（两路是物理分开录的，说话人天然可分，无需声纹分离）

录音结束后，每场会议输出一个目录，最终只保留两个文件：

```
recordings/2026-06-02_153012/
  mixed.wav        # 整场录音（双方混音，直接能听）
  transcript.md    # 带 [时间] 我/对方 标签的逐字稿
```

---

## 运行要求
- **Windows 10/11**（WASAPI Loopback 是 Windows 音频接口）
- **Python 3.9+**，且在 PATH 中

## 安装
```powershell
python -m pip install -r requirements.txt
```
或双击 `install.bat`。

> 在国内或需要代理时，pip 与首次下载语音模型可能要走代理：
> `set HTTP_PROXY=http://127.0.0.1:端口` 和 `set HTTPS_PROXY=...` 后再安装。

## 运行
```powershell
python app.py
```
或双击 `run.bat`。

## 使用
1. 「麦克风」选你的输入设备，「系统回环」一般保持`（系统默认）`即可
   （插耳机后系统默认输出会自动切到耳机，回环跟着走）。
2. 先放一段有声内容 + 对麦说话，确认两根**电平条**都跳动。
3. 点「开始录音」，结束点「停止录音」，随后自动转写出文字稿。

---

## 配置（settings.json，运行后自动生成）
| 字段 | 说明 | 默认 |
|---|---|---|
| `whisper_model` | tiny/base/small/medium/large-v3，越大越准越慢 | `small` |
| `whisper_device` | `cpu` 或 `cuda`（GPU 加速） | `cpu` |
| `whisper_compute` | CPU 用 `int8`；GPU 用 `int8_float16` 或 `float16` | `int8` |
| `language` | 转写语言，`zh` 中文；留空自动识别 | `zh` |
| `auto_transcribe` | 录完是否自动转写 | `true` |

**GPU 加速（可选）**：把 `whisper_device` 改 `cuda`、`whisper_compute` 改 `int8_float16`，
需先装好 CUDA + cuDNN。装不上也能用，默认 CPU 即可，只是慢一些。

## 常见问题
- **某一路电平条不动 / 录出来是哑的**：检查 Windows「声音设置」里默认播放设备是否为当前在用设备；
  麦克风是否被静音或被其它程序独占。开录前用电平条确认。
- **首次转写很慢/卡住**：第一次会自动下载 whisper 模型（`small` 约几百 MB），需联网，下完即快。
- **`soundcard` 找不到设备**：确认在 Windows 原生 Python 下运行。

## 文件结构
```
app.py            GUI 入口（tkinter）
recorder.py       双路采集 + 混音 + 保存
transcribe.py     双轨转写 + 合并
config.py         读写 settings.json
requirements.txt
```

## 技术栈
[soundcard](https://github.com/bastibe/SoundCard)（采集）·
[soundfile](https://github.com/bastibe/python-soundfile)（写 wav）·
numpy（混音）· [faster-whisper](https://github.com/SYSTRAN/faster-whisper)（本地转写）· tkinter（界面）

## License
[MIT](LICENSE)

## 最终效果

<img width="577" height="465" alt="image" src="https://github.com/user-attachments/assets/0ca3cfa1-d0c7-4599-9982-5bbdaf762e1e" />

文件存储：音频+文字记录
<img width="556" height="112" alt="image" src="https://github.com/user-attachments/assets/d14a888c-c088-4424-aa8e-e41d91450ab7" />

  
