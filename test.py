# download video audio OK
import os, re, random
import logging
import ffmpeg
from pathlib import Path
from pytube import YouTube, Playlist
import urllib.request
from mutagen.mp4 import MP4, MP4Cover
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, ID3NoHeaderError

def get_random():
    temp = [i for i in range(1, 10000)]
    random.shuffle(temp)
    for i in temp:
        yield str(i)
# 解析ID
def get_id_from_url(url):
    """Extracts video_ID and list_ID from a YouTube URL.

    Args:
        url (str): YouTube URL.

    Returns:
        tuple: (video_ID, list_ID) or (None, None) if not found.
    """
    video_id = get_video_ID(url)
    playlist_id = get_playlist_ID(url)
    return video_id, playlist_id
def get_video_ID(url):
    """Returns YouTube's video ID from the URL.

    Args:
        url (str): YouTube URL.

    Returns:
        str: video_ID or None if not found.
    """
    youtube_regex = r"^(?:https?:\/\/)?(?:www\.)?(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=))(?P<video_ID>(\w|-)[^&]+)(?:\S+)?$"
    sreMatch = re.match(youtube_regex, url)
    if sreMatch is not None:
        return sreMatch.group("video_ID")
    else:
        logging.warning("Not a YouTube's URL.")
        return None
def get_playlist_ID(url):
    """Returns YouTube's Playlist ID from the URL.

    Args:
        url (str): YouTube URL.

    Returns:
        str: Playlist_ID or None if not found.
    """
    youtube_regex = r"[?&]list=(?P<list_ID>([^&]+))"
    sreMatch = re.search(youtube_regex, url)
    if sreMatch is not None:
        return sreMatch.group("list_ID")
    else:
        logging.warning("Not a YouTube's PlayList URL.")
        return None
    
def download(url, save_path, audio_only=False):
    yt = YouTube(url)
    video_id, _ = get_id_from_url(url)
    img = Path("./temp/img/"+video_id+".jpg")
    if not img.exists():
        urllib.request.urlretrieve(yt.thumbnail_url, img) # download img
    info_dict ={
        "title": yt.title, 
        "thumbnail_path": str(img),
        "author": yt.author,
        #"captions": yt.captions,# 字幕
        "publish_date": yt.publish_date,
        "views": yt.views,
        "play_len": yt.length
        }
    audio_stream = yt.streams.filter(mime_type="audio/mp4").last() # 最高音質
    audio_path = audio_stream.download(output_path="temp", filename_prefix=next(random_num), skip_existing=False)
    if audio_only:
        output_path = os.path.join(save_path, audio_stream.default_filename.replace(".mp4", ".mp3"))
        convert_to_mp3(audio_path, output_path)
    else:
        video_stream = yt.streams.filter(adaptive=True, mime_type="video/mp4").first() # 最高畫質
        video_path = video_stream.download(output_path="temp", filename_prefix=next(random_num), skip_existing=False)
        output_path = os.path.join(save_path, video_stream.default_filename)
        merge_audio_and_video(audio_path, video_path, output_path)
        os.remove(video_path)
        
    add_info(output_path, info_dict)
    os.remove(audio_path)
    return output_path
def convert_to_mp3(input_path, output_path):
    try:
        ffmpeg.input(input_path).output(output_path).run(overwrite_output=True)
    except ffmpeg.Error as e:
        os.remove(input_path)
        os.remove(output_path)
        logging.error("convert_to_mp3 error.")
        logging.error(f"Error(stdout): {e.stdout}")
        logging.error(f"Error(stderr): {e.stderr}")
def merge_audio_and_video(audio_path, video_path, output_path):
    try:
        audio = ffmpeg.input(audio_path)
        video = ffmpeg.input(video_path)
        ffmpeg.output(audio, video, output_path, acodec='aac').run(overwrite_output=True)
    except ffmpeg.Error as e:
        os.remove(audio_path)
        os.remove(video_path)
        os.remove(output_path)
        logging.error("merge_audio_and_video")
        logging.error(f"Error(stdout): {e.stdout}")
        logging.error(f"Error(stderr): {e.stderr}")
def add_info(file_name, info_dict):
    _, file_extension = os.path.splitext(file_name.lower())
    if file_extension == '.mp3':
        add_info_mp3(file_name, info_dict)
    elif file_extension == '.mp4':
        add_info_mp4(file_name, info_dict)

def add_info_mp3(file_name, info_dict):
    try:
        audio = ID3(file_name)
    except ID3NoHeaderError as e:
        audio = ID3()
        logging.error("add_info_mp3 error.")
        logging.error(e)
    audio.delete()
    audio.add(TIT2(encoding=3, text=info_dict["title"]))
    audio.add(TPE1(encoding=3, text=info_dict["author"]))
    audio.add(TALB(encoding=3, text=info_dict["author"]))
    with open(info_dict["thumbnail_path"], 'rb') as f:
        cover_data = f.read()
        audio.add(APIC(3, 'image/jpeg', 3, 'Front cover', cover_data))
    audio.save(file_name)

def add_info_mp4(file_name, info_dict):
    mp4 = MP4(file_name)
    mp4.delete()
    mp4["\xa9nam"] = info_dict["title"]
    mp4["\xa9ART"] = info_dict["author"]
    mp4["\xa9alb"] = info_dict["author"]
    with open(info_dict["thumbnail_path"], 'rb') as f:
        cover_data = f.read()
        mp4["covr"] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
    mp4.save()
def playlist(url):
    playlist = Playlist(url)
    playlist_gen = playlist.url_generator()
    try:
        video_url = next(playlist_gen)
        print(video_url)
    except StopIteration:
        print("No videos available.")
if __name__ == "__main__":
    random_num = get_random()
    url = "https://www.youtube.com/watch?v=_7vMtu_nqaI&list=RDGMEMXdNDEg4wQ96My0DhjI-cIg&index=23"
    Path("./temp/img/").mkdir(parents=True, exist_ok=True)
    download(url, 'E:\Program\Code\yt_auto_tracker\ot', False)