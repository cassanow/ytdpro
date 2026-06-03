import os
import re
import uuid
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from flask import (
    Flask,
    request,
    jsonify,
    send_file,
    render_template
)

cookies_content = os.environ.get('COOKIES_CONTENT')
if cookies_content:
    with open("cookies.txt", "w") as f:
        f.write(cookies_content)

from flask_sqlalchemy import SQLAlchemy
from yt_dlp import YoutubeDL

app = Flask(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    DATABASE_URL = "postgresql://neondb_owner:npg_3NMgHK5fokyR@ep-aged-dew-ac105efh.sa-east-1.aws.neon.tech/neondb?sslmode=require"

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


class DownloadHistory(db.Model):
    __tablename__ = 'historico' 
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.String(50), unique=True, nullable=False) 
    titulo = db.Column(db.String(200), nullable=False)
    data = db.Column(db.Integer, nullable=True) 
    link = db.Column(db.String(500), nullable=False)

    def __init__(self, job_id, titulo, data, link):
        self.job_id = job_id
        self.titulo = titulo
        self.data = data
        self.link = link

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

FFMPEG_PATH = "C:\\ffmpeg\\bin"

if os.path.exists("/opt/render/project/src/ffmpeg_bin"):
    FFMPEG_PATH = "/opt/render/project/src/ffmpeg_bin"
elif os.path.exists("ffmpeg_bin"):
    FFMPEG_PATH = os.path.abspath("ffmpeg_bin")

jobs = {}
executor = ThreadPoolExecutor(max_workers=3)

def clean_old_files():
    try:
        now = time.time()
        for filename in os.listdir(DOWNLOAD_FOLDER):
            filepath = os.path.join(DOWNLOAD_FOLDER, filename)
            if os.path.isfile(filepath) and os.stat(filepath).st_mtime < now - 1200:
                os.remove(filepath)
                print(f"[FAXINA] Arquivo antigo removido: {filename}")
    except Exception as e:
        print(f"[FAXINA] Erro ao limpar pasta: {e}")

def sanitize_filename(name):
    if not name:
        return "video"
    invalid_chars = '<>:"/\\|?*'
    for ch in invalid_chars:
        name = name.replace(ch, '')
    name = name.encode('ascii', 'ignore').decode()
    name = re.sub(r'\s+', ' ', name).strip()
    name = name.replace(" ", "_")
    name = name[:50]
    return name if name else "video"

def progress_hook_factory(job_id):
    def hook(d):
        if job_id not in jobs:
            return
        job = jobs[job_id]
        if d["status"] == "downloading":
            total = (d.get("total_bytes") or d.get("total_bytes_estimate") or 1)
            downloaded = d.get("downloaded_bytes", 0)
            pct = round(downloaded / total * 100, 1)
            job["progress"] = pct
            job["status"] = "downloading"
        elif d["status"] == "finished":
            job["progress"] = 100
            job["status"] = "processing"
    return hook

def download_video(job_id, url, quality):
    clean_old_files()

    if job_id not in jobs:
        return
    job = jobs[job_id]

    try:
        output_template = os.path.join(DOWNLOAD_FOLDER, f"{job_id}_%(title).80s.%(ext)s")
        postprocessors = []
        if quality == "audio":
            format_selector = "bestaudio/best"
        elif quality in ["1080p", "720p", "480p"]:
            height = quality.replace('p', '')
            format_selector = (
            f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]"
            f"/best[height<={height}][ext=mp4]"
            f"/best[height<={height}]"
            f"/best")
        else:
            format_selector = "best[ext=mp4]/best"

        ydl_opts = {
                "format": format_selector,
                "outtmpl": output_template,
                "quiet": True,
                "noplaylist": True,
                "progress_hooks": [progress_hook_factory(job_id)],
                "merge_output_format": "mp4",
                "cookiefile": "cookies.txt",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "extractor_args": {"youtube": {"skip": ["dash", "hls"]}},  # evita formatos que precisam de merge
                "socket_timeout": 30,
            }
        
        if FFMPEG_PATH and os.path.exists(FFMPEG_PATH):
            ydl_opts["ffmpeg_location"] = FFMPEG_PATH

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get("title", "video")
            video_date = info.get("upload_date")  
            title = sanitize_filename(video_title)

            downloaded_files = sorted(
                [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(job_id)],
                key=lambda x: os.path.getmtime(os.path.join(DOWNLOAD_FOLDER, x)),
                reverse=True
            )

            if not downloaded_files:
                raise Exception("Arquivo baixado não foi localizado no servidor.")

            real_file = downloaded_files[0]
            real_ext = os.path.splitext(real_file)[1]
            expected_name = f"{title}{real_ext}"

            old_path = os.path.join(DOWNLOAD_FOLDER, real_file)
            new_path = os.path.join(DOWNLOAD_FOLDER, expected_name)

            if old_path != new_path:
                if os.path.exists(new_path):
                    os.remove(new_path)
                os.replace(old_path, new_path)

            job["filename"] = expected_name
            job["title"] = video_title
            job["status"] = "done"
            job["progress"] = 100

            with app.app_context():
                try:
                    novo_download = DownloadHistory(job_id=job_id, titulo=video_title, data=video_date, link=url)
                    db.session.add(novo_download)
                    db.session.commit()
                except Exception as db_err:
                    db.session.rollback()
                    print(f"[BANCO DE DADOS] Erro ao registrar histórico: {db_err}")

    except Exception as e:
        print(traceback.format_exc())
        job["status"] = "error"
        job["error"] = str(e)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/ffmpeg-status")
def ffmpeg_status():
    ffmpeg_disponivel = False
    if FFMPEG_PATH:
        ffmpeg_bin = os.path.join(FFMPEG_PATH, "ffmpeg.exe")
        ffmpeg_disponivel = os.path.exists(ffmpeg_bin) or os.path.exists(os.path.join(FFMPEG_PATH, "ffmpeg"))
    if not ffmpeg_disponivel:
        ffmpeg_disponivel = os.system("ffmpeg -version") == 0
    return jsonify({"ffmpeg_available": ffmpeg_disponivel})

@app.route("/start", methods=["POST"])
def start():
    try:
        data = request.get_json(force=True)
        url = data.get("url", "").strip()
        quality = data.get("quality", "best").strip()

        if not url:
            return jsonify({"error": "URL inválida"}), 400

        job_id = str(uuid.uuid4())
        jobs[job_id] = {
            "status": "starting",
            "progress": 0,
            "filename": None,
            "title": None,
            "error": None
        }

        executor.submit(download_video, job_id, url, quality)
        return jsonify({"job_id": job_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"status": "error", "error": "Job não encontrado"})
    return jsonify(job)

@app.route("/download/<job_id>")
def download(job_id):
    job = jobs.get(job_id)
    if not job or not job.get("filename"):
        return "Arquivo não processado", 404
        
    filepath = os.path.join(DOWNLOAD_FOLDER, job["filename"])
    if not os.path.exists(filepath):
        return "Arquivo físico não encontrado", 404
        
    ext = os.path.splitext(job["filename"])[1].lower()
    mimetype = "audio/mpeg" if ext == ".mp3" else "video/mp4"

    return send_file(
        filepath, 
        mimetype=mimetype,
        as_attachment=True, 
        download_name=job["filename"]
    )

@app.route("/historico")
def ver_historico():
    try:
        historico = DownloadHistory.query.order_by(DownloadHistory.id.desc()).all()
        return jsonify([{
            "id": item.id,
            "titulo": item.titulo,
            "data": item.data, 
            "link": item.link
        } for item in historico])
    except Exception as e:
        return jsonify({"error": f"Não foi possível ler o histórico: {str(e)}"}), 500

@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, use_reloader=False, port=5000)