# 搶票機器人 (Ticket Bot)

自動搶票、購票的 Selenium 機器人，支持多種購票網站。

## 快速開始

### 模式 A：使用已登入的 Chrome（推薦）
有登入狀態，可保留原先的帳號、購物車等。

1. 開啟帶除錯模式的 Chrome（二選一）：
   - **雙擊** `start_chrome_for_bot.bat`（Windows 會先關閉所有 Chrome 再開）
   - 或在 PowerShell 執行：`powershell -ExecutionPolicy Bypass -File start_chrome_ps1.ps1`

2. 執行搶票腳本：
   ```bash
   python rb/generic_ticket_bot.py "https://你要搶的活動網址"
   ```

### 模式 B：腳本自動開啟全新 Chrome
無登入狀態（無帳號、無歷史紀錄）。

在 `rb/generic_ticket_bot.py` 中將 `CHROME_MODE = "A"` 改成 `CHROME_MODE = "B"` 即可。

---

## 功能說明

### 通用搶票 (`rb/generic_ticket_bot.py`)

**只需提供目標網址，無需寫特定網站的 XPath/CSS**

- ✅ 自動依按鈕/連結**文字**尋找元素（例：購票、立即訂購、同意、提交、確認）
- ✅ 自動尋找驗證碼圖片與輸入框，用 OCR 辨識並填入
- ✅ 自動嘗試選座、選票數、勾選同意、點擊送出

### 專案搶票 (`rb/my_ticket_bot.py`)

針對 **tixcraft** 網站的固定流程（保留備用）。

---

## 安裝依賴

### 必需
```bash
pip install selenium
```

### 可選（用於自動驗證碼辨識）
```bash
pip install Pillow opencv-python pytesseract
```

並安裝 [Tesseract-OCR](https://github.com/UB-Mannheim/tesseract/wiki)

---

## 常見問題

### 「127.0.0.1:9333 沒有程式在監聽」

| 原因 | 解決方式 |
|------|--------|
| Chrome 在執行 bat/ps1 前就在執行 | 在工作管理員完全關閉所有 `chrome.exe`，再執行 bat/ps1 |
| `taskkill` 沒關乾淨 | 手動在工作管理員結束所有 `chrome.exe`，或用管理員身分執行 bat |
| cmd 的 `start` 沒正確傳參 | 改用 PowerShell 版本 (`start_chrome_ps1.ps1`) |
| 防毒軟體阻擋遠端除錯 | 暫時關閉防毒或將 Chrome 加入排除清單 |

---

## 專案結構

```
.
├── README.md                    # 本說明文件
├── start_chrome_for_bot.bat     # Windows 啟動 Chrome (cmd 版)
├── start_chrome_ps1.ps1         # Windows 啟動 Chrome (PowerShell 版)
└── rb/                          # 搶票機器人代碼
    ├── generic_ticket_bot.py    # 通用搶票機器人（推薦）
    ├── my_ticket_bot.py         # tixcraft 專用（備用）
    └── captcha/                 # 驗證碼相關輔助檔案
```

---

## 使用建議

1. **先用模式 A + `generic_ticket_bot.py`** 嘗試
2. 若自動流程卡住，檢查驗證碼是否需要手動輸入
3. 需要自訂流程可參考 `my_ticket_bot.py` 結構
