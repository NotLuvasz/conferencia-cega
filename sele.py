from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import threading

class MotorSAP:
    def __init__(self):
        self.driver = None
        self.url_base = "http://134.65.18.92:8000/quality/transferencia/#/conferencias"
        self.lock_input = threading.Lock()

    def conectar(self):
        try:
            opcoes = Options()
            opcoes.add_experimental_option("debuggerAddress", "127.0.0.1:9224")
            self.driver = webdriver.Chrome(options=opcoes)
            return True, "Conectado ao Chrome!"
        except Exception as e:
            return False, f"Erro: O Chrome com a porta 9224 está aberto?\n{str(e)}"

    def iniciar_conferencia(self, numero_ot):
        """Localiza a OT na lista e entra na tela de edição"""
        url_atual = self.driver.current_url
        
        # O SEGREDO ESTÁ AQUI: Aumentamos a paciência do robô de 5 para 20 segundos.
        # Ele vai ficar "vigiando" a tela até a tabela terminar de carregar.
        wait = WebDriverWait(self.driver, 20)

        # 1. Se já está na tela de conferência exata
        if "editar" in url_atual and numero_ot in self.driver.page_source:
            self._abrir_ot_se_pausada()
            return True, "Já na tela de edição"

        doc_num = None

        # 2. Verifica se a URL já contém o ID do documento
        partes_url = url_atual.split("/")
        if len(partes_url) > 0 and partes_url[-1].isdigit():
            doc_num = partes_url[-1]
        elif len(partes_url) > 1 and partes_url[-2].isdigit() and partes_url[-1] == "editar":
            doc_num = partes_url[-2]

        # 3. Busca a OT na tabela inicial se não tiver o ID
        if not doc_num:
            try:
                # Agora o 'wait' dá tempo suficiente para o "Carregando..." sumir
                ot_elemento = wait.until(EC.presence_of_element_located(
                    (By.XPATH, f"//span[text()='{numero_ot}']")
                ))
                
                id_ot = ot_elemento.get_attribute("id")
                sulfixo_clone = id_ot.split("-")[-1] 
                
                elementos_linha = self.driver.find_elements(
                    By.XPATH, f"//span[contains(@id, '{sulfixo_clone}')]"
                )
                
                for el in elementos_linha:
                    texto = el.get_attribute("textContent").strip()
                    if texto.isdigit() and len(texto) >= 7 and texto != numero_ot:
                        doc_num = texto
                        break
            except Exception:
                # Mensagem de erro mais clara caso a net da loja esteja muito ruim
                return False, f"A OT {numero_ot} não carregou na lista após 20 segundos.\nA página está logada corretamente?"

        # 4. Navega para a URL de edição final
        if doc_num and doc_num.isdigit():
            nova_url = f"{self.url_base}/{doc_num}/editar"
            if url_atual != nova_url:
                self.driver.get(nova_url)
                
            self._abrir_ot_se_pausada()
            return True, doc_num
        else:
            return False, "Falha ao extrair o número do documento."

    def inserir_codigo(self, codigo_barras):
        with self.lock_input:
            try:
                wait = WebDriverWait(self.driver, 3)
                
                # --- PREVENÇÃO: Fecha qualquer popup travado de um erro anterior ---
                try:
                    btn_prev = self.driver.find_element(By.ID, "__mbox-btn-0")
                    btn_prev.click()
                    time.sleep(0.2)
                except:
                    pass
                
                # Procura a caixa de texto
                caixa_texto = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//input[contains(@id, 'editCodigoDeBarras-inner')]")
                ))
                
                # Injeta e dá Enter
                self.driver.execute_script("arguments[0].value = arguments[1];", caixa_texto, codigo_barras)
                caixa_texto.send_keys(Keys.ENTER)
                
                # --- VERIFICAÇÃO DE ERRO ---
                # Esperamos um curtíssimo tempo para ver se o SAP sobe um popup de erro
                time.sleep(0.5)
                try:
                    # Tenta achar o botão OK do popup de erro usando o ID específico que você passou
                    btn_ok = self.driver.find_element(By.ID, "__mbox-btn-0")
                    btn_ok.click() # Fecha o popup automaticamente
                    return False, "Código Inválido" 
                except:
                    # Se não achou o botão OK, o bip entrou com sucesso
                    return True, "Sucesso"

            except Exception as e:
                return False, str(e)

    def remover_item(self, codigo_barras):
        """Clica no botão de remover da linha específica do código"""
        try:
            btn_remover = WebDriverWait(self.driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, f"//tr[.//span[text()='{codigo_barras}']]//button"))
            )
            btn_remover.click()
            time.sleep(0.2) 
            return True
        except:
            return False

    def pausar_ot(self):
        """Clica em Verificar e retorna o status atual (Com/Sem divergência)"""
        try:
            wait = WebDriverWait(self.driver, 5)
            btn_verificar = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[.//bdi[text()='Verificar']]")))
            btn_verificar.click()
            
            btn_sim = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[.//bdi[text()='Sim']]")))
            btn_sim.click()
            
            status_element = wait.until(EC.presence_of_element_located((By.XPATH, "//span[contains(@class, 'sapMObjStatusText')]")))
            return True, status_element.text 
        except Exception as e:
            return False, str(e)

    def finalizar_ot(self):
        """Clica no botão Finalizar e lida com confirmações"""
        try:
            btn_finalizar = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[.//bdi[text()='Finalizar']]"))
            )
            btn_finalizar.click()
            
            try:
                wait_curto = WebDriverWait(self.driver, 1)
                btn_sim = wait_curto.until(EC.element_to_be_clickable((By.XPATH, "//button[.//bdi[text()='Sim']]")))
                btn_sim.click()
            except:
                pass
            return True
        except Exception:
            return False

    def _abrir_ot_se_pausada(self):
        """Destrava a OT se ela estiver em modo apenas leitura"""
        try:
            wait_curto = WebDriverWait(self.driver, 2)
            btn_abrir = wait_curto.until(EC.element_to_be_clickable((By.XPATH, "//button[.//bdi[text()='Abrir']]")))
            btn_abrir.click()
            
            btn_sim = wait_curto.until(EC.element_to_be_clickable((By.XPATH, "//button[.//bdi[text()='Sim']]")))
            btn_sim.click()
            time.sleep(1)
        except:
            pass

    def desconectar(self):
        """Solta o driver sem fechar a janela do navegador"""
        if self.driver:
            self.driver.quit()