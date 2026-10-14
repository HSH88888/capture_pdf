"""
Capture PDF - 화면을 캡처해서 바로 PDF로 저장하는 Windows 프로그램

기능
  - 전체 화면 캡처 (모든 모니터)       : Ctrl+Shift+1
  - 영역 지정 캡처 (마우스 드래그)     : Ctrl+Shift+2
  - 캡처 즉시 PDF 파일로 저장 (파일명: capture_YYYYMMDD_HHMMSS.pdf)
  - "여러 장 모으기" 모드: 캡처를 모아 두었다가 한 개의 PDF(여러 페이지)로 저장
  - 단축키는 프로그램이 최소화되어 있어도 동작 (전역 단축키)

필요 패키지: Pillow  (pip install pillow)
"""

import ctypes
import ctypes.wintypes
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox

from PIL import Image, ImageGrab, ImageTk

APP_NAME = "Capture PDF"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".capture_pdf.json")
DEFAULT_SAVE_DIR = os.path.join(os.path.expanduser("~"), "Documents", "CapturePDF")

IS_WINDOWS = sys.platform == "win32"

# ---------------------------------------------------------------------------
# Windows 설정 (고해상도 DPI 대응, 전역 단축키)
# ---------------------------------------------------------------------------

def enable_dpi_awareness():
    """125%/150% 배율 화면에서도 실제 픽셀 좌표로 캡처하도록 설정."""
    if not IS_WINDOWS:
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def virtual_screen_rect():
    """모든 모니터를 합친 가상 화면의 (left, top, width, height)."""
    if IS_WINDOWS:
        u32 = ctypes.windll.user32
        return (u32.GetSystemMetrics(76), u32.GetSystemMetrics(77),
                u32.GetSystemMetrics(78), u32.GetSystemMetrics(79))
    return None


MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

HOTKEYS = {
    1: (MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, ord("1"), "full"),
    2: (MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, ord("2"), "region"),
}


class HotkeyThread(threading.Thread):
    """RegisterHotKey 로 전역 단축키를 등록하고, 눌리면 큐에 이벤트를 넣는다."""

    def __init__(self, event_queue):
        super().__init__(daemon=True)
        self.event_queue = event_queue
        self.failed = []

    def run(self):
        if not IS_WINDOWS:
            return
        u32 = ctypes.windll.user32
        for hk_id, (mods, vk, name) in HOTKEYS.items():
            if not u32.RegisterHotKey(None, hk_id, mods, vk):
                self.failed.append(name)
        msg = ctypes.wintypes.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY and msg.wParam in HOTKEYS:
                self.event_queue.put(HOTKEYS[msg.wParam][2])


# ---------------------------------------------------------------------------
# 캡처 / PDF 저장
# ---------------------------------------------------------------------------

def grab_full_screen():
    """모든 모니터를 포함한 전체 화면 캡처."""
    try:
        return ImageGrab.grab(all_screens=True)
    except TypeError:
        return ImageGrab.grab()


def save_images_as_pdf(images, path):
    """이미지 목록을 한 개의 PDF로 저장 (이미지 1장 = 1페이지)."""
    pages = [img.convert("RGB") for img in images]
    first, rest = pages[0], pages[1:]
    # resolution=96 → 화면에서 보던 크기 그대로 PDF 페이지 크기가 잡힌다.
    first.save(path, "PDF", resolution=96.0, save_all=True, append_images=rest)
    return path


def unique_pdf_path(folder, prefix="capture"):
    os.makedirs(folder, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(folder, f"{prefix}_{stamp}.pdf")
    n = 1
    while os.path.exists(path):
        path = os.path.join(folder, f"{prefix}_{stamp}_{n}.pdf")
        n += 1
    return path


class RegionSelector:
    """전체 화면 스크린샷을 띄워 놓고 마우스로 영역을 드래그해서 선택."""

    def __init__(self, root, screenshot, on_done):
        self.screenshot = screenshot
        self.on_done = on_done
        self.start = None
        self.rect_id = None

        rect = virtual_screen_rect()
        if rect:
            left, top, width, height = rect
        else:
            left, top = 0, 0
            width, height = screenshot.size

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.geometry(f"{width}x{height}{left:+d}{top:+d}")

        # 선택 중임을 알 수 있도록 화면을 살짝 어둡게 표시
        dim = Image.blend(screenshot.convert("RGB"),
                          Image.new("RGB", screenshot.size, (0, 0, 0)), 0.35)
        self.photo = ImageTk.PhotoImage(dim)
        self.bright = screenshot.convert("RGB")
        self.bright_photo = None

        self.canvas = tk.Canvas(self.win, width=width, height=height,
                                highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        self.canvas.create_text(
            width // 2, 40,
            text="드래그해서 캡처할 영역을 선택하세요  (취소: Esc / 마우스 오른쪽 버튼)",
            fill="white", font=("Malgun Gothic", 16, "bold"))
        self.preview_id = None

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", lambda e: self.finish(None))
        self.win.bind("<Escape>", lambda e: self.finish(None))

        self.win.after(50, self._focus)

    def _focus(self):
        self.win.lift()
        self.win.focus_force()
        self.canvas.focus_set()

    def on_press(self, event):
        self.start = (event.x, event.y)

    def _box(self, event):
        x0, y0 = self.start
        x1, y1 = event.x, event.y
        w, h = self.screenshot.size
        left, right = sorted((max(0, min(x0, w)), max(0, min(x1, w))))
        top, bottom = sorted((max(0, min(y0, h)), max(0, min(y1, h))))
        return left, top, right, bottom

    def on_drag(self, event):
        if not self.start:
            return
        box = self._box(event)
        # 선택 영역은 원래 밝기로 보여 준다
        if self.preview_id:
            self.canvas.delete(self.preview_id)
            self.preview_id = None
        if box[2] - box[0] > 1 and box[3] - box[1] > 1:
            self.bright_photo = ImageTk.PhotoImage(self.bright.crop(box))
            self.preview_id = self.canvas.create_image(box[0], box[1], anchor="nw",
                                                       image=self.bright_photo)
        if self.rect_id:
            self.canvas.coords(self.rect_id, *box)
            self.canvas.tag_raise(self.rect_id)
        else:
            self.rect_id = self.canvas.create_rectangle(*box, outline="#ff3b30", width=2)

    def on_release(self, event):
        if not self.start:
            return
        box = self._box(event)
        if box[2] - box[0] < 5 or box[3] - box[1] < 5:
            # 너무 작은 영역은 무시하고 다시 선택하게 한다
            self.start = None
            return
        self.finish(self.screenshot.crop(box))

    def finish(self, image):
        self.win.destroy()
        self.on_done(image)


# ---------------------------------------------------------------------------
# 메인 창
# ---------------------------------------------------------------------------

class App:
    def __init__(self, root):
        self.root = root
        self.config = self.load_config()
        self.pending = []      # "여러 장 모으기" 모드에서 모은 캡처들
        self.busy = False
        self.events = queue.Queue()

        root.title(APP_NAME)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        pad = {"padx": 10, "pady": 4}
        font = ("Malgun Gothic", 10)

        tk.Label(root, text="화면 캡처 → PDF 저장", font=("Malgun Gothic", 14, "bold")
                 ).pack(pady=(12, 6))

        btns = tk.Frame(root)
        btns.pack(**pad)
        tk.Button(btns, text="전체 화면 캡처\n(Ctrl+Shift+1)", width=18, height=3,
                  font=font, command=lambda: self.start_capture("full")).grid(row=0, column=0, padx=4)
        tk.Button(btns, text="영역 지정 캡처\n(Ctrl+Shift+2)", width=18, height=3,
                  font=font, command=lambda: self.start_capture("region")).grid(row=0, column=1, padx=4)

        # 저장 폴더
        folder = tk.Frame(root)
        folder.pack(fill="x", **pad)
        tk.Label(folder, text="저장 폴더:", font=font).pack(side="left")
        self.folder_var = tk.StringVar(value=self.config["save_dir"])
        tk.Entry(folder, textvariable=self.folder_var, width=36, font=font,
                 state="readonly").pack(side="left", padx=4)
        tk.Button(folder, text="변경", font=font, command=self.choose_folder).pack(side="left")
        tk.Button(folder, text="열기", font=font, command=self.open_folder).pack(side="left", padx=(4, 0))

        # 옵션
        opts = tk.Frame(root)
        opts.pack(fill="x", **pad)
        self.multi_var = tk.BooleanVar(value=self.config["multi_page"])
        tk.Checkbutton(opts, text="여러 장 모아서 한 PDF로 저장", font=font,
                       variable=self.multi_var, command=self.on_option_change).pack(anchor="w")
        self.open_var = tk.BooleanVar(value=self.config["open_after_save"])
        tk.Checkbutton(opts, text="저장 후 PDF 바로 열기", font=font,
                       variable=self.open_var, command=self.on_option_change).pack(anchor="w")
        self.hide_var = tk.BooleanVar(value=self.config["hide_window"])
        tk.Checkbutton(opts, text="캡처할 때 이 창 숨기기", font=font,
                       variable=self.hide_var, command=self.on_option_change).pack(anchor="w")

        # 여러 장 모드 컨트롤
        multi = tk.Frame(root)
        multi.pack(fill="x", **pad)
        self.count_label = tk.Label(multi, text="", font=font)
        self.count_label.pack(side="left")
        self.discard_btn = tk.Button(multi, text="비우기", font=font, command=self.discard_pending)
        self.discard_btn.pack(side="right")
        self.save_btn = tk.Button(multi, text="PDF로 저장", font=font, command=self.save_pending)
        self.save_btn.pack(side="right", padx=4)

        self.status = tk.Label(root, text="준비됨", anchor="w", relief="sunken",
                               font=("Malgun Gothic", 9))
        self.status.pack(fill="x", side="bottom")

        self.update_multi_ui()

        # 전역 단축키
        self.hotkeys = HotkeyThread(self.events)
        self.hotkeys.start()
        root.after(300, self.check_hotkey_registration)
        root.after(100, self.poll_events)

    # ----- 설정 -----
    def load_config(self):
        cfg = {"save_dir": DEFAULT_SAVE_DIR, "multi_page": False,
               "open_after_save": False, "hide_window": True}
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (OSError, ValueError):
            pass
        return cfg

    def save_config(self):
        self.config.update(save_dir=self.folder_var.get(),
                           multi_page=self.multi_var.get(),
                           open_after_save=self.open_var.get(),
                           hide_window=self.hide_var.get())
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def on_option_change(self):
        self.save_config()
        self.update_multi_ui()

    def choose_folder(self):
        path = filedialog.askdirectory(initialdir=self.folder_var.get())
        if path:
            self.folder_var.set(os.path.normpath(path))
            self.save_config()

    def open_folder(self):
        folder = self.folder_var.get()
        os.makedirs(folder, exist_ok=True)
        open_path(folder)

    # ----- 단축키 -----
    def check_hotkey_registration(self):
        if self.hotkeys.failed:
            self.set_status("일부 단축키 등록 실패(다른 프로그램이 사용 중): "
                            + ", ".join(self.hotkeys.failed))

    def poll_events(self):
        try:
            while True:
                self.start_capture(self.events.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self.poll_events)

    # ----- 캡처 -----
    def start_capture(self, mode):
        if self.busy:
            return
        self.busy = True
        hide = self.hide_var.get()
        if hide:
            self.prev_state = self.root.state()
            self.root.withdraw()
            self.root.update()
        # 창이 완전히 사라질 시간을 준 뒤 캡처
        self.root.after(250 if hide else 50, lambda: self._do_capture(mode, hide))

    def _do_capture(self, mode, hide):
        try:
            shot = grab_full_screen()
        except Exception as e:
            self._restore(hide)
            self.busy = False
            messagebox.showerror(APP_NAME, f"캡처 실패: {e}")
            return

        if mode == "full":
            self._restore(hide)
            self.handle_image(shot)
        else:
            def done(img):
                self._restore(hide)
                if img is None:
                    self.set_status("영역 캡처 취소됨")
                    self.busy = False
                else:
                    self.handle_image(img)
            RegionSelector(self.root, shot, done)

    def _restore(self, hide):
        if hide:
            self.root.deiconify()
            if getattr(self, "prev_state", "normal") == "iconic":
                self.root.iconify()

    def handle_image(self, img):
        try:
            if self.multi_var.get():
                self.pending.append(img)
                self.set_status(f"캡처 추가됨 ({img.width}x{img.height})")
                self.update_multi_ui()
            else:
                path = save_images_as_pdf([img], unique_pdf_path(self.folder_var.get()))
                self.after_save(path)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"저장 실패: {e}")
        finally:
            self.busy = False

    # ----- 여러 장 모드 -----
    def update_multi_ui(self):
        multi = self.multi_var.get()
        state = "normal" if multi and self.pending else "disabled"
        self.save_btn.config(state=state)
        self.discard_btn.config(state=state)
        if multi:
            self.count_label.config(text=f"모은 캡처: {len(self.pending)}장")
        else:
            self.count_label.config(text="캡처하면 바로 PDF로 저장됩니다.")

    def save_pending(self):
        if not self.pending:
            return
        try:
            path = save_images_as_pdf(self.pending, unique_pdf_path(self.folder_var.get()))
        except Exception as e:
            messagebox.showerror(APP_NAME, f"저장 실패: {e}")
            return
        count = len(self.pending)
        self.pending = []
        self.update_multi_ui()
        self.after_save(path, count)

    def discard_pending(self):
        if self.pending and messagebox.askyesno(
                APP_NAME, f"모은 캡처 {len(self.pending)}장을 버릴까요?"):
            self.pending = []
            self.update_multi_ui()
            self.set_status("모은 캡처를 비웠습니다")

    def after_save(self, path, pages=1):
        self.set_status(f"저장됨 ({pages}페이지): {path}")
        if self.open_var.get():
            open_path(path)

    def set_status(self, text):
        self.status.config(text=text)

    def on_close(self):
        if self.pending and not messagebox.askyesno(
                APP_NAME, f"저장하지 않은 캡처 {len(self.pending)}장이 있습니다. 종료할까요?"):
            return
        self.save_config()
        self.root.destroy()


def open_path(path):
    try:
        if IS_WINDOWS:
            os.startfile(path)
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}" >/dev/null 2>&1 &')
    except OSError:
        pass


def main():
    enable_dpi_awareness()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
