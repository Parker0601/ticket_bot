from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import torch
import torch.nn as nn
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait
from torchvision import transforms


# -----------------------------
# 可自行調整區域
# -----------------------------
TARGET_URL = "https://tixcraft.com/activity/detail/26_laufey"
RUN_AT_TW = "01:23"  # 例如 "12:00" 或 "12:00:00"，設為 "" 代表立即執行
DEBUGGER_ADDRESS = "127.0.0.1:9222"
WAIT_TIMEOUT_SECONDS = 10
TICKET_SELECT_XPATH = "//*[@id='TicketForm_ticketPrice_11']"
TICKET_COUNT = "1"


class CaptchaCRNN(nn.Module):
    def __init__(self, seq_length: int = 4, num_classes: int = 26):
        super().__init__()
        self.seq_length = seq_length
        self.num_classes = num_classes

        self.cnn = nn.Sequential(
            nn.Conv2d(1, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Dropout(0.25),
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Dropout(0.25),
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Dropout(0.25),
            nn.Conv2d(256, 256, kernel_size=(7, 1)),
            nn.BatchNorm2d(256),
            nn.ReLU(),
            nn.Dropout(0.25),
        )

        self.rnn_input_size = 256
        self.rnn_hidden_size = 512
        self.lstm = nn.LSTM(
            self.rnn_input_size,
            self.rnn_hidden_size,
            num_layers=2,
            bidirectional=True,
            dropout=0.5,
            batch_first=True,
        )
        self.adaptive_pool = nn.AdaptiveAvgPool1d(self.seq_length)
        self.classifier = nn.Linear(self.rnn_hidden_size * 2, self.num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.cnn(x)
        x = x.squeeze(2)
        x = x.permute(0, 2, 1)
        output, _ = self.lstm(x)
        output = output.permute(0, 2, 1)
        output = self.adaptive_pool(output)
        output = output.permute(0, 2, 1)
        output = self.classifier(output.contiguous().view(-1, self.rnn_hidden_size * 2))
        output = output.view(-1, self.seq_length, self.num_classes)
        return output


CHAR_SET = "abcdefghijklmnopqrstuvwxyz"
IDX_TO_CHAR = {idx: ch for idx, ch in enumerate(CHAR_SET)}


def wait_until_tw_time(run_at_tw: str) -> None:
    run_at_tw = (run_at_tw or "").strip()
    if not run_at_tw:
        print("未設定排程時間，立即執行。")
        return

    tz = ZoneInfo("Asia/Taipei")
    fmt = "%H:%M:%S" if len(run_at_tw.split(":")) == 3 else "%H:%M"
    target_clock = datetime.strptime(run_at_tw, fmt).time()
    now = datetime.now(tz)
    target_dt = datetime.combine(now.date(), target_clock, tzinfo=tz)

    if now >= target_dt:
        print(f"目前台灣時間 {now.strftime('%H:%M:%S')} 已超過設定時間 {run_at_tw}，立即執行。")
        return

    print(f"已預載完成，等待台灣時間 {run_at_tw} 開始流程...")
    last_print_second = -1
    while True:
        now = datetime.now(tz)
        remain = (target_dt - now).total_seconds()
        if remain <= 0:
            print(f"到達台灣時間 {run_at_tw}，開始執行。")
            return

        if int(remain) != last_print_second and int(remain) % 30 == 0:
            print(f"倒數 {int(remain)} 秒")
            last_print_second = int(remain)

        time.sleep(0.2 if remain <= 5 else 1.0)


def fast_click(driver: webdriver.Chrome, wait: WebDriverWait, by: By, selector: str) -> None:
    element = wait.until(EC.element_to_be_clickable((by, selector)))
    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", element)
    driver.execute_script("arguments[0].click();", element)


def predict_captcha_text(
    model: nn.Module,
    device: torch.device,
    transform: transforms.Compose,
    captcha_image_path: Path,
) -> str:
    image = Image.open(captcha_image_path).convert("RGB")
    image_tensor = transform(image).unsqueeze(0).to(device)

    with torch.no_grad():
        logits = model(image_tensor)
        pred_idx = logits.argmax(dim=2).squeeze(0).tolist()

    return "".join(IDX_TO_CHAR[i] for i in pred_idx)


def main() -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = CaptchaCRNN().to(device)
    model_path = Path(__file__).resolve().parent / "captcha_model" / "best_lowercase_crnn.pth"
    if model_path.exists():
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval()
        print(f"模型已加載: {model_path}")
    else:
        raise FileNotFoundError(f"模型文件未找到: {model_path}")

    transform = transforms.Compose(
        [
            transforms.Grayscale(),
            transforms.Resize((60, 200)),
            transforms.ToTensor(),
        ]
    )

    options = Options()
    options.add_experimental_option("debuggerAddress", DEBUGGER_ADDRESS)
    options.page_load_strategy = "eager"
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, WAIT_TIMEOUT_SECONDS)

    wait_until_tw_time(RUN_AT_TW)

    print("開啟網頁中...")
    driver.get(TARGET_URL)

    # 點開購票
    fast_click(driver, wait, By.XPATH, "//div[@class='activityContent']//li[@class='buy']/a")

    # 立即訂購
    fast_click(
        driver,
        wait,
        By.XPATH,
        "//button[@class='btn btn-primary text-bold m-0' and contains(text(), '立即訂購')]",
    )

    # 選擇座位（第一個可點擊）
    seats = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.select_form_a")))
    if not seats:
        raise RuntimeError("無可購買座位")
    driver.execute_script("arguments[0].click();", seats[0])

    # 選擇票數
    ticket_select = wait.until(EC.element_to_be_clickable((By.XPATH, TICKET_SELECT_XPATH)))
    Select(ticket_select).select_by_value(TICKET_COUNT)

    # 擷取驗證碼
    captcha_element = wait.until(EC.presence_of_element_located((By.ID, "TicketForm_verifyCode-image")))
    print("驗證碼網址：", captcha_element.get_attribute("src"))
    captcha_dir = Path("captcha")
    os.makedirs(captcha_dir, exist_ok=True)
    captcha_path = captcha_dir / "captcha.png"
    captcha_element.screenshot(str(captcha_path))

    text = predict_captcha_text(model, device, transform, captcha_path)
    print(f"CRNN 模型識別結果: '{text}'")

    # 輸入驗證碼
    input_captcha = wait.until(EC.presence_of_element_located((By.ID, "TicketForm_verifyCode")))
    input_captcha.clear()
    input_captcha.send_keys(text)
    print("驗證碼已輸入")

    # 關閉可能彈窗
    try:
        driver.switch_to.alert.accept()
    except Exception:
        pass

    # 同意條款 + 提交
    fast_click(driver, wait, By.XPATH, "//*[@id='TicketForm_agree']")
    fast_click(driver, wait, By.CSS_SELECTOR, "button.btn.btn-primary.btn-green")
    print("提交流程完成")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"錯誤：{exc}")
        raise
