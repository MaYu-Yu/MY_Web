import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from pytube import YouTube, Playlist,Channel
import re

app = Flask(__name__)

def init_db():
    with sqlite3.connect('youtube_data.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                id TEXT NOT NULL PRIMARY KEY,
                name TEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS playlists (
                id TEXT NOT NULL PRIMARY KEY,
                title TEXT NOT NULL,
                last_updated DATE,
                track_flag INTEGER,
                channel_id TEXT,
                FOREIGN KEY (channel_id) REFERENCES channels (id)
            )
        ''')

        # 刪除 videos 表的 PRIMARY KEY 約束
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT NOT NULL,
                url TEXT NOT NULL,
                is_download_flag INTEGER,
                playlists_id TEXT,
                FOREIGN KEY (playlists_id) REFERENCES playlists (id)
            )
        ''')

        conn.commit()

def get_video_ID(url):
    """Returns YouTube's video ID from the URL."""
    youtube_regex = r"^(?:https?:\/\/)?(?:www\.)?(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=))(?P<video_ID>(\w|-)[^&]+)(?:\S+)?$"
    sreMatch = re.match(youtube_regex, url)
    if sreMatch is not None:
        return sreMatch.group("video_ID")
    return None

def get_playlist_ID(url):
    """Returns YouTube's Playlist ID from the URL."""
    youtube_regex = r"[?&]list=(?P<list_ID>([^&]+))"
    sreMatch = re.search(youtube_regex, url)
    if sreMatch is not None:
        return sreMatch.group("list_ID")
    return None

def get_channel_info(url):
    channel_id = get_video_ID(url)
    if channel_id is None:    
        channel_id = get_playlist_ID(url)
        if channel_id is not None:
            channel_id = Playlist(url).owner_id
    else:
        channel_id = YouTube(url).channel_id
    if channel_id is not None:
        url = "https://www.youtube.com/channel/" + channel_id
        channel_name = Channel(url).channel_name
        url += '/playlists'

    # 設定ChromeDriver的路徑&init
    chrome_path = "./chromedriver.exe"
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    service = ChromeService(chrome_path)
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # 如果 URL 中間有 @，則保留 @ 後面到下一個 / 之間的文本，然後直接 + '/playlists'
    if '@' in url:
        url = url.split('@')[0] + '@' + url.split('@')[1].split('/')[0] + '/playlists'
    print(url)
    # 打開目標URL
    driver.get(url)
    # 等待頁面加載完成
    driver.implicitly_wait(10)

    # 獲取頁面源碼
    page_source = driver.page_source

    soup = BeautifulSoup(page_source, 'html.parser')

    # 找到 channel_name 的 <yt-formatted-string>
    channel_name_element = soup.find('yt-formatted-string', {'class': 'style-scope ytd-channel-name'})
    channel_name = channel_name_element.get_text(strip=True) if channel_name_element else None

    # 找到 channel_id 的 <yt-formatted-string>
    channel_id_element = soup.find('yt-formatted-string', {'class': 'style-scope ytd-c4-tabbed-header-renderer'})
    channel_id = channel_id_element.get_text(strip=True) if channel_id_element else None

    # 找到所有的超連結
    links = soup.find_all('a', href=True)

    # 獲取播放清單的 id
    playlist_id_list = []
    for link in links:
        href = link['href']
        playlist_id = get_playlist_ID(href)
        if playlist_id is not None:
            playlist_id_list.append(playlist_id)

    # 關閉瀏覽器
    driver.quit()

    return channel_id, channel_name, playlist_id_list

def get_data_from_db():
    with sqlite3.connect('youtube_data.db') as conn:
        cursor = conn.cursor()

        # 獲取所有 channels
        cursor.execute('SELECT * FROM channels')
        channels = []
        for channel_row in cursor.fetchall():
            channel = {'id':channel_row[0],'name': channel_row[1], 'playlists': []}

            # 獲取該 channel 的所有 playlists
            cursor.execute('SELECT * FROM playlists WHERE channel_id = ?', (channel_row[0],))
            for playlist_row in cursor.fetchall():
                playlists = {'id': playlist_row[0],'title': playlist_row[1], 'last_updated': playlist_row[2], 'track_flag': playlist_row[3]}
                channel['playlists'].append(playlists)

            channels.append(channel)

    return channels

@app.route('/toggle_track_flag', methods=['POST'])
def toggle_track_flag():
    if request.method == 'POST':
        playlist_id = request.form['playlistId']

        # 确保 current_flag 是整数
        current_flag = int(request.form['currentFlag'])

        with sqlite3.connect('youtube_data.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT track_flag FROM playlists WHERE id = ?', (playlist_id,))
            existing_track_flag = cursor.fetchone()[0]

            if existing_track_flag is not None:
                new_track_flag = 1 if current_flag == 0 else 0
                cursor.execute('UPDATE playlists SET track_flag = ? WHERE id = ?', (new_track_flag, playlist_id))
                conn.commit()

    # 重定向到主页
    return redirect(url_for('index'))

@app.route('/', methods=['GET', 'POST'])
def index():
    error_message = None
    channels = []

    if request.method == 'POST':
        url = request.form['url']
        channel_id, channel_name, playlist_id_list = get_channel_info(url)

        if channel_id == None: 
            error_message = "Invalid YouTube Channel URL"
        else:
            with sqlite3.connect('youtube_data.db') as conn:
                cursor = conn.cursor()

                # 查詢 channels 表中是否已經存在相同的 channel_id
                cursor.execute('SELECT id FROM channels WHERE id = ?', (channel_id,))
                existing_channel = cursor.fetchone()
                # 如果不存在，則插入新資料
                if not existing_channel:
                    cursor.execute('INSERT INTO channels (id, name) VALUES (?, ?)', (channel_id, channel_name))
                    conn.commit()

                for list_id in playlist_id_list:
                    # 查詢 playlists 表中是否已經存在相同的 playlists_id
                    cursor.execute('SELECT id FROM playlists WHERE id = ?', (list_id,))
                    existing_playlist = cursor.fetchone()

                    # 如果不存在，則插入新資料
                    if not existing_playlist:
                        try:
                            pytube_playlist = Playlist("https://www.youtube.com/playlist?list=" + list_id)
                            cursor.execute('INSERT INTO playlists (id, title, last_updated, track_flag, channel_id) VALUES (?, ?, ?, ?, ?)',
                                            (list_id, pytube_playlist.title, pytube_playlist.last_updated, 0, channel_id))
                            conn.commit()
                        # pytube_playlist.last_updated 如果年齡、會員限制會出錯
                        except Exception:
                            print(f"playlists's id:{list_id} has some problem.")
                            cursor.execute('INSERT INTO playlists (id, title, last_updated, track_flag, channel_id) VALUES (?, ?, ?, ?, ?)',
                                (list_id, pytube_playlist.title, None, 0, channel_id))
                            continue
                    else:
                        pytube_playlist = Playlist("https://www.youtube.com/playlist?list=" + list_id)            
                    # 插入 videos 資料
                    for video_url in pytube_playlist.video_urls:
                        video_id = get_video_ID(video_url)

                        # 檢查是否已經存在相同的 video_id
                        cursor.execute('SELECT video_id FROM videos WHERE video_id = ? AND playlists_id = ?', (video_id, list_id))
                        existing_video = cursor.fetchone()

                        if not existing_video:
                            cursor.execute('INSERT INTO videos (video_id, url, is_download_flag, playlists_id) VALUES (?, ?, ?, ?)',
                                            (video_id, video_url, 0,list_id))
                            conn.commit()
    channels = get_data_from_db()
    return render_template('index.html', error_message=error_message, channels=channels)
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
