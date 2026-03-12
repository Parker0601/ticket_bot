from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image
import cv2
import pytesseract

# 設定 Tesseract 路徑
pytesseract.pytesseract.tesseract_cmd = r"C:\Windsurf\OCR_data\tesseract.exe"

# 以下 XPATH 與 CSS_SELECTOR 已根據 ibon 流程填入
IBON_URL = "https://ticket.ibon.com.tw/ActivityInfo/Details/39449"  # 修改為實際購票頁面
# 點選「線上購票」按鈕，預設使用 XPath 文字匹配。
# 有時文字是透過 ::before 加入，Selenium 無法讀取，這時可改用 CSS 選擇器
OPERATE_1_XPATH = "//button[@class='btn btn-pink btn-buy ng-tns-c58-1 ng-star-inserted']"  # 或空字串代表使用 CSS 後備方案
# 以 id 開頭為 B0A 的 tr 做為區域列表，真正的可用性在迴圈內判斷
SEAT_SELECTOR = "tr[id^='B0A']"
# 票數下拉選單（依附圖中的 id）
TICKET_QUANTITY_XPATH = "//*[@id='ctl00_ContentPlaceHolder1_DataGrid_ctl02_AMOUNT_DDL']"
CAPTCHA_IMAGE_ID = ""  # ibon 暫無驗證碼
CAPTCHA_INPUT_ID = ""
AGREE_CHECKBOX_XPATH = ""  # 如有同意勾選，可填入 XPATH
CONFIRM_BUTTON_SELECTOR = ""  # 最後送出按鈕，可視情況填寫

try:
    options = Options()
    options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    options.page_load_strategy = 'eager'
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 10)

    import time

    def scroll(num):
        # 將頁面向下卷動到指定位置，並稍微停頓以確保效果
        driver.execute_script("window.scrollTo(0, arguments[0]);", num)
        time.sleep(0.5)
        # 進一步確認是否真的滾動到指定位置，必要時可重新執行
        current = driver.execute_script("return document.documentElement.scrollTop")
        if current < num:
            driver.execute_script("window.scrollBy(0, arguments[0]);", num - current)
            time.sleep(0.3)


    print("開啟 ibon 網頁中...")
    driver.get(IBON_URL)

    # 等頁面載入並列出目前所有 button 元素以便調試
    driver.implicitly_wait(3)
    btns = driver.find_elements(By.TAG_NAME, "button")
    print(f"頁面共有 {len(btns)} 個<button>元件")
    for i, b in enumerate(btns, start=1):
        print(f"button {i}: class={b.get_attribute('class')} text='{b.text}' outerHTML={b.get_attribute('outerHTML')}\n")
    # 檢查是否存在 iframe
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    print(f"頁面共有 {len(iframes)} 個 iframe")
    for i, f in enumerate(iframes, start=1):
        print(f"iframe {i} src={f.get_attribute('src')}\n")

    scroll(500)

    # 線上購票
    elem_operate_1 = None
    if OPERATE_1_XPATH:
        try:
            elem_operate_1 = wait.until(EC.element_to_be_clickable((By.XPATH, OPERATE_1_XPATH)))
        except Exception as e:
            print(f"XPath 失效: {e}")
    # 如果還沒找到或 OPERATE_1_XPATH 為空，用 CSS 選擇器做後備
    if not elem_operate_1:
        # 列出所有符合條件的按鈕以便調試
        candidates = driver.find_elements(By.CSS_SELECTOR, "button.btn-buy")
        print(f"CSS btn-buy 找到 {len(candidates)} 個候選按鈕")
        for idx, btn in enumerate(candidates, start=1):
            print(f"候選 {idx} outerHTML:\n{btn.get_attribute('outerHTML')}\n")
        try:
            elem_operate_1 = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn-buy")))
        except Exception as e:
            print(f"CSS btn-buy 也找不到或不可點擊: {e}")
    # 最終嘗試再使用包含文字的遲緩查找
    if not elem_operate_1:
        try:
            elem_operate_1 = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., '線上購票')]")))
        except Exception as e:
            print(f"最後文字匹配也失敗: {e}")
            raise Exception("無法定位線上購票按鈕")
    elem_operate_1.click()

    scroll(500)

    # 選擇座位區（掃第一個有空位的 tr）
    if SEAT_SELECTOR:
        rows = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, SEAT_SELECTOR)))
        picked = False
        for row in rows:
            try:
                span = row.find_element(By.CSS_SELECTOR, "td[data-title='空位'] span")
                if span.text.strip() and int(span.text.strip()) > 0:
                    wait.until(EC.element_to_be_clickable(row)).click()
                    picked = True
                    break
            except Exception:
                continue
        if not picked:
            raise Exception("找不到有空位的座位區")

    scroll(400)

    # 選擇票數
    if TICKET_QUANTITY_XPATH:
        elem_select_num = wait.until(EC.element_to_be_clickable((By.XPATH, TICKET_QUANTITY_XPATH)))
        Select(elem_select_num).select_by_value("1")

    # 截圖驗證碼
    path = 'captcha/screenshot.png'
    driver.save_screenshot(path)

    if CAPTCHA_IMAGE_ID:
        element = driver.find_element(By.ID, CAPTCHA_IMAGE_ID)
        print(element.get_attribute("src"))

        location = element.location
        size = element.size
        # 依實際位置調整裁切邏輯
        left = location['x']
        top = location['y']
        right = location['x'] + size['width']
        bottom = location['y'] + size['height']

        image = Image.open(path)
        image = image.crop((left, top, right, bottom))
        image.save('captcha/captcha.png', 'png')

        # OCR 辨識驗證碼
        img = cv2.imread('captcha/captcha.png')
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        dst = 255 - gray
        cv2.imwrite('captcha/captcha_gray.png', dst)

        picture = Image.open('captcha/captcha_gray.png')
        gray = picture.convert('L')

        threshold = 115
        table = [0 if i < threshold else 1 for i in range(256)]
        binary = gray.point(table, '1')
        binary.save('captcha/captcha_binary.png')

        Pic_read = Image.open('captcha/captcha_binary.png')
        text = pytesseract.image_to_string(Pic_read)

        # 輸入驗證碼
        print("正在定位驗證碼輸入欄位...")
        try:
            input_captcha = wait.until(EC.presence_of_element_located((
                (By.ID, CAPTCHA_INPUT_ID)
            )))
            input_captcha.clear()
            input_captcha.send_keys(text)
            print("測試驗證碼已輸入")
        except Exception as e:
            print(f"輸入驗證碼時發生錯誤：{e}")
            raise

    try:
        driver.switch_to.alert.accept()
    except Exception:
        pass

    # 點選 "我同意"
    if AGREE_CHECKBOX_XPATH:
        accept = wait.until(EC.element_to_be_clickable((By.XPATH, AGREE_CHECKBOX_XPATH)))
        accept.click()

    # 提交
    if CONFIRM_BUTTON_SELECTOR:
        confirm = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR, 
            CONFIRM_BUTTON_SELECTOR
        )))
        confirm.click()

except Exception as e:
    print(f"錯誤：{e}")
