from __future__ import annotations

import os
import time
from datetime import datetime
from http.cookiejar import Cookie, CookieJar
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener
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
RUN_AT_TW = "15:39"  # 例如 "12:00" 或 "12:00:00"，設為 "" 代表立即執行
DEBUGGER_ADDRESS = "127.0.0.1:9222"
WAIT_TIMEOUT_SECONDS = 10
TICKET_SELECT_CSS = "select[id^='TicketForm_ticketPrice_']"
TICKET_COUNT = "1"
PAGELOAD_TIMEOUT_SECONDS = 20
ENABLE_ATTACH_HANDSHAKE = True
CAPTCHA_IMAGE_ID = "TicketForm_verifyCode-image"
CAPTCHA_INPUT_ID = "TicketForm_verifyCode"
CAPTCHA_MIN_CONFIDENCE = 0.92
CAPTCHA_MAX_ATTEMPTS = 3
PREFERRED_AREAS = [
    "黃1B-2區 (best available)",
    "黃2B-1區",
]


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
    driver.execute_script("arguments[0].click();", element)


def fast_click_js_xpath(driver: webdriver.Chrome, xpath: str) -> bool:
    return bool(
        driver.execute_script(
            """
            const xp = arguments[0];
            const node = document.evaluate(
                xp,
                document,
                null,
                XPathResult.FIRST_ORDERED_NODE_TYPE,
                null
            ).singleNodeValue;
            if (!node) return false;
            node.click();
            return true;
            """,
            xpath,
        )
    )


def visible_attach_handshake(driver: webdriver.Chrome) -> None:
    # 可視化握手：幫你確認程式控制的是哪個 Chrome 視窗
    ts = int(time.time())
    driver.switch_to.new_window("tab")
    driver.get(f"about:blank#bot_connected_{ts}")
    print(f"[可視化握手] 已建立識別分頁: about:blank#bot_connected_{ts}")


def click_first_available_seat(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.area-list li a[id]")))
    blocked_keywords = ("已售完", "Sold Out", "售完", "暫無票")
    blocked_classes = ("disabled", "soldout", "sold_out", "none", "off")

    def _is_blocked(text: str, class_name: str) -> bool:
        if any(keyword in text for keyword in blocked_keywords):
            return True
        return any(flag in class_name for flag in blocked_classes)

    seats = driver.find_elements(By.CSS_SELECTOR, "ul.area-list li a[id]")

    # 先嘗試使用者指定區域名稱（不綁 group_0，跨所有 area-list 搜尋）
    for area_name in PREFERRED_AREAS:
        for seat in seats:
            text = (seat.text or "").strip()
            class_name = (seat.get_attribute("class") or "").lower()
            if area_name not in text:
                continue
            if _is_blocked(text, class_name):
                continue
            if driver.execute_script("arguments[0].click(); return true;", seat):
                print(f"已選指定區域: area='{area_name}' text='{text}'")
                return

    # 指定區域不可用時，回退為任一可買區域
    for seat in seats:
        text = (seat.text or "").strip()
        class_name = (seat.get_attribute("class") or "").lower()
        if _is_blocked(text, class_name):
            continue
        if driver.execute_script("arguments[0].click(); return true;", seat):
            print(f"已選回退區域: text='{text}'")
            return

    debug_text = [
        f"{idx}: text='{(s.text or '').strip()}' class='{(s.get_attribute('class') or '').strip()}'"
        for idx, s in enumerate(seats[:10])
    ]
    raise RuntimeError("無可購買座位。候選座位: " + " | ".join(debug_text))


def capture_captcha_image(
    driver: webdriver.Chrome,
    wait: WebDriverWait,
    output_path: Path,
) -> str:
    captcha_element = wait.until(EC.presence_of_element_located((By.ID, CAPTCHA_IMAGE_ID)))
    captcha_src = captcha_element.get_attribute("src") or ""
    captcha_element.screenshot(str(output_path))

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("驗證碼截圖失敗：檔案不存在或大小為 0")
    return captcha_src


def _selenium_cookie_to_jar_cookie(raw_cookie: dict, domain: str) -> Cookie:
    cookie_domain = raw_cookie.get("domain") or domain
    return Cookie(
        version=0,
        name=raw_cookie["name"],
        value=raw_cookie["value"],
        port=None,
        port_specified=False,
        domain=cookie_domain,
        domain_specified=bool(cookie_domain),
        domain_initial_dot=str(cookie_domain).startswith("."),
        path=raw_cookie.get("path", "/"),
        path_specified=True,
        secure=bool(raw_cookie.get("secure", False)),
        expires=raw_cookie.get("expiry"),
        discard=False,
        comment=None,
        comment_url=None,
        rest={"HttpOnly": raw_cookie.get("httpOnly", False)},
        rfc2109=False,
    )


def download_captcha_image_with_browser_cookies(
    driver: webdriver.Chrome,
    captcha_src: str,
    output_path: Path,
) -> bool:
    if not captcha_src:
        return False

    parsed = urlparse(captcha_src)
    if not parsed.scheme or not parsed.netloc:
        return False

    jar = CookieJar()
    for cookie in driver.get_cookies():
        if "name" in cookie and "value" in cookie:
            jar.set_cookie(_selenium_cookie_to_jar_cookie(cookie, parsed.netloc))

    opener = build_opener(HTTPCookieProcessor(jar))
    user_agent = driver.execute_script("return navigator.userAgent;") or "Mozilla/5.0"
    req = Request(captcha_src, headers={"User-Agent": user_agent, "Referer": driver.current_url})
    with opener.open(req, timeout=10) as resp:
        image_bytes = resp.read()

    output_path.write_bytes(image_bytes)
    return output_path.exists() and output_path.stat().st_size > 0


def refresh_captcha_image(driver: webdriver.Chrome, wait: WebDriverWait) -> None:
    captcha_element = wait.until(EC.presence_of_element_located((By.ID, CAPTCHA_IMAGE_ID)))
    driver.execute_script("arguments[0].click();", captcha_element)
    time.sleep(0.35)


def build_captcha_tensor(captcha_image_path: Path, device: torch.device) -> torch.Tensor:
    # Keep grayscale + fixed size to match the training/input shape expected by the CRNN.
    image = Image.open(captcha_image_path).convert("L")
    image = image.resize((200, 60), resample=Image.BILINEAR)
    image_tensor = transforms.ToTensor()(image).unsqueeze(0).to(device)
    if image_tensor.ndim != 4 or image_tensor.shape[1] != 1:
        raise RuntimeError(f"模型輸入維度不正確: shape={tuple(image_tensor.shape)}")
    return image_tensor


def predict_captcha_text(
    model: nn.Module,
    device: torch.device,
    captcha_image_path: Path,
) -> tuple[str, float]:
    image_tensor = build_captcha_tensor(captcha_image_path, device)

    with torch.no_grad():
        logits = model(image_tensor)
        probs = torch.softmax(logits, dim=2)
        conf_per_char, pred_idx = probs.max(dim=2)
    text = "".join(IDX_TO_CHAR[i] for i in pred_idx.squeeze(0).tolist())
    confidence = float(conf_per_char.mean().item())
    return text, confidence


def fast_select_ticket_count_js(driver: webdriver.Chrome, ticket_count: str) -> bool:
    return bool(
        driver.execute_script(
            """
            const desired = String(arguments[0]);
            const selects = Array.from(
              document.querySelectorAll("select[id^='TicketForm_ticketPrice_']")
            );
            const visible = (el) => {
              const style = window.getComputedStyle(el);
              return !!(el.offsetParent || el.getClientRects().length) &&
                     style.visibility !== 'hidden' &&
                     style.display !== 'none';
            };
            for (const s of selects) {
              if (s.disabled || !visible(s)) continue;
              const hasOption = Array.from(s.options).some(o => o.value === desired);
              if (!hasOption) continue;
              s.value = desired;
              s.dispatchEvent(new Event('input', { bubbles: true }));
              s.dispatchEvent(new Event('change', { bubbles: true }));
              return true;
            }
            return false;
            """,
            ticket_count,
        )
    )


def select_ticket_count(driver: webdriver.Chrome, wait: WebDriverWait, ticket_count: str) -> None:
    if fast_select_ticket_count_js(driver, ticket_count):
        print(f"已選擇票數(JS): count={ticket_count}")
        return

    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, TICKET_SELECT_CSS)))
    selects = driver.find_elements(By.CSS_SELECTOR, TICKET_SELECT_CSS)
    for elem in selects:
        if not elem.is_displayed() or not elem.is_enabled():
            continue

        select = Select(elem)
        values = [opt.get_attribute("value") for opt in select.options]
        if ticket_count not in values:
            continue

        select.select_by_value(ticket_count)
        print(f"已選擇票數: count={ticket_count} select_id={elem.get_attribute('id')}")
        return

    available = []
    for elem in selects:
        if not elem.is_displayed() or not elem.is_enabled():
            continue
        select = Select(elem)
        available.append(
            f"{elem.get_attribute('id')} values={[opt.get_attribute('value') for opt in select.options]}"
        )
    raise RuntimeError(f"找不到可選擇票數 {ticket_count} 的票數下拉。可用候選: {' | '.join(available)}")


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

    options = Options()
    options.add_experimental_option("debuggerAddress", DEBUGGER_ADDRESS)
    options.page_load_strategy = "eager"
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, WAIT_TIMEOUT_SECONDS)
    driver.set_page_load_timeout(PAGELOAD_TIMEOUT_SECONDS)

    wait_until_tw_time(RUN_AT_TW)

    if ENABLE_ATTACH_HANDSHAKE:
        visible_attach_handshake(driver)

    print("開啟網頁中...")
    nav_start = time.perf_counter()
    driver.get(TARGET_URL)
    nav_elapsed = time.perf_counter() - nav_start
    ready_state = driver.execute_script("return document.readyState;")
    current_host = driver.execute_script("return location.hostname;")
    print(
        f"[導航結果] host={current_host} readyState={ready_state} "
        f"elapsed={nav_elapsed:.2f}s"
    )

    # 點開購票（優先直接 JS 查找+點擊；失敗時回退既有等待點擊）
    buy_link_xpath = "//div[@class='activityContent']//li[@class='buy']/a"
    if not fast_click_js_xpath(driver, buy_link_xpath):
        fast_click(driver, wait, By.XPATH, buy_link_xpath)

    # 立即訂購（優先直接 JS 查找+點擊；失敗時回退既有等待點擊）
    order_btn_xpath = "//button[@class='btn btn-primary text-bold m-0' and contains(text(), '立即訂購')]"
    if not fast_click_js_xpath(driver, order_btn_xpath):
        fast_click(driver, wait, By.XPATH, order_btn_xpath)

    # 選擇座位
    click_first_available_seat(driver, wait)

    # 選擇票數
    select_ticket_count(driver, wait, TICKET_COUNT)

    captcha_dir = Path("captcha")
    os.makedirs(captcha_dir, exist_ok=True)
    captcha_path = captcha_dir / "captcha.png"
    captcha_src = capture_captcha_image(driver, wait, captcha_path)
    print("驗證碼網址：", captcha_src)

    text = ""
    confidence = 0.0
    for attempt in range(1, CAPTCHA_MAX_ATTEMPTS + 1):
        downloaded = False
        try:
            downloaded = download_captcha_image_with_browser_cookies(driver, captcha_src, captcha_path)
        except Exception as exc:
            print(f"[captcha] 下載原圖失敗，改用元素截圖（attempt={attempt}）：{exc}")

        if not downloaded:
            captcha_src = capture_captcha_image(driver, wait, captcha_path)

        text, confidence = predict_captcha_text(model, device, captcha_path)
        print(
            f"CRNN 模型識別結果（第 {attempt}/{CAPTCHA_MAX_ATTEMPTS} 次）: "
            f"'{text}' (conf={confidence:.3f})"
        )

        if confidence >= CAPTCHA_MIN_CONFIDENCE:
            break

        if attempt < CAPTCHA_MAX_ATTEMPTS:
            print("[captcha] 置信度偏低，刷新驗證碼後重試。")
            refresh_captcha_image(driver, wait)
            captcha_src = capture_captcha_image(driver, wait, captcha_path)

    # 輸入驗證碼
    input_captcha = wait.until(EC.presence_of_element_located((By.ID, CAPTCHA_INPUT_ID)))
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
