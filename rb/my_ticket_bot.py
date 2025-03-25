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

    def scroll(num):
        driver.execute_script(f"window.scrollTo(0, {num});")  
        wait.until(lambda d: d.execute_script("return document.documentElement.scrollTop") >= num)

    print("開啟網頁中...")
    driver.get("https://tixcraft.com/activity/detail/25_bii")

    scroll(500)

    # 點開購票
    elem_operate_1 = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@class='activityContent']//li[@class='buy']/a")))
    elem_operate_1.click()

    # 立即購票
    elem_operate_2 = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@class='btn btn-primary text-bold m-0' and contains(text(), '立即訂購')]")))
    elem_operate_2.click()

    scroll(500)

    # 選擇座位
    available_seats = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.select_form_b")))
    if available_seats:
        seat = wait.until(EC.element_to_be_clickable(available_seats[0]))
        seat.click()
    else:
        raise Exception("無可購買座位")

    scroll(400)

    # 選擇票數
    elem_select_num = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@id='TicketForm_ticketPrice_02']")))
    Select(elem_select_num).select_by_value("1")

    # 截圖驗證碼
    path = 'captcha/screenshot.png'
    driver.save_screenshot(path)  # 先將目前的 screen 存起來


    element = driver.find_element(By.ID, "TicketForm_verifyCode-image")
    print(element.get_attribute("src"))  # 檢查驗證碼圖片網址

    location = element.location
    size = element.size
    left = location['x'] + 140
    top = location['y'] - 330
    right = location['x'] + size['width'] + 160
    bottom = location['y'] + size['height'] - 330

    image = Image.open(path)
    image = image.crop((left, top, right, bottom))
    image.save('captcha/captcha.png', 'png')

    # OCR 辨識驗證碼
    img = cv2.imread('captcha/captcha.png')
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    dst = 255 - gray
    cv2.imwrite('captcha/captcha_gray.png', dst)

    # 圖片二值化
    picture = Image.open('captcha/captcha_gray.png')
    gray = picture.convert('L')

    threshold = 115
    table = [0 if i < threshold else 1 for i in range(256)]
    binary = gray.point(table, '1')
    binary.save('captcha/captcha_binary.png')

    # OCR 解析
    Pic_read = Image.open('captcha/captcha_binary.png')
    text = pytesseract.image_to_string(Pic_read)

    # 輸入驗證碼
    print("正在定位驗證碼輸入欄位...")
    try:
        input_captcha = wait.until(EC.presence_of_element_located((
            (By.ID, "TicketForm_verifyCode")
        )))
        input_captcha.clear()  # 清除可能存在的文字
        input_captcha.send_keys(text)
        print("測試驗證碼已輸入")
    except Exception as e:
        print(f"輸入驗證碼時發生錯誤：{e}")
        raise

    try:
        driver.switch_to.alert.accept()  # 若出現彈出視窗，點掉
    except Exception:
        pass

    # 點選 "我同意"
    accept = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@id='TicketForm_agree']")))
    accept.click()

    # 提交
    confirm = wait.until(EC.element_to_be_clickable((
        By.CSS_SELECTOR, 
        "button.btn.btn-primary.btn-green"
    )))
    confirm.click()

except Exception as e:
    print(f"錯誤：{e}")
