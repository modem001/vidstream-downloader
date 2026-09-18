import os
import re
import uuid
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask


app = FastAPI(title="VidStream Downloader")


# -----------------------------
# CORS
# -----------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Download directory
# -----------------------------

DOWNLOAD_DIR = Path("/tmp/vidstream_downloads")
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


# -----------------------------
# Helpers
# -----------------------------

def is_youtube_url(url: str) -> bool:
    try:
        hostname = (urlparse(url).hostname or "").lower()

        return hostname in [
            "youtube.com",
            "www.youtube.com",
            "m.youtube.com",
            "youtu.be",
            "www.youtu.be",
        ] or hostname.endswith(".youtube.com")

    except Exception:
        return False


def safe_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    name = name.strip().strip(".")
    return name[:100] or "VidStream Video"


def remove_file(file_path: str):
    try:
        path = Path(file_path)

        if path.exists():
            path.unlink()

    except Exception:
        pass


def get_quality(quality: str) -> int:
    try:
        value = int(
            str(quality)
            .lower()
            .replace("p", "")
            .strip()
        )

        allowed = [
            144,
            240,
            360,
            480,
            720,
            1080,
            1440,
            2160
        ]

        if value in allowed:
            return value

        return 720

    except Exception:
        return 720


# -----------------------------
# Routes
# -----------------------------

@app.get("/")
def root():
    return {
        "status": "online",
        "service": "VidStream Downloader"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/download")
def download(
    url: str = Query(...),
    quality: str = Query("720p"),
    format: str = Query("video")
):
    if not url:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Video URL is required"
            }
        )

    if not is_youtube_url(url):
        return JSONResponse(
            status_code=400,
            content={
                "error": "Please provide a valid YouTube URL"
            }
        )

    height = get_quality(quality)

    download_id = uuid.uuid4().hex

    output_template = str(
        DOWNLOAD_DIR / f"{download_id}.%(ext)s"
    )

    selected_format = str(format).lower().strip()

    # -----------------------------
    # Audio download
    # -----------------------------

    if selected_format in [
        "audio",
        "mp3",
        "music"
    ]:
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
                    "player_client": [
                        "android_vr",
                        "web"
                    ]
                }
            }
        }

    # -----------------------------
    # Video download
    # -----------------------------

    else:
        ydl_opts = {
            "format": (
                f"best[height<={height}][ext=mp4]/"
                f"best[height<={height}]/"
                "best"
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
                    "player_client": [
                        "android_vr",
                        "web"
                    ]
                }
            }
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                url,
                download=True
            )

            file_path = Path(
                ydl.prepare_filename(info)
            )

            # Handle changed extension
            if not file_path.exists():
                matching_files = list(
                    DOWNLOAD_DIR.glob(
                        f"{download_id}.*"
                    )
                )

                if not matching_files:
                    return JSONResponse(
                        status_code=500,
                        content={
                            "error": "Downloaded file not found"
                        }
                    )

                file_path = matching_files[0]

            title = safe_filename(
                info.get("title", "VidStream Video")
            )

        if not file_path.exists():
            return JSONResponse(
                status_code=500,
                content={
                    "error": "File does not exist"
                }
            )

        extension = file_path.suffix.lower()

        if selected_format in [
            "audio",
            "mp3",
            "music"
        ]:
            filename = f"{title}{extension}"
            media_type = (
                mimetypes.guess_type(
                    str(file_path)
                )[0]
                or "audio/mpeg"
            )

        else:
            filename = f"{title}{extension}"
            media_type = (
                mimetypes.guess_type(
                    str(file_path)
                )[0]
                or "video/mp4"
            )

        # Send file as an attachment to Android browser
        headers = {
            "Content-Disposition": (
                f'attachment; filename="{filename}"'
            ),
            "Cache-Control": "no-cache",
            "Access-Control-Expose-Headers": (
                "Content-Disposition, Content-Length"
            )
        }

        return FileResponse(
            path=str(file_path),
            media_type=media_type,
            filename=filename,
            headers=headers,
            background=BackgroundTask(
                remove_file,
                str(file_path)
            )
        )

    except yt_dlp.utils.DownloadError as error:
        message = str(error)

        if "Sign in to confirm" in message:
            return JSONResponse(
                status_code=403,
                content={
                    "error": (
                        "YouTube bot verification blocked "
                        "this video."
                    ),
                    "details": message
                }
            )

        return JSONResponse(
            status_code=500,
            content={
                "error": message
            }
        )

    except Exception as error:
        return JSONResponse(
            status_code=500,
            content={
                "error": str(error)
            }
        )
