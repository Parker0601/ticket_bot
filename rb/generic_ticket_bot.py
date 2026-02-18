"""
通用搶票機器人：只需提供目標網址，依頁面上的按鈕文字自動尋找並操作。
不依賴特定網站的 XPath/CSS，適用多種購票網站。
"""
import re
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

# 可選：驗證碼 OCR（若未安裝 PIL/cv2/pytesseract 則跳過驗證碼自動輸入）
try:
    from PIL import Image
    import cv2
    import pytesseract
    HAS_OCR = True
    # 若你有自訂 Tesseract 路徑可在此設定
    if os.path.exists(r"C:\Windsurf\OCR_data\tesseract.exe"):
        pytesseract.pytesseract.tesseract_cmd = r"C:\Windsurf\OCR_data\tesseract.exe"
except ImportError:
    HAS_OCR = False

# ========== 設定：只需改這裡 ==========
TICKET_URL = "https://tixcraft.com/activity/detail/26_amz"  # 改成你要搶的活動網址
WAIT_TIMEOUT = 15
SCROLL_PAUSE = 0.5
CAPTCHA_SAVE_DIR = "captcha"

# ---------- 瀏覽器模式 ----------
#  A. 你自己先開 Chrome（需帶除錯 port），腳本再連線到該 Chrome。有你的登入狀態。
#     先關閉所有 Chrome，再用：chrome.exe --remote-debugging-port=9333 開啟（或執行 start_chrome_for_bot.bat）。
#  B. 由腳本開一個全新的 Chrome（無帳號，無登入）。
#
CHROME_MODE = "A"  # 選 A 或 B

# A 模式：你手動開的 Chrome 的除錯位址（需與你啟動 Chrome 時用的 port 一致）
CHROME_DEBUGGER_ADDRESS = "127.0.0.1:9222"

# 除錯：是否印出找到的按鈕數量
DEBUG_FIND_BUTTONS = True
# ======================================

# 依「按鈕/連結文字」自動辨識的關鍵字（可依需要增減）
KEYWORDS_BUY = ["購票", "訂票", "立即購票", "立即訂購", "立即購買", "我要購票", "買票", "訂購"]
KEYWORDS_SUBMIT = ["提交", "確認", "送出", "完成訂購", "結帳", "下一步"]
KEYWORDS_AGREE = ["同意", "我同意", "接受", "勾選同意"]
KEYWORDS_SEAT = ["選座", "選擇座位", "選位"]
# 用於尋找「可點選的座位」：通常是有剩餘張數的區塊
KEYWORDS_SEAT_AVAILABLE = ["可售", "剩餘", "選取", "選擇"]


def get_driver(headless=False, mode_override=None):
    """
    - A：連到你已開啟的 Chrome（你需先用 --remote-debugging-port 開 Chrome），腳本只做連線。
    - B：由 ChromeDriver 開一個全新的 Chrome（該 Chrome 會連上 ChromeDriver 的除錯 port）。
    """
    options = Options()
    options.page_load_strategy = "eager"
    options.add_argument("--disable-blink-features=AutomationControlled")

    mode = (mode_override or CHROME_MODE).strip().upper()

    if mode == "A":
        addr = CHROME_DEBUGGER_ADDRESS
        options.add_experimental_option("debuggerAddress", addr)
        print("模式 A：連線至你已開啟的 Chrome ({})".format(addr))
    else:
        # B：全新 Chrome（ChromeDriver 自己開，除錯 port 由 ChromeDriver 處理）
        print("模式 B：全新 Chrome")

    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")

    return webdriver.Chrome(options=options)


def scroll(driver, num, wait):
    driver.execute_script(f"window.scrollTo(0, {num});")
    time.sleep(SCROLL_PAUSE)
    try:
        wait.until(lambda d: d.execute_script("return document.documentElement.scrollTop") >= max(0, num - 50))
    except TimeoutException:
        pass


def get_visible_text(el):
    """取得元素的可見文字（不含子元素重複）。"""
    return (el.text or "").strip()


def is_clickable_element(el):
    """判斷是否為可點擊元素。"""
    tag = el.tag_name.lower()
    if tag in ("a", "button"):
        return True
    if tag == "input":
        t = (el.get_attribute("type") or "").lower()
        return t in ("submit", "button", "image")
    role = (el.get_attribute("role") or "").lower()
    if role == "button":
        return True
    return False


def find_clickables_by_keywords(driver, keywords, scroll_into_view=True):
    """
    在頁面上找出「文字包含任一關鍵字」且可點擊的元素。
    回傳 list of (element, matched_keyword)。
    """
    candidates = []
    # 常見可點擊的選擇器
    selectors = [
        "a", "button", "input[type='submit']", "input[type='button']",
        "[role='button']", "span[onclick]", "div[onclick]", "li a", "li"
    ]
    seen = set()
    for sel in selectors:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                if not el.is_displayed():
                    continue
                text = get_visible_text(el)
                if not text:
                    # 按鈕有時文字在子節點
                    text = (el.get_attribute("innerText") or el.get_attribute("value") or "").strip()
                for kw in keywords:
                    if kw in text:
                        key = (el.id, el.get_attribute("outerHTML")[:80] if el.get_attribute("outerHTML") else None)
                        if key not in seen and is_clickable_element(el):
                            seen.add(key)
                            candidates.append((el, kw))
                        break
        except Exception:
            continue
    # 用 XPath 補強：任何包含文字的可點擊元素
    try:
        for kw in keywords:
            xpath = f"//*[contains(text(), '{kw}') and (self::a or self::button or @role='button' or self::input)]"
            for el in driver.find_elements(By.XPATH, xpath):
                if not el.is_displayed():
                    continue
                key = (el.id, el.get_attribute("outerHTML")[:80] if el.get_attribute("outerHTML") else None)
                if key not in seen and is_clickable_element(el):
                    seen.add(key)
                    candidates.append((el, kw))
    except Exception:
        pass
    if scroll_into_view and candidates:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", candidates[0][0])
            time.sleep(0.3)
        except Exception:
            pass
    return candidates


def click_first_match(driver, wait, keywords, step_name="按鈕"):
    """找到第一個符合關鍵字的可點擊元素並點擊。"""
    for attempt in range(3):
        scroll(driver, 300, wait)
        time.sleep(0.3)
        matches = find_clickables_by_keywords(driver, keywords)
        if not matches:
            scroll(driver, 800, wait)
            time.sleep(0.3)
            matches = find_clickables_by_keywords(driver, keywords)
        if DEBUG_FIND_BUTTONS:
            if matches:
                print("  [除錯] 找到 {} 個符合 {} 的按鈕，關鍵字: {}".format(
                    len(matches), step_name, [kw for _, kw in matches[:5]]))
            else:
                print("  [除錯] 未找到符合「{}」的按鈕（關鍵字: {}）".format(step_name, keywords[:5]))
        if matches:
            el, kw = matches[0]
            try:
                wait.until(EC.element_to_be_clickable(el))
                el.click()
                print(f"  已點擊 [{step_name}]: 含「{kw}」")
                return True
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", el)
                print(f"  已點擊 (JS) [{step_name}]: 含「{kw}」")
                return True
            except Exception as e:
                print(f"  點擊失敗: {e}")
        time.sleep(0.5)
    return False


def find_and_click_agree(driver, wait):
    """尋找「同意」類的 checkbox 或按鈕並點擊。"""
    # Checkbox
    for sel in ["input[type='checkbox']", "[role='checkbox']"]:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                if not el.is_displayed():
                    continue
                # 找相鄰或父層的 label 文字
                try:
                    label = el.get_attribute("aria-label") or ""
                    parent = el.find_element(By.XPATH, "./..")
                    label = label or (parent.text or "").strip()[:50]
                except Exception:
                    label = ""
                for kw in KEYWORDS_AGREE:
                    if kw in label or (el.get_attribute("id") or "").lower().find("agree") >= 0:
                        try:
                            if not el.is_selected():
                                el.click()
                            print("  已勾選同意")
                            return True
                        except Exception:
                            driver.execute_script("arguments[0].click();", el)
                            return True
        except Exception:
            continue
    # 按鈕/連結形式的「我同意」
    return click_first_match(driver, wait, KEYWORDS_AGREE, "同意")


def find_quantity_select(driver, default_value="1"):
    """尋找票數下拉選單並設為 default_value。"""
    try:
        for sel in driver.find_elements(By.TAG_NAME, "select"):
            if not sel.is_displayed():
                continue
            opts = [o.get_attribute("value") for o in sel.find_elements(By.TAG_NAME, "option") if o.get_attribute("value")]
            if default_value in opts:
                Select(sel).select_by_value(default_value)
                print(f"  已選擇票數: {default_value}")
                return True
            if opts:
                Select(sel).select_by_value(opts[0])
                print(f"  已選擇票數: {opts[0]}")
                return True
    except Exception as e:
        print(f"  選擇票數時發生錯誤: {e}")
    return False


def find_seat_clickable(driver, wait):
    """嘗試找到可點選的座位（例如第一個可售區）。"""
    # 常見座位區塊 class 關鍵字
    seat_selectors = [
        "li.select_form_b", "li[class*='seat']", "li[class*='select']",
        "[class*='seat-available']", "[data-status='available']",
        ".seat-available", ".available"
    ]
    for sel in seat_selectors:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in els:
                if not el.is_displayed():
                    continue
                try:
                    wait.until(EC.element_to_be_clickable(el))
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    time.sleep(0.2)
                    el.click()
                    print("  已選擇座位區")
                    return True
                except Exception:
                    try:
                        driver.execute_script("arguments[0].click();", el)
                        print("  已選擇座位區 (JS)")
                        return True
                    except Exception:
                        continue
        except Exception:
            continue
    # 若頁面上有「選座」按鈕，可能要先點一下
    click_first_match(driver, wait, KEYWORDS_SEAT + KEYWORDS_SEAT_AVAILABLE, "選座")
    return False


def find_captcha_image_and_input(driver):
    """尋找驗證碼圖片與對應輸入框（通用推測）。"""
    # 常見驗證碼圖片
    img_selectors = [
        "img[id*='captcha']", "img[id*='verify']", "img[id*='code']",
        "img[class*='captcha']", "img[class*='verify']", "img[alt*='驗證']"
    ]
    cap_img = None
    for sel in img_selectors:
        try:
            imgs = driver.find_elements(By.CSS_SELECTOR, sel)
            for img in imgs:
                if img.is_displayed() and img.size.get("width", 0) > 20 and img.size.get("height", 0) > 20:
                    cap_img = img
                    break
        except Exception:
            continue
        if cap_img:
            break
    if not cap_img:
        return None, None
    # 找同一 form 或附近的 input text
    try:
        parent = cap_img.find_element(By.XPATH, "./ancestor::form | ./ancestor::div[position()<5]")
        inputs = parent.find_elements(By.CSS_SELECTOR, "input[type='text']")
        for inp in inputs:
            if inp.is_displayed():
                return cap_img, inp
    except Exception:
        pass
    # 全頁找 name/id 含 verify/captcha/code 的 input
    for inp in driver.find_elements(By.CSS_SELECTOR, "input[type='text']"):
        if not inp.is_displayed():
            continue
        aid = (inp.get_attribute("id") or "") + (inp.get_attribute("name") or "")
        if "verify" in aid.lower() or "captcha" in aid.lower() or "code" in aid.lower():
            return cap_img, inp
    return cap_img, None


def try_ocr_captcha(driver, cap_img, input_el, save_dir=CAPTCHA_SAVE_DIR):
    """截圖驗證碼、OCR、填入輸入框。"""
    if not HAS_OCR or not input_el:
        return False
    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, "screenshot.png")
    driver.save_screenshot(path)
    try:
        loc = cap_img.location
        sz = cap_img.size
        left = loc["x"]
        top = loc["y"]
        right = left + sz["width"]
        bottom = top + sz["height"]
        image = Image.open(path)
        image = image.crop((left, top, right, bottom))
        cap_path = os.path.join(save_dir, "captcha.png")
        image.save(cap_path, "png")
        img = cv2.imread(cap_path)
        if img is None:
            return False
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        dst = 255 - gray
        picture = Image.fromarray(dst)
        threshold = 115
        table = [0 if i < threshold else 1 for i in range(256)]
        binary = picture.convert("L").point(table, "1")
        text = pytesseract.image_to_string(binary).strip()
        text = re.sub(r"\s+", "", text)[:10]
        if text:
            input_el.clear()
            input_el.send_keys(text)
            print(f"  已自動填入驗證碼: {text}")
            return True
    except Exception as e:
        print(f"  OCR 驗證碼失敗: {e}")
    return False


def run_generic_flow(url, headless=False, chrome_mode=None, ticket_count="1"):
    """執行通用搶票流程：只依賴網址與頁面文字。"""
    driver = get_driver(headless=headless, mode_override=chrome_mode)
    wait = WebDriverWait(driver, WAIT_TIMEOUT)

    print("開啟網頁:", url)
    driver.get(url)
    time.sleep(1)

    # 1) 購票 / 訂購 按鈕
    if not click_first_match(driver, wait, KEYWORDS_BUY, "購票/訂購"):
        print("未找到購票按鈕，請手動操作或檢查關鍵字")
    time.sleep(1)

    # 2) 立即訂購 / 選座 等
    click_first_match(driver, wait, KEYWORDS_BUY + KEYWORDS_SEAT, "立即訂購/選座")
    time.sleep(1)
    scroll(driver, 500, wait)

    # 3) 選座位（若頁面有）
    find_seat_clickable(driver, wait)
    time.sleep(0.5)
    scroll(driver, 400, wait)

    # 4) 票數
    find_quantity_select(driver, default_value=ticket_count)
    time.sleep(0.5)

    # 5) 驗證碼
    cap_img, input_el = find_captcha_image_and_input(driver)
    if cap_img and input_el:
        try_ocr_captcha(driver, cap_img, input_el)
    elif cap_img:
        print("  找到驗證碼圖但未找到輸入框，請手動輸入驗證碼")
    time.sleep(0.3)

    # 關閉可能的 alert
    try:
        driver.switch_to.alert.accept()
    except Exception:
        pass

    # 6) 同意
    find_and_click_agree(driver, wait)
    time.sleep(0.3)

    # 7) 提交 / 確認
    if not click_first_match(driver, wait, KEYWORDS_SUBMIT, "提交/確認"):
        print("未找到提交按鈕，請手動點擊確認")

    print("流程執行完畢，請在瀏覽器內確認結果。")
    return driver


if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else TICKET_URL
    run_generic_flow(url, headless=False)
