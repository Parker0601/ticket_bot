# ticket_bot
搶票機器人啦幹

## 通用搶票（只給網址）

使用 `rb/generic_ticket_bot.py`：**只需提供要搶票的網址**，不用再寫該網站的 XPath 或 CSS。

- 自動依按鈕/連結**文字**找元素（例如：購票、立即訂購、同意、提交、確認）。
- 自動嘗試找驗證碼圖片與輸入框並用 OCR 辨識（需安裝 PIL、cv2、pytesseract）。
- 自動嘗試選座、選票數、勾選同意、點擊送出。

### 模式說明

- **A**：你自己先開 Chrome（帶除錯 port 9333），腳本再連線。有登入狀態。可用 `start_chrome_for_bot.bat` 或 ps1 開 Chrome。
- **B**：腳本開一個全新的 Chrome（無帳號）。在 `generic_ticket_bot.py` 設 `CHROME_MODE = "B"` 即可。

### A 模式步驟

1. 先**用 port 9333 開啟 Chrome**（二選一）：
   - 雙擊 **`start_chrome_for_bot.bat`**（會先關閉所有 Chrome 再開）
   - 或 PowerShell：**`powershell -ExecutionPolicy Bypass -File start_chrome_ps1.ps1`**
2. 再執行：**`python rb\generic_ticket_bot.py`**

若一直出現「127.0.0.1:9333 沒有程式在監聽」：

| 可能原因 | 做法 |
|----------|------|
| Chrome 在跑 bat 前就已經在跑 | 先**完全關閉** Chrome（工作管理員結束所有 chrome.exe），再執行 bat 或 ps1。 |
| taskkill 沒關乾淨 | 工作管理員手動結束所有 **chrome.exe**，或用「以系統管理員身分執行」跑 bat。 |
| cmd 的 start 沒把參數傳給 Chrome | 改用 **`start_chrome_ps1.ps1`**（PowerShell 較可靠）。 |
| 防毒擋遠端除錯 | 暫時關閉防毒，或把 Chrome 加入排除。 |

### 使用方式

1. **改程式裡的網址**：在 `generic_ticket_bot.py` 最上方改 `TICKET_URL`。
2. **或用指令列傳入網址**：
   ```bash
   python rb/generic_ticket_bot.py "https://你要搶的活動網址"
   ```

### 依賴

- Selenium、Chrome/Chromium
- 驗證碼自動辨識（可選）：PIL、opencv-python、pytesseract，並安裝 Tesseract

---

原本針對 tixcraft 寫的固定流程仍保留在 `rb/my_ticket_bot.py`。
