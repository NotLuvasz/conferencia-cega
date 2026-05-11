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
            return False, f"Erro: Automação não abriu corretamente.\n{str(e)}"

    def iniciar_conferencia(self, numero_ot):
        # procura a OT na lista do controle de transferência e entra na tela de conferência da OT supracitada fi, palavras bonitas
        url_atual = self.driver.current_url
        
        for aba in self.driver.window_handles:
            self.driver.switch_to.window(aba)
            if "transferencia" in self.driver.current_url: # reconhcer o controle
                break

        # selenium foca no controle esperando a OT aparecer
        wait = WebDriverWait(self.driver, 20)

        # 1. verifica se já está na tela de conferência da OT
        if "editar" in url_atual:
            if str(numero_ot) in self.driver.page_source:
                self._abrir_ot_se_pausada()
                return True, "Já na tela de conferência"
            else:
                # Caso esteja na tela de conferência, mas na OT errada, o script volta pra página inicial do controle.
                print(f"[DEBUG] OT errada. Voltando tela principal")
                self.driver.get(self.url_base)
                
                # dá um tempo pra tela carregar
                time.sleep(1) 
                url_atual = self.driver.current_url

        doc_num = None

        # 2. verifica se a URL tem o doc num
        partes_url = url_atual.split("/")
        if "editar" in url_atual: 
            if len(partes_url) > 1 and partes_url[-2].isdigit():
                doc_num = partes_url[-2]

        # 3. busca a OT na tabela inicial se não tiver o num doc
        if not doc_num:
            try:
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
                return False, f"A OT {numero_ot} não apareceu na lista após 20 segundos.\nA OT está na lista do controle?"

        # 4. vai direto pra URL de conferência
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
                
                # fecha popup do controle em caso de erros, no código de barras. etc, pra conferência continuar sem impedimentos
                try:
                    btn_prev = self.driver.find_element(By.ID, "__mbox-btn-0")
                    btn_prev.click()
                    time.sleep(0.2)
                except:
                    pass
                
                # procura a caixa de texto onde os códigos são inseridos no controle de transferência
                caixa_texto = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//input[contains(@id, 'editCodigoDeBarras-inner')]")
                ))
                
                # inputa o código e dá erro manual
                self.driver.execute_script("arguments[0].value = arguments[1];", caixa_texto, codigo_barras)
                caixa_texto.send_keys(Keys.ENTER)
                
                # espera um tempo pra ver se algum popup de erro aparece
                time.sleep(0.5)
                try:
                    # procura o botão de ok do pop pra fehcar
                    btn_ok = self.driver.find_element(By.ID, "__mbox-btn-0")
                    btn_ok.click() 
                    return False, "Código Inválido" 
                except:
                    return True, "Sucesso"

            except Exception as e:
                return False, str(e)

    def remover_item(self, codigo_barras):
        # clica no botão de remover na linha do código de barras
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
        # verifica a OT e retorna se a OT foi verificada com ou sem divergência
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
        # clica no botão de finalizar, as vezes aparece uma msgbox de confirmação, mas as vezes tb n aparece, n peguei o padrão, ent lidei com isso no wait_curto
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
        # caso a OT esteja verificada, ela é destravada para conferência
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
        if self.driver:
            self.driver.quit()