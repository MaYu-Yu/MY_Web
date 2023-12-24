import torch, os
from pathlib import Path
from whisper.utils import get_writer
from deep_translator import GoogleTranslator
import pysrt
import ffmpeg
import whisper

class AutoSubtitles:
    def __init__(self, output_folder_path="./", model_type="medium"):
        """
        初始化 AutoSubtitles 類別

        參數:
            output_folder_path (str): 輸出資料夾路徑
            model_type (str): Whisper 模型類型
        """
        self.AUDIO_EXTENSIONS = ['.mp3', '.mp4', '.wav']
        self.SRT_EXTENSIONS = ['.srt']
        
        # 設定預設的輸出資料夾
        self.output_folder = Path(output_folder_path)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        
        # 檢查 GPU cuda
        print(torch.version)  # 檢查 PyTorch 版本
        self.DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_type = model_type
        print("使用 GPU:", torch.cuda.is_available())  # 檢查是否使用 GPU

        # 載入 Whisper 模型 model_type= tiny < base < small < medium < large
        print("正在加载 Whisper 模型...")  # 載入 Whisper 語音轉文字模型
        self.whisper_model = whisper.load_model(self.model_type, device=self.DEVICE)
        
        
    def is_audio_file(self, file_path):
        return Path(file_path).suffix.lower() in self.AUDIO_EXTENSIONS
    
    def is_srt_file(self, file_path):
        return Path(file_path).suffix.lower() in self.SRT_EXTENSIONS       
    
    def extract_audio_to_srt(self, input_path):
        """
        從音頻提取文字到文本

        参数:
            input_path (str): 輸入音頻檔案路徑

        返回:
            str: SRT檔案路徑，提取失敗則為None
        """
        if not self.is_audio_file(input_path):
            return None

        output_path = self.output_folder / f"{Path(input_path).stem}.srt"
        print("正在音頻轉文本...")  # 開始從音頻提取文字
        audio = whisper.load_audio(input_path)
        
        # 音頻轉文本
        result = self.whisper_model.transcribe(audio)

        # 存入srt
        srt_writer = get_writer("srt", str(self.output_folder))  # 提供完整路徑
        srt_writer(result, output_path)
        print(f"SRT 存入: {output_path}")  # SRT 檔案存入位置
        return output_path

    def srt_translate_to_srt(self, input_path, source='auto', target='zh-TW'):
        """
        將srt檔案翻譯成指定語言

        参数:
            input_path (str): 輸入SRT檔案路徑
            source (str): SRT檔案原始語言，預設為'auto'
            target (str): 翻譯目標語言，預設為'zh-TW'

        返回:
            str: SRT檔案路徑，翻譯失敗則為None
        """
        if not self.is_srt_file(input_path): return None
        output_path = str(self.output_folder / f"{Path(input_path).with_suffix('').stem}_{target}.srt")
        print("正在翻譯文本...")  # 開始翻譯文字
        subs = pysrt.open(input_path, encoding='utf-8')
        with open(output_path, 'w', encoding='UTF-8') as fw:
            for sub in subs:
                translated_text = GoogleTranslator(source=source, target=target).translate(sub.text)
                if translated_text is not None:
                    sub.text = translated_text
                    fw.write(str(sub) + '\n')
        print(f"翻譯結果存入: {output_path}")  # 翻譯結果存入位置
        return output_path
    

    def add_subtitles(self, srt_path, input_path):
        """
        將SRT字幕加入到視頻內

        参数:
            srt_path (str):  輸入SRT檔案路徑
            input_path (str): 輸入視頻檔案路徑

        返回:
            str: 視頻檔案路徑，加入失敗則為None
        """
        import shutil
        if not self.is_audio_file(input_path):
            return None
        if not self.is_srt_file(srt_path):
            return None


        temp_output_path = str(self.output_folder / f"{Path(input_path).stem}_temp.mp4")
        
        print("正在加入字幕...")  # 開始將字幕嵌入音頻
        
        try:
            # 臨時檔案
            ffmpeg.input(input_path).output(temp_output_path, vf=f'subtitles={srt_path}').run()
            # 重命名
            shutil.move(temp_output_path, input_path)

            print(f"視頻已加入字幕: {input_path}")  # 嵌入字幕後的檔案存入位置
            return input_path
        except ffmpeg.Error as e:
            print(f"加入字幕時發生錯誤: {e.stderr}")
            return str(e.stderr)
        
    def auto_add_subtitles(self, audio_path):
        """
        一鍵執行生成字幕、翻譯、加入視頻內

        参数:
            audio_path (str): 輸入音頻/視頻檔案路徑

        返回:
            str: 輸出的視頻檔案路徑，輸出失敗則為None
        """
        
        try:
            audio_srt_path = self.extract_audio_to_srt(audio_path)
            if not audio_srt_path:
                return None
            transed_srt_path = auto_subtitles.srt_translate_to_srt(audio_srt_path)
            if not transed_srt_path:
                return None
            result = auto_subtitles.add_subtitles(transed_srt_path, audio_path)
            os.remove(audio_srt_path)
            os.remove(transed_srt_path)
            return result
        except Exception as e:
            try:
                os.remove(audio_srt_path)
                os.remove(transed_srt_path)
            except Exception as e:
                print(f"刪除TEMP出錯: {e}")
if __name__ == "__main__":
    auto_subtitles = AutoSubtitles()
    audio_path = "o/test.mp4"
    
    result = auto_subtitles.auto_add_subtitles(audio_path)
    print(result)
