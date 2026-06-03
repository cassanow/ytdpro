import os
import re
import uuid
from flask import Flask, request, jsonify, send_file, render_template
from flask_sqlalchemy import SQLAlchemy
from yt_dlp import YoutubeDL
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)


DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL or "sqlite:///database.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class DownloadJob(db.Model):
    __tablename__ = 'jobs'
    id = db.Column(db.String(50), primary_key=True) 
    status = db.Column(db.String(20), default="starting")
    progress = db.Column(db.Float, default=0.0)
    titulo = db.Column(db.String(200))
    link = db.Column(db.String(500))
    filename = db.Column(db.String(200))

executor = ThreadPoolExecutor(max_workers=3)

def progress_hook_factory(job_id):
    def hook(d):
        with app.app_context():
            job = DownloadJob.query.get(job_id)
            if job and d["status"] == "downloading":
                total = (d.get("total_bytes") or d.get("total_bytes_estimate") or 1)
                job.progress = round(d.get("downloaded_bytes", 0) / total * 100, 1)
                job.status = "downloading"
                db.session.commit()
    return hook

def download_video(job_id, url, quality):
    try:
        with app.app_context():
            job = DownloadJob.query.get(job_id)
            ydl_opts = {
                "format": "bestaudio/best" if quality == "audio" else "bestvideo+bestaudio/best",
                "outtmpl": f"downloads/{job_id}_%(title).50s.%(ext)s",
                "progress_hooks": [progress_hook_factory(job_id)],
                "merge_output_format": "mp4",
                "cookiefile": "cookies.txt" if os.path.exists("cookies.txt") else None
            }
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                job.titulo = info.get("title")
                job.filename = f"{job_id}_{info.get('title')[:50]}.mp4".replace(" ", "_")
                job.status = "done"
                job.progress = 100
                db.session.commit()
    except Exception as e:
        with app.app_context():
            job = DownloadJob.query.get(job_id)
            if job:
                job.status = "error"
                db.session.commit()

@app.route("/start", methods=["POST"])
def start():
    data = request.get_json()
    job_id = str(uuid.uuid4())
    novo_job = DownloadJob(id=job_id, status="starting", link=data['url'])
    db.session.add(novo_job)
    db.session.commit()
    executor.submit(download_video, job_id, data['url'], data.get('quality', 'best'))
    return jsonify({"job_id": job_id})

@app.route("/status/<job_id>")
def status(job_id):
    job = DownloadJob.query.get(job_id)
    if not job:
        return jsonify({"error": "Job não encontrado"}), 404
    return jsonify({"status": job.status, "progress": job.progress, "filename": job.filename})

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run()