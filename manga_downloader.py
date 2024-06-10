import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import json
from selenium.common.exceptions import NoSuchElementException, WebDriverException
import re, random

class MangaDownloader:
    def __init__(self):
        # 設置ChromeDriver的選項
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--disable-infobars')
        self.chrome_options.add_argument('--disable-extensions')
        self.chrome_options.add_argument('--log-level=3') 
        self.chrome_path = "./chromedriver.exe"
    
        # 設定儲存圖片的資料夾
        self.static_folder = "static"
        self.manga_folder = "static/manga"
        self.json_folder = "static/manga/json"
        if not os.path.exists(self.json_folder):
            os.makedirs(self.json_folder)
        self.history_json_path = os.path.join(self.json_folder, "history.json")
    
    def get_json_path(self):
        return self.json_folder
    def get_history_path(self):
        return self.history_json_path
    
    def load_history(self):
        unfinished_manga = {}
        if os.path.exists(self.history_json_path):
            with open(self.history_json_path, 'r', encoding='utf-8') as f:
                history = json.load(f)
                unfinished_manga = {entry['chapter_name']: entry['downloaded_title'] for entry in history}
        return unfinished_manga
    def start_webdriver(self):
        self.service = Service(self.chrome_path)
        self.service.start()
        self.driver = webdriver.Remote(self.service.service_url, options=self.chrome_options)
        self.wait = WebDriverWait(self.driver, 10)

    def stop_webdriver(self):
        self.driver.quit()
        self.service.stop()

    def retry_func(self, func, max_retries=3, min_wait_time=1, max_wait_time=5):
        for attempt in range(max_retries):
            try:
                return func()
            except WebDriverException as e:
                if "ERR_SSL_PROTOCOL_ERROR" in str(e):
                    print(f"嘗試 {attempt + 1}/{max_retries} 失敗，出現 ERR_SSL_PROTOCOL_ERROR 錯誤，正在重試...")
                    wait_time = random.uniform(min_wait_time, max_wait_time)
                    print(f"等待 {wait_time:.2f} 秒後重試...")
                    time.sleep(wait_time)
                    self.stop_webdriver()
                    self.start_webdriver()
                else:
                    raise e
        raise Exception(f"重試 {max_retries} 次後仍然失敗")

    def search_manga(self, search_keyword):
        self.start_webdriver()
        url = "https://www.cartoonmad.com/"
        try:
            # 使用ChromeDriver打開網頁
            self.retry_func(lambda: self.driver.get(url))

            # 找到搜索框並輸入關鍵字
            search_input = self.driver.find_element(By.NAME, "keyword")
            search_input.send_keys(search_keyword)

            # 找到提交按鈕並點擊submit
            submit_button = self.driver.find_element(By.XPATH, '/html/body/table/tbody/tr[1]/td[1]/table/tbody/tr[3]/td/table/tbody/tr[3]/td/input')
            submit_button.click()

            # 等待搜索結果頁面加載完成
            self.retry_func(lambda: self.wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/table/tbody/tr[1]/td[2]/table/tbody/tr[4]/td/table/tbody/tr[2]/td[2]/table'))))

            # 獲取搜索結果中的超連結和對應的標題
            search_results = self.driver.find_elements(By.XPATH, '/html/body/table/tbody/tr[1]/td[2]/table/tbody/tr[4]/td/table/tbody/tr[2]/td[2]/table//a')
            result_links = {}  # title:link
            for result in search_results:
                title = result.text
                err_title_patterns = [
                    r"更新到第 ",
                    r"^\s*$"  # Is entirely empty or contains only whitespace
                ]
                if any(re.search(pattern, title) for pattern in err_title_patterns):
                    continue
                link = result.get_attribute("href")
                result_links[title] = link
            return result_links
        except Exception as e:
            print(e)

        finally:
            self.stop_webdriver()
            
    def manga_to_json(self, title, link):
        self.start_webdriver()
        try:
            # 打開用戶選擇的漫畫鏈接
            self.retry_func(lambda: self.driver.get(link))

            # 等待頁面加載完成
            self.retry_func(lambda: self.wait.until(EC.presence_of_element_located((By.XPATH, '/html/body/table/tbody/tr[1]/td[2]/table/tbody/tr[4]/td/table/tbody/tr[2]/td[2]/table[3]/tbody/tr/td/fieldset/table'))))

            # 獲取漫畫集數和每集的鏈接及頁數
            chapter = self.driver.find_element(By.XPATH, '/html/body/table/tbody/tr[1]/td[2]/table/tbody/tr[4]/td/table/tbody/tr[2]/td[2]/table[3]/tbody/tr/td/fieldset/table')
            chapter_info = []
            link_elements = chapter.find_elements(By.TAG_NAME, 'a')
            
            for link_element in link_elements:
                chapter_title = link_element.text
                chapter_link = link_element.get_attribute('href')
                pages = chapter.find_element(By.TAG_NAME, 'font').text
                chapter_info.append({
                    'title': chapter_title,
                    'link': chapter_link,
                    'pages': pages
                })
            # 將漫畫信息存儲到JSON文件中
            json_save_path = os.path.join(self.json_folder, f"{title}.json")
            with open(json_save_path, 'w', encoding='utf-8') as json_file:
                json.dump(chapter_info, json_file, ensure_ascii=False, indent=4)
            # 存入history
            self.save_chapter_title(title, chapter_info[0]['title'])
            print(f"漫畫信息已存儲到 {json_save_path}")
            return json_save_path
        except Exception as e:
            print(e)

        finally:
            self.stop_webdriver()
    def save_chapter_title(self, chapter_name, chapter_title):
        # 檢查是否已存在下載歷史檔案
        if os.path.exists(self.history_json_path):
            # 讀取現有的下載歷史
            with open(self.history_json_path, 'r', encoding='utf-8') as json_file:
                download_history = json.load(json_file)
        else:
            download_history = []

        # 檢查是否已存在相同的章節名稱
        found = False
        for item in download_history:
            if item['chapter_name'] == chapter_name:
                item['downloaded_title'] = chapter_title
                found = True
                break

        # 如果沒找到相同的章節名稱，則新增一條記錄
        if not found:
            download_history.append({
                'chapter_name': chapter_name,
                'downloaded_title': chapter_title,
            })

        # 將更新後的下載歷史寫回 JSON 文件
        with open(self.history_json_path, 'w', encoding='utf-8') as json_file:
            json.dump(download_history, json_file, ensure_ascii=False, indent=4)
        print("{} 已更新".format(self.history_json_path))
    def get_chapter_title(self, chapter_name):

        # 檢查下載歷史檔案是否存在
        if os.path.exists(self.history_json_path):
            # 讀取下載歷史檔案
            with open(self.history_json_path, 'r', encoding='utf-8') as json_file:
                download_history = json.load(json_file)

            # 在下載歷史中尋找指定章節名稱
            for item in download_history:
                if item['chapter_name'] == chapter_name:
                    return item['downloaded_title']
            
            # 如果指定章節名稱不存在，返回 None
            return None
        else:
            print("{} 下載歷史檔案不存在".format(chapter_name))
            return None
    def download_manga(self, json_file_path):
        self.start_webdriver()
        try:
            with open(json_file_path, 'r', encoding='utf-8') as json_file:
                chapter_info = json.load(json_file)
            chapter_name = os.path.splitext(os.path.basename(json_file_path))[0]  # json名稱

            now_chapter_title = self.get_chapter_title(chapter_name)
            is_downlaoded_flag = now_chapter_title != None
            # 下載每個章節的圖片
            for chapter in chapter_info:
                chapter_title = chapter['title']
                chapter_link = chapter['link']
                chapter_pages = chapter['pages']
                
                if now_chapter_title and chapter_title == now_chapter_title: 
                    is_downlaoded_flag = False
                if is_downlaoded_flag: 
                    print("跳過{}".format(chapter_title))
                    continue
                self.save_chapter_title(chapter_name, chapter_title)
                # 目標網址
                url = chapter_link

                # 設定儲存圖片的資料夾
                save_folder_path = os.path.join(self.manga_folder, chapter_name, chapter_title)
                if not os.path.exists(save_folder_path):
                    os.makedirs(save_folder_path)
                chapter_num = 0
                while True:
                    chapter_num += 1
                    # 使用ChromeDriver打開網頁
                    self.retry_func(lambda: self.driver.get(url))

                    # 等待圖片加載完成
                    self.retry_func(lambda: self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'img[src*=".jpg"]'))))

                    # 獲取第一張圖片元素
                    image = self.driver.find_element(By.CSS_SELECTOR, 'img[src*=".jpg"]')

                    # 獲取圖片URL
                    image_src = image.get_attribute("src")

                    # 保存圖片，以連續順序命名
                    image_path = os.path.join(save_folder_path, f"{chapter_name}_{chapter_title}_{chapter_num}.jpg")
                    response = requests.get(image_src)
                    with open(image_path, "wb") as img_file:
                        img_file.write(response.content)
                    print(f"圖片 {image_path} 已保存")

                    try:
                        # 找到下一頁按鈕
                        next_button = self.driver.find_element(By.XPATH, '//a[@class="pages" and contains(text(), "下一頁")]')
                    except NoSuchElementException:
                        print("已到達最後一頁，結束下載。")
                        break

                    # 點擊下一頁按鈕
                    next_button.click()
                    # 等待頁面跳轉完成
                    time.sleep(5)
                    # 更新當前網址
                    url = self.driver.current_url
                    if "thend.asp" in url:
                        print("已到達最後一頁，結束下載。")
                        break
        except Exception as e:
            print(e)

        finally:
            self.stop_webdriver()

# 使用示例
if __name__ == "__main__":
    downloader = MangaDownloader()
    
    # 搜索漫畫
    #search_keyword = input("請輸入要搜索的關鍵字：")
    #downloader.search_manga(search_keyword)

    # 下載漫畫
    json_file_path = input("請輸入JSON文件的路徑：")
    downloader.download_manga(json_file_path)
