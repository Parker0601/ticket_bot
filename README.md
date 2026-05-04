# 搶票機器人

針對 Tixcraft 的自動搶票機器人，使用 Selenium 控制瀏覽器，並以 CRNN 深度學習模型自動辨識驗證碼。

---

## Clone 後的初始設定

### 1. 安裝 Python 套件

```bash
pip install selenium torch torchvision Pillow
```

> 需要 Python 3.10+。

### 2. 安裝 ChromeDriver

確認本機安裝的 Chrome 版本，下載對應的 [ChromeDriver](https://chromedriver.chromium.org/downloads) 並確保它在系統 PATH 中，或放在專案根目錄。

### 3. 設定搶票參數

開啟 [rb/my_ticket_bot.py](rb/my_ticket_bot.py)，修改頂部的設定區：

```python
TARGET_URL = "https://tixcraft.com/activity/detail/26_malone"  # 活動頁面網址
RUN_AT_TW  = "11:14"   # 台灣時間幾點開始執行，設為 "" 代表立即執行
TICKET_COUNT = "1"     # 購票數量
PREFERRED_AREAS = [
    "搖滾站區(GA)",     # 優先選擇的區域名稱（依序嘗試）
    ""                  # 空字串 = 任何區域皆可（最後備用）
]
```

---

## 執行流程

### 步驟一：啟動 Debug 模式的 Chrome

機器人需要接管一個已登入 Tixcraft 帳號的 Chrome 視窗。

**方式 A（建議）：雙擊 bat 腳本**
```
start_chrome_for_bot.bat
```

**方式 B：PowerShell**
```powershell
powershell -ExecutionPolicy Bypass -File start_chrome_ps1.ps1
```

> 腳本會自動關閉所有現有 Chrome，再以 remote debug port 9222 重新開啟。
> 開啟後請手動登入 Tixcraft 帳號。

確認 Chrome 正常啟動後，可在瀏覽器開啟 `http://127.0.0.1:9222/json/version` 驗證。

---

### 步驟二：啟動搶票主程式

**方式 A：雙擊 bat 腳本**
```
run_my_ticket_bot_with_crnn.bat
```

**方式 B：PowerShell**
```powershell
powershell -ExecutionPolicy Bypass -File run_my_ticket_bot_with_crnn.ps1
```

**方式 C：直接執行 Python**
```bash
python rb/my_ticket_bot.py
```

程式啟動後會：
1. 載入 CRNN 驗證碼模型
2. 等待到 `RUN_AT_TW` 設定的台灣時間
3. 自動開啟活動頁面 → 點擊購票 → 選座 → 選票數 → 辨識驗證碼 → 提交

---

## 重新訓練驗證碼模型（可選）

若現有模型辨識率不佳，可自行收集資料重新訓練。

### 訓練資料格式

將驗證碼圖片放在 `rb/captcha_dataset/images/`，並在 `rb/captcha_dataset/labels/captchas.csv` 填入對應標籤：

```csv
filename,label,captcha_src
abc1.png,abcd,https://...
xyz2.png,wxyz,https://...
```

- `filename`：圖片檔名
- `label`：4 個英文小寫字母的正確答案
- `captcha_src`：原始驗證碼 URL（可留空）

### 執行訓練

```bash
python rb/captcha_model/train_lowercase_crnn.py
```

常用參數：

```bash
python rb/captcha_model/train_lowercase_crnn.py \
  --epochs 30 \
  --batch-size 64 \
  --lr 1e-3
```

訓練完成後，將輸出的 `.pth` 模型權重複製到 `rb/captcha_model/best_lowercase_crnn.pth` 覆蓋即可。

---

## 常見問題

### Chrome 無法被接管（`127.0.0.1:9222 沒有程式在監聽`）

| 原因 | 解決方式 |
|------|--------|
| bat 執行前 Chrome 已在跑 | 工作管理員手動關閉所有 `chrome.exe` 後再執行 bat |
| taskkill 沒關乾淨 | 用管理員身分執行 bat |
| 防毒軟體阻擋 | 暫時關閉防毒或將 Chrome 加入排除清單 |
| bat 版本有問題 | 改用 PowerShell 版本 `start_chrome_ps1.ps1` |

### 驗證碼辨識信心值過低

機器人預設信心門檻為 `0.92`，低於此值會自動刷新重試（最多 3 次）。若持續失敗，可在 [rb/my_ticket_bot.py](rb/my_ticket_bot.py) 調整：

```python
CAPTCHA_MIN_CONFIDENCE = 0.92  # 降低門檻或重新訓練模型
CAPTCHA_MAX_ATTEMPTS = 3
```

---

## 專案結構

```
.
├── start_chrome_for_bot.bat         # 啟動 Chrome debug 模式（bat 版）
├── start_chrome_ps1.ps1             # 啟動 Chrome debug 模式（PowerShell 版）
├── run_my_ticket_bot_with_crnn.bat  # 啟動搶票主程式（bat 版）
├── run_my_ticket_bot_with_crnn.ps1  # 啟動搶票主程式（PowerShell 版）
└── rb/
    ├── my_ticket_bot.py             # 搶票主程式（設定區在頂部）
    ├── ibon_ticket_bot.py           # ibon 平台版本（獨立使用）
    └── captcha_model/
        ├── best_lowercase_crnn.pth  # 訓練好的模型權重（執行必需）
        ├── predict_single.py        # 單張驗證碼預測腳本
        └── train_lowercase_crnn.py  # 模型訓練腳本
```
