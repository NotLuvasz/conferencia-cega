import cv2
import os
import time
import json
import zxingcpp
import shutil
import zipfile
import smtplib
import pyautogui
import pygetwindow as gw
import customtkinter as ctk
from datetime import datetime
from collections import defaultdict
from tkinter import messagebox
from PIL import Image
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


# ──────────────────────────────────────────────
#  CONSTANTES
# ──────────────────────────────────────────────
NOME_PASTA_RAIZ  = "Aut Conferencia Cega"
ARQUIVO_CONFIG   = "conf_cega_config.txt"
ARQUIVO_SESSAO   = "sessao.json"
FORMATOS_ACEITOS = zxingcpp.BarcodeFormat.EAN13
SENHA_ADMIN      = "23032005"
DIAS_LIXEIRA     = 7
ICONE_PATH = resource_path("icone.ico")

pyautogui.FAILSAFE = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ──────────────────────────────────────────────
#  CONFIGURAÇÃO DE EMAIL
# ──────────────────────────────────────────────
EMAIL_REMETENTE     = "conferenciagto@gmail.com"
SENHA_APP           = "ctni ipyg kdde etbm"
EMAIL_DESTINATARIOS = [
    "inventario@grupotesouradeouro.com.br",
]

# ──────────────────────────────────────────────
#  SISTEMA DE LIXEIRA (OPÇÃO 01)
# ──────────────────────────────────────────────
def processar_lixeira(diretorio_raiz):
    """Verifica e apaga arquivos da lixeira com mais de 7 dias"""
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
                try:
                    os.remove(caminho_file)
                except:
                    pass

# ──────────────────────────────────────────────
#  ÍCONE
# ──────────────────────────────────────────────
def aplicar_icone(janela):
    try:
        janela.iconbitmap(ICONE_PATH)
    except Exception:
        pass


# ──────────────────────────────────────────────
#  SESSÃO — salva e carrega estado acumulado da OT
# ──────────────────────────────────────────────
def _caminho_sessao(diretorio_destino):
    return os.path.join(diretorio_destino, ARQUIVO_SESSAO)


def carregar_sessao(diretorio_destino):
    caminho = _caminho_sessao(diretorio_destino)
    if os.path.exists(caminho):
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
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
#  ZIP — compacta fotos + relatório da OT
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
#  EMAIL — envia o zip via Gmail
# ──────────────────────────────────────────────
def enviar_email(numero_ot, caminho_zip, total_itens, total_manuais, total_removidos):
    try:
        msg = MIMEMultipart()
        msg["From"]    = EMAIL_REMETENTE
        msg["To"]      = ", ".join(EMAIL_DESTINATARIOS)
        msg["Subject"] = f"Conferência Cega — OT {numero_ot} encerrada"

        corpo = (
            f"OT {numero_ot} encerrada.\n\n"
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
        parte.add_header("Content-Disposition",
                         f"attachment; filename={os.path.basename(caminho_zip)}")
        msg.attach(parte)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(EMAIL_REMETENTE, SENHA_APP)
            servidor.sendmail(EMAIL_REMETENTE, EMAIL_DESTINATARIOS, msg.as_string())

        return True, None

    except Exception as e:
        return False, str(e)


# ──────────────────────────────────────────────
#  DIGITAÇÃO NO CONTROLE VIA PYAUTOGUI
# ──────────────────────────────────────────────
def digitar_no_sap(codigo):
    try:
        janelas = gw.getWindowsWithTitle("Controle de Transferência")
        if janelas:
            janelas[0].activate()
            time.sleep(0.2)

        pyautogui.hotkey('ctrl', 'a')
        pyautogui.typewrite(codigo, interval=0.03)
        pyautogui.press('enter')
        time.sleep(0.15)

        janelas_script = gw.getWindowsWithTitle("Conferência Cega")
        if janelas_script:
            janelas_script[0].activate()

    except Exception as e:
        print(f"  [CONTROLE] erro ao digitar: {e}")


# ──────────────────────────────────────────────
#  PARTIÇÃO
# ──────────────────────────────────────────────
def _listar_particoes():
    return [f"{l}:\\" for l in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            if os.path.exists(f"{l}:\\")]


def _tornar_oculto(caminho):
    os.system(f'attrib +h "{caminho}"')


def encontrar_melhor_particao():
    # --- PARTE 1: VERIFICA SE JÁ EXISTE ---
    for particao in _listar_particoes():
        cfg = os.path.join(particao, NOME_PASTA_RAIZ, ARQUIVO_CONFIG)
        if os.path.exists(cfg):
            with open(cfg, "r", encoding="utf-8") as f:
                salvo = f.read().strip()
            if os.path.exists(salvo):
                # 
                caminho_admin = os.path.join(salvo, "admin")
                if os.path.exists(caminho_admin):
                    _tornar_oculto(caminho_admin)

                processar_lixeira(salvo)
                return salvo

    # --- PARTE 2: BUSCA O MELHOR HD ---
    melhor, maior = None, -1
    for particao in _listar_particoes():
        try:
            livre = shutil.disk_usage(particao).free
            if livre > maior:
                maior, melhor = livre, particao
        except Exception:
            continue

    if not melhor:
        raise RuntimeError("Nenhum HD acessível encontrado.")

    # --- PARTE 3: CRIAÇÃO DA ESTRUTURA ---
    raiz = os.path.join(melhor, NOME_PASTA_RAIZ)
    os.makedirs(raiz, exist_ok=True)
    
    # definicao do blablabla
    caminho_admin = os.path.join(raiz, "admin")
    os.makedirs(os.path.join(caminho_admin, "Lixeira"), exist_ok=True)
    _tornar_oculto(caminho_admin)
    
    cfg = os.path.join(raiz, ARQUIVO_CONFIG)
    with open(cfg, "w", encoding="utf-8") as f:
        f.write(raiz)
    _tornar_oculto(cfg)
    
    processar_lixeira(raiz)
    return raiz


# ──────────────────────────────────────────────
#  RELATÓRIO
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
#  EMAIL SEM FOTOS — só o relatório txt, pra OT sem divergência
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
        parte.add_header("Content-Disposition",
                         f"attachment; filename={os.path.basename(caminho_rel)}")
        msg.attach(parte)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as servidor:
            servidor.login(EMAIL_REMETENTE, SENHA_APP)
            servidor.sendmail(EMAIL_REMETENTE, EMAIL_DESTINATARIOS, msg.as_string())

        return True, None

    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════
#  TELA 1 — ENTRADA DA OT
# ══════════════════════════════════════════════
class TelaOT(ctk.CTk):
    def __init__(self, diretorio_raiz):
        super().__init__()
        self.diretorio_raiz = diretorio_raiz
        self.title("Conferência Cega")
        self.geometry("420x480")
        self.resizable(False, False)
        aplicar_icone(self)

        ctk.CTkLabel(self, text="Conferência Cega",
                     font=ctk.CTkFont(size=24, weight="bold")).pack(pady=(36, 4))
        ctk.CTkLabel(self, text="Prevenção de Perdas",
                     font=ctk.CTkFont(size=13),
                     text_color="gray").pack(pady=(0, 20))

        ctk.CTkLabel(self, text="Nome", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=60)
        self.campo_nome = ctk.CTkEntry(self, placeholder_text="Ex: Lucas Domingues",
                                       width=300, height=36)
        self.campo_nome.pack(padx=60, pady=(4, 12))

        ctk.CTkLabel(self, text="Função", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=60)
        self.campo_funcao = ctk.CTkEntry(self, placeholder_text="Ex: Gerente",
                                         width=300, height=36)
        self.campo_funcao.pack(padx=60, pady=(4, 12))

        ctk.CTkLabel(self, text="Número da OT",
                     font=ctk.CTkFont(size=13)).pack(anchor="w", padx=60)
        self.campo_ot = ctk.CTkEntry(self, placeholder_text="123456",
                                     width=300, height=42,
                                     font=ctk.CTkFont(size=13))
        self.campo_ot.pack(padx=60, pady=(4, 6))
        self.campo_ot.bind("<Return>", lambda e: self.iniciar())

        self.label_erro = ctk.CTkLabel(self, text="", text_color="#e05c5c",
                                       font=ctk.CTkFont(size=12))
        self.label_erro.pack()

        ctk.CTkButton(self, text="Iniciar conferência", width=300, height=42,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self.iniciar).pack(pady=(10, 0))

        # Botão de Acesso Admin (Discreto)
        self.btn_admin = ctk.CTkButton(self, text="⚙", width=30, fg_color="transparent", 
                                      text_color="gray30", hover_color="gray25", 
                                      command=self._acesso_admin)
        self.btn_admin.place(x=10, y=440)

        self.campo_nome.focus()

    def _acesso_admin(self):
        """Abre a janela de senha e já foca no campo automaticamente"""
        janela_senha = ctk.CTkToplevel(self)
        janela_senha.title("Área Restrita")
        janela_senha.geometry("320x200")
        janela_senha.resizable(False, False)
        janela_senha.grab_set() 
        janela_senha.lift()
        aplicar_icone(janela_senha)

        ctk.CTkLabel(janela_senha, text="Senha de Administrador", 
                     font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(25, 10))

        campo_senha = ctk.CTkEntry(janela_senha, placeholder_text="Digite a senha...", 
                                   width=220, show="*", height=35)
        campo_senha.pack(pady=5)

        # O PULO DO GATO:
        # 1. Tenta focar imediatamente
        campo_senha.focus()
        # 2. Garante o foco após 100ms (tempo da janela renderizar)
        janela_senha.after(100, campo_senha.focus)

        def validar():
            if campo_senha.get() == SENHA_ADMIN:
                janela_senha.destroy()
                caminho_lixeira = os.path.join(self.diretorio_raiz, "admin", "Lixeira")
                if os.path.exists(caminho_lixeira):
                    os.startfile(caminho_lixeira)
                else:
                    messagebox.showerror("Erro", "Pasta da lixeira não encontrada.")
            else:
                messagebox.showerror("Erro", "Senha incorreta!")
                campo_senha.delete(0, "end")
                campo_senha.focus()

        ctk.CTkButton(janela_senha, text="Acessar", width=220, height=35,
                      command=validar).pack(pady=15)

        # Atalho Enter: Você digita e já cai pra dentro
        janela_senha.bind("<Return>", lambda e: validar())

    def iniciar(self):
        nome   = self.campo_nome.get().strip()
        funcao = self.campo_funcao.get().strip()
        ot     = self.campo_ot.get().strip()

        if not nome or not funcao:
            self.label_erro.configure(text="Preencha nome e função.")
            return
        if not (ot.isdigit() and len(ot) == 6):
            self.label_erro.configure(text="Digite exatamente 6 números para a OT.")
            return

        diretorio_destino = os.path.join(self.diretorio_raiz, f"OT_{ot}")
        sessao_anterior   = carregar_sessao(diretorio_destino)

        if sessao_anterior:
            self._perguntar_retomada(ot, nome, funcao, sessao_anterior)
        else:
            self._abrir_conferencia(ot, nome, funcao)

    def _perguntar_retomada(self, ot, nome, funcao, sessao_anterior):
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

        ctk.CTkLabel(win, text=f"OT {ot} — conferência em andamento",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(24, 4))
        ctk.CTkLabel(win,
                     text=f"Última sessão encerrada em:\n{ultimo_fim}\nOperador: {ultimo_op}",
                     font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(0, 8))

        frame_info = ctk.CTkFrame(win, fg_color="gray20", corner_radius=8)
        frame_info.pack(padx=24, fill="x", pady=(0, 16))
        ctk.CTkLabel(frame_info,
                     text=f"  {total_anterior} itens conferidos em "
                          f"{len(sessao_anterior['sessoes'])} sessão(ões)",
                     font=ctk.CTkFont(size=13)).pack(pady=12)

        ctk.CTkLabel(win, text="Deseja continuar a conferência desta OT?",
                     font=ctk.CTkFont(size=13)).pack(pady=(0, 12))

        frame_btns = ctk.CTkFrame(win, fg_color="transparent")
        frame_btns.pack(padx=24, fill="x")

        def continuar():
            win.destroy()
            self._abrir_conferencia(ot, nome, funcao, sessao_anterior)

        def cancelar():
            win.destroy()
            self.campo_ot.delete(0, "end")
            self.label_erro.configure(text="")

        ctk.CTkButton(frame_btns, text="Continuar",
                      height=40, font=ctk.CTkFont(size=13, weight="bold"),
                      command=continuar).pack(side="left", expand=True, padx=(0, 6))
        ctk.CTkButton(frame_btns, text="Cancelar",
                      height=40, font=ctk.CTkFont(size=13),
                      fg_color="gray30", hover_color="gray40",
                      command=cancelar).pack(side="left", expand=True, padx=(6, 0))

    def _abrir_conferencia(self, ot, nome, funcao, sessao_anterior=None):
        self.withdraw()
        TelaConferencia(master_root=self, diretorio_raiz=self.diretorio_raiz,
                        numero_ot=ot, nome_operador=nome, funcao_operador=funcao,
                        sessao_anterior=sessao_anterior)


# ══════════════════════════════════════════════
#  TELA 2 — CONFERÊNCIA
# ══════════════════════════════════════════════
class TelaConferencia(ctk.CTkToplevel):
    def __init__(self, master_root, diretorio_raiz, numero_ot,
                 nome_operador, funcao_operador, sessao_anterior=None):
        super().__init__(master_root)
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
        self.ultimo_codigo = ""
        self.tempo_ultima  = 0
        self.rodando       = False
        self._after_id     = None

        self.title(f"Conferência Cega — OT {numero_ot}")
        self.geometry("1060x680")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.encerrar)
        aplicar_icone(self)

        self._construir_layout()

        if sessao_anterior:
            self._atualizar_painel()

        self.cap = cv2.VideoCapture(0)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        img_vazia = Image.new("RGB", (720, 580), (0, 0, 0))
        self.ctk_img = ctk.CTkImage(light_image=img_vazia, dark_image=img_vazia,
                                    size=(720, 580))

        self.rodando = True
        self.after(100, self._atualizar_camera)

    def _construir_layout(self):
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        frame_cam = ctk.CTkFrame(self, corner_radius=12)
        frame_cam.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")

        self.label_camera = ctk.CTkLabel(frame_cam, text="Aguardando câmera...")
        self.label_camera.pack(expand=True, fill="both", padx=8, pady=8)

        painel = ctk.CTkFrame(self, corner_radius=12, width=280)
        painel.grid(row=0, column=1, padx=(8, 16), pady=16, sticky="nsew")
        painel.grid_propagate(False)

        ctk.CTkLabel(painel, text=f"OT  {self.numero_ot}",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(24, 2))

        n_sessao = len(self.sessoes) + 1
        ctk.CTkLabel(painel, text=f"sessão {n_sessao}  •  {self.nome_operador}",
                     font=ctk.CTkFont(size=12), text_color="gray").pack()

        ctk.CTkFrame(painel, height=1, fg_color="gray30").pack(fill="x", padx=20, pady=16)

        ctk.CTkLabel(painel, text="Último código lido",
                     font=ctk.CTkFont(size=12), text_color="gray").pack()
        self.label_codigo = ctk.CTkLabel(painel, text="—",
                                         font=ctk.CTkFont(size=18, weight="bold"),
                                         text_color="#4fc3f7")
        self.label_codigo.pack(pady=(2, 16))

        frame_contadores = ctk.CTkFrame(painel, fg_color="transparent")
        frame_contadores.pack(fill="x", padx=20)

        self._card_contador(frame_contadores, "Total", "label_total")
        self._card_contador(frame_contadores, "Automático", "label_auto")
        self._card_contador(frame_contadores, "Manual", "label_manual")

        ctk.CTkFrame(painel, height=1, fg_color="gray30").pack(fill="x", padx=20, pady=15)

        ctk.CTkButton(painel, text="Gerenciar códigos",
                      height=40, font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color="gray30", hover_color="gray40",
                      command=self.abrir_remocao).pack(padx=20, fill="x", pady=(0, 10))

        ctk.CTkButton(painel, text="Digitar código manual",
                      height=40, font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color="#e65100", hover_color="#bf360c",
                      command=self.abrir_manual).pack(padx=20, fill="x")

        ctk.CTkLabel(painel, text="use quando a etiqueta\nnão puder ser lida",
                     font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(6, 0))

        ctk.CTkFrame(painel, fg_color="transparent").pack(expand=True)

        ctk.CTkButton(painel, text="Encerrar e gerar relatório",
                      height=44, font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color="#c62828", hover_color="#8e0000",
                      command=self.encerrar).pack(padx=20, pady=20, fill="x")

    def _card_contador(self, parent, titulo, attr_name):
        card = ctk.CTkFrame(parent, corner_radius=8, fg_color="gray20")
        card.pack(fill="x", pady=4)
        ctk.CTkLabel(card, text=titulo,
                     font=ctk.CTkFont(size=11), text_color="gray").pack(pady=(8, 0))
        label = ctk.CTkLabel(card, text="0",
                              font=ctk.CTkFont(size=26, weight="bold"))
        label.pack(pady=(0, 8))
        setattr(self, attr_name, label)

    def _atualizar_painel(self):
        total         = sum(self.contagem.values())
        total_manuais = sum(self.entradas_manuais.values())
        self.label_total.configure(text=str(total))
        self.label_auto.configure(text=str(total - total_manuais))
        self.label_manual.configure(text=str(total_manuais))

    def _atualizar_camera(self):
        if not self.rodando:
            return
        try:
            self.winfo_exists()
        except Exception:
            return

        ret, frame = self.cap.read()
        if ret:
            resultados = zxingcpp.read_barcodes(frame, formats=FORMATOS_ACEITOS)
            for res in resultados:
                codigo = res.text
                agora  = time.time()
                if codigo != self.ultimo_codigo or (agora - self.tempo_ultima) > 2:
                    self._registrar(codigo, manual=False, frame=frame)
                    self.ultimo_codigo = codigo
                    self.tempo_ultima  = agora

                if res.position:
                    pos = res.position
                    pts = [
                        (int(pos.top_left.x),     int(pos.top_left.y)),
                        (int(pos.top_right.x),    int(pos.top_right.y)),
                        (int(pos.bottom_right.x), int(pos.bottom_right.y)),
                        (int(pos.bottom_left.x),  int(pos.bottom_left.y))
                    ]
                    for i in range(4):
                        cv2.line(frame, pts[i], pts[(i+1) % 4], (0, 255, 80), 2)
                    cv2.putText(frame, f"Lido: {codigo}",
                                (pts[0][0], pts[0][1] - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 80), 2)

            img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(img_rgb).resize((720, 580), Image.LANCZOS)
            self.ctk_img.configure(light_image=img_pil, dark_image=img_pil)
            self.label_camera.configure(image=self.ctk_img, text="")

        if self.rodando:
            self._after_id = self.after(30, self._atualizar_camera)

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
                f.write(f"Código    : {codigo}\n"
                        f"Modo      : MANUAL sem foto\n"
                        f"Timestamp : {timestamp}\n")

        self._atualizar_painel()
        self.label_codigo.configure(text=codigo)
        digitar_no_sap(codigo)

    def abrir_manual(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Entrada manual")
        modal.geometry("380x230")
        modal.resizable(False, False)
        modal.grab_set()
        modal.lift()
        aplicar_icone(modal)

        ctk.CTkLabel(modal, text="Digite o código de barras",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(28, 4))
        ctk.CTkLabel(modal, text="13 dígitos numéricos",
                     font=ctk.CTkFont(size=12), text_color="gray").pack()

        campo = ctk.CTkEntry(modal, placeholder_text="0000000000000",
                             width=260, height=42,
                             font=ctk.CTkFont(size=18))
        campo.pack(pady=14)

        label_erro = ctk.CTkLabel(modal, text="", text_color="#e05c5c",
                                  font=ctk.CTkFont(size=12))
        label_erro.pack()

        def confirmar():
            cod = campo.get().strip()
            if not (cod.isdigit() and len(cod) == 13):
                label_erro.configure(
                    text=f"Código inválido. Você digitou {len(cod)} caractere(s).")
                return
            ret, frame_foto = self.cap.read()
            self._registrar(cod, manual=True, frame=frame_foto if ret else None)
            campo.delete(0, "end")
            label_erro.configure(text="✓ Registrado!", text_color="#4caf50")
            modal.after(900, lambda: label_erro.configure(text="", text_color="#e05c5c"))

        campo.bind("<Return>", lambda e: confirmar())
        ctk.CTkButton(modal, text="Registrar", width=260, height=40,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      fg_color="#e65100", hover_color="#bf360c",
                      command=confirmar).pack()
        campo.focus()

    def abrir_remocao(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Gerenciar e Remover Códigos")
        modal.geometry("500x520")
        modal.resizable(False, False)
        modal.grab_set()
        modal.lift()
        aplicar_icone(modal)

        ctk.CTkLabel(modal, text="Remover Códigos",
                     font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(15, 5))
        ctk.CTkLabel(modal,
                     text="Selecione o tipo de entrada que deseja remover.\n"
                          "O código removido deve ser retirado manualmente do Controle.",
                     font=ctk.CTkFont(size=12), text_color="gray",
                     justify="center").pack(pady=(0, 10))

        scroll_frame = ctk.CTkScrollableFrame(modal, width=460)
        scroll_frame.pack(padx=20, pady=10, fill="both", expand=True)

        def carregar_lista():
            for widget in scroll_frame.winfo_children():
                widget.destroy()

            codigos_ativos = {c: q for c, q in self.contagem.items() if q > 0}
            if not codigos_ativos:
                ctk.CTkLabel(scroll_frame, text="Nenhum código lido ainda.").pack(pady=20)
                return

            for cod in sorted(codigos_ativos.keys()):
                qtd_total  = self.contagem[cod]
                qtd_manual = self.entradas_manuais.get(cod, 0)
                qtd_auto   = qtd_total - qtd_manual

                linha = ctk.CTkFrame(scroll_frame, fg_color="gray20")
                linha.pack(fill="x", pady=4, padx=5)

                info = ctk.CTkFrame(linha, fg_color="transparent")
                info.pack(side="left", padx=10, pady=5)
                ctk.CTkLabel(info, text=cod,
                             font=ctk.CTkFont(weight="bold")).pack(anchor="w")
                ctk.CTkLabel(info, text=f"Auto: {qtd_auto} | Manual: {qtd_manual}",
                             font=ctk.CTkFont(size=11),
                             text_color="gray").pack(anchor="w")

                if qtd_manual > 0:
                    ctk.CTkButton(linha, text="Manual", width=65, height=30,
                                  font=ctk.CTkFont(size=11, weight="bold"),
                                  fg_color="#c62828", hover_color="#8e0000",
                                  command=lambda c=cod: remover_item(c, "manual")
                                  ).pack(side="right", padx=5, pady=10)

                if qtd_auto > 0:
                    ctk.CTkButton(linha, text="Auto", width=65, height=30,
                                  font=ctk.CTkFont(size=11, weight="bold"),
                                  fg_color="gray40", hover_color="gray50",
                                  command=lambda c=cod: remover_item(c, "auto")
                                  ).pack(side="right", padx=5, pady=10)

        def remover_item(codigo, tipo):
            if self.contagem.get(codigo, 0) <= 0:
                return
            self.contagem[codigo]  -= 1
            self.removidos[codigo] += 1
            if tipo == "manual" and self.entradas_manuais.get(codigo, 0) > 0:
                self.entradas_manuais[codigo] -= 1
            if self.contagem[codigo] == 0:
                del self.contagem[codigo]
                if codigo in self.entradas_manuais and self.entradas_manuais[codigo] == 0:
                    del self.entradas_manuais[codigo]
            self._atualizar_painel()
            carregar_lista()

        carregar_lista()
        ctk.CTkButton(modal, text="Voltar para Câmera", width=180, height=40,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=modal.destroy).pack(pady=20)

    # ── ENCERRAR — MODIFICADO PARA OPÇÃO 01 e 02 ─────────────────
    def encerrar(self):
        modal = ctk.CTkToplevel(self)
        modal.title("Encerrar")
        modal.geometry("380x420")  # Ficou um pouco mais alto e estreito, mais elegante
        modal.resizable(False, False)
        modal.grab_set()
        modal.lift()
        aplicar_icone(modal)

        # Header mais limpo
        ctk.CTkLabel(modal, text="Encerrar Conferência",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(35, 5))
        ctk.CTkLabel(modal, text=f"OT {self.numero_ot}",
                     font=ctk.CTkFont(size=14), text_color="gray60").pack(pady=(0, 30))

        # Configuração padrão para os botões de ação
        btn_params = {"height": 45, "width": 280, "font": ctk.CTkFont(size=13, weight="bold")}

        # Botão: Divergência (Vermelho mais suave)
        ctk.CTkButton(modal, text="Finalizar com Divergência",
                      fg_color="#b71c1c", hover_color="#ee4444",
                      command=lambda: [modal.destroy(), self._confirmar_finalizacao("divergencia")],
                      **btn_params).pack(pady=6)

        # Botão: Sem Divergência (Verde mais sóbrio)
        ctk.CTkButton(modal, text="Finalizar sem Divergência",
                      fg_color="#1b5e20", hover_color="#407744",
                      command=lambda: [modal.destroy(), self._confirmar_finalizacao("sem_divergencia")],
                      **btn_params).pack(pady=6)

        # Linha divisória sutil
        ctk.CTkFrame(modal, height=1, width=220, fg_color="#b71c1c").pack(pady=20)

        # Botão: Pausar (Cinza neutro)
        ctk.CTkButton(modal, text="Pausar conferência",
                      fg_color="#37474f", hover_color="#263238",
                      command=lambda: [modal.destroy(), self._pausar()],
                      **btn_params).pack(pady=5)

        # Botão: Cancelar (Apenas texto, sem fundo)
        ctk.CTkButton(modal, text="Voltar para a conferência",
                      fg_color="transparent",  # Fundo transparente
                      hover_color="gray25",    # Efeito discreto ao passar o mouse
                      text_color="gray60",     # Cor de texto mais suave
                      width=280,
                      height=35,
                      command=modal.destroy).pack(pady=(15, 0))

    def _confirmar_finalizacao(self, modo):
        conf = ctk.CTkToplevel(self)
        conf.title("Confirmação Final")
        conf.geometry("420x260")
        conf.grab_set()
        conf.lift()
        aplicar_icone(conf)

        if modo == "divergencia":
            titulo = "Atenção: OT com Divergência"
            texto = "Verificou etiqueta interna?\n(Confirme se todos os itens foram bipados corretamente)"
            cor_btn = "#c62828"
        else:
            titulo = "Atenção: OT sem Divergência"
            texto = "Você confirmou que não há nenhuma peça sobrando ou faltando?\nAs imagens registradas serão descartadas."
            cor_btn = "#2e7d32"

        ctk.CTkLabel(conf, text=titulo, font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 10))
        ctk.CTkLabel(conf, text=texto, wraplength=360, justify="center").pack(pady=10)

        frame_btns = ctk.CTkFrame(conf, fg_color="transparent")
        frame_btns.pack(pady=20)

        ctk.CTkButton(frame_btns, text="Sim, Confirmar", fg_color=cor_btn,
                      command=lambda: [conf.destroy(), self._finalizar(modo)]).pack(side="left", padx=10)
        ctk.CTkButton(frame_btns, text="Voltar", fg_color="gray40",
                      command=conf.destroy).pack(side="left", padx=10)

    def _pausar(self):
        self.rodando = False
        if self._after_id:
            self.after_cancel(self._after_id)
        self.cap.release()
        fim_sessao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.sessoes.append({
            "inicio": self.inicio_sessao,
            "fim":    fim_sessao,
            "nome":   self.nome_operador,
            "funcao": self.funcao_operador,
            "modo":   "pausa"
        })
        salvar_sessao(self.diretorio_destino, self.contagem,
                      self.entradas_manuais, self.removidos, self.sessoes)
        messagebox.showinfo("Pausado", "OT salva. Continue depois.")
        self.master_root.destroy()

    def _finalizar(self, modo):
        self.rodando = False
        if self._after_id:
            self.after_cancel(self._after_id)
        self.cap.release()

        fim_sessao = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.sessoes.append({
            "inicio": self.inicio_sessao, "fim": fim_sessao,
            "nome": self.nome_operador, "funcao": self.funcao_operador, "modo": modo
        })
        salvar_sessao(self.diretorio_destino, self.contagem, self.entradas_manuais, self.removidos, self.sessoes)

        caminho_rel, conteudo, total_itens, total_manuais, total_removidos = gerar_relatorio(
            self.numero_ot, self.diretorio_destino,
            self.contagem, self.entradas_manuais, self.removidos, self.sessoes)

        if modo == "divergencia":
            caminho_zip = zipar_ot(self.numero_ot, self.diretorio_destino)
            sucesso, erro = enviar_email(self.numero_ot, caminho_zip, total_itens, total_manuais, total_removidos)
            self._mostrar_relatorio(caminho_rel, conteudo, sucesso, erro, modo)
        else:
            sucesso, erro = enviar_email_sem_fotos(self.numero_ot, caminho_rel, total_itens, total_manuais)
            self._apagar_fotos() # Agora ele move para lixeira
            self._mostrar_relatorio(caminho_rel, conteudo, sucesso, erro, modo)

    def _apagar_fotos(self):
        # Move fotos para a lixeira ao invés de apagar, invés tá certo?
        caminho_lixeira = os.path.join(self.diretorio_raiz, "admin", "Lixeira")
        prefixo_ot = f"OT_{self.numero_ot}_DESCARTADA_"
        
        for arquivo in os.listdir(self.diretorio_destino):
            if arquivo.endswith(".jpg") or arquivo.endswith("_SEM_FOTO.txt"):
                try:
                    origem = os.path.join(self.diretorio_destino, arquivo)
                    destino = os.path.join(caminho_lixeira, prefixo_ot + arquivo)
                    shutil.move(origem, destino)
                except Exception:
                    pass

    def _mostrar_relatorio(self, caminho_rel, conteudo, email_ok, email_erro, modo):
        win = ctk.CTkToplevel(self)
        win.title("Relatório gerado")
        win.geometry("620x600")
        win.grab_set()
        aplicar_icone(win)
        win.protocol("WM_DELETE_WINDOW", self.master_root.destroy)

        ctk.CTkLabel(win, text="Conferência encerrada", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 4))
        cor_modo  = "#c62828" if modo == "divergencia" else "#2e7d32"
        texto_modo = "OT com divergência" if modo == "divergencia" else "OT sem divergência"
        ctk.CTkLabel(win, text=texto_modo, text_color=cor_modo, font=ctk.CTkFont(weight="bold")).pack(pady=(0, 6))

        if email_ok:
            ctk.CTkLabel(win, text="✓ Registro enviado por email", text_color="#4caf50").pack()
        else:
            ctk.CTkLabel(win, text=f"⚠ Erro email: {email_erro}", text_color="#e05c5c").pack()

        caixa = ctk.CTkTextbox(win, font=ctk.CTkFont(family="Courier New", size=12))
        caixa.pack(expand=True, fill="both", padx=16, pady=10)
        caixa.insert("end", conteudo)
        caixa.configure(state="disabled")

        ctk.CTkButton(win, text="Fechar", height=40, command=self.master_root.destroy).pack(padx=16, pady=16, fill="x")


if __name__ == "__main__":
    diretorio_raiz = encontrar_melhor_particao()
    app = TelaOT(diretorio_raiz)
    app.mainloop()