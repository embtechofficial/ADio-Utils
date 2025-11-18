# ADio Utils

ADio ボード向けの **FTDI/D2XX ユーティリティ**です。  
接続中デバイスの列挙、シリアル指定オープン、受信バッファの安全クリア、行読み出し、指定バイト読み出し、  
サンプリング設定コマンド生成、ADC値→電圧変換などを提供します。

---

## 🚀 主な機能

### 🔹 基本ユーティリティ

- FTDIデバイスのシリアル番号列挙  
  - `list_ftdi_serials()`
- シリアル番号指定でのデバイスオープン  
  - `open_ftdi(serial=...)`
- 受信バッファの安全クリア  
  - `flush_input_buffer(handle)`
- 指定バイト数の読み出し（タイムアウト付き）  
  - `read_exact(handle, size, timeout)`
- サンプリング設定コマンド生成  
  - `get_sampling_command(fs_ksps, target)`
- ADCコード値 → 実電圧変換  
  - `convert_to_voltage(adc_value, gain)`

---

### 🔹 ADC 関連コマンドラッパ

- チャンクサイズ設定 / チャンク数設定  
  - `cmd_set_chunk_size(handle, ch, chunk_size)`  
  - `cmd_set_chunk_num(handle, ch, chunk_num)`
- 蓄積開始・停止  
  - `cmd_start_accumulation(handle)`  
  - `cmd_stop_accumulation(handle)`
- 単発サンプル取得 / 連続チャンク要求  
  - `cmd_adc_single_sample(handle, ch)`  
  - `cmd_adc_chunk_request(handle, ch, chunk_size)`

---

### 🔹 DAC / オペアンプ関連

- DAC出力データセット / 即時出力  
  - `cmd_dac_set_data(handle, ch, value)`  
  - `cmd_dac_immediate_out(handle, ch, value)`
- LDAC制御 / LDACマスク設定  
  - `cmd_set_ldac(handle, level)`  
  - `cmd_set_ldac_mask(handle, mask)`  
  - `ldac_mask_from_channels([...])`
- オペアンプゲイン設定（±10V〜±0.16V相当まで）  
  - `cmd_set_opamp_gain(handle, ch, gain_code)`

---

### 🔹 GPIO / PWM 関連

- GPIO入出力方向設定  
  - `cmd_set_gpio_dir(handle, active_channels, input_channels)`
- GPIO / PWM モード切り替え  
  - `cmd_set_gpio_pwm_mode(handle, active_channels, pwm_channels)`
- PWM 周波数・デューティ比設定  
  - `cmd_pwm_set_frequency(handle, channels, freq_hz)`  
  - `cmd_pwm_set_duty(handle, channels, duty)`
- GPIO 出力 / 入力読み取り  
  - `cmd_gpio_write(handle, value)`  
  - `cmd_gpio_write_mask(handle, high_channels)`  
  - `cmd_gpio_read(handle)`

---

### 🔹 エンコーダ関連

- エンコーダモード有効化  
  - `cmd_set_encoder_mode(handle, channels)`
- カウントプリセット設定（16bit/32bit）  
  - `cmd_encoder_preset_hi(handle, ch, value16)`  
  - `cmd_encoder_preset_lo(handle, ch, value16)`  
  - `cmd_encoder_preset_32(handle, ch, value32)`
- カウント制御・状態取得  
  - `cmd_encoder_count_reset(handle, channels)`  
  - `cmd_encoder_load_preset(handle, channels)`  
  - `cmd_encoder_dir_invert(handle, channels, invert)`  
  - `cmd_encoder_status_read(handle, channel)`

---

### 🔹 リセット関連

- ADio全体リセット / ADC送信系のみリセット  
  - `cmd_reset_all(handle)`  
  - `cmd_reset_adc_tx(handle)`


---

## 💾 インストール

1. まず **FTDI D2XX ドライバ** をインストールしてください。  
   - [Windows用ドライバ (FTDI公式サイト)](https://ftdichip.com/drivers/d2xx-drivers/)
   - macOS / Linux も対応しています。

2. このリポジトリをダウンロードまたはクローンし、ローカルでインストールします。

```bash
git clone https://github.com/embtechofficial/ADio-Utils.git
cd ADio-Utils
pip install -e .
```

## 🧰 使用例
```python
from adio_utils import ADio_Utils as adu

# 接続中のFTDIデバイスを列挙
print(adu.list_ftdi_serials())

# シリアルを指定して開く（指定しない場合は最初のデバイス）
handle = adu.open_ftdi(serial="FT9YKFGE")

# 受信バッファをクリア
adu.flush_input_buffer(handle)

# 行単位で読み取り
line = adu.readline(handle, timeout=1.0)
print("LINE:", line)

# ADC値を電圧に変換
v = adu.convert_to_voltage(12345, gain=1)
print("Voltage:", v, "V")
```
## 📁 ディレクトリ構成
```
ADio-Utils/
├─ src/
│  └─ adio_utils/
│     └─ ADio_Utils.py
├─ examples/
│  ├─ 01_list_serials.py
│  └─ 02_open_and_flush.py
├─ README.md
├─ LICENSE
└─ pyproject.toml
```
