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
VERSAO_ATUAL   = "v1.0"
TOKEN_GITHUB   = "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" 
GITHUB_API_URL = "https://api.github.com/repos/NotLuvasz/conferencia-cega/releases/latest"
TIMEOUT_REDE   = 4  

# ──────────────────────────────────────────────
#  VERIFICAÇÃO SILENCIOSA (COM TOKEN)
# ──────────────────────────────────────────────
def verificar_atualizacao_async(callback):
    """
    Verifica no GitHub se tem versão nova de forma autenticada.
    Roda em thread pra não travar a abertura do sistema.
    """
    def _worker():
        try:
            req = urllib.request.Request(GITHUB_API_URL)
            req.add_header('Authorization', f'token {TOKEN_GITHUB}')
            req.add_header('Accept', 'application/vnd.github.v3+json')

            with urllib.request.urlopen(req, timeout=TIMEOUT_REDE) as r:
                dados = json.loads(r.read().decode('utf-8'))

            versao_remota = dados.get("tag_name", "")
            
            # Se for a mesma versão (ou vazio), encerra silenciosamente
            if not versao_remota or versao_remota == VERSAO_ATUAL:
                return

            # Acha o .exe nos assets (usando a URL da API para download privado)
            url_exe = None
            for asset in dados.get("assets", []):
                if asset["name"].endswith(".exe"):
                    url_exe = asset["url"]
                    break

            if url_exe:
                callback(versao_remota, url_exe)

        except Exception as e:
            # Silencioso se a rede da loja cair, mas útil para você debugar se precisar:
            print(f"Update ignorado/falhou: {e}")

    threading.Thread(target=_worker, daemon=True).start()

# ──────────────────────────────────────────────
#  JANELA DE ATUALIZAÇÃO
# ──────────────────────────────────────────────
class JanelaUpdate(ctk.CTkToplevel):
    def __init__(self, master, versao_nova, url_exe):
        super().__init__(master)
        self.versao_nova = versao_nova
        self.url_exe     = url_exe
        self.cancelado   = False

        self.title("Atualização disponível")
        self.geometry("380x220")
        self.resizable(False, False)
        self.grab_set()
        self.lift()

        try:
            from ConferenciaCega import resource_path, ICONE_PATH
            self.iconbitmap(ICONE_PATH)
        except Exception:
            pass

        ctk.CTkLabel(self, text="Nova versão disponível",
                     font=ctk.CTkFont(size=17, weight="bold")).pack(pady=(28, 4))
        ctk.CTkLabel(self, text=f"Versão atual: {VERSAO_ATUAL}  →  Nova: {versao_nova}",
                     font=ctk.CTkFont(size=12), text_color="gray").pack()

        self.label_status = ctk.CTkLabel(self, text="Deseja atualizar agora?", font=ctk.CTkFont(size=12))
        self.label_status.pack(pady=(12, 6))

        self.barra = ctk.CTkProgressBar(self, width=300)
        self.barra.set(0)
        self.barra.pack(pady=(0, 16))
        self.barra.pack_forget()  # esconde até começar o download

        frame_btns = ctk.CTkFrame(self, fg_color="transparent")
        frame_btns.pack()

        self.btn_sim = ctk.CTkButton(frame_btns, text="Atualizar agora", width=150, height=38,
                                     font=ctk.CTkFont(size=13, weight="bold"), command=self._iniciar_download)
        self.btn_sim.pack(side="left", padx=8)

        self.btn_nao = ctk.CTkButton(frame_btns, text="Agora não", width=120, height=38,
                                     fg_color="gray30", hover_color="gray40", command=self.destroy)
        self.btn_nao.pack(side="left", padx=8)

    def _iniciar_download(self):
        self.btn_sim.configure(state="disabled")
        self.btn_nao.configure(state="disabled")
        self.label_status.configure(text="Baixando atualização...")
        self.barra.pack(pady=(0, 16))
        self.barra.set(0)

        threading.Thread(target=self._download_com_token, daemon=True).start()

    def _download_com_token(self):
        try:
            pasta_exe   = os.path.dirname(sys.executable)
            nome_exe    = os.path.basename(sys.executable)
            caminho_tmp = os.path.join(tempfile.gettempdir(), "ConferenciaCega_novo.exe")
            caminho_bkp = os.path.join(pasta_exe, nome_exe + ".bkp")

            # Monta a requisição de download enviando o Token
            req = urllib.request.Request(self.url_exe)
            req.add_header('Authorization', f'token {TOKEN_GITHUB}')
            req.add_header('Accept', 'application/octet-stream')

            with urllib.request.urlopen(req) as response, open(caminho_tmp, 'wb') as out_file:
                tam_total = int(response.info().get("Content-Length", 0))
                baixado = 0
                tam_bloco = 8192 # Baixa de 8 em 8 KB

                while True:
                    if self.cancelado:
                        return
                    bloco = response.read(tam_bloco)
                    if not bloco:
                        break
                    
                    out_file.write(bloco)
                    baixado += len(bloco)
                    
                    # Atualiza a barra de progresso
                    if tam_total > 0:
                        pct = min(baixado / tam_total, 1.0)
                        self.after(0, lambda p=pct: self.barra.set(p))
                        self.after(0, lambda p=pct: self.label_status.configure(text=f"Baixando... {int(p * 100)}%"))

            self.after(0, lambda: self.label_status.configure(text="Aplicando atualização..."))

            # O Segredo do Windows: Deleta backup antigo, renomeia o executável atual, e joga o novo no lugar
            if os.path.exists(caminho_bkp):
                try:
                    os.remove(caminho_bkp)
                except Exception:
                    pass # Se não conseguir apagar o backup velho, segue o jogo
            
            os.rename(sys.executable, caminho_bkp)
            shutil.move(caminho_tmp, sys.executable)

            self.after(0, self._concluido)

        except Exception as e:
            self.after(0, lambda err=e: self._erro(str(err)))

    def _concluido(self):
        self.label_status.configure(text="✓ Atualização concluída!", text_color="#4caf50")
        self.barra.set(1)
        self.btn_nao.configure(state="normal", text="Fechar")

        # reinicia o sistema com o novo .exe
        self.after(1500, self._reiniciar)

    def _reiniciar(self):
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv[1:])
        self.master.destroy()
        sys.exit() # Garante que a instância velha morra imediatamente

    def _erro(self, msg):
        self.label_status.configure(text=f"Erro no download: {msg}", text_color="#e05c5c")
        self.btn_nao.configure(state="normal")
        self.btn_sim.configure(state="normal", text="Tentar de novo")