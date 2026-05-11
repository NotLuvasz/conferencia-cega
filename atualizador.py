import os
import sys
import json
import shutil
import threading
import tempfile
import urllib.request
import customtkinter as ctk
from tkinter import messagebox

# ──────────────────────────────────────────────
#  CONFIGURAÇÕES
# ──────────────────────────────────────────────
VERSAO_ATUAL   = "v1.3"
GITHUB_API_URL = "https://api.github.com/repos/NotLuvasz/conferencia-cega/releases/latest"
TIMEOUT_REDE   = 4  

def verificar_atualizacao_async(callback):
    def _worker():
        try:
            req = urllib.request.Request(
                GITHUB_API_URL,
                headers={"User-Agent": "ConferenciaCega-Updater"}
            )
            with urllib.request.urlopen(req, timeout=TIMEOUT_REDE) as r:
                dados = json.loads(r.read())

            versao_remota = dados.get("tag_name", "")
            if not versao_remota or versao_remota == VERSAO_ATUAL:
                return 

            url_exe = None
            for asset in dados.get("assets", []):
                if asset["name"].endswith(".exe"):
                    url_exe = asset["browser_download_url"]
                    break

            if url_exe:
                callback(versao_remota, url_exe)
        except Exception:
            pass
    threading.Thread(target=_worker, daemon=True).start()

class JanelaUpdate(ctk.CTkToplevel):
    def __init__(self, master, versao_nova, url_exe):
        super().__init__(master)
        self.versao_nova = versao_nova
        self.url_exe     = url_exe
        self.cancelado   = False
        self._baixando   = False

        self.title("Atualização disponível")
        self.geometry("380x220")
        self.resizable(False, False)
        self.grab_set()
        self.lift()

        try:
            import sys
            import os
            eh_exe = getattr(sys, 'frozen', False)
            base_path = sys._MEIPASS if eh_exe else os.path.abspath(".")
            icone_path = os.path.join(base_path, "icone.ico")
            self.iconbitmap(icone_path)
        except Exception: 
            pass

        ctk.CTkLabel(self, text="Nova versão disponível", font=ctk.CTkFont(size=17, weight="bold")).pack(pady=(28, 4))
        ctk.CTkLabel(self, text=f"Versão atual: {VERSAO_ATUAL}  →  Nova: {versao_nova}", font=ctk.CTkFont(size=12), text_color="gray").pack()

        self.label_status = ctk.CTkLabel(self, text="Deseja atualizar agora?", font=ctk.CTkFont(size=12))
        self.label_status.pack(pady=(12, 6))

        self.barra = ctk.CTkProgressBar(self, width=300)
        self.barra.set(0)
        self.barra.pack(pady=(3, 13))
        self.barra.pack_forget() 

        frame_btns = ctk.CTkFrame(self, fg_color="transparent")
        frame_btns.pack()

        self.btn_sim = ctk.CTkButton(frame_btns, text="Atualizar agora", width=150, height=38, font=ctk.CTkFont(size=13, weight="bold"), command=self._iniciar_download)
        self.btn_sim.pack(side="left", padx=8)

        self.btn_nao = ctk.CTkButton(frame_btns, text="Agora não", width=120, height=38, fg_color="gray30", hover_color="gray40", command=self.destroy)
        self.btn_nao.pack(side="left", padx=8)

    def _iniciar_download(self):
        if self._baixando: return
        self._baixando = True
        self.btn_sim.configure(state="disabled")
        self.btn_nao.configure(state="disabled")
        self.label_status.configure(text="Baixando atualização...")
        self.barra.pack(pady=(0, 16))
        self.barra.set(0)

        threading.Thread(target=self._download, daemon=True).start()

    def _download(self):
        try:
            import tempfile
            import shutil
            import sys
            import os
            
            # identifica se o app tá rodando pelo .exe ou pelo .py (cmd). esse foi o problema de cascata que deu no código
            # aliás, historia interessante, antes dessa identificação existir, quando vc atualizava o app que estava rodando pelo .py
            # ele substituia o arquivo do python.exe, isso fazia com que o motor do OS python, virasse o app, então toda vez que tentava rodar
            # qualquer .py, o app abria desatualizado
            eh_exe = getattr(sys, 'frozen', False)
            caminho_atual = sys.executable if eh_exe else os.path.abspath(sys.argv[0])
            pasta_exe   = os.path.dirname(caminho_atual)
            nome_exe    = os.path.basename(caminho_atual)
            
            caminho_tmp = os.path.join(tempfile.gettempdir(), "ConferenciaCega_novo.exe")
            caminho_bkp = os.path.join(pasta_exe, nome_exe + ".old")

            def _progresso(bloco, tam_bloco, tam_total):
                if tam_total > 0 and not self.cancelado:
                    pct = min(bloco * tam_bloco / tam_total, 1.0)
                    self.after(0, lambda p=pct: self.barra.set(p))
                    self.after(0, lambda p=pct: self.label_status.configure(text=f"Baixando... {int(p * 100)}%"))

            # repositório publico já serve pra puxar o release
            urllib.request.urlretrieve(self.url_exe, caminho_tmp, _progresso)

            if self.cancelado: return

            self.after(0, lambda: self.label_status.configure(text="Aplicando atualização..."))

            if eh_exe:
                # renomear o .exe atual, q tá rodando a bagaça
                if os.path.exists(caminho_bkp):
                    try: os.remove(caminho_bkp)
                    except: pass
                
                os.rename(caminho_atual, caminho_bkp)
                shutil.move(caminho_tmp, caminho_atual)
            else:
                # se roda pelo cmd, ele cria um executavel novo
                caminho_novo_exe = os.path.join(pasta_exe, "ConferenciaCega_Novo.exe")
                shutil.move(caminho_tmp, caminho_novo_exe)

            self.after(0, self._concluido)

        except Exception as e:
            self.after(0, lambda err=str(e): self._erro(err))

    def _concluido(self):
        self.label_status.configure(text="✓ Atualização concluída!", text_color="#4caf50")
        self.barra.set(1)
        self.btn_nao.configure(state="normal", text="Fechar")
        self.after(1500, self._reiniciar)

    def _reiniciar(self):
        import subprocess
        import sys
        import os
        
        eh_exe = getattr(sys, 'frozen', False)
        if eh_exe:
            subprocess.Popen([sys.executable] + sys.argv[1:])
        else:
            # se estava pelo terminal, abre o executável que acabou de baixar
            pasta_exe = os.path.dirname(os.path.abspath(sys.argv[0]))
            subprocess.Popen([os.path.join(pasta_exe, "ConferenciaCega_Novo.exe")])
        
        # mata os coiso q tava aberto antes, o app, p n dar conflito e n confundir tb
        os._exit(0)

    def _erro(self, msg):
        self._baixando = False
        self.label_status.configure(text=f"Erro: {msg}", text_color="#e05c5c")
        self.btn_nao.configure(state="normal")
        self.btn_sim.configure(state="normal", text="Tentar de novo")