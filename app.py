import os
import re
import uuid
from flask import Flask, request, jsonify, send_file, render_template
from flask_sqlalchemy import SQLAlchemy
from yt_dlp import YoutubeDL
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Configuração do Banco
DATABASE_URL = os.environ.get('DATABASE_URL', "postgresql://neondb_owner:npg_3NMgHK5fokyR@ep-aged-dew-ac105efh.sa-east-1.aws.neon.tech/neondb?sslmode=require")
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Tabela unificada para Jobs e Histórico
class DownloadHistory(db.Model):
    __tablename__ = 'historico'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.String(50), unique=True, nullable=False)
    titulo = db.Column(db.String(200))
    link = db.Column(db.String(500))
    status = db.Column(db.String(20), default="starting")
    progress = db.Column(db.Float, default=0.0)
    filename = db.Column(db.String(200))

executor = ThreadPoolExecutor(max_workers=3)
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def download_task(job_id, url, quality):
    with app.app_context():
        job = DownloadHistory.query.filter_by(job_id=job_id).first()
        try:
            ydl_opts = {
                "format": "bestaudio/best" if quality == "audio" else "bestvideo+bestaudio/best",
                "outtmpl": os.path.join(DOWNLOAD_FOLDER, f"{job_id}_%(title)s.%(ext)s"),
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
            job.status = "error"
            db.session.commit()

@app.route("/")
def home(): return render_template("index.html")

@app.route("/start", methods=["POST"])
def start():
    data = request.get_json()
    job_id = str(uuid.uuid4())
    novo_job = DownloadHistory(job_id=job_id, status="starting", link=data['url'])
    db.session.add(novo_job)
    db.session.commit()
    executor.submit(download_task, job_id, data['url'], data.get('quality', 'best'))
    return jsonify({"job_id": job_id})

@app.route("/status/<job_id>")
def status(job_id):
    job = DownloadHistory.query.filter_by(job_id=job_id).first()
    if not job: return jsonify({"error": "Job não encontrado"}), 404
    return jsonify({"status": job.status, "progress": job.progress, "filename": job.filename})

@app.route("/download/<job_id>")
def download(job_id):
    job = DownloadHistory.query.filter_by(job_id=job_id).first()
    return send_file(os.path.join(DOWNLOAD_FOLDER, job.filename), as_attachment=True)

@app.route("/historico")
def ver_historico():
    historico = DownloadHistory.query.filter_by(status="done").order_by(DownloadHistory.id.desc()).all()
    return jsonify([{"titulo": i.titulo, "link": i.link} for i in historico])

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(port=5000)