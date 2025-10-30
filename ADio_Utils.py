# ADio_Utils.py
# ADio（FTDI D2XX）ユーティリティ
# - 10文字コマンド "*C H H E DDDD#" を厳守（C:1桁, HH:2桁, E:1桁, DDDD:4桁）
# - "*4HH1xxxx#" 以外の全コマンドで "*OK#/*NG#" 等の1行応答を必ず読む
# - CHリスト指定は "all" に対応（GPIO:0..7, ENC:0..3, ADC:0..15）

from __future__ import annotations
import time
from typing import Iterable, Union, Optional

import ftd2xx
import ftd2xx.defines as fd


# ==========
# 内部ヘルパ
# ==========

def _open_flag_by_serial() -> int:
    return getattr(fd, "OPEN_BY_SERIAL_NUMBER",
           getattr(fd, "FT_OPEN_BY_SERIAL_NUMBER", 1))

def _is_handle_alive(handle) -> bool:
    try:
        handle.getStatus()
        return True
    except Exception:
        return False

def _write_ascii(handle, s: str) -> None:
    """FTDIへASCIIコマンド送信し、送信内容を表示"""
    print(f"→SEND: {s.strip()}")
    handle.write(s.encode("ascii", errors="ignore"))

def _readline(handle, timeout: float = 2.0, terminator: bytes = b"\n") -> bytes:
    line = bytearray()
    start = time.time()
    while time.time() - start < timeout:
        if handle.getQueueStatus() > 0:
            b = handle.read(1)
            if b:
                line += b
                if b in terminator:
                    break
        else:
            time.sleep(0.001)
    return bytes(line)

def _send_and_read_one_line(handle, cmd: str, print_line: bool = True) -> bytes:
    """ASCIIコマンド送信→1行だけ読む。送信＆応答をprint"""
    _write_ascii(handle, cmd)
    resp = _readline(handle, timeout=2.0)
    if resp:
        try:
            txt = resp.decode(errors="ignore").strip()
        except Exception:
            txt = f"<decode error: {resp[:16]!r}>"
    else:
        txt = "<no response>"
    if print_line:
        print(f"←RECV: {txt}")
    return resp

def _fmt_cmd(C: str, HH: int, E: int, DDDD: int) -> str:
    """
    10文字フォーマット: '*C HH E DDDD #' 例: '*B000801#'
    C: '0'～'F' 1桁, HH: 0x00～0xFF 2桁, E: 0x0～0xF 1桁, DDDD: 0x0000～0xFFFF 4桁
    """
    s = f"*{C}{HH:02X}{E:X}{DDDD:04X}#"
    if len(s) != 10:
        raise RuntimeError(f"cmd length != 10: {s!r} ({len(s)})")
    return s

def _normalize_channels(chs: Union[str, int, Iterable[int]], *, max_ch: int) -> list[int]:
    """
    'all' → [0..max_ch], int → [int], 反復可能 → 昇順ユニーク
    """
    if isinstance(chs, str) and chs.lower() == "all":
        return list(range(max_ch + 1))
    if isinstance(chs, int):
        chs = [chs]
    try:
        lst = sorted(set(int(x) for x in chs))  # type: ignore[arg-type]
    except Exception:
        raise ValueError("CH指定は 'all'、整数、または整数の反復可能で指定してください。")
    for c in lst:
        if not (0 <= c <= max_ch):
            raise ValueError(f"CH は 0～{max_ch} の範囲で指定してください（不正: {c}）")
    return lst

def _mask_from_channels(ch_list: Iterable[int]) -> int:
    m = 0
    for ch in ch_list:
        m |= (1 << ch)
    return m


# ==========
# 公開API：FTDI オープン/列挙/ユーティリティ
# ==========

def list_ftdi_serials() -> list[str]:
    """接続中FTDIのシリアル番号一覧（失敗時 []）。"""
    try:
        n = ftd2xx.createDeviceInfoList()
        serials = []
        for i in range(n):
            info = ftd2xx.getDeviceInfoDetail(i)
            s = info[4]
            if isinstance(s, (bytes, bytearray)):
                s = s.decode(errors="ignore")
            serials.append(str(s).strip())
        return serials
    except Exception:
        try:
            devs = ftd2xx.listDevices()
            if not devs:
                return []
            serials = []
            for s in devs:
                if isinstance(s, (bytes, bytearray)):
                    s = s.decode(errors="ignore")
                serials.append(str(s).strip())
            return serials
        except Exception:
            return []

def open_ftdi(serial: Optional[str] = None,
              in_timeout_ms: int = 100,
              out_timeout_ms: int = 100,
              latency_ms: int = 2,
              usb_in_kb: int = 64,
              usb_out_kb: int = 64):
    """FTDIを開いて基本設定。"""
    try:
        if serial:
            flag = _open_flag_by_serial()
            ser_b = serial.encode("ascii", errors="ignore") if isinstance(serial, str) else serial
            handle = ftd2xx.openEx(ser_b, flag)
        else:
            devs = ftd2xx.listDevices()
            if not devs:
                print("FTDIデバイスが見つかりません")
                return None
            handle = ftd2xx.open(0)

        handle.resetDevice()
        time.sleep(0.1)
        handle.purge(fd.PURGE_RX | fd.PURGE_TX)
        time.sleep(0.05)

        handle.setTimeouts(in_timeout_ms, out_timeout_ms)
        handle.setUSBParameters(usb_in_kb * 1024, usb_out_kb * 1024)
        handle.setLatencyTimer(latency_ms)
        handle.setFlowControl(fd.FLOW_NONE, 0, 0)
        handle.purge()

        try:
            info = handle.getDeviceInfo()
            s = info[2].decode() if isinstance(info[2], (bytes, bytearray)) else info[2]
            print(f"[FTDI] Opened Serial={s}, Latency={latency_ms}ms, USB(IN/OUT)={usb_in_kb}/{usb_out_kb}KB")
        except Exception:
            pass

        return handle
    except Exception as e:
        print(f"[ERROR] FTDIを開けませんでした: {e}")
        if serial:
            serials = list_ftdi_serials()
            if serials:
                print("接続中のシリアル候補:", ", ".join(serials))
            else:
                print("接続中のFTDIデバイスが見つかりません。")
        return None

def flush_input_buffer(handle, wait_time=0.05, stable_count=5, max_attempts=3) -> str:
    """受信バッファを読み捨て。"""
    empty_counter = 0
    attempts = 0
    all_data = []
    while empty_counter < stable_count and attempts < max_attempts:
        time.sleep(wait_time)
        bytes_avail = handle.getQueueStatus()
        if bytes_avail > 0:
            raw = handle.read(bytes_avail)
            try:
                text = raw.decode(errors='ignore').strip()
            except Exception:
                text = f"<decode error: {raw[:16]!r}>"
            if text:
                for line in text.splitlines():
                    line = line.strip()
                    print(f"[flush] {line}")
                    all_data.append(line)
            empty_counter = 0
            attempts += 1
        else:
            empty_counter += 1
    return "\n".join(all_data)

def read_exact(handle, size: int, timeout: float = 1.0) -> Optional[bytes]:
    """指定バイト数が揃うまで read()。揃わなければ None。"""
    buf = bytearray()
    start = time.time()
    while len(buf) < size:
        if time.time() - start > timeout:
            print(f"[TIMEOUT] read_exact {len(buf)}/{size} bytes")
            return None
        n = handle.getQueueStatus()
        if n > 0:
            to_read = min(size - len(buf), n)
            buf.extend(handle.read(to_read))
        else:
            time.sleep(0.01)
    return bytes(buf)


# ==========
# 便利ユーティリティ
# ==========

def get_sampling_command(fs_ksps: int, target: int = 0) -> str:
    """fs_ksps∈{1,2,4,8,16,32,64,128,256}, target=0(CH0-7)/1(CH8-15) → '*XXXXXXXX#'"""
    allowed = [1, 2, 4, 8, 16, 32, 64, 128, 256]
    if fs_ksps not in allowed:
        raise ValueError(f"Unsupported fs_ksps: {fs_ksps}. Must be one of {allowed}")
    base = 0x00000000 if target == 0 else (0x00100000 if target == 1 else None)
    if base is None:
        raise ValueError("target must be 0 (CH0–7) or 1 (CH8–15)")
    index = allowed.index(fs_ksps)
    return f"*{(base + index):08X}#"

def convert_to_voltage(adc_value: int, gain: int = 1) -> float:
    """20bit相当（±524288）を ±5V 基準で換算し、ゲイン倍率を反映。"""
    MAX_ADC = 524288
    if adc_value >= MAX_ADC:
        adc_value -= 2 * MAX_ADC
    return (adc_value / MAX_ADC) * 5.0 * gain


# ==========
# ★ ADCコマンド群（C=1,4 など）
# ==========

def cmd_set_chunk_size(handle, ch: int, chunk_size: int, print_response: bool = True) -> str:
    """*1 HH 0 DDDD#  CHUNK_SIZE≤2047"""
    if not (0 <= ch <= 0x0F):
        raise ValueError("CH は 0～15")
    if not (0 <= chunk_size <= 0x07FF):
        raise ValueError("CHUNK_SIZE は 0～2047")
    cmd = _fmt_cmd("1", ch, 0x0, chunk_size)
    _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmd

def cmd_start_accumulation(handle, print_response: bool = True) -> str:
    """*4 00 2 0000#  ADCデータ蓄積開始"""
    cmd = _fmt_cmd("4", 0x00, 0x2, 0x0000)
    _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmd

def cmd_set_chunk_num(handle, ch: int, chunk_num: int, print_response: bool = True) -> str:
    """*4 HH 1 (CHUNK_NUM-1)#   CHUNK_NUM≥1"""
    if not (0 <= ch <= 0x0F):
        raise ValueError("CH は 0～15")
    if not (1 <= chunk_num <= 0x10000):
        raise ValueError("CHUNK_NUM は 1～65536")
    field = (chunk_num - 1) & 0xFFFF
    cmd = _fmt_cmd("4", ch, 0x1, field)
    _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmd

def cmd_stop_accumulation(handle, print_response: bool = True) -> str:
    """*4 00 3 0000#  ADCデータ蓄積STOP"""
    cmd = _fmt_cmd("4", 0x00, 0x3, 0x0000)
    _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmd

def cmd_adc_single_sample(handle, ch: int, print_response: bool = True) -> bytes:
    """*4 HH 0 0000#  指定CHの単発1件読み（1行のデータ応答）"""
    if not (0 <= ch <= 0x0F):
        raise ValueError("CH は 0～15")
    cmd = _fmt_cmd("4", ch, 0x0, 0x0000)
    _write_ascii(handle, cmd)
    resp = _readline(handle, timeout=2.0)
    if print_response and resp:
        try:
            print(resp.decode(errors="ignore").strip())
        except Exception:
            print(f"<decode error: {resp[:16]!r}>")
    return resp

def cmd_adc_chunk_request(handle, ch: int, chunk_size: int) -> str:
    """*4 HH 1 DDDD#  連続データ要求（※このコマンドは応答を読まない）"""
    if not (0 <= ch <= 0x0F):
        raise ValueError("CH は 0～15")
    if not (0 <= chunk_size <= 0x07FF):
        raise ValueError("chunk_size は 0～2047")
    cmd = _fmt_cmd("4", ch, 0x1, chunk_size)
    _write_ascii(handle, cmd)
    return cmd


# ==========
# ★ DACコマンド群（C=6,7,8,5）
# ==========

def cmd_set_ldac(handle, level: int, print_response: bool = True) -> str:
    """*7 00 0 000y#  LDAC信号 y=0/1"""
    if level not in (0, 1):
        raise ValueError("LDAC レベルは 0 または 1")
    cmd = _fmt_cmd("7", 0x00, 0x0, level & 0x000F)
    _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmd

def ldac_mask_from_channels(channels: Iterable[int]) -> int:
    """CH0..CH7 から 8bitマスク（1=LDACで出力しない）。"""
    mask = 0
    for ch in channels:
        if not (0 <= ch <= 7):
            raise ValueError("CH は 0～7")
        mask |= (1 << ch)
    return mask & 0xFF

def cmd_set_ldac_mask(handle, mask: int, print_response: bool = True) -> str:
    """*8 00 0 00yy#  LDACマスク設定（1=マスク）"""
    if not (0x00 <= mask <= 0xFF):
        raise ValueError("mask は 0x00～0xFF")
    dddd = (mask & 0xFF)  # 00yy
    cmd = _fmt_cmd("8", 0x00, 0x0, dddd)
    _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmd

def cmd_dac_set_data(handle, ch: int, value: int, print_response: bool = True) -> str:
    """*6 HH 1 yyyy#  DAC出力データセット（CH=0..8, yyyy=0x0000..0xFFFF）"""
    if not (0 <= ch <= 8):
        raise ValueError("DAC CH は 0～8")
    if not (0x0000 <= value <= 0xFFFF):
        raise ValueError("value は 0x0000～0xFFFF")
    cmd = _fmt_cmd("6", ch, 0x1, value)
    _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmd

def cmd_dac_immediate_out(handle, ch: int, value: int, print_response: bool = True) -> str:
    """*6 HH 3 yyyy#  DAC即時出力（CH=0..8）"""
    if not (0 <= ch <= 8):
        raise ValueError("DAC CH は 0～8")
    if not (0x0000 <= value <= 0xFFFF):
        raise ValueError("value は 0x0000～0xFFFF")
    cmd = _fmt_cmd("6", ch, 0x3, value)
    _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmd

def cmd_set_opamp_gain(handle, ch: int, gain_code: int, print_response: bool = True) -> str:
    """
    *5 HH 0 000y#  オペアンプゲイン（y=0..4）
      0: ±10V=1/2, 1: ±5V=1/1, 2: ±1.25V=×4, 3: ±0.3125V=×16, 4: ±0.12625V=×32
    """
    if not (0 <= ch <= 0x0F):
        raise ValueError("CH は 0～15")
    if gain_code not in (0, 1, 2, 3, 4):
        raise ValueError("gain_code は 0～4")
    cmd = _fmt_cmd("5", ch, 0x0, gain_code & 0x000F)
    _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmd


# ==========
# ★ GPIO / PWM コマンド群（C=9,A,B,C,D,E）
# ==========

# 9) DIR設定（入力/出力）
def cmd_set_gpio_dir(handle,
                     active_channels: Union[str, int, Iterable[int]],
                     input_channels: Union[str, int, Iterable[int]],
                     print_response: bool = True) -> str:
    """
    *9 HH 0 DDDD#  HH:反映するCHマスク, DDDD: 入力=1 / 出力=0 （bit0=CH0..bit7=CH7）
    """
    act = _normalize_channels(active_channels, max_ch=7)
    ins = _normalize_channels(input_channels,   max_ch=7)
    hh = _mask_from_channels(act) & 0xFF
    dddd = _mask_from_channels(ins) & 0xFFFF
    cmd = _fmt_cmd("9", hh, 0x0, dddd)
    _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmd

# A) PWM/GPIO モード切替（E=0）
def cmd_set_gpio_pwm_mode(handle,
                          active_channels: Union[str, int, Iterable[int]],
                          pwm_channels: Union[str, int, Iterable[int]],
                          print_response: bool = True) -> str:
    """
    *A HH 0 DDDD#  DDDD: 1=PWM, 0=GPIO
    - 先に DIR=出力（コマンド9）へ自動設定（activeのみ）
    - pwm_channels に含まれないCHはGPIO（=0）
    """
    act = _normalize_channels(active_channels, max_ch=7)
    pwm = _normalize_channels(pwm_channels,   max_ch=7)
    cmd_set_gpio_dir(handle, active_channels=act, input_channels=[], print_response=print_response)
    hh = _mask_from_channels(act) & 0xFF
    dd = _mask_from_channels([c for c in pwm if c in act]) & 0xFFFF
    cmd = _fmt_cmd("A", hh, 0x0, dd)
    _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmd

# A) エンコーダーモード指定（E=1）— 引数1つに統一
def cmd_set_encoder_mode(handle,
                         channels: Union[str, int, Iterable[int]],
                         print_response: bool = True) -> str:
    """
    *A HH 1 0000#  HH: 0..3のみ。指定CHをENCモードへ。
    事前に: DIR=入力（9）, PWMではなくGPIO固定（A/E=0, D=0000）を自動実行。
    """
    chs = _normalize_channels(channels, max_ch=3)
    hh = _mask_from_channels(chs) & 0xFF
    # DIR=入力
    cmd_set_gpio_dir(handle, active_channels=chs, input_channels=chs, print_response=print_response)
    # GPIO固定
    _send_and_read_one_line(handle, _fmt_cmd("A", hh, 0x0, 0x0000), print_line=print_response)
    # ENC有効
    cmd = _fmt_cmd("A", hh, 0x1, 0x0000)
    _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmd

# A) ENCx_PRESET_HI/LO（E=2/3） + 32bit一括
def _norm_enc_ch(ch: Union[str, int]) -> list[int]:
    if isinstance(ch, str) and ch.lower() == "all":
        return [0,1,2,3]
    if isinstance(ch, int):
        if 0 <= ch <= 3:
            return [ch]
    raise ValueError("エンコーダ対応CHは 0～3 または 'all'")

def _hh_from_single_ch(ch: int) -> int:
    return ch & 0xFF  # ここは“単一CH番号”をそのままHHに入れる仕様

def cmd_encoder_preset_hi(handle, ch: Union[str, int], value16: int, print_response: bool = True) -> list[str]:
    """*A HH 2 DDDD#  ENCx_PRESET_HI（上位16bit）"""
    if not (0x0000 <= value16 <= 0xFFFF):
        raise ValueError("value16 は 0x0000～0xFFFF")
    cmds = []
    for c in _norm_enc_ch(ch):
        cmd = _fmt_cmd("A", _hh_from_single_ch(c), 0x2, value16)
        cmds.append(cmd)
        _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmds

def cmd_encoder_preset_lo(handle, ch: Union[str, int], value16: int, print_response: bool = True) -> list[str]:
    """*A HH 3 DDDD#  ENCx_PRESET_LO（下位16bit）"""
    if not (0x0000 <= value16 <= 0xFFFF):
        raise ValueError("value16 は 0x0000～0xFFFF")
    cmds = []
    for c in _norm_enc_ch(ch):
        cmd = _fmt_cmd("A", _hh_from_single_ch(c), 0x3, value16)
        cmds.append(cmd)
        _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmds

def cmd_encoder_preset_32(handle, ch: Union[str, int], value32: int, print_response: bool = True) -> list[str]:
    """32bit一括（内部で HI→LO 送信し毎回1行読む）"""
    if not (0x00000000 <= value32 <= 0xFFFFFFFF):
        raise ValueError("value32 は 0x00000000～0xFFFFFFFF")
    hi = (value32 >> 16) & 0xFFFF
    lo = value32 & 0xFFFF
    cmds: list[str] = []
    cmds += cmd_encoder_preset_hi(handle, ch, hi, print_response=print_response)
    cmds += cmd_encoder_preset_lo(handle, ch, lo, print_response=print_response)
    return cmds

# A) エンコーダ制御（E=4）
def cmd_encoder_ctrl(handle,
                     channels: Union[str, int, Iterable[int]],
                     *,
                     dir_invert: bool | None = None,
                     do_reset: bool = False,
                     load_preset: bool = False,
                     print_response: bool = True) -> list[str]:
    """
    *A HH 4 DDDD#
      bit0=DIR_INV(R/W), bit1=COUNT_RESET(W1P), bit2=COUNT_PRESET_EN(W1P)
    """
    if do_reset and load_preset:
        raise ValueError("do_reset と load_preset の同時指定は不可")
    chs = _normalize_channels(channels, max_ch=3)
    cmds = []
    for ch in chs:
        d = 0x0000
        if dir_invert is True:  d |= (1 << 0)
        elif dir_invert is False:  d |= 0  # 明示0
        if do_reset:    d |= (1 << 1)
        if load_preset: d |= (1 << 2)
        cmd = _fmt_cmd("A", _hh_from_single_ch(ch), 0x4, d)
        cmds.append(cmd)
        _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmds

def cmd_encoder_dir_invert(handle, channels, invert: bool, print_response: bool = True) -> list[str]:
    return cmd_encoder_ctrl(handle, channels, dir_invert=invert, print_response=print_response)

def cmd_encoder_count_reset(handle, channels, print_response: bool = True) -> list[str]:
    return cmd_encoder_ctrl(handle, channels, do_reset=True, print_response=print_response)

def cmd_encoder_load_preset(handle, channels, print_response: bool = True) -> list[str]:
    return cmd_encoder_ctrl(handle, channels, load_preset=True, print_response=print_response)

# B) PWM 周波数設定（E=0）
def cmd_pwm_set_frequency(handle,
                          channels: Union[str, int, Iterable[int]],
                          freq_hz: int,
                          print_response: bool = True) -> list[str]:
    """
    *B HH 0 DDDD#
      DDDD=0x0000..0x0FFF → Hz(1Hz刻み) / DDDD=0x8000..0x8061 → kHz(1kHz刻み, 0..97kHz)
    """
    if freq_hz < 0:
        raise ValueError("freq_hz は 0 以上")
    cmds = []
    for ch in _normalize_channels(channels, max_ch=7):
        if 0 <= freq_hz <= 4095:
            dddd = freq_hz
        elif (freq_hz % 1000 == 0) and (0 <= (freq_hz // 1000) <= 97):
            dddd = 0x8000 + (freq_hz // 1000)
        else:
            raise ValueError("周波数は 0..4095Hz または 0..97kHz(1kHz刻み)")
        cmd = _fmt_cmd("B", ch, 0x0, dddd)
        cmds.append(cmd)
        _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmds

# C) PWM デューティ比設定（E=0）
def cmd_pwm_set_data_raw(handle,
                         channels: Union[str, int, Iterable[int]],
                         dddd: int,
                         print_response: bool = True) -> list[str]:
    """
    *C HH 0 DDDD#  0000h=停止0固定, 0001h..03FEh=1..1022/1024, 01FFh=50%, 03FFh=停止1固定
    """
    if not (0x0000 <= dddd <= 0x03FF):
        raise ValueError("DDDD は 0x0000～0x03FF")
    cmds = []
    for ch in _normalize_channels(channels, max_ch=7):
        cmd = _fmt_cmd("C", ch, 0x0, dddd)
        cmds.append(cmd)
        _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmds

def cmd_pwm_set_duty(handle,
                     channels: Union[str, int, Iterable[int]],
                     duty: float,
                     print_response: bool = True) -> list[str]:
    """
    PWMデューティ比設定（C/E=0）
      0.0 → 0000h / 1.0 → 03FFh / 中間は 1..03FEh
      ※ ADioは比較式が「<=」想定のため 0.5 は 0x01FF を優先
    """
    if not (0.0 <= duty <= 1.0):
        raise ValueError("duty は 0.0～1.0")
    if duty == 0.0:
        code = 0x0000
    elif duty == 1.0:
        code = 0x03FF
    else:
        ticks = int(duty * 1024)
        if   ticks <= 0:   code = 0x0001
        elif ticks >= 1023: code = 0x03FE
        else:
            code = 0x01FF if abs(duty - 0.5) < (1/1024) else ticks
    return cmd_pwm_set_data_raw(handle, channels, code, print_response)

# D) GPIO 読み取り（E=0）/ エンコーダーステータス（E=1）
def cmd_gpio_read(handle, print_response: bool = True) -> tuple[str, int, bytes]:
    """*D 00 0 0000# → 応答: '*D0000XX#' 想定（XX=下位8bit）"""
    cmd = _fmt_cmd("D", 0x00, 0x0, 0x0000)
    _write_ascii(handle, cmd)
    resp = _readline(handle, timeout=2.0)
    if resp and print_response:
        print(resp.decode(errors="ignore").strip())
    value = -1
    try:
        txt = resp.decode(errors="ignore").strip().upper() if resp else ""
        hx = "".join(c for c in txt if c in "0123456789ABCDEF")
        if len(hx) >= 2:
            value = int(hx[-2:], 16)
    except Exception:
        pass
    return cmd, value, resp if resp else b""

def cmd_encoder_status_read(handle, channel: int, print_response: bool = True) -> dict:
    """*D HH 1 0000# → CSVっぽい文字列を返すので生文字列と簡易パースを返却。"""
    if not (0 <= channel <= 3):
        raise ValueError("channel は 0～3")
    cmd = _fmt_cmd("D", channel, 0x1, 0x0000)
    _write_ascii(handle, cmd)
    resp = _readline(handle, timeout=2.0)
    txt = resp.decode(errors="ignore").strip() if resp else ""
    if print_response and txt:
        print(txt)
    result = {"raw": txt, "ch": channel, "count": None, "dir": None, "ovf": None, "ae": None}
    try:
        body = txt[2:] if txt.startswith("*D") else txt
        parts = [p for p in body.split(",") if p]
        if len(parts) >= 2:
            pc = parts[1].strip().upper().replace("H","").replace("#","")
            base = 16 if any(c in pc for c in "ABCDEF") else 10
            result["count"] = int(pc, base)
        if len(parts) >= 3: result["dir"] = parts[2].strip()
        if len(parts) >= 4: result["ovf"] = parts[3].strip()
        if len(parts) >= 5: result["ae"]  = parts[4].strip().rstrip("#")
    except Exception:
        pass
    return result

# E) GPIO データ出力（E=0, HH=00 固定）
def cmd_gpio_write(handle, value: int, print_response: bool = True) -> str:
    """*E 00 0 DDDD#（下位8bitが出力。入力設定のポートは変化なし）"""
    if not (0x00 <= value <= 0xFF):
        raise ValueError("value は 0x00～0xFF")
    cmd = _fmt_cmd("E", 0x00, 0x0, value & 0x00FF)
    _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmd

def cmd_gpio_write_mask(handle, high_channels: Union[str, int, Iterable[int]], print_response: bool = True) -> str:
    """ハイにしたいCH列挙（"all"可）で一括設定。"""
    chs = _normalize_channels(high_channels, max_ch=7)
    mask = 0
    for ch in chs:
        mask |= (1 << ch)
    return cmd_gpio_write(handle, mask & 0xFF, print_response)

# F) リセット（E=0, HH=00 固定）
def cmd_reset(handle, mode: str = "all", print_response: bool = True) -> str:
    """*F 00 0 0000# 全設定リセット / *F 00 0 0001# ADC送信リセット"""
    if mode not in ("all", "adc"):
        raise ValueError('mode は "all" か "adc"')
    dddd = 0x0000 if mode == "all" else 0x0001
    cmd = _fmt_cmd("F", 0x00, 0x0, dddd)
    _send_and_read_one_line(handle, cmd, print_line=print_response)
    return cmd

def cmd_reset_all(handle, print_response: bool = True) -> str:
    return cmd_reset(handle, "all", print_response)

def cmd_reset_adc_tx(handle, print_response: bool = True) -> str:
    return cmd_reset(handle, "adc", print_response)
