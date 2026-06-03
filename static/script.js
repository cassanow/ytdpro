const urlInput = document.getElementById('urlInput');
const thumbnailArea = document.getElementById('thumbnailArea');
const videoPlayer = document.getElementById('videoPlayer');
const qualityGrid = document.getElementById('qualityGrid');
const qualityButtons = document.querySelectorAll('.q-btn');
const downloadBtn = document.getElementById('downloadBtn');
const progressContainer = document.getElementById('progressContainer');
const progressPercent = document.getElementById('progressPercent');
const stageLabel = document.getElementById('stageLabel');
const progressFill = document.getElementById('progressFill');
const statusMsg = document.getElementById('statusMsg');
const saveArea = document.getElementById('saveArea');
const ffLed = document.getElementById('ffLed');
const ffText = document.getElementById('ffText');

let selectedQuality = 'best';

function obtenerIdVideo(url) {
    if (!url) return null;
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|\&v=)([^#\&\?]*).*/;
    const match = url.match(regExp);
    return (match && match[2].length === 11) ? match[2] : null;
}

window.executarDownload = async function(e) {
    if (e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    if (!urlInput) return;
    const url = urlInput.value.trim();
    
    if (!obtenerIdVideo(url)) {
    if (progressContainer) progressContainer.classList.remove('hidden');
    if (stageLabel) stageLabel.textContent = "Erro de validação";
    if (progressPercent) progressPercent.textContent = "X";
    if (progressFill) progressFill.style.width = "0%";
    if (statusMsg) {
        statusMsg.innerHTML = '<div class="status-badge" style="color: #EF4444; border-color: #EF4444;"><i class="fas fa-exclamation-circle"></i> Insira um link válido do YouTube!</div>';
    }
    return;
}

    if (downloadBtn) downloadBtn.disabled = true;
    if (progressContainer) progressContainer.classList.remove('hidden');
    if (saveArea) saveArea.innerHTML = '';
    
    if (stageLabel) stageLabel.textContent = "Iniciando tarefa no servidor...";
    if (progressPercent) progressPercent.textContent = "0%";
    if (progressFill) progressFill.style.width = "0%";
    if (statusMsg) statusMsg.innerHTML = '';
    
    try {
        const response = await fetch('/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: url, quality: selectedQuality })
        });
        
        const data = await response.json();
        if (data.error) {
            alert("Erro: " + data.error);
            if (downloadBtn) downloadBtn.disabled = false;
            return;
        }
        
        const jobId = data.job_id;
        
        const checarStatus = setInterval(async () => {
            try {
                const resStatus = await fetch(`/status/${jobId}`);
                const statusData = await resStatus.json();
                
                if (statusData.status === "downloading") {
                    if (stageLabel) stageLabel.textContent = "Fazendo download das faixas...";
                    if (progressPercent) progressPercent.textContent = `${statusData.progress}%`;
                    if (progressFill) progressFill.style.width = `${statusData.progress}%`;
                } 
                else if (statusData.status === "processing") {
                    if (stageLabel) stageLabel.textContent = "Convertendo e aplicando FFmpeg...";
                    if (progressPercent) progressPercent.textContent = "95%";
                    if (progressFill) progressFill.style.width = "95%";
                } 
                else if (statusData.status === "done") {
                    clearInterval(checarStatus);
                    if (progressPercent) progressPercent.textContent = "100%";
                    if (progressFill) progressFill.style.width = "100%";
                    if (stageLabel) stageLabel.textContent = "Concluído!";
                    if (statusMsg) statusMsg.innerHTML = '<div class="status-badge" style="color: #22C55E; border-color: #22C55E;"><i class="fas fa-check-circle"></i> O download começou!</div>';
                    
                    const linkOculto = document.createElement('a');
                    linkOculto.href = `/download/${jobId}`;
                    linkOculto.setAttribute('download', '');
                    document.body.appendChild(linkOculto);
                    linkOculto.click();
                    document.body.removeChild(linkOculto);
                    
                    if (downloadBtn) downloadBtn.disabled = false;
                } 
                else if (statusData.status === "error") {
                    clearInterval(checarStatus);
                    alert("Erro no download: " + statusData.error);
                    if (downloadBtn) downloadBtn.disabled = false;
                }
            } catch (err) {
                console.error("Erro ao buscar status:", err);
            }
        }, 1000);

    } catch (err) {
        alert("Erro de comunicação com o servidor.");
        if (downloadBtn) downloadBtn.disabled = false;
    }
};

if (urlInput) {
    urlInput.addEventListener('input', (e) => {
        const url = e.target.value.trim();
        const videoId = obtenerIdVideo(url);

        if (videoId && videoPlayer) {
            videoPlayer.src = `https://www.youtube.com/embed/${videoId}`;
            if (thumbnailArea) thumbnailArea.classList.add('has-image');
        } else if (videoPlayer) {
            videoPlayer.src = '';
            if (thumbnailArea) thumbnailArea.classList.remove('has-image');
        }
    });
}

if (qualityGrid) {
    qualityGrid.addEventListener('click', (e) => {
        const button = e.target.closest('.q-btn');
        if (!button || button.classList.contains('disabled-opt')) return;

        if (qualityButtons) qualityButtons.forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');
        selectedQuality = button.dataset.quality;
    });
}

async function checarFFmpegServidor() {
    try {
        const res = await fetch('/api/ffmpeg-status');
        const data = await res.json();
        if (data.ffmpeg_available) {
            if (ffLed) ffLed.classList.remove('off');
            if (ffText) ffText.textContent = "FFmpeg Ready";
        } else {
            if (ffLed) ffLed.classList.add('off');
            if (ffText) ffText.textContent = "FFmpeg Ausente";
        }
    } catch (e) {}
}

checarFFmpegServidor();