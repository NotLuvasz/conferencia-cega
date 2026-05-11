import cv2
import os
import win32com.client
import time
import subprocess
import json
import urllib.request
import shutil
import zipfile
import smtplib
import customtkinter as ctk
import threading
import ctypes
from datetime import datetime
from collections import defaultdict
from tkinter import messagebox
from sele import MotorSAP
from PIL import Image
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from atualizador import verificar_atualizacao_async, JanelaUpdate, VERSAO_ATUAL
from atualizador import VERSAO_ATUAL


def preparar_ambiente_chrome():
    """
    Garante que existe um Chrome isolado com a porta 9224 ativa.
    Clona o perfil original para C:\DadosSele de forma plana para manter logins.
    """
    # 1. o chrome abre na porta, então isso verifica se a porta tá aberta, no caso de a loja já estar com chrome diferenciado aberto.
    try:
        urllib.request.urlopen("http://127.0.0.1:9224/json", timeout=2)
        return True 
    except Exception:
        pass

    # 2. mata os chromes abertos, pra não dar b.o (conflito btw)
    os.system("taskkill /F /IM chrome.exe /T >nul 2>&1")
    os.system("taskkill /F /IM chromedriver.exe /T >nul 2>&1")
    time.sleep(2) 

    # 3. configurando os diretórios
    # c:\DadosSele vira o caminho do perfil do chrome da loja
    pasta_raiz = r"C:\DadosSele"
    appdata_local = os.getenv('LOCALAPPDATA')
    # origem original dos dados do perfil, de onde vão ser importados
    origem_dados = os.path.join(appdata_local, 'Google', 'Chrome', 'User Data')

    # 4. clonagem do perfil (se a pasta não existir)
    if not os.path.exists(pasta_raiz):
        messagebox.showinfo(
            "Configuração Inicial", 
            "Formatando perfil da loja para conferência\nIsso leva de 1 a 2 minutos."
        )
        try:
            # se o diretório tiver sido criado corretamente, vai fazer copytree da pasta do perfil
            shutil.copytree(origem_dados, pasta_raiz, dirs_exist_ok=True)
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao clonar perfil: {e}")
            return False

    # 5. diretório do executável do chrome.
    caminho_chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if not os.path.exists(caminho_chrome):
        caminho_chrome = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

    # 6. abrir o chrome
    # o --user-data-dir ve onde os arquivos clonados estão e abre o chrome com o perfil e direto na página do controle
    url_sap = "http://134.65.18.92:8000/quality/transferencia/#/conferencias"
    comando = f'"{caminho_chrome}" --remote-debugging-port=9224 --user-data-dir="{pasta_raiz}" --remote-allow-origins=* "{url_sap}"'

    # tive que fazer isso por conta de uma pegadihna kkkkkk, quando o taskkill rodou, ele matou o chrome, quando a gente abre ele aqui, aquele msgbox
    # de restaurar página aparece, quando ela aparece, o script falha quando tenta focar em algumas coisas, isso aqui serve pra fechar o restaurar páginas.
    caminho_prefs = os.path.join(pasta_raiz, "Default", "Preferences")
    if os.path.exists(caminho_prefs):
        try:
            with open(caminho_prefs, "r", encoding="utf-8") as f:
                dados_prefs = f.read()
            # aqui os dados são trocados, tira a informação de que o chrome crashou.
            dados_prefs = dados_prefs.replace('"exit_type":"Crashed"', '"exit_type":"Normal"')
            dados_prefs = dados_prefs.replace('"exited_cleanly":false', '"exited_cleanly":true')
            with open(caminho_prefs, "w", encoding="utf-8") as f:
                f.write(dados_prefs)
        except Exception:
            pass

    # abertura do chrome, com alguns comandos pra impedir msgbox popup essas coisas
    url_sap = "http://134.65.18.92:8000/quality/transferencia/#/conferencias"
    comando = f'"{caminho_chrome}" --remote-debugging-port=9224 --user-data-dir="{pasta_raiz}" --disable-infobars --disable-session-crashed-bubble "{url_sap}"'
    
    subprocess.Popen(comando, shell=True)
    time.sleep(5) 
    
    # 7. validação da porta
    try:
        urllib.request.urlopen("http://127.0.0.1:9224/json", timeout=5)
        return True
    except Exception:
        messagebox.showerror("Erro", "O Chrome abriu, mas a porta 9224 não respondeu.")
        return False
    

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS # type: ignore
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def configurar_chrome_loja():
    # isso aqui cria um novo atalho com a porta 9224, isso aqui é pra caso, a loja abra por essa porta
    # a conferência já vai poder ser feita sem ter q dar o taskkill, é mais UX
    try:
        caminho_chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        if not os.path.exists(caminho_chrome):
            caminho_chrome = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
        if not os.path.exists(caminho_chrome):
            return

        user_profile   = os.environ.get('USERPROFILE', '')
        caminho_atalho = os.path.join(user_profile, 'Desktop', 'Google Chrome.lnk')

        shell  = win32com.client.Dispatch("WScript.Shell")
        atalho = shell.CreateShortCut(caminho_atalho)

        if "--remote-debugging-port=9224" in atalho.Arguments:
            return

        atalho.TargetPath   = caminho_chrome
        atalho.Arguments    = "--remote-debugging-port=9224 --remote-allow-origins=*"
        atalho.Description  = "Google Chrome"
        atalho.IconLocation = caminho_chrome + ",0"
        atalho.Save()

        messagebox.showinfo(
            "Configuração do Chrome",
            "O atalho do Chrome foi atualizado.\n"
        )

    except Exception:
        pass

# ──────────────────────────────────────────────
# constantes globais
# ──────────────────────────────────────────────
NOME_PASTA_RAIZ  = "Aut Conferencia Cega"
ARQUIVO_CONFIG   = "conf_cega_config.txt"
ARQUIVO_SESSAO   = "sessao.json"
SENHA_ADMIN      = "23032005"
DIAS_LIXEIRA     = 7
ICONE_PATH = resource_path("icone.ico")
LIMITE_AUTO_SEG  = 0.30 # 150ms maximo pro laser bater (humano n chega perto)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ──────────────────────────────────────────────
# config smtp
# ──────────────────────────────────────────────
EMAIL_REMETENTE     = "conferenciagto@gmail.com"
SENHA_APP           = "ctni ipyg kdde etbm"
EMAIL_DESTINATARIOS = [
    "inventario@grupotesouradeouro.com.br",
]

# ──────────────────────────────────────────────
# script da lixeira
# ──────────────────────────────────────────────
def processar_lixeira(diretorio_raiz):
    caminho_lixeira = os.path.join(diretorio_raiz, "admin", "Lixeira")
    if not os.path.exists(caminho_lixeira):
        os.makedirs(caminho_lixeira, exist_ok=True)
        return

    agora = time.time()
    segundos_limite = DIAS_LIXEIRA * 24 * 60 * 60

    for arquivo in os.listdir(caminho_lixeira):
        caminho_file = os.path.join(caminho_lixeira, arquivo)
        if os.path.isfile(caminho_file):
            tempo_arquivo = os.path.getmtime(caminho_file)
            if (agora - tempo_arquivo) > segundos_limite:
                try: os.remove(caminho_file)
                except: pass

# ──────────────────────────────────────────────
# setup icone ctk
# ──────────────────────────────────────────────
def aplicar_icone(janela):
    try: janela.iconbitmap(ICONE_PATH)
    except Exception: pass

# ──────────────────────────────────────────────
# controle de estado e json da sessao
# ──────────────────────────────────────────────
def _caminho_sessao(diretorio_destino):
    return os.path.join(diretorio_destino, ARQUIVO_SESSAO)

def carregar_sessao(diretorio_destino):
    caminho = _caminho_sessao(diretorio_destino)
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: pass
    return None

def salvar_sessao(diretorio_destino, contagem, entradas_manuais, removidos, sessoes):
    dados = {
        "contagem":         dict(contagem),
        "entradas_manuais": dict(entradas_manuais),
        "removidos":        dict(removidos),
        "sessoes":          sessoes
    }
    with open(_caminho_sessao(diretorio_destino), "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

# ──────────────────────────────────────────────
# utils arquivos
# ──────────────────────────────────────────────
def zipar_ot(numero_ot, diretorio_destino):
    nome_zip    = f"OT_{numero_ot}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    caminho_zip = os.path.join(diretorio_destino, nome_zip)

    with zipfile.ZipFile(caminho_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for arquivo in os.listdir(diretorio_destino):
            if arquivo.endswith(".jpg") or arquivo.endswith(".txt"):
                zf.write(os.path.join(diretorio_destino, arquivo), arquivo)

    return caminho_zip

# ──────────────────────────────────────────────
# emails
# ──────────────────────────────────────────────
def enviar_email(numero_ot, caminho_zip, total_itens, total_manuais, total_removidos, status_texto=""):
    try:
        msg = MIMEMultipart()
        msg["From"]    = EMAIL_REMETENTE
        msg["To"]      = ", ".join(EMAIL_DESTINATARIOS)
        extra = f" - {status_texto()}" if status_texto else ""
        msg["Subject"] = f"Conferência Cega — OT {numero_ot} encerrada{extra}"

        corpo = (
            f"OT {numero_ot} encerrada {status_texto}.\n\n"
            f"Total de itens conferidos : {total_itens}\n"
            f"Entradas manuais          : {total_manuais}\n"
            f"Itens removidos           : {total_removidos}\n\n"
            f"As fotos e o relatório estão em anexo.\n\n"
            f"Em caso de falhas ou erros, entrar em contato com o departamento de Prevenção de Perdas.\n"
            f"Sistema de Conferência Cega"
        )
        msg.attach(MIMEText(corpo, "plain", "utf-8"))

        with open(caminho_zip, "rb") as f:
            parte = MIMEBase("application", "octet-stream")
            parte.set_payload(f.read())
        encoders.encode_base64(parte)
        parte.add_header("Content-Disposition", f"attachment; filename={os.path.basename(caminho_zip)}")
        msg.attach(parte)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(EMAIL_REMETENTE, SENHA_APP)
            servidor.sendmail(EMAIL_REMETENTE, EMAIL_DESTINATARIOS, msg.as_string())

        return True, None
    except Exception as e:
        return False, str(e)


# ──────────────────────────────────────────────
# hds e pastas locais
# ──────────────────────────────────────────────
def _listar_particoes():
    particoes_locais = []
    
    for l in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        caminho = f"{l}:\\"
        if os.path.exists(caminho):
            tipo = ctypes.windll.kernel32.GetDriveTypeW(caminho)
            if tipo == 3:
                particoes_locais.append(caminho)
                
    return particoes_locais

def _tornar_oculto(caminho):
    os.system(f'attrib +h "{caminho}"')

def encontrar_melhor_particao():
    # 1. verifica se config ja existe
    for particao in _listar_particoes():
        cfg = os.path.join(particao, NOME_PASTA_RAIZ, ARQUIVO_CONFIG)
        if os.path.exists(cfg):
            with open(cfg, "r", encoding="utf-8") as f:
                salvo = f.read().strip()
            if os.path.exists(salvo):
                caminho_admin = os.path.join(salvo, "admin")
                if os.path.exists(caminho_admin):
                    _tornar_oculto(caminho_admin)
                processar_lixeira(salvo)
                return salvo

    # 2. busca pra ver a partição com mais espaço
    melhor, maior = None, -1
    for particao in _listar_particoes():
        try:
            livre = shutil.disk_usage(particao).free
            if livre > maior:
                maior, melhor = livre, particao
        except Exception: continue

    if not melhor: raise RuntimeError("Nenhum HD acessível encontrado.")

    # 3. scaffold pastas locais
    raiz = os.path.join(melhor, NOME_PASTA_RAIZ)
    os.makedirs(raiz, exist_ok=True)
    
    caminho_admin = os.path.join(raiz, "admin")
    os.makedirs(os.path.join(caminho_admin, "Lixeira"), exist_ok=True)
    _tornar_oculto(caminho_admin)
    
    cfg = os.path.join(raiz, ARQUIVO_CONFIG)
    with open(cfg, "w", encoding="utf-8") as f: f.write(raiz)
    _tornar_oculto(cfg)
    
    processar_lixeira(raiz)
    return raiz

# ──────────────────────────────────────────────
# relatorio final
# ──────────────────────────────────────────────
def gerar_relatorio(numero_ot, diretorio_destino, contagem, entradas_manuais, removidos, sessoes):
    agora             = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    total_itens       = sum(contagem.values())
    total_manuais     = sum(entradas_manuais.values())
    total_removidos   = sum(removidos.values())
    total_automaticos = total_itens - total_manuais

    frase_final = ""
    if sessoes:
        ultima = sessoes[-1]
        nome_op = ultima.get("nome", "N/A")
        modo_final = ultima.get("modo", "")
        status_texto = "com divergência" if modo_final == "divergencia" else "sem divergência"
        frase_final = f"  *** {nome_op} finalizou a OT {status_texto} ***"

    L = []
    L.append("=" * 60)
    L.append("  RELATÓRIO DE CONFERÊNCIA CEGA")
    L.append("=" * 60)
    if frase_final:
        L.append(frase_final) 
        L.append("-" * 60)
    L.append(f"  OT             : {numero_ot}")
    L.append(f"  Data/Hora      : {agora}")
    L.append(f"  Cód. únicos    : {len(contagem)}")
    L.append(f"  Total itens    : {total_itens}")
    L.append(f"  Automáticos    : {total_automaticos}")
    L.append(f"  Manuais        : {total_manuais}")
    L.append(f"  Removidos      : {total_removidos}")
    L.append("=" * 60)

    if sessoes:
        L.append("")
        L.append("  SESSÕES DE CONFERÊNCIA")
        L.append("-" * 60)
        for i, s in enumerate(sessoes, 1):
            nome  = s.get("nome", "N/A")
            func  = s.get("funcao", "N/A")
            L.append(f"  Sessão {i}: início {s['inicio']} — fim {s['fim']}")
            L.append(f"            Operador: {nome} ({func})")
        L.append("-" * 60)

    L.append("")
    L.append("  DETALHAMENTO POR CÓDIGO DE BARRAS")
    L.append("-" * 60)
    L.append(f"  {'CÓD BARRAS':<15} {'TOTAL':>5}  {'MANUAL':>6}  {'AUTO':>5}")
    L.append("-" * 60)

    for cod in sorted(contagem):
        tot  = contagem[cod]
        man  = entradas_manuais.get(cod, 0)
        aut  = tot - man
        flag = "  ← MANUAL" if man > 0 else ""
        L.append(f"  {cod:<15} {tot:>5}  {man:>6}  {aut:>5}{flag}")

    L.append("-" * 60)
    L.append(f"  {'TOTAL':<15} {total_itens:>5}  {total_manuais:>6}  {total_automaticos:>5}")
    L.append("")

    if removidos:
        L.append("=" * 60)
        L.append("  HISTÓRICO DE REMOÇÕES")
        L.append("-" * 60)
        for cod, qtd in sorted(removidos.items()):
            L.append(f"  {cod}  →  {qtd} unidade(s) removida(s) pelo conferente")
        L.append("")

    if entradas_manuais:
        L.append("=" * 60)
        L.append("  ATENÇÃO — ITENS COM ENTRADA MANUAL")
        L.append("  (etiqueta ilegível — recomendado imprimir outra etiqueta)")
        L.append("-" * 60)
        for cod, qtd in sorted(entradas_manuais.items()):
            L.append(f"  {cod}  →  {qtd} unidade(s) lançada(s) manualmente")
    else:
        L.append("  Nenhuma entrada manual registrada nesta OT.")

    L.append("=" * 60)
    L.append("  Fim do relatório.")
    L.append("=" * 60)

    conteudo    = "\n".join(L)
    nome_rel    = f"relatorio_OT_{numero_ot}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    caminho_rel = os.path.join(diretorio_destino, nome_rel)
    with open(caminho_rel, "w", encoding="utf-8") as f:
        f.write(conteudo)
    return caminho_rel, conteudo, total_itens, total_manuais, total_removidos

# ──────────────────────────────────────────────
# ot sem divergencia enviador de email plus master
# ──────────────────────────────────────────────
def enviar_email_sem_fotos(numero_ot, caminho_rel, total_itens, total_manuais):
    try:
        msg = MIMEMultipart()
        msg["From"]    = EMAIL_REMETENTE
        msg["To"]      = ", ".join(EMAIL_DESTINATARIOS)
        msg["Subject"] = f"Conferência Cega — OT {numero_ot} SEM DIVERGÊNCIA"

        corpo = (
            f"OT {numero_ot} encerrada sem divergência.\n\n"
            f"Total de itens conferidos : {total_itens}\n"
            f"Entradas manuais          : {total_manuais}\n\n"
            f"OT foi apontada como sem divergência.\n"
            f"Relatório em anexo.\n\n"
            f"Em caso de falhas ou erros, entrar em contato com Prevenção de Perdas.\n"
            f"Sistema de Conferência Cega"
        )
        msg.attach(MIMEText(corpo, "plain", "utf-8"))

        with open(caminho_rel, "rb") as f:
            parte = MIMEBase("application", "octet-stream")
            parte.set_payload(f.read())
        encoders.encode_base64(parte)
        parte.add_header("Content-Disposition", f"attachment; filename={os.path.basename(caminho_rel)}")
        msg.attach(parte)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(EMAIL_REMETENTE, SENHA_APP)
            servidor.sendmail(EMAIL_REMETENTE, EMAIL_DESTINATARIOS, msg.as_string())

        return True, None
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════
# TelaOT - primeira tela, onde preenche as info
# ══════════════════════════════════════════════
class TelaOT(ctk.CTk):
    def __init__(self, diretorio_raiz):
        super().__init__()
        
        configurar_chrome_loja()
        
        self.diretorio_raiz = diretorio_raiz
        self.title("Conferência Cega")
        self.geometry("420x480")
        self.resizable(False, False)
        aplicar_icone(self)

        # verifica update lá no github do pai
        self.after(2000, self._checar_update)

        

        ctk.CTkLabel(self, text="Conferência Cega", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(36, 4))
        ctk.CTkLabel(self, text="Prevenção de Perdas", font=ctk.CTkFont(size=13), text_color="gray").pack(pady=(0, 20))

        ctk.CTkLabel(self, text="Nome", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=60)
        self.campo_nome = ctk.CTkEntry(self, placeholder_text="Ex: Ana Beatriz", width=300, height=36)
        self.campo_nome.pack(padx=60, pady=(4, 12))

        ctk.CTkLabel(self, text="Função", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=60)
        self.campo_funcao = ctk.CTkEntry(self, placeholder_text="Ex: Gerente", width=300, height=36)
        self.campo_funcao.pack(padx=60, pady=(4, 12))

        ctk.CTkLabel(self, text="Número da OT", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=60)
        self.campo_ot = ctk.CTkEntry(self, placeholder_text="123456", width=300, height=42, font=ctk.CTkFont(size=13))
        self.campo_ot.pack(padx=60, pady=(4, 6))
        self.campo_ot.bind("<Return>", lambda e: self.iniciar())

        self.label_erro = ctk.CTkLabel(self, text="", text_color="#e05c5c", font=ctk.CTkFont(size=12))
        self.label_erro.pack()

        ctk.CTkButton(self, text="Iniciar conferência", width=300, height=42, font=ctk.CTkFont(size=14, weight="bold"), command=self.iniciar).pack(pady=(10, 0))

        texto_rodape = f"Desenvolvido por Lucas S. Domingues | {VERSAO_ATUAL}"
        self.label_creditos = ctk.CTkLabel(self, text=texto_rodape, font=ctk.CTkFont(size=11), text_color="gray50")
        self.label_creditos.place(x=15, y=445)

        self.btn_admin = ctk.CTkButton(self, text="⚙", width=30, fg_color="transparent", text_color="gray30", hover_color="gray25", command=self._acesso_admin)
        self.btn_admin.place(x=380, y=440)

        self.campo_nome.focus()

    def _checar_update(self):
            def _on_update(versao_nova, url_exe):
                self.after(0, lambda: JanelaUpdate(self, versao_nova, url_exe))
            verificar_atualizacao_async(_on_update)

    def _acesso_admin(self):
        janela_senha = ctk.CTkToplevel(self)
        janela_senha.title("Área Restrita")
        janela_senha.geometry("320x200")
        janela_senha.resizable(False, False)
        janela_senha.grab_set() 
        janela_senha.lift()
        aplicar_icone(janela_senha)

        ctk.CTkLabel(janela_senha, text="Senha de Administrador", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(25, 10))
        campo_senha = ctk.CTkEntry(janela_senha, placeholder_text="Digite a senha", width=220, show="*", height=35)
        campo_senha.pack(pady=5)

        campo_senha.focus()
        janela_senha.after(100, campo_senha.focus)

        def validar():
            if campo_senha.get() == SENHA_ADMIN:
                janela_senha.destroy()
                caminho_admin = os.path.join(self.diretorio_raiz, "admin")
                if os.path.exists(caminho_admin): os.startfile(caminho_admin)
                else: messagebox.showerror("Erro", "Pasta admin não encontrada.")
            else:
                messagebox.showerror("Erro", "Senha incorreta!")
                campo_senha.delete(0, "end")
                campo_senha.focus()

        ctk.CTkButton(janela_senha, text="Acessar", width=220, height=35, command=validar).pack(pady=15)
        janela_senha.bind("<Return>", lambda e: validar())

    def iniciar(self):
        nome   = self.campo_nome.get().strip()
        funcao = self.campo_funcao.get().strip()
        ot     = self.campo_ot.get().strip()

        if not nome or not funcao:
            self.label_erro.configure(text="Preencha nome e função.", text_color="#e05c5c")
            return
        if not (ot.isdigit() and len(ot) == 6):
            self.label_erro.configure(text="Digite o número da OT", text_color="#e05c5c")
            return

        self.label_erro.configure(text="Preparando automação...", text_color="#e3a83b")
        self.update()

        # abridura do chrome na porta 9224
        sucesso_chrome = preparar_ambiente_chrome()
        if not sucesso_chrome:
            self.label_erro.configure(text="Falha ao iniciar automação.", text_color="#e05c5c")
            return

        self.label_erro.configure(text="Conectando ao Controle, aguarde.", text_color="#e3a83b")
        self.update()

        bot = MotorSAP()
        status_conn, msg_conn = bot.conectar()

        if not status_conn:
            self.label_erro.configure(text="Falha ao iniciar. O Chrome fechou?", text_color="#e05c5c")
            return

        self.label_erro.configure(text="Procurando OT no sistema...", text_color="#e3a83b")
        self.update()

        status_ot, msg_ot = bot.iniciar_conferencia(ot)

        if not status_ot:
            self.label_erro.configure(text=msg_ot, text_color="#e05c5c")
            bot.desconectar()
            return

        self.label_erro.configure(text="Controle Conectado! Preparando câmera...", text_color="#4caf50")
        self.update()

        diretorio_destino = os.path.join(self.diretorio_raiz, f"OT_{ot}")
        sessao_anterior   = carregar_sessao(diretorio_destino)

        if sessao_anterior:
            self._perguntar_retomada(ot, nome, funcao, sessao_anterior, bot)
        else:
            self._abrir_conferencia(ot, nome, funcao, None, bot)

    def _perguntar_retomada(self, ot, nome, funcao, sessao_anterior, bot):
        total_anterior = sum(sessao_anterior["contagem"].values())
        ultima_sessao  = sessao_anterior["sessoes"][-1] if sessao_anterior["sessoes"] else {}
        ultimo_fim     = ultima_sessao.get("fim", "—")
        ultimo_op      = ultima_sessao.get("nome", "—")

        win = ctk.CTkToplevel(self)
        win.title("OT já iniciada")
        win.geometry("420x320")
        win.resizable(False, False)
        win.grab_set()
        win.lift()
        aplicar_icone(win)

        ctk.CTkLabel(win, text=f"OT {ot} — conferência em andamento", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(24, 4))
        ctk.CTkLabel(win, text=f"Última sessão encerrada em:\n{ultimo_fim}\nOperador: {ultimo_op}", font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(0, 8))

        frame_info = ctk.CTkFrame(win, fg_color="gray20", corner_radius=8)
        frame_info.pack(padx=24, fill="x", pady=(0, 16))
        ctk.CTkLabel(frame_info, text=f"  {total_anterior} itens conferidos em {len(sessao_anterior['sessoes'])} sessão(ões)", font=ctk.CTkFont(size=13)).pack(pady=12)

        ctk.CTkLabel(win, text="Deseja continuar a conferência desta OT?", font=ctk.CTkFont(size=13)).pack(pady=(0, 12))

        frame_btns = ctk.CTkFrame(win, fg_color="transparent")
        frame_btns.pack(padx=24, fill="x")

        def continuar():
            win.destroy()
            self._abrir_conferencia(ot, nome, funcao, sessao_anterior, bot)

        def cancelar():
            win.destroy()
            self.campo_ot.delete(0, "end")
            self.label_erro.configure(text="")
            bot.desconectar()

        ctk.CTkButton(frame_btns, text="Continuar", height=40, font=ctk.CTkFont(size=13, weight="bold"), command=continuar).pack(side="left", expand=True, padx=(0, 6))
        ctk.CTkButton(frame_btns, text="Cancelar", height=40, font=ctk.CTkFont(size=13), fg_color="gray30", hover_color="gray40", command=cancelar).pack(side="left", expand=True, padx=(6, 0))

    def _abrir_conferencia(self, ot, nome, funcao, sessao_anterior=None, bot=None):
        self.withdraw()
        TelaConferencia(master_root=self, diretorio_raiz=self.diretorio_raiz,
                        numero_ot=ot, nome_operador=nome, funcao_operador=funcao,
                        sessao_anterior=sessao_anterior, bot_sap=bot)
        
    def perguntar_nova_ot(self, nome_antigo, funcao_antiga):
        self.deiconify() # TelaOTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT
        self.campo_ot.delete(0, "end")
        self.label_erro.configure(text="")
        
        modal = ctk.CTkToplevel(self)
        modal.title("Nova Conferência")
        modal.geometry("420x220")
        modal.resizable(False, False)
        modal.grab_set()
        modal.lift()
        aplicar_icone(modal)
        
        ctk.CTkLabel(modal, text="Conferência Salva!", font=ctk.CTkFont(size=18, weight="bold"), text_color="#4caf50").pack(pady=(20, 5))
        ctk.CTkLabel(modal, text="Deseja iniciar uma nova OT mantendo\nos dados do operador atual?", justify="center").pack(pady=(0, 20))
        
        frame_btns = ctk.CTkFrame(modal, fg_color="transparent")
        frame_btns.pack()
        
        def sim():
            self.campo_nome.delete(0, "end")
            self.campo_nome.insert(0, nome_antigo)
            self.campo_funcao.delete(0, "end")
            self.campo_funcao.insert(0, funcao_antiga)
            self.campo_ot.focus()
            modal.destroy()
            
        def nao():
            self.campo_nome.delete(0, "end")
            self.campo_funcao.delete(0, "end")
            self.campo_nome.focus()
            modal.destroy()
            
        ctk.CTkButton(frame_btns, text="Sim, manter", width=140, height=40, font=ctk.CTkFont(weight="bold"), command=sim).pack(side="left", padx=10)
        ctk.CTkButton(frame_btns, text="Não, trocar usuário", width=140, height=40, fg_color="gray40", hover_color="gray50", command=nao).pack(side="left", padx=10)

# ══════════════════════════════════════════════
# tela 2 - tela principal
# ══════════════════════════════════════════════
class TelaConferencia(ctk.CTkToplevel):
    def __init__(self, master_root, diretorio_raiz, numero_ot, nome_operador, funcao_operador, sessao_anterior=None, bot_sap=None):
        super().__init__(master_root)
        self.bot_sap         = bot_sap 
        self.master_root     = master_root
        self.diretorio_raiz  = diretorio_raiz
        self.numero_ot       = numero_ot
        self.nome_operador   = nome_operador
        self.funcao_operador = funcao_operador
        self.diretorio_destino = os.path.join(diretorio_raiz, f"OT_{numero_ot}")
        os.makedirs(self.diretorio_destino, exist_ok=True)

        if sessao_anterior:
            self.contagem         = defaultdict(int, sessao_anterior["contagem"])
            self.entradas_manuais = defaultdict(int, sessao_anterior["entradas_manuais"])
            self.removidos        = defaultdict(int, sessao_anterior.get("removidos", {}))
            self.sessoes          = sessao_anterior["sessoes"]
        else:
            self.contagem         = defaultdict(int)
            self.entradas_manuais = defaultdict(int)
            self.removidos        = defaultdict(int)
            self.sessoes          = []

        self.inicio_sessao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        self.rodando = False
        self._after_id = None
        self.frame_atual = None
        self.lock_camera = threading.Lock()

        self.tempo_inicio_input = 0.0
        self.flag_colou = False

        self.title(f"Conferência Cega — OT {numero_ot}")
        self.geometry("1060x680")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.encerrar)
        aplicar_icone(self)

        self._construir_layout()
        if sessao_anterior: self._atualizar_painel()

        self.cap = None

        img_vazia = Image.new("RGB", (720, 580), (0, 0, 0))
        self.ctk_img = ctk.CTkImage(light_image=img_vazia, dark_image=img_vazia, size=(720, 580))

        self.rodando = True
        
        threading.Thread(target=self._thread_camera, daemon=True).start()
        self.after(100, self._atualizar_camera)

    def _construir_layout(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        frame_cam = ctk.CTkFrame(self, corner_radius=12)
        frame_cam.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")

        self.label_camera = ctk.CTkLabel(frame_cam, text="Aguardando câmera...")
        self.label_camera.pack(expand=True, fill="both", padx=8, pady=8)

        self.label_status_cam = ctk.CTkLabel(frame_cam, text="⬤  aguardando...", font=ctk.CTkFont(size=11), text_color="gray40")
        self.label_status_cam.pack(pady=(0, 6))

        painel = ctk.CTkFrame(self, corner_radius=12, width=280)
        painel.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")
        painel.grid_propagate(False)

        ctk.CTkLabel(painel, text=f"OT  {self.numero_ot}", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(20, 2))

        n_sessao = len(self.sessoes) + 1
        ctk.CTkLabel(painel, text=f"sessão {n_sessao}  •  {self.nome_operador}", font=ctk.CTkFont(size=12), text_color="gray").pack()

        ctk.CTkFrame(painel, height=1, fg_color="gray30").pack(fill="x", padx=20, pady=12)

        ctk.CTkLabel(painel, text="Leitura de Código", font=ctk.CTkFont(size=13, weight="bold"), text_color="#6870d8").pack()
        self.campo_leitor = ctk.CTkEntry(painel, placeholder_text="0000000000000", width=220, height=45, font=ctk.CTkFont(size=16, weight="bold"), justify="center")
        self.campo_leitor.pack(pady=(5, 10))
        
        self.campo_leitor.bind("<KeyPress>", self._on_keypress)
        self.campo_leitor.bind("<Return>", self._on_enter)
        self.campo_leitor.bind("<<Paste>>", self._on_paste)
        self.campo_leitor.focus_force()

        ctk.CTkLabel(painel, text="Último código lido", font=ctk.CTkFont(size=11), text_color="gray").pack()
        self.label_codigo = ctk.CTkLabel(painel, text="—", font=ctk.CTkFont(size=18, weight="bold"), text_color="#4fc3f7")
        self.label_codigo.pack(pady=(2, 10))

        frame_contadores = ctk.CTkFrame(painel, fg_color="transparent")
        frame_contadores.pack(fill="x", padx=20)

        self._card_contador(frame_contadores, "Total", "label_total")
        self._card_contador(frame_contadores, "Automático (Laser)", "label_auto")
        self._card_contador(frame_contadores, "Manual (Digitação)", "label_manual")

        ctk.CTkFrame(painel, height=1, fg_color="gray30").pack(fill="x", padx=20, pady=12)

        ctk.CTkButton(painel, text="Gerenciar códigos", height=40, font=ctk.CTkFont(size=13, weight="bold"), fg_color="gray30", hover_color="gray40", command=self.abrir_remocao).pack(padx=20, fill="x")

        ctk.CTkFrame(painel, fg_color="transparent").pack(expand=True)

        ctk.CTkButton(painel, text="Encerrar e gerar relatório", height=44, font=ctk.CTkFont(size=13, weight="bold"), fg_color="#c62828", hover_color="#8e0000", command=self.encerrar).pack(padx=20, pady=20, fill="x")

    def _card_contador(self, parent, titulo, attr_name):
        card = ctk.CTkFrame(parent, corner_radius=8, fg_color="gray20")
        card.pack(fill="x", pady=4)
        ctk.CTkLabel(card, text=titulo, font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(6, 0))
        label = ctk.CTkLabel(card, text="0", font=ctk.CTkFont(size=24, weight="bold"))
        label.pack(pady=(0, 6))
        setattr(self, attr_name, label)

    def _atualizar_painel(self):
        total         = sum(self.contagem.values())
        total_manuais = sum(self.entradas_manuais.values())
        self.label_total.configure(text=str(total))
        self.label_auto.configure(text=str(total - total_manuais))
        self.label_manual.configure(text=str(total_manuais))

    def _on_keypress(self, event):
        if event.keysym in ("Return", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R"):
            return
        if len(self.campo_leitor.get()) == 0:
            self.tempo_inicio_input = time.time()
            self.flag_colou = False

    def _on_paste(self, event):
        self.flag_colou = True

    def _on_enter(self, event):
        codigo = self.campo_leitor.get().strip()
        self.campo_leitor.delete(0, "end")
        
        if not (codigo.isdigit() and len(codigo) == 13):
            self.label_codigo.configure(text="Código Incorreto", text_color="#e05c5c")
            return "break"
            
        tempo_decorrido = time.time() - self.tempo_inicio_input
        
        is_manual = (tempo_decorrido > LIMITE_AUTO_SEG) or self.flag_colou
        
        frame_foto = None
        with self.lock_camera:
            if self.frame_atual is not None:
                frame_foto = self.frame_atual.copy()

        self._registrar(codigo, manual=is_manual, frame=frame_foto)
        
        cor_feedback = "#e65100" if is_manual else "#4caf50" 
        self.label_codigo.configure(text=codigo, text_color=cor_feedback)
        
        self.campo_leitor.focus()
        return "break" 

    def _estornar_registro(self, codigo, manual):
        # estorna contagem em caso de erro no controle de transferência
        if self.contagem.get(codigo, 0) > 0:
            self.contagem[codigo] -= 1
            if manual and self.entradas_manuais.get(codigo, 0) > 0:
                self.entradas_manuais[codigo] -= 1
            
            if self.contagem[codigo] == 0:
                del self.contagem[codigo]
                if codigo in self.entradas_manuais and self.entradas_manuais[codigo] == 0:
                    del self.entradas_manuais[codigo]
            
            self._atualizar_painel()
            
            pass
            
            self.label_codigo.configure(text="Código Inválido.", text_color="#ff0000")

    def _thread_camera(self):
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        while self.rodando:
            if self.cap and self.cap.isOpened():
                try:
                    ret, frame = self.cap.read()
                    if ret:
                        with self.lock_camera:
                            self.frame_atual = frame
                except:
                    break
            time.sleep(0.03)

    def _atualizar_camera(self):
        if not self.rodando: return
        try: self.winfo_exists()
        except Exception: return

        frame_exibicao = None
        with self.lock_camera:
            if self.frame_atual is not None:
                frame_exibicao = self.frame_atual.copy()

        if frame_exibicao is not None:
            img_rgb = cv2.cvtColor(frame_exibicao, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img_rgb).resize((720, 580), Image.BILINEAR)
            self.ctk_img.configure(light_image=img_pil, dark_image=img_pil)
            self.label_camera.configure(image=self.ctk_img, text="")
            self.label_status_cam.configure(text="⬤  câmera ativa", text_color="#4caf50")

        if self.rodando:
            self._after_id = self.after(60, self._atualizar_camera)

    def _registrar(self, codigo, manual, frame=None):
        self.contagem[codigo] += 1
        if manual:
            self.entradas_manuais[codigo] += 1

        timestamp = int(time.time())
        modo      = "MANUAL" if manual else "AUTO"
        nome_arq  = f"registro_{modo}_{codigo}_{timestamp}.jpg"
        caminho   = os.path.join(self.diretorio_destino, nome_arq)

        if frame is not None:
            cv2.imwrite(caminho, frame)
        else:
            with open(caminho.replace(".jpg", "_SEM_FOTO.txt"), "w", encoding="utf-8") as f:
                f.write(f"Código    : {codigo}\nModo      : MANUAL sem foto\nTimestamp : {timestamp}\n") # melhorar isso dps, nao ficou bom

        self._atualizar_painel()
        
        if self.bot_sap:
            def worker_sap():
                sucesso, _ = self.bot_sap.inserir_codigo(codigo)
                if not sucesso:
                    self.after(0, lambda: self._estornar_registro(codigo, manual))
            
            threading.Thread(target=worker_sap, daemon=True).start()

    def abrir_remocao(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Gerenciar e Remover Códigos")
        modal.geometry("500x520")
        modal.resizable(False, False)
        modal.grab_set()
        modal.lift()
        aplicar_icone(modal)

        ctk.CTkLabel(modal, text="Remover Códigos", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 5))
        ctk.CTkLabel(modal, text="Selecione o tipo de entrada que deseja remover.", font=ctk.CTkFont(size=12), text_color="gray", justify="center").pack(pady=(0, 10))
        
        campo_busca = ctk.CTkEntry(modal, placeholder_text="Buscar código...", width=460, height=34)
        campo_busca.pack(padx=20, pady=(0, 8))

        scroll_frame = ctk.CTkScrollableFrame(modal, width=460)
        scroll_frame.pack(padx=20, pady=10, fill="both", expand=True)

        def carregar_lista(filtro=""):
            for widget in scroll_frame.winfo_children(): widget.destroy()

            codigos_ativos = {c: q for c, q in self.contagem.items() if q > 0 and filtro in c}
                              
            if not codigos_ativos:
                msg = "Nenhum resultado encontrado." if filtro else "Nenhum código lido ainda."
                ctk.CTkLabel(scroll_frame, text=msg).pack(pady=20)
                return

            for cod in sorted(codigos_ativos.keys()):
                qtd_total  = self.contagem[cod]
                qtd_manual = self.entradas_manuais.get(cod, 0)
                qtd_auto   = qtd_total - qtd_manual

                linha = ctk.CTkFrame(scroll_frame, fg_color="gray20")
                linha.pack(fill="x", pady=4, padx=5)

                info = ctk.CTkFrame(linha, fg_color="transparent")
                info.pack(side="left", padx=10, pady=5)
                ctk.CTkLabel(info, text=cod, font=ctk.CTkFont(weight="bold")).pack(anchor="w")
                ctk.CTkLabel(info, text=f"Auto: {qtd_auto} | Manual: {qtd_manual}", font=ctk.CTkFont(size=11), text_color="gray").pack(anchor="w")

                if qtd_manual > 0:
                    ctk.CTkButton(linha, text="Manual", width=65, height=30, font=ctk.CTkFont(size=11, weight="bold"), fg_color="#c62828", hover_color="#8e0000", command=lambda c=cod: remover_item(c, "manual")).pack(side="right", padx=5, pady=10)

                if qtd_auto > 0:
                    ctk.CTkButton(linha, text="Auto", width=65, height=30, font=ctk.CTkFont(size=11, weight="bold"), fg_color="gray40", hover_color="gray50", command=lambda c=cod: remover_item(c, "auto")).pack(side="right", padx=5, pady=10)

        def remover_item(codigo, tipo):
            if self.contagem.get(codigo, 0) <= 0: return

            if self.bot_sap:
                threading.Thread(target=self.bot_sap.remover_item, args=(codigo,), daemon=True).start()

            self.contagem[codigo]  -= 1
            self.removidos[codigo] += 1
            if tipo == "manual" and self.entradas_manuais.get(codigo, 0) > 0:
                self.entradas_manuais[codigo] -= 1
            if self.contagem[codigo] == 0:
                del self.contagem[codigo]
                if codigo in self.entradas_manuais and self.entradas_manuais[codigo] == 0:
                    del self.entradas_manuais[codigo]
            self._atualizar_painel()
            carregar_lista(campo_busca.get().strip())

        campo_busca.bind("<KeyRelease>", lambda e: carregar_lista(campo_busca.get().strip()))
        carregar_lista()
        
        ctk.CTkButton(modal, text="Voltar", width=180, height=40, font=ctk.CTkFont(size=14, weight="bold"), command=modal.destroy).pack(pady=20)

    def encerrar(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Encerrar")
        modal.geometry("380x350")  
        modal.resizable(False, False)
        modal.grab_set()
        modal.lift()
        aplicar_icone(modal)

        ctk.CTkLabel(modal, text="Encerrar Conferência", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(35, 5))
        ctk.CTkLabel(modal, text=f"OT {self.numero_ot}", font=ctk.CTkFont(size=14), text_color="gray60").pack(pady=(0, 20))

        ctk.CTkButton(modal, text="Finalizar Conferência", fg_color="#1b5e20", hover_color="#407744", height=45, width=280, font=ctk.CTkFont(size=13, weight="bold"), command=lambda: [modal.destroy(), self._confirmar_finalizacao()]).pack(pady=6)
        ctk.CTkButton(modal, text="Pausar conferência", fg_color="#37474f", hover_color="#263238", height=45, width=280, font=ctk.CTkFont(size=13, weight="bold"), command=lambda: [modal.destroy(), self._pausar()]).pack(pady=5)

        ctk.CTkFrame(modal, height=1, width=220, fg_color="#b71c1c").pack(pady=20)

        ctk.CTkButton(modal, text="Voltar para a conferência", fg_color="transparent", hover_color="gray25", text_color="gray60", width=280, height=35, command=modal.destroy).pack(pady=(5, 0))

    def _confirmar_finalizacao(self):
        conf = ctk.CTkToplevel(self)
        conf.title("Confirmação Final")
        conf.geometry("420x260")
        conf.grab_set()
        conf.lift()
        aplicar_icone(conf)

        ctk.CTkLabel(conf, text="Atenção: Finalizar OT", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 10))
        ctk.CTkLabel(conf, text="O sistema irá finalizar a OT no Controle e enviar para auditoria.\nVocê não poderá alterar esta OT depois.\n\nDeseja prosseguir?", wraplength=360, justify="center").pack(pady=10)

        frame_btns = ctk.CTkFrame(conf, fg_color="transparent")
        frame_btns.pack(pady=20)

        ctk.CTkButton(frame_btns, text="Sim, Finalizar", fg_color="#2e7d32", command=lambda: [conf.destroy(), self._iniciar_processo_sap()]).pack(side="left", padx=10)
        ctk.CTkButton(frame_btns, text="Voltar", fg_color="gray40", command=conf.destroy).pack(side="left", padx=10)

    def _pausar(self):
        self.rodando = False 
        if self._after_id: self.after_cancel(self._after_id)
        time.sleep(0.1) 
        if self.cap and self.cap.isOpened(): self.cap.release()

        if self.bot_sap:
            self.bot_sap.pausar_ot()
            self.bot_sap.desconectar()

        fim_sessao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.sessoes.append({
            "inicio": self.inicio_sessao, "fim": fim_sessao, "nome": self.nome_operador,
            "funcao": self.funcao_operador, "modo": "pausa"
        })
        salvar_sessao(self.diretorio_destino, self.contagem, self.entradas_manuais, self.removidos, self.sessoes)
        messagebox.showinfo("Pausado", "OT salva e verificada no Controle. Continue depois.")
        nome = self.nome_operador
        funcao = self.funcao_operador
        master = self.master_root
        self.destroy() 
        master.perguntar_nova_ot(nome, funcao)

    def _iniciar_processo_sap(self):
        self.rodando = False 
        if self._after_id: self.after_cancel(self._after_id)
        time.sleep(0.1) 
        if self.cap and self.cap.isOpened(): self.cap.release()

        loading = ctk.CTkToplevel(self)
        loading.title("Aguarde")
        loading.geometry("340x160")
        loading.resizable(False, False)
        loading.grab_set()
        loading.lift()
        aplicar_icone(loading)

        ctk.CTkLabel(loading, text="Processando OT...", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(30, 8))
        self._label_loading = ctk.CTkLabel(loading, text="Verificando divergências no Controle", font=ctk.CTkFont(size=12), text_color="#e3a83b")
        self._label_loading.pack()
        loading.update()

        def atualizar_texto(texto):
            try:
                if loading.winfo_exists():
                    self._label_loading.configure(text=texto)
                    loading.update()
            except: pass

        def _worker_sap():
            modo = "divergencia" 
            
            try:
                if self.bot_sap:
                    sucesso, msg_status = self.bot_sap.pausar_ot()
                    
                    if sucesso and ("Sem" in msg_status or "sem" in msg_status):
                        modo = "sem_divergencia"
                    elif sucesso and "Com" in msg_status:
                        modo = "divergencia"
                        
                    self.after(0, lambda: atualizar_texto(f"Status Controle:\n{msg_status}"))
                    time.sleep(1.5)
                    
                    self.after(0, lambda: atualizar_texto("Finalizando OT no sistema..."))
                    self.bot_sap.finalizar_ot()
                    self.bot_sap.desconectar()
                    
                self.after(0, lambda: self._finalizar_apos_sap(modo, loading))
                
            except Exception as e:
                self.after(0, lambda: loading.destroy())
                self.bot_sap.desconectar()
                self.after(0, lambda: messagebox.showerror(
                    "Erro de Conexão com Controle", 
                    f"Ocorreu um erro ao comunicar com o Controle. A OT não foi finalizada.\n\nDetalhe técnico: {str(e)}"
                ))

        threading.Thread(target=_worker_sap, daemon=True).start()

    def _finalizar_apos_sap(self, modo, loading):
        fim_sessao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        status_texto = "com divergência" if modo == "divergencia" else "sem divergência"
        self.sessoes.append({
            "inicio": self.inicio_sessao, "fim": fim_sessao, "nome": self.nome_operador,
            "funcao": self.funcao_operador, "modo": modo
        })
        salvar_sessao(self.diretorio_destino, self.contagem, self.entradas_manuais, self.removidos, self.sessoes)

        caminho_rel, conteudo, total_itens, total_manuais, total_removidos = gerar_relatorio(
            self.numero_ot, self.diretorio_destino, self.contagem, self.entradas_manuais, self.removidos, self.sessoes)

        def _enviar():
            nonlocal status_texto

            self.after(0, lambda: [loading.destroy(), self._mostrar_relatorio(caminho_rel, conteudo, "pendente", "", modo)])
            if modo == "divergencia":
                caminho_zip = zipar_ot(self.numero_ot, self.diretorio_destino)
                sucesso, erro = enviar_email(self.numero_ot, caminho_zip, total_itens, total_manuais, total_removidos, status_texto)
            else:
                sucesso, erro = enviar_email_sem_fotos(self.numero_ot, caminho_rel, total_itens, total_manuais)
                self._apagar_fotos()

        # thread em segundo plano
        threading.Thread(target=_enviar, daemon=True).start()

    def _apagar_fotos(self):
        caminho_lixeira = os.path.join(self.diretorio_raiz, "admin", "Lixeira")
        prefixo_ot = f"OT_{self.numero_ot}_DESCARTADA_"
        for arquivo in os.listdir(self.diretorio_destino):
            if arquivo.endswith(".jpg") or arquivo.endswith("_SEM_FOTO.txt"):
                try:
                    origem = os.path.join(self.diretorio_destino, arquivo)
                    destino = os.path.join(caminho_lixeira, prefixo_ot + arquivo)
                    shutil.move(origem, destino)
                except: pass

    def _mostrar_relatorio(self, caminho_rel, conteudo, email_ok, email_erro, modo):
        win = ctk.CTkToplevel(self)
        win.title("Relatório gerado")
        win.geometry("620x600")
        win.grab_set()
        aplicar_icone(win)
        

        def fechar_tudo():
            win.destroy()                # Fecha essa janela do relatório
            nome = self.nome_operador    # Salva o nome
            funcao = self.funcao_operador# Salva a função
            master = self.master_root    # Salva a referência da tela principal
            self.destroy()               # Fecha a tela da câmera/conferência
            master.perguntar_nova_ot(nome, funcao) # abre a TelaOT com a msgbox 
            
        win.protocol("WM_DELETE_WINDOW", fechar_tudo)

        ctk.CTkLabel(win, text="Conferência encerrada", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 4))
        cor_modo  = "#c62828" if modo == "divergencia" else "#2e7d32"
        texto_modo = "OT COM DIVERGÊNCIA" if modo == "divergencia" else "OT SEM DIVERGÊNCIA"
        ctk.CTkLabel(win, text=texto_modo, text_color=cor_modo, font=ctk.CTkFont(weight="bold")).pack(pady=(0, 6))

        if email_ok == "pendente":
            ctk.CTkLabel(win, text="☁ E-mail sendo enviado em segundo plano...", text_color="#e3a83b").pack()
        elif email_ok: ctk.CTkLabel(win, text="✓ Registro enviado por email", text_color="#4caf50").pack()
        else: ctk.CTkLabel(win, text=f"⚠ Erro email: {email_erro}", text_color="#e05c5c").pack()

        caixa = ctk.CTkTextbox(win, font=ctk.CTkFont(family="Courier New", size=12))
        caixa.pack(expand=True, fill="both", padx=16, pady=10)
        caixa.insert("end", conteudo)
        caixa.configure(state="disabled")

        ctk.CTkButton(win, text="Fechar", height=40, command=fechar_tudo).pack(padx=16, pady=16, fill="x")

if __name__ == "__main__":
    diretorio_raiz = encontrar_melhor_particao()
    app = TelaOT(diretorio_raiz)
    app.mainloop()