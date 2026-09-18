from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
import yt_dlp
import tempfile
import os
import re

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

    quality_number = re.search(r"\d+", str(quality))
    height = quality_number.group() if quality_number else "720"

    output_template = os.path.join(
        temp_dir,
        "%(title)s.%(ext)s"
    )

    if format.lower() == "audio":
        options = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "quiet": True,
            "noplaylist": True
        }
    else:
        options = {
            "format": (
                f"best[height<={height}]/"
                "best"
            ),
            "outtmpl": output_template,
            "quiet": True,
            "noplaylist": True
        }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)

        if not os.path.exists(downloaded_file):
            files = os.listdir(temp_dir)
            if not files:
                return {"error": "Ba a samu file ba"}
            downloaded_file = os.path.join(temp_dir, files[0])

        return FileResponse(
            downloaded_file,
            filename=os.path.basename(downloaded_file),
            media_type="application/octet-stream"
        )

    except Exception as error:
        return {
            "error": str(error)
        }
