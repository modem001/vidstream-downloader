from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
import yt_dlp
import tempfile
import os

app = FastAPI()


@app.get("/")
def home():
    return {
        "status": "online",
        "message": "VidStream Downloader API"
    }


@app.get("/download")
def download_video(
    url: str = Query(...),
    quality: str = Query("720"),
    format: str = Query("video")
):
    temp_dir = tempfile.mkdtemp()

    output_template = os.path.join(
        temp_dir,
        "%(title)s.%(ext)s"
    )

    options = {
        "outtmpl": output_template,
        "quiet": True,
        "noplaylist": True,
    }

    if format == "audio":
        options.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        })
    else:
        options["format"] = (
            f"best[height<={quality}][ext=mp4]/best"
        )

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)

        if format == "audio":
            downloaded_file = os.path.splitext(
                downloaded_file
            )[0] + ".mp3"

        return FileResponse(
            downloaded_file,
            filename=os.path.basename(downloaded_file),
            media_type="application/octet-stream"
        )

    except Exception as error:
        return {
            "error": str(error)
        }
