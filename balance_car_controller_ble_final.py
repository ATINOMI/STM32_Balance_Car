"""
Balance Car Controller - BLE Final Variant
HC-04BLE + bleak
"""

from bleak import BleakClient
import asyncio
import threading
import re

UART_SERVICE = "0000FFE0-0000-1000-8000-00805F9B34FB"
UART_TX = "0000FFE1-0000-1000-8000-00805F9B34FB"

class BLEManager:
    def __init__(self):
        self.client = None
        self.connected = False
        self.last_error = ""
        self.bytes_sent = 0
        self.packets_sent = 0
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._run_loop, daemon=True).start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    @staticmethod
    def instance_id_to_mac(iid: str):
        m = re.search(r"DEV_([0-9A-Fa-f]{12})", iid)
        if not m:
            return None
        raw = m.group(1)
        return ":".join(raw[i:i+2] for i in range(0, 12, 2)).upper()

    async def _connect(self, mac):
        self.client = BleakClient(mac)
        await self.client.connect()
        self.connected = await self.client.is_connected()
        return self.connected

    def connect(self, mac):
        fut = asyncio.run_coroutine_threadsafe(
            self._connect(mac), self.loop
        )
        return fut.result(timeout=10)

    async def _disconnect(self):
        if self.client:
            await self.client.disconnect()
        self.connected = False

    def disconnect(self):
        asyncio.run_coroutine_threadsafe(
            self._disconnect(), self.loop
        )

    async def _send(self, payload: bytes):
        await self.client.write_gatt_char(
            UART_TX,
            payload,
            response=False
        )

    def send(self, lh, lv, rh, rv):
        if not self.connected:
            return False

        msg = (
            f"joystick,{int(lh)},{int(lv)},"
            f"{int(rh)},{int(rv)}\n"
        ).encode("utf-8")

        asyncio.run_coroutine_threadsafe(
            self._send(msg),
            self.loop
        )

        self.bytes_sent += len(msg)
        self.packets_sent += 1
        return True

# ===== Original source below for manual merge =====

"""
平衡车上位机控制程序  —  Claude Design Style
硬件：HC-04 蓝牙模块（Windows WinRT 扫描 → 自动配对 → 虚拟 COMx）+ PS5 DualSense
协议：joystick,LH,LV,RH,RV\n  （无方括号，strtok 直接解析）
STM32 使用：lv → speed_pid.target_（÷25），rh → diff_pwm（÷2）
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import math
import asyncio
import subprocess
import re
import serial
import serial.tools.list_ports

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# WinRT 蓝牙扫描（可选依赖）
try:
    from winrt.windows.devices.bluetooth import BluetoothDevice
    from winrt.windows.devices.enumeration import DeviceInformation
    WINRT_AVAILABLE = True
except ImportError:
    WINRT_AVAILABLE = False

# ─────────────────────────────────────────────
#  常量
# ─────────────────────────────────────────────
SEND_HZ       = 20
SEND_INTERVAL = 1.0 / SEND_HZ
DEADZONE      = 0.08
AXIS_LH, AXIS_LV, AXIS_RH, AXIS_RV = 0, 1, 2, 3

# HC-04 经典蓝牙 SPP 服务 UUID（用于 WinRT AQS 过滤）
BT_SPP_AQS = (
    'System.Devices.Aep.ProtocolId:="{e0cbf06c-cd8b-4647-bb8a-263b43f0f974}"'
    ' AND System.Devices.Aep.IsPaired:=System.StructuredQueryType.Boolean#False'
)
BT_AQS_ALL = (
    'System.Devices.Aep.ProtocolId:="{e0cbf06c-cd8b-4647-bb8a-263b43f0f974}"'
)

# ─────────────────────────────────────────────
#  蓝牙扫描模块
# ─────────────────────────────────────────────
class BluetoothScanner:
    """
    扫描附近经典蓝牙设备，返回 list[dict]
    每项：{name, address, paired, id}
    """

    @staticmethod
    def scan_winrt(timeout: float = 8.0) -> list:
        """使用 Windows WinRT API 扫描（需要 winrt 包）"""
        results = []

        async def _scan():
            # 先查已配对设备
            paired = await DeviceInformation.find_all_async(
                'System.Devices.Aep.ProtocolId:="{e0cbf06c-cd8b-4647-bb8a-263b43f0f974}"'
                ' AND System.Devices.Aep.IsPaired:=System.StructuredQueryType.Boolean#True'
            )
            for d in paired:
                results.append({
                    "name":    d.name or "Unknown",
                    "address": "",
                    "paired":  True,
                    "id":      d.id,
                })
            # 再查未配对（主动扫描）
            unpaired = await DeviceInformation.find_all_async(BT_SPP_AQS)
            for d in unpaired:
                results.append({
                    "name":    d.name or "Unknown",
                    "address": "",
                    "paired":  False,
                    "id":      d.id,
                })

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(asyncio.wait_for(_scan(), timeout))
        except asyncio.TimeoutError:
            pass
        finally:
            loop.close()
        return results

    @staticmethod
    def scan_powershell(timeout: float = 10.0) -> list:
        """用 PowerShell Get-PnpDevice 查询所有已配对蓝牙设备"""
        ps_cmd = (
            "Get-PnpDevice -Class Bluetooth -ErrorAction SilentlyContinue | "
            "Select-Object FriendlyName, InstanceId | "
            "ConvertTo-Json -Compress"
        )
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, text=True, timeout=timeout
            )
            import json
            stdout = r.stdout.strip()
            if not stdout:
                return []
            raw = json.loads(stdout)
            if isinstance(raw, dict):
                raw = [raw]

            # InstanceId 前缀对照：
            #   BTHLE\DEV_...       → BLE 真实外设（如 HC-04BLE）✓
            #   BTHLEDEVICE\...     → BLE 服务层/GATT 服务  ✗
            #   BTHENUM\DEV_...     → 经典蓝牙真实外设        ✓
            #   BTHENUM\{UUID}...   → 经典蓝牙服务层         ✗
            #   BTH\MS_...          → Windows 系统驱动        ✗
            #   USB\...             → 蓝牙适配器硬件          ✗
            KEEP_PREFIXES = ("BTHLE\\DEV_", "BTHENUM\\DEV_")

            results = []
            seen = set()
            for d in raw:
                name = (d.get("FriendlyName") or "").strip()
                iid  = (d.get("InstanceId")   or "").strip()
                if not name:
                    continue
                # 只保留真实外设前缀
                iid_upper = iid.upper()
                if not any(iid_upper.startswith(p.upper()) for p in KEEP_PREFIXES):
                    continue
                # 去重
                if name.lower() in seen:
                    continue
                seen.add(name.lower())
                results.append({
                    "name":    name,
                    "address": iid,
                    "paired":  True,
                    "id":      iid,
                })
            return results
        except Exception:
            return []

    @staticmethod
    def find_com_for_device(device_name: str) -> str:
        """
        在已注册虚拟串口里找名称含 device_name 关键词的 COM 口
        pyserial list_ports 会返回端口的描述字段，HC-04 配对后通常描述含设备名
        """
        keyword = device_name.lower().replace("-", "").replace(" ", "")
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").lower().replace("-", "").replace(" ", "")
            if keyword in desc or "hc" in desc or "bluetooth" in desc.lower():
                return p.device
        return ""

    @staticmethod
    def pair_device_powershell(device_id: str) -> bool:
        """
        触发 Windows 系统蓝牙配对对话框（只能对未配对设备用）
        真正的静默配对需要 WinRT BluetoothDevice.pair_async，
        这里用 devcon 或 bthprops 调起系统 UI 作为备用
        """
        ps_cmd = f"""
$device = Get-PnpDevice | Where-Object {{ $_.InstanceId -eq '{device_id}' }}
if ($device) {{ $device | Enable-PnpDevice -Confirm:$false }}
"""
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, timeout=10
            )
            return True
        except Exception:
            return False


# ─────────────────────────────────────────────
#  手柄读取模块
# ─────────────────────────────────────────────
class GamepadReader:
    def __init__(self):
        self._lh = self._lv = self._rh = self._rv = 0.0
        self._lock = threading.Lock()
        self._running = False
        self.connected = False
        self.joystick = None

    def start(self):
        if not PYGAME_AVAILABLE:
            return False
        pygame.init()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            return False
        self.joystick = pygame.joystick.Joystick(0)
        self.joystick.init()
        self.connected = True
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()
        return True

    def stop(self):
        self._running = False
        self.connected = False
        if PYGAME_AVAILABLE:
            try:
                pygame.quit()
            except Exception:
                pass

    def get_axes(self):
        with self._lock:
            return (self._lh, self._lv, self._rh, self._rv)

    def get_name(self):
        return self.joystick.get_name() if self.joystick else "未连接"

    def _loop(self):
        while self._running:
            pygame.event.pump()
            if self.joystick and self.joystick.get_numaxes() > 3:
                raw = [self.joystick.get_axis(i) for i in (AXIS_LH, AXIS_LV, AXIS_RH, AXIS_RV)]
                processed = [self._process(v) for v in raw]
                with self._lock:
                    self._lh, self._lv, self._rh, self._rv = processed
            time.sleep(0.01)

    @staticmethod
    def _process(v: float) -> float:
        if abs(v) < DEADZONE:
            return 0.0
        sign = 1 if v > 0 else -1
        return round(sign * (abs(v) - DEADZONE) / (1.0 - DEADZONE) * 100)


# ─────────────────────────────────────────────
#  串口管理模块
# ─────────────────────────────────────────────
class SerialManager:
    def __init__(self):
        self.ser = None
        self.connected = False
        self._lock = threading.Lock()
        self.last_error = ""
        self.bytes_sent = 0
        self.packets_sent = 0

    def connect(self, port: str, baud: int = 9600) -> bool:
        try:
            with self._lock:
                if self.ser and self.ser.is_open:
                    self.ser.close()
                self.ser = serial.Serial(port, baud, timeout=1)
                self.connected = True
                self.last_error = ""
                return True
        except Exception as e:
            self.last_error = str(e)
            self.connected = False
            return False

    def disconnect(self):
        with self._lock:
            if self.ser and self.ser.is_open:
                self.ser.close()
            self.connected = False

    def send(self, lh, lv, rh, rv) -> bool:
        msg = f"joystick,{int(lh)},{int(lv)},{int(rh)},{int(rv)}\n"
        try:
            with self._lock:
                if self.ser and self.ser.is_open:
                    data = msg.encode("ascii")
                    self.ser.write(data)
                    self.bytes_sent += len(data)
                    self.packets_sent += 1
                    return True
        except Exception as e:
            self.last_error = str(e)
            self.connected = False
        return False

    @staticmethod
    def list_ports():
        return [p.device for p in serial.tools.list_ports.comports()]


# ─────────────────────────────────────────────
#  配色 (Claude Design System)
# ─────────────────────────────────────────────
C = {
    "bg0": "#FFFFFF", "bg1": "#F5F4EF", "bg2": "#EFEDE6", "bg3": "#E8E5DB",
    "text0": "#1A1A19", "text1": "#3D3D38", "text2": "#6B6B5F", "text3": "#9B9B90",
    "acc0": "#F2C4A0", "acc1": "#E8A07A", "acc2": "#D97757", "acc3": "#C8684A",
    "green": "#22C55E", "red": "#EF4444", "blue": "#3B82F6", "amber": "#F59E0B",
    "green_bg": "#F0FDF4", "red_bg": "#FEF2F2", "blue_bg": "#EFF6FF",
    "amber_bg": "#FFFBEB",
}
FONT_SM   = ("Segoe UI",  9)
FONT_TINY = ("Segoe UI",  8)
FONT_MONO = ("Consolas", 10)
FONT_H1   = ("Segoe UI", 13, "bold")
FONT_BOLD = ("Segoe UI",  9, "bold")


# ─────────────────────────────────────────────
#  蓝牙设备选择弹窗
# ─────────────────────────────────────────────
class BluetoothDialog(tk.Toplevel):
    """弹出蓝牙扫描窗口，选中设备后返回 COM 口字符串"""

    def __init__(self, parent, on_select_port):
        super().__init__(parent)
        self.on_select_port = on_select_port   # callback(port: str)
        self._devices = []
        self._scan_thread = None

        self.title("搜索蓝牙设备")
        self.configure(bg=C["bg1"])
        self.resizable(False, False)
        self.grab_set()   # modal
        self.transient(parent)

        self._build()
        self._do_scan()

        # 居中
        self.update_idletasks()
        pw = parent.winfo_x() + parent.winfo_width()  // 2
        ph = parent.winfo_y() + parent.winfo_height() // 2
        self.geometry(f"460x480+{pw - 230}+{ph - 240}")

    # ── UI ──────────────────────────────────
    def _build(self):
        # 标题行
        hdr = tk.Frame(self, bg=C["bg1"],
                        highlightbackground=C["bg3"], highlightthickness=1)
        hdr.pack(fill="x")
        inner = tk.Frame(hdr, bg=C["bg1"])
        inner.pack(padx=16, pady=12, fill="x")
        tk.Label(inner, text="搜索蓝牙设备",
                 font=FONT_H1, fg=C["text0"], bg=C["bg1"]).pack(side="left")
        self.scan_btn = self._pill_btn(inner, "重新扫描", self._do_scan)
        self.scan_btn.pack(side="right")

        tk.Frame(self, height=1, bg=C["bg3"]).pack(fill="x")

        # 状态条
        self.status_var = tk.StringVar(value="正在扫描附近蓝牙设备…")
        status_bar = tk.Frame(self, bg=C["amber_bg"],
                               highlightbackground=C["amber"],
                               highlightthickness=1)
        status_bar.pack(fill="x", padx=14, pady=(12, 0))
        self.status_lbl = tk.Label(status_bar,
                                   textvariable=self.status_var,
                                   font=FONT_TINY, fg=C["amber"],
                                   bg=C["amber_bg"], padx=8, pady=5,
                                   anchor="w")
        self.status_lbl.pack(fill="x")

        # 进度条（扫描动画用）
        self.progress = ttk.Progressbar(self, mode="indeterminate",
                                        style="BT.Horizontal.TProgressbar",
                                        length=432)
        self.progress.pack(padx=14, pady=4)

        # 设备列表区（可滚动）
        list_outer = tk.Frame(self, bg=C["bg0"],
                              highlightbackground=C["bg3"],
                              highlightthickness=1)
        list_outer.pack(fill="both", expand=True, padx=14, pady=8)

        # 列头
        tk.Label(list_outer,
                 text="  设备名称                              状态",
                 font=("Segoe UI", 8, "bold"),
                 fg=C["text3"], bg=C["bg1"],
                 anchor="w").pack(fill="x")
        tk.Frame(list_outer, height=1, bg=C["bg3"]).pack(fill="x")

        # Canvas + Scrollbar
        canvas_wrap = tk.Frame(list_outer, bg=C["bg0"])
        canvas_wrap.pack(fill="both", expand=True)

        self._list_canvas = tk.Canvas(canvas_wrap, bg=C["bg0"],
                                      highlightthickness=0,
                                      yscrollincrement=1)
        self._list_canvas.pack(side="left", fill="both", expand=True)

        list_sb = ttk.Scrollbar(canvas_wrap, orient="vertical",
                                command=self._list_canvas.yview)
        list_sb.pack(side="right", fill="y")
        self._list_canvas.configure(yscrollcommand=list_sb.set)

        # 真正装设备行的 Frame，嵌在 Canvas 里
        self.listbox_frame = tk.Frame(self._list_canvas, bg=C["bg0"])
        self._list_window = self._list_canvas.create_window(
            (0, 0), window=self.listbox_frame, anchor="nw")

        # 让 Frame 宽度随 Canvas 变化
        def _on_canvas_resize(e):
            self._list_canvas.itemconfig(self._list_window, width=e.width)
        self._list_canvas.bind("<Configure>", _on_canvas_resize)

        # Frame 内容变化时更新 scrollregion
        def _on_frame_resize(e):
            self._list_canvas.configure(
                scrollregion=self._list_canvas.bbox("all"))
        self.listbox_frame.bind("<Configure>", _on_frame_resize)

        # 鼠标滚轮绑定
        def _on_mousewheel(e):
            self._list_canvas.yview_scroll(-1 * (e.delta // 120), "units")
        self._list_canvas.bind("<MouseWheel>", _on_mousewheel)
        self.listbox_frame.bind("<MouseWheel>", _on_mousewheel)

        self.empty_label = tk.Label(
            self.listbox_frame,
            text="未发现设备\n\n请确保小车已开机并处于可发现状态",
            font=FONT_SM, fg=C["text3"], bg=C["bg0"],
            pady=40)
        self.empty_label.pack(expand=True)

        # 手动输入 COM 口备用
        manual_frame = tk.Frame(self, bg=C["bg1"],
                                 highlightbackground=C["bg3"],
                                 highlightthickness=1)
        manual_frame.pack(fill="x", padx=14, pady=(0, 14))
        inner2 = tk.Frame(manual_frame, bg=C["bg1"])
        inner2.pack(padx=12, pady=10, fill="x")
        tk.Label(inner2, text="手动输入 COM 口", font=FONT_TINY,
                 fg=C["text2"], bg=C["bg1"]).pack(side="left")
        self.manual_var = tk.StringVar()
        tk.Entry(inner2, textvariable=self.manual_var,
                 font=FONT_MONO, width=8,
                 bg=C["bg0"], fg=C["text0"],
                 relief="solid", bd=1,
                 highlightthickness=1,
                 highlightbackground=C["bg3"],
                 highlightcolor=C["acc2"]
                 ).pack(side="left", padx=8)
        self._pill_btn(inner2, "直接连接", self._manual_connect,
                       color=C["acc2"]).pack(side="left")

        # TTK 进度条样式
        s = ttk.Style()
        s.configure("BT.Horizontal.TProgressbar",
                    troughcolor=C["bg3"],
                    background=C["acc2"],
                    bordercolor=C["bg3"],
                    lightcolor=C["acc1"],
                    darkcolor=C["acc3"])

    # ── 工具 ────────────────────────────────
    def _pill_btn(self, parent, text, cmd, color=None):
        bg  = color or C["bg3"]
        fg  = "#FFFFFF" if color else C["text1"]
        hbg = C["acc3"] if color else C["bg3"]
        btn = tk.Label(parent, text=text, font=FONT_BOLD,
                       fg=fg, bg=bg, padx=12, pady=4,
                       cursor="hand2")
        btn.bind("<Button-1>", lambda e: cmd())
        btn.bind("<Enter>",    lambda e: btn.config(bg=hbg))
        btn.bind("<Leave>",    lambda e: btn.config(bg=bg))
        return btn

    def _device_row(self, parent, dev: dict, idx: int) -> tk.Frame:
        """创建一行设备条目"""
        row_bg  = C["bg0"] if idx % 2 == 0 else C["bg1"]
        row = tk.Frame(parent, bg=row_bg, cursor="hand2")
        row.pack(fill="x")

        # 蓝牙图标（文字代替）
        tk.Label(row, text="⬡", font=("Segoe UI", 11),
                 fg=C["acc1"], bg=row_bg, padx=10, pady=10).pack(side="left")

        # 名称 + 地址
        info = tk.Frame(row, bg=row_bg)
        info.pack(side="left", fill="x", expand=True, pady=8)
        tk.Label(info, text=dev["name"], font=FONT_BOLD,
                 fg=C["text0"], bg=row_bg, anchor="w").pack(fill="x")
        sub = dev.get("address", "") or dev.get("id", "")[:40]
        tk.Label(info, text=sub, font=FONT_TINY,
                 fg=C["text3"], bg=row_bg, anchor="w").pack(fill="x")

        # 配对状态标签
        if dev["paired"]:
            tag_bg, tag_fg, tag_txt = C["green_bg"], C["green"], "已配对"
        else:
            tag_bg, tag_fg, tag_txt = C["amber_bg"], C["amber"], "未配对"
        tk.Label(row, text=f" {tag_txt} ", font=FONT_TINY,
                 fg=tag_fg, bg=tag_bg, padx=6, pady=2).pack(side="right", padx=10)

        # 整行点击 → 连接；滚轮 → 透传给 canvas
        def _mw(e):
            self._list_canvas.yview_scroll(-1*(e.delta//120), "units")
        for widget in [row, info] + list(info.winfo_children()) + list(row.winfo_children()):
            widget.bind("<Button-1>", lambda e, d=dev: self._on_device_click(d))
            widget.bind("<Enter>",    lambda e, r=row, b=row_bg: r.config(bg=C["acc0"]))
            widget.bind("<Leave>",    lambda e, r=row, b=row_bg: r.config(bg=b))
            widget.bind("<MouseWheel>", _mw)

        tk.Frame(parent, height=1, bg=C["bg3"]).pack(fill="x")
        return row

    # ── 扫描逻辑 ───────────────────────────
    def _do_scan(self):
        # 清空列表，重置滚动
        for w in self.listbox_frame.winfo_children():
            w.destroy()
        self._list_canvas.yview_moveto(0)
        self.empty_label = tk.Label(
            self.listbox_frame,
            text="正在扫描…",
            font=FONT_SM, fg=C["text3"], bg=C["bg0"], pady=40)
        self.empty_label.pack(expand=True)

        self.status_var.set("正在扫描附近蓝牙设备…")
        self._set_status_color(C["amber_bg"], C["amber"])
        self.progress.start(12)

        self._scan_thread = threading.Thread(target=self._scan_worker, daemon=True)
        self._scan_thread.start()

    def _scan_worker(self):
        devices = []
        if WINRT_AVAILABLE:
            try:
                devices = BluetoothScanner.scan_winrt(timeout=8.0)
            except Exception:
                pass
        # fallback：PowerShell 查已配对设备
        if not devices:
            devices = BluetoothScanner.scan_powershell(timeout=6.0)

        self.after(0, self._on_scan_done, devices)

    def _on_scan_done(self, devices: list):
        self.progress.stop()
        self._devices = devices

        for w in self.listbox_frame.winfo_children():
            w.destroy()

        if not devices:
            self.status_var.set("未发现设备  ·  请确认小车已开机")
            self._set_status_color(C["red_bg"], C["red"])
            tk.Label(self.listbox_frame,
                     text="未发现任何蓝牙设备\n\n"
                          "• 请确认 HC-04 已上电（LED 快闪）\n"
                          "• 尝试先在 Windows 设置 → 蓝牙中手动配对\n"
                          "• 配对后直接在下方手动输入 COM 口",
                     font=FONT_SM, fg=C["text3"], bg=C["bg0"],
                     pady=30, justify="left").pack(expand=True)
        else:
            n = len(devices)
            self.status_var.set(f"发现 {n} 个设备  ·  点击选择")
            self._set_status_color(C["green_bg"], C["green"])
            for i, dev in enumerate(devices):
                self._device_row(self.listbox_frame, dev, i)

    def _set_status_color(self, bg, fg):
        self.status_lbl.config(bg=bg, fg=fg)
        self.status_lbl.master.config(
            bg=bg, highlightbackground=fg)

    # ── 选择设备 ────────────────────────────
    def _on_device_click(self, dev: dict):
        name = dev["name"]

        # 1. 先从已注册 COM 口里匹配（最快）
        port = BluetoothScanner.find_com_for_device(name)

        # 2. 没找到 → 查所有 COM 口描述
        if not port:
            # HC-04 配对后 Windows 会建两个口，取第一个
            bt_ports = [
                p.device for p in serial.tools.list_ports.comports()
                if "bluetooth" in (p.description or "").lower()
                or "hc" in (p.description or "").lower()
                or "standard" in (p.description or "").lower()
            ]
            if bt_ports:
                port = bt_ports[0]

        if port:
            self.status_var.set(f"已匹配到 {port}，正在连接…")
            self._set_status_color(C["green_bg"], C["green"])
            self.after(300, lambda: self._finish(port))
        else:
            # 3. 找不到 → 提示用户手动输入
            self.status_var.set(
                f"已选中「{name}」但未找到对应 COM 口，请在下方手动输入")
            self._set_status_color(C["amber_bg"], C["amber"])
            self.manual_var.set("")

    def _manual_connect(self):
        port = self.manual_var.get().strip().upper()
        if not port:
            return
        if not port.startswith("COM"):
            port = "COM" + port
        self._finish(port)

    def _finish(self, port: str):
        self.grab_release()
        self.destroy()
        self.on_select_port(port)


# ─────────────────────────────────────────────
#  主 GUI
# ─────────────────────────────────────────────
class BalanceCarGUI:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.gamepad = GamepadReader()
        self.serial_mgr = SerialManager()
        self._running = True
        self._axes = (0, 0, 0, 0)

        self._build_ui()
        self._style_ttk()
        self._refresh_ports()
        self._start_gamepad()
        self._start_send_loop()
        self._update_ui()

    # ══════════════════════════════════════════
    #  TTK 样式
    # ══════════════════════════════════════════
    def _style_ttk(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("Claude.TCombobox",
                    fieldbackground=C["bg0"], background=C["bg1"],
                    foreground=C["text0"], selectbackground=C["acc0"],
                    selectforeground=C["text0"], bordercolor=C["bg3"],
                    arrowcolor=C["text2"], padding=(6, 4))
        s.map("Claude.TCombobox",
              fieldbackground=[("readonly", C["bg0"])],
              bordercolor=[("focus", C["acc2"])])
        s.configure("Claude.Vertical.TScrollbar",
                    background=C["bg3"], troughcolor=C["bg1"],
                    bordercolor=C["bg2"], arrowcolor=C["text2"], relief="flat")

    # ══════════════════════════════════════════
    #  UI 构建
    # ══════════════════════════════════════════
    def _build_ui(self):
        self.root.title("Balance Car Controller")
        self.root.configure(bg=C["bg2"])
        self.root.resizable(False, False)

        # ── 标题栏 ────────────────────────────
        header = tk.Frame(self.root, bg=C["bg1"],
                          highlightbackground=C["bg3"], highlightthickness=1)
        header.pack(fill="x")
        inner_h = tk.Frame(header, bg=C["bg1"])
        inner_h.pack(padx=20, pady=12, fill="x")

        logo_row = tk.Frame(inner_h, bg=C["bg1"])
        logo_row.pack(side="left")
        dot_c = tk.Canvas(logo_row, width=10, height=10,
                          bg=C["bg1"], highlightthickness=0)
        dot_c.pack(side="left", padx=(0, 8))
        dot_c.create_oval(1, 1, 9, 9, fill=C["acc2"], outline="")
        tk.Label(logo_row, text="Balance Car Controller",
                 font=FONT_H1, fg=C["text0"], bg=C["bg1"]).pack(side="left")

        tk.Label(inner_h, text=" HC-04 · DualSense · 20Hz ",
                 font=("Segoe UI", 8, "bold"),
                 fg=C["acc3"], bg=C["acc0"], padx=8, pady=3
                 ).pack(side="right")

        # ── 主内容区 ──────────────────────────
        shell = tk.Frame(self.root, bg=C["bg2"])
        shell.pack(padx=20, pady=16, fill="both")

        left = tk.Frame(shell, bg=C["bg2"])
        left.pack(side="left", fill="both", anchor="n")
        right = tk.Frame(shell, bg=C["bg2"])
        right.pack(side="left", fill="both", padx=(14, 0), anchor="n")

        self._build_serial_panel(left)
        self._build_gamepad_panel(left)
        self._build_stick_panel(right)
        self._build_log_panel(right)

    # ── 通用卡片 ──────────────────────────────
    def _card(self, parent, title: str) -> tk.Frame:
        outer = tk.Frame(parent, bg=C["bg0"],
                         highlightbackground=C["bg3"], highlightthickness=1)
        outer.pack(fill="x", pady=(0, 10))
        tk.Label(outer, text=title.upper(),
                 font=("Segoe UI", 8, "bold"),
                 fg=C["text3"], bg=C["bg1"],
                 padx=14, pady=7, anchor="w").pack(fill="x")
        tk.Frame(outer, height=1, bg=C["bg3"]).pack(fill="x")
        content = tk.Frame(outer, bg=C["bg0"], padx=14, pady=12)
        content.pack(fill="x")
        return content

    # ── 蓝牙串口面板 ──────────────────────────
    def _build_serial_panel(self, parent):
        f = self._card(parent, "蓝牙串口连接")

        # ① 搜索设备按钮（主入口）
        search_row = tk.Frame(f, bg=C["bg0"])
        search_row.pack(fill="x", pady=(0, 10))
        search_btn = tk.Label(search_row,
                              text="  🔍  搜索蓝牙设备  ",
                              font=("Segoe UI", 9, "bold"),
                              fg="#FFFFFF", bg=C["acc2"],
                              padx=12, pady=6, cursor="hand2")
        search_btn.pack(side="left")
        search_btn.bind("<Button-1>", lambda e: self._open_bt_dialog())
        search_btn.bind("<Enter>",    lambda e: search_btn.config(bg=C["acc3"]))
        search_btn.bind("<Leave>",    lambda e: search_btn.config(bg=C["acc2"]))

        tk.Label(search_row,
                 text="自动扫描并配对 HC-04",
                 font=FONT_TINY, fg=C["text3"], bg=C["bg0"],
                 padx=10).pack(side="left")

        tk.Frame(f, height=1, bg=C["bg3"]).pack(fill="x", pady=(0, 10))

        # ② 手动端口选择（备用）
        tk.Label(f, text="手动选择端口",
                 font=("Segoe UI", 8, "bold"),
                 fg=C["text3"], bg=C["bg0"], anchor="w").pack(fill="x", pady=(0, 6))

        row = tk.Frame(f, bg=C["bg0"])
        row.pack(fill="x", pady=(0, 8))
        tk.Label(row, text="端口", font=FONT_SM, fg=C["text2"],
                 bg=C["bg0"], width=5, anchor="w").pack(side="left")
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(row, textvariable=self.port_var,
                                       width=12, style="Claude.TCombobox",
                                       state="readonly")
        self.port_combo.pack(side="left", padx=(4, 4))
        self._icon_btn(row, "↺", self._refresh_ports).pack(side="left")

        row2 = tk.Frame(f, bg=C["bg0"])
        row2.pack(fill="x", pady=(0, 12))
        tk.Label(row2, text="波特率", font=FONT_SM, fg=C["text2"],
                 bg=C["bg0"], width=5, anchor="w").pack(side="left")
        self.baud_var = tk.StringVar(value="9600")
        ttk.Combobox(row2, textvariable=self.baud_var, width=10,
                     style="Claude.TCombobox", state="readonly",
                     values=["9600","19200","38400","57600","115200"]
                     ).pack(side="left", padx=4)

        # ③ 连接按钮 + 状态
        btn_row = tk.Frame(f, bg=C["bg0"])
        btn_row.pack(fill="x", pady=(0, 8))
        self.conn_btn = tk.Label(btn_row,
                                 text="连接",
                                 font=FONT_BOLD,
                                 fg="#FFFFFF", bg=C["acc2"],
                                 padx=16, pady=5, cursor="hand2")
        self.conn_btn.pack(side="left")
        self.conn_btn.bind("<Button-1>", lambda e: self._toggle_serial())
        self.conn_btn.bind("<Enter>",    lambda e: self.conn_btn.config(bg=C["acc3"]))
        self.conn_btn.bind("<Leave>",    lambda e: self._conn_btn_leave())

        self.serial_status = tk.Label(btn_row, text="● 未连接",
                                      font=FONT_SM, fg=C["red"], bg=C["bg0"])
        self.serial_status.pack(side="left", padx=12)

        self.stat_label = tk.Label(f, text="已发送  0 包 · 0 字节",
                                   font=("Segoe UI", 8),
                                   fg=C["text3"], bg=C["bg0"], anchor="w")
        self.stat_label.pack(fill="x")

    def _conn_btn_leave(self):
        bg = C["red"] if self.serial_mgr.connected else C["acc2"]
        self.conn_btn.config(bg=bg)

    # ── 手柄面板 ──────────────────────────────
    def _build_gamepad_panel(self, parent):
        f = self._card(parent, "手柄状态")

        top = tk.Frame(f, bg=C["bg0"])
        top.pack(fill="x", pady=(0, 10))
        self.gp_status = tk.Label(top, text="● 未连接",
                                  font=FONT_SM, fg=C["red"], bg=C["bg0"])
        self.gp_status.pack(side="left")
        self.gp_name = tk.Label(top, text="", font=FONT_SM,
                                fg=C["text2"], bg=C["bg0"])
        self.gp_name.pack(side="left", padx=8)

        self.axis_bars, self.axis_vals = {}, {}
        for name, label in zip(
            ["LH",   "LV",         "RH",         "RV"],
            ["左水平", "左垂直 → 速度", "右水平 → 转向", "右垂直"]
        ):
            row = tk.Frame(f, bg=C["bg0"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, font=FONT_TINY,
                     fg=C["text3"], bg=C["bg0"], width=10,
                     anchor="w").pack(side="left")
            c = tk.Canvas(row, width=180, height=12,
                          bg=C["bg1"], highlightthickness=0)
            c.pack(side="left", padx=4)
            vl = tk.Label(row, text="   0", font=FONT_MONO,
                          fg=C["text1"], bg=C["bg0"], width=5, anchor="e")
            vl.pack(side="left")
            self.axis_bars[name] = c
            self.axis_vals[name]  = vl

    # ── 摇杆可视化 ────────────────────────────
    def _build_stick_panel(self, parent):
        f = self._card(parent, "摇杆预览")
        row = tk.Frame(f, bg=C["bg0"])
        row.pack()
        for side, attr, title in [
            ("left",  "left_canvas",  "LEFT  L"),
            ("left",  "right_canvas", "RIGHT  R"),
        ]:
            col = tk.Frame(row, bg=C["bg0"])
            col.pack(side="left", padx=8)
            tk.Label(col, text=title, font=FONT_TINY,
                     fg=C["text3"], bg=C["bg0"]).pack()
            c = tk.Canvas(col, width=130, height=130,
                          bg=C["bg1"], highlightthickness=0)
            c.pack()
            setattr(self, attr, c)

    # ── 日志面板 ──────────────────────────────
    def _build_log_panel(self, parent):
        f = self._card(parent, "发送日志")
        self.log_text = tk.Text(f, width=38, height=9,
                                bg=C["bg1"], fg=C["text1"],
                                font=FONT_MONO, relief="flat",
                                state="disabled",
                                selectbackground=C["acc0"],
                                insertbackground=C["acc2"],
                                padx=6, pady=6,
                                highlightthickness=1,
                                highlightbackground=C["bg3"])
        sb = ttk.Scrollbar(f, command=self.log_text.yview,
                           style="Claude.Vertical.TScrollbar")
        self.log_text.configure(yscrollcommand=sb.set)
        self.log_text.pack(side="left", fill="both")
        sb.pack(side="right", fill="y")
        for tag, fg in [("ts","text3"),("ok","green"),("err","red"),("warn","amber")]:
            self.log_text.tag_configure(tag, foreground=C[fg])

    # ── 小工具 ────────────────────────────────
    def _icon_btn(self, parent, text, cmd):
        btn = tk.Label(parent, text=text, font=("Segoe UI", 10),
                       fg=C["acc2"], bg=C["bg0"], cursor="hand2", padx=2)
        btn.bind("<Button-1>", lambda e: cmd())
        btn.bind("<Enter>",    lambda e: btn.config(fg=C["acc3"]))
        btn.bind("<Leave>",    lambda e: btn.config(fg=C["acc2"]))
        return btn

    # ══════════════════════════════════════════
    #  蓝牙扫描弹窗
    # ══════════════════════════════════════════
    def _open_bt_dialog(self):
        if self.serial_mgr.connected:
            if not messagebox.askyesno("提示", "当前已连接，是否断开并重新选择设备？"):
                return
            self.serial_mgr.disconnect()
            self._update_conn_btn_state(connected=False)
            self._log("已断开，准备重新扫描", "warn")

        BluetoothDialog(self.root, self._on_bt_port_selected)

    def _on_bt_port_selected(self, port: str):
        """蓝牙弹窗回调：拿到 COM 口后自动连接"""
        self._log(f"蓝牙选择 → {port}，正在连接…", "warn")
        # 更新下拉框
        current_ports = SerialManager.list_ports()
        if port not in current_ports:
            current_ports.insert(0, port)
        self.port_combo["values"] = current_ports
        self.port_var.set(port)

        baud = int(self.baud_var.get())
        ok = self.serial_mgr.connect(port, baud)
        if ok:
            self._update_conn_btn_state(connected=True)
            self._log(f"已连接  {port}  @  {baud} baud", "ok")
        else:
            messagebox.showerror("连接失败",
                                 f"无法打开 {port}\n\n"
                                 f"{self.serial_mgr.last_error}\n\n"
                                 "提示：HC-04 配对后 Windows 会生成两个 COM 口，\n"
                                 "请尝试另一个编号。")
            self._log(f"连接失败: {self.serial_mgr.last_error}", "err")

    # ══════════════════════════════════════════
    #  串口逻辑
    # ══════════════════════════════════════════
    def _refresh_ports(self):
        ports = SerialManager.list_ports()
        self.port_combo["values"] = ports
        self.port_combo.set(ports[0] if ports else "")

    def _toggle_serial(self):
        if self.serial_mgr.connected:
            self.serial_mgr.disconnect()
            self._update_conn_btn_state(connected=False)
            self._log("串口已断开", "warn")
        else:
            port = self.port_var.get()
            baud = int(self.baud_var.get())
            if not port:
                messagebox.showerror("错误", "请先选择端口，或使用「搜索蓝牙设备」")
                return
            ok = self.serial_mgr.connect(port, baud)
            if ok:
                self._update_conn_btn_state(connected=True)
                self._log(f"已连接  {port}  @  {baud} baud", "ok")
            else:
                messagebox.showerror("连接失败", self.serial_mgr.last_error)
                self._log(f"连接失败: {self.serial_mgr.last_error}", "err")

    def _update_conn_btn_state(self, connected: bool):
        if connected:
            self.conn_btn.config(text="断开", bg=C["red"])
            self.conn_btn.bind("<Leave>", lambda e: self.conn_btn.config(bg=C["red"]))
        else:
            self.conn_btn.config(text="连接", bg=C["acc2"])
            self.conn_btn.bind("<Leave>", lambda e: self.conn_btn.config(bg=C["acc2"]))

    # ══════════════════════════════════════════
    #  发送循环
    # ══════════════════════════════════════════
    def _start_gamepad(self):
        ok = self.gamepad.start()
        if not ok:
            self._log("⚠ 未检测到手柄，请连接后重启", "warn")

    def _start_send_loop(self):
        threading.Thread(target=self._send_loop, daemon=True).start()

    def _send_loop(self):
        next_t = time.perf_counter()
        while self._running:
            lh, lv, rh, rv = self.gamepad.get_axes()
            self._axes = (lh, lv, rh, rv)
            if self.serial_mgr.connected:
                ok = self.serial_mgr.send(lh, lv, rh, rv)
                if not ok:
                    self._log(f"发送失败: {self.serial_mgr.last_error}", "err")
            next_t += SEND_INTERVAL
            sleep = next_t - time.perf_counter()
            if sleep > 0:
                time.sleep(sleep)

    # ══════════════════════════════════════════
    #  UI 刷新
    # ══════════════════════════════════════════
    def _update_ui(self):
        if not self._running:
            return
        lh, lv, rh, rv = self._axes

        if self.gamepad.connected:
            self.gp_status.config(text="● 已连接", fg=C["green"])
            self.gp_name.config(text=self.gamepad.get_name())
        else:
            self.gp_status.config(text="● 未连接", fg=C["red"])
            self.gp_name.config(text="")

        self.serial_status.config(
            text="● 已连接" if self.serial_mgr.connected else "● 未连接",
            fg=C["green"] if self.serial_mgr.connected else C["red"]
        )
        self.stat_label.config(
            text=f"已发送  {self.serial_mgr.packets_sent} 包 · "
                 f"{self.serial_mgr.bytes_sent} 字节"
        )

        for name, val in zip(["LH","LV","RH","RV"], [lh,lv,rh,rv]):
            self.axis_vals[name].config(text=f"{int(val):>4}")
            self._draw_bar(self.axis_bars[name], val)

        self._draw_stick(self.left_canvas,  lh, lv)
        self._draw_stick(self.right_canvas, rh, rv)
        self.root.after(50, self._update_ui)

    # ── 绘制 ──────────────────────────────────
    def _draw_bar(self, canvas: tk.Canvas, val: float):
        canvas.delete("all")
        W, H, mid = 180, 12, 90
        canvas.create_rectangle(0, 2, W, H-2, fill=C["bg3"], outline="")
        canvas.create_line(mid, 0, mid, H, fill=C["bg0"], width=1)
        pct = val / 100.0
        if pct > 0:
            x0, x1, col = mid, mid + int(pct*(mid-2)), C["acc2"]
        elif pct < 0:
            x0, x1, col = mid+int(pct*(mid-2)), mid, C["acc1"]
        else:
            return
        canvas.create_rectangle(x0, 3, x1, H-3, fill=col, outline="")

    def _draw_stick(self, canvas: tk.Canvas, x_val: float, y_val: float):
        canvas.delete("all")
        cx = cy = 65
        R, r = 52, 9
        canvas.create_oval(cx-R, cy-R, cx+R, cy+R,
                           fill=C["bg2"], outline=C["bg3"], width=2)
        r2 = R // 2
        canvas.create_oval(cx-r2, cy-r2, cx+r2, cy+r2,
                           outline=C["bg3"], dash=(3,4), width=1)
        canvas.create_line(cx-R+4, cy, cx+R-4, cy, fill=C["bg3"])
        canvas.create_line(cx, cy-R+4, cx, cy+R-4, fill=C["bg3"])
        dx = (x_val/100.0)*(R-r-2)
        dy = (y_val/100.0)*(R-r-2)
        px, py = cx+dx, cy+dy
        canvas.create_line(cx, cy, px, py, fill=C["acc1"], width=2)
        canvas.create_oval(px-(r+5), py-(r+5), px+(r+5), py+(r+5),
                           fill=C["acc0"], outline="")
        canvas.create_oval(px-r, py-r, px+r, py+r,
                           fill=C["acc2"], outline=C["acc3"], width=1)
        canvas.create_text(cx, 125, text=f"{int(x_val)}, {int(y_val)}",
                           fill=C["text3"], font=("Segoe UI", 8))

    # ── 日志 ──────────────────────────────────
    def _log(self, msg: str, level: str = ""):
        ts = time.strftime("%H:%M:%S")
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{ts}]  ", "ts")
        self.log_text.insert("end", msg + "\n", level or None)
        self.log_text.see("end")
        if int(self.log_text.index("end-1c").split(".")[0]) > 200:
            self.log_text.delete("1.0", "10.0")
        self.log_text.config(state="disabled")

    def on_close(self):
        self._running = False
        self.gamepad.stop()
        self.serial_mgr.disconnect()
        self.root.destroy()


# ─────────────────────────────────────────────
#  主入口
# ─────────────────────────────────────────────
def main():
    if not PYGAME_AVAILABLE:
        print("⚠ 请先安装 pygame：pip install pygame")
    root = tk.Tk()
    app  = BalanceCarGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()

if __name__ == "__main__":
    main()