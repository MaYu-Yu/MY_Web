import os
import re
import random
import ffmpeg
from pathlib import Path
from pytube import YouTube, Playlist
import urllib.request
from mutagen.mp4 import MP4, MP4Cover
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, ID3NoHeaderError
import threading

class YouTubeDownloader:
    def __init__(self):
        self.random_num = self.get_random()
        Path("./temp/img/").mkdir(parents=True, exist_ok=True)

    def get_random(self):
        while True:
            temp = [i for i in range(1, 10000)]
            random.shuffle(temp)
            for i in temp:
                yield str(i)
                
    def get_id_from_url(self, url):
        video_id = self.get_video_ID(url)
        playlist_id = self.get_playlist_ID(url)
        return video_id, playlist_id

    def get_video_ID(self, url):
        youtube_regex = r"^(?:https?:\/\/)?(?:www\.)?(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=))(?P<video_ID>(\w|-)[^&]+)(?:\S+)?$"
        sreMatch = re.match(youtube_regex, url)
        if sreMatch is not None:
            return sreMatch.group("video_ID")
        else:
            # print("Not a YouTube's URL.")
            return None

    def get_playlist_ID(self, url):
        youtube_regex = r"[?&]list=(?P<list_ID>([^&]+))"
        sreMatch = re.search(youtube_regex, url)
        if sreMatch is not None:
            return sreMatch.group("list_ID")
        else:
            # print("Not a YouTube's PlayList URL.")
            return None
    
    def convert_to_mp3(self, input_path, output_path):
        try:
            ffmpeg.input(input_path).output(output_path).run(overwrite_output=True)
        except ffmpeg.Error as e:
            os.remove(input_path)
            os.remove(output_path)
            print("convert_to_mp3 error.")
            print(f"Error(stdout): {e.stdout}")
            print(f"Error(stderr): {e.stderr}")

    def merge_audio_and_video(self, audio_path, video_path, output_path):
        try:
            audio = ffmpeg.input(audio_path)
            video = ffmpeg.input(video_path)
            ffmpeg.output(audio, video, output_path, acodec='aac').run(overwrite_output=True)
        except ffmpeg.Error as e:
            os.remove(audio_path)
            os.remove(video_path)
            os.remove(output_path)
            print("merge_audio_and_video")
            print(f"Error(stdout): {e.stdout}")
            print(f"Error(stderr): {e.stderr}")

    def add_info(self, file_name, info_dict):
        _, file_extension = os.path.splitext(file_name.lower())
        if file_extension == '.mp3':
            self.add_info_mp3(file_name, info_dict)
        elif file_extension == '.mp4':
            self.add_info_mp4(file_name, info_dict)

    def add_info_mp3(self, file_name, info_dict):
        try:
            audio = ID3(file_name)
        except ID3NoHeaderError as e:
            audio = ID3()
            print("add_info_mp3 error.")
            print(error(e))
        audio.delete()
        audio.add(TIT2(encoding=3, text=info_dict["title"]))
        audio.add(TPE1(encoding=3, text=info_dict["author"]))
        audio.add(TALB(encoding=3, text=info_dict["author"]))
        with open(info_dict["thumbnail_path"], 'rb') as f:
            cover_data = f.read()
            audio.add(APIC(3, 'image/jpeg', 3, 'Front cover', cover_data))
        audio.save(file_name)

    def add_info_mp4(self, file_name, info_dict):
        mp4 = MP4(file_name)
        mp4.delete()
        mp4["\xa9nam"] = info_dict["title"]
        mp4["\xa9ART"] = info_dict["author"]
        mp4["\xa9alb"] = info_dict["author"]
        with open(info_dict["thumbnail_path"], 'rb') as f:
            cover_data = f.read()
            mp4["covr"] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
        mp4.save()
    
    def download_thread(self, url, output_folder, audio_only, lock):
        try:
            yt = YouTube(url)
            video_id, _ = self.get_id_from_url(url)
            img = Path("./temp/img/"+video_id+".jpg")
            if not img.exists():
                urllib.request.urlretrieve(yt.thumbnail_url, img)  # download img
            info_dict ={
                "title": yt.title, 
                "thumbnail_path": str(img),
                "author": yt.author,
            }
            audio_stream = yt.streams.filter(mime_type="audio/mp4").last()
            audio_path = audio_stream.download(output_path="temp", filename_prefix=next(self.random_num), skip_existing=False)
            if audio_only:
                output_path = os.path.join(output_folder, audio_stream.default_filename.replace(".mp4", ".mp3"))
                self.convert_to_mp3(audio_path, output_path)
            else:
                video_stream = yt.streams.filter(adaptive=True, mime_type="video/mp4").first()
                video_path = video_stream.download(output_path="temp", filename_prefix=next(self.random_num), skip_existing=False)
                output_path = os.path.join(output_folder, video_stream.default_filename)
                self.merge_audio_and_video(audio_path, video_path, output_path)
                os.remove(video_path)
            
            self.add_info(output_path, info_dict)
            os.remove(audio_path)
            with lock:
                print(f"Downloaded: {url}")
        except Exception as e:
            with lock:
                print(f"Error downloading {url}: {e}")

    def download(self, urls, output_folder, audio_only=True):
        threads = []
        lock = threading.Lock()

        for url in urls:
            thread = threading.Thread(target=self.download_thread, args=(url, output_folder, audio_only, lock))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()
    def download_from_playlist_id(self, list_id, output_folder, audio_only=True):
        pl = Playlist("https://www.youtube.com/playlist?list=" + list_id)
        self.download(self, pl.video_urls, output_folder, audio_only)
if __name__ == "__main__":
    downloader = YouTubeDownloader()
    url = ["https://www.youtube.com/watch?v=HSTYgU5SH4s&list=PL1NeGg1woXqlISJkxjgwHKgB8LmR7tk92&index=2"]
    urls = ["https://www.youtube.com/watch?v=khplMpm4ctc&list=PLaxauk3chSWj6Lg0HZtQ8mhTeGRyopOl5", "https://www.youtube.com/watch?v=Igr6jQJEoNs&list=PLaxauk3chSWj6Lg0HZtQ8mhTeGRyopOl5&index=2"]
    output_folder = 'E:\Program\Code\yt_auto_tracker\ot'
    audio_only = True
    downloader.download(urls, output_folder, audio_only)