from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image
import cv2
import torch
import torch.nn as nn
from torchvision import transforms
from pathlib import Path


# 定義 CRNN 模型
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


# 字符集定義
CHAR_SET = "abcdefghijklmnopqrstuvwxyz"
IDX_TO_CHAR = {idx: ch for idx, ch in enumerate(CHAR_SET)}

# 初始化模型
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = CaptchaCRNN().to(device)
model_path = Path(__file__).resolve().parent / "captcha_model" / "best_lowercase_crnn.pth"
if model_path.exists():
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.eval()
    print(f"模型已加載: {model_path}")
else:
    print(f"警告：模型文件未找到: {model_path}")

transform = transforms.Compose([
    transforms.Grayscale(),
    transforms.Resize((60, 200)),
    transforms.ToTensor(),
])

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
    driver.get("https://tixcraft.com/activity/detail/26_laufey")

    scroll(500)

    # 點開購票
    elem_operate_1 = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@class='activityContent']//li[@class='buy']/a")))
    elem_operate_1.click()

    # 立即購票
    elem_operate_2 = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@class='btn btn-primary text-bold m-0' and contains(text(), '立即訂購')]")))
    elem_operate_2.click()



    # 選擇座位
    available_seats = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "li.select_form_a")))
    if available_seats:
        seat = wait.until(EC.element_to_be_clickable(available_seats[0]))
        seat.click()
    else:
        raise Exception("無可購買座位")

    scroll(400)

    # 選擇票數
    elem_select_num = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@id='TicketForm_ticketPrice_11']")))
    Select(elem_select_num).select_by_value("1")

    # 截圖驗證碼—直接讓 element 擷取，避免座標偏移
    element = driver.find_element(By.ID, "TicketForm_verifyCode-image")
    print("驗證碼網址：", element.get_attribute("src"))
    # 確保目錄存在
    import os
    os.makedirs('captcha', exist_ok=True)
    element.screenshot('captcha/captcha.png')

    # 使用 CRNN 模型辨識驗證碼
    try:
        image = Image.open('captcha/captcha.png').convert("RGB")
        image_tensor = transform(image).unsqueeze(0).to(device)
        
        with torch.no_grad():
            logits = model(image_tensor)
            pred_idx = logits.argmax(dim=2).squeeze(0).tolist()
        
        text = "".join(IDX_TO_CHAR[i] for i in pred_idx)
        print(f"CRNN 模型識別結果: '{text}'")
    except Exception as e:
        print(f"模型推理失敗，改用備用方案：{e}")
        # 備用方案：簡單的圖像處理
        img = cv2.imread('captcha/captcha.png')
        if img is None:
            raise Exception('無法讀取 captcha.png 檔案')
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        gray = cv2.medianBlur(gray, 3)
        dst = 255 - gray
        _, binary_img = cv2.threshold(dst, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # 由於移除了 pytesseract，此處使用簡單替代
        print("無法進行備用識別")
        text = ""


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
