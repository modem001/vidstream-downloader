import os
import uuid
import shutil
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="VidStream Downloader API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOAD_DIR = Path("/tmp/vidstream_downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def valid_youtube_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""

        return (
            hostname == "youtube.com"
            or hostname.endswith(".youtube.com")
            or hostname == "youtu.be"
            or hostname.endswith(".youtu.be")
        )
    except Exception:
        return False


def clean_old_files():
    try:
        for file in DOWNLOAD_DIR.iterdir():
            if file.is_file():
                file.unlink()
    except Exception:
        pass


@app.get("/")
def home():
    return {
        "status": "online",
        "service": "VidStream Downloader",
        "message": "API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/download")
def download_video(
    url: str = Query(...),
    quality: str = Query("720p"),
    format: str = Query("video")
):
    if not url:
        return JSONResponse(
            status_code=400,
            content={"error": "Video URL is required"}
        )

    if not valid_youtube_url(url):
        return JSONResponse(
            status_code=400,
            content={"error": "Only YouTube URLs are supported"}
        )

    # Convert quality values such as 720p or 720 into a number
    quality_value = str(quality).lower().replace("p", "").strip()

    try:
        height = int(quality_value)
    except ValueError:
        height = 720

    if height not in [144, 240, 360, 480, 720, 1080, 1440, 2160]:
        height = 720

    # Prevent unlimited disk usage
    clean_old_files()

    download_id = uuid.uuid4().hex

    if format.lower() in ["audio", "mp3", "music"]:
        output_template = str(
            DOWNLOAD_DIR / f"{download_id}.%(ext)s"
        )

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android_vr", "web"]
                }
            }
        }

    else:
        output_template = str(
            DOWNLOAD_DIR / f"{download_id}.%(ext)s"
        )

        ydl_opts = {
            "format": (
                f"best[height<={height}][ext=mp4]/"
                f"best[height<={height}]/best"
            ),
            "outtmpl": output_template,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android_vr", "web"]
                }
            }
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)

            downloaded_file = Path(
                ydl.prepare_filename(info)
            )

            # Find actual file if extension changed
            if not downloaded_file.exists():
                possible_files = list(
                    DOWNLOAD_DIR.glob(f"{download_id}.*")
                )

                if not possible_files:
                    return JSONResponse(
                        status_code=500,
                        content={
                            "error": "Downloaded file was not found"
                        }
                    )

                downloaded_file = possible_files[0]

        if not downloaded_file.exists():
            return JSONResponse(
                status_code=500,
                content={"error": "File does not exist"}
            )

        if format.lower() in ["audio", "mp3", "music"]:
            media_type = "audio/mpeg"
            filename = "vidstream-audio" + downloaded_file.suffix
        else:
            media_type = "video/mp4"
            filename = "vidstream-video" + downloaded_file.suffix

        return FileResponse(
            path=str(downloaded_file),
            media_type=media_type,
            filename=filename
        )

    except yt_dlp.utils.DownloadError as error:
        error_message = str(error)

        if "Sign in to confirm" in error_message:
            return JSONResponse(
                status_code=403,
                content={
                    "error": (
                        "YouTube requested bot verification. "
                        "This video cannot be downloaded currently."
                    ),
                    "details": error_message
                }
            )

        return JSONResponse(
            status_code=500,
            content={
                "error": error_message
            }
        )

    except Exception as error:
        return JSONResponse(
            status_code=500,
            content={
                "error": str(error)
            }
        )
