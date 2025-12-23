import os
import json
import base64
import time
import logging
import fitz  # PyMuPDF
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURAÇÕES DE PRODUÇÃO ---
DIR_ENTRADA = os.getenv("PASTA_ENTRADA")
DIR_SAIDA_BRUTA = os.getenv("TESTE_GEMINI_JSON")
DIR_LOGS = r"outputs\logs"

# Configuração da API Google Gemini
API_KEY = os.getenv("GEMINI_API_KEY")
MODELO_GEMINI = "gemini-2.5-flash-preview-09-2025" # O "Nano Banana"

# Configuração do Rate Limiter (Timer)
ARQUIVOS_POR_LOTE = 4
TEMPO_ESPERA_SEGUNDOS = 60

# Logging
os.makedirs(DIR_SAIDA_BRUTA, exist_ok=True)
os.makedirs(DIR_LOGS, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(DIR_LOGS, f"extracao_gemini_{datetime.now().strftime('%Y%m%d')}.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

def converter_pdf_para_imagens_b64(caminho_pdf):
    """
    Converte páginas estratégicas (Início + Fim) em imagens Base64.
    Estratégia: 2 primeiras (valores/prazo) + 3 últimas (assinaturas).
    """
    imagens_payload = []
    try:
        doc = fitz.open(caminho_pdf)
        total_pags = len(doc)
        
        if total_pags > 6:
            indices = list(range(3)) + list(range(total_pags - 2, total_pags))
        else:
            indices = range(total_pags)

        for i in indices:
            pagina = doc.load_page(i)
            # Zoom 2.0x para o Gemini ler letras miúdas de carimbos
            pix = pagina.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            img_bytes = pix.tobytes("jpeg")
            b64_str = base64.b64encode(img_bytes).decode('utf-8')
            
            # Formato específico para o payload do Gemini
            imagens_payload.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": b64_str
                }
            })
            
        return imagens_payload
    except Exception as e:
        logging.error(f"Erro ao converter PDF {caminho_pdf}: {e}")
        return []

def consultar_gemini_vision(imagens_payload, nome_arquivo):
    """
    Envia imagens para o Gemini 2.5 Flash via REST API.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO_GEMINI}:generateContent?key={API_KEY}"
    headers = {"Content-Type": "application/json"}
    
    prompt_text = f"""
    Você é um Perito Forense e Calculista Judicial. Analise este contrato: {nome_arquivo}.
    
    ETAPA 1: EXTRAÇÃO
    1. Valor Aluguel Mensal (Ignore condomínio/IPTU).
    2. Status Assinatura:
       - DIGITAL (GOV/ICP): Logos Gov.br, DocuSign ou Qualquer outra assinatura digital.
       - FÍSICA (COM FIRMA): Selos de cartório coloridos.
       - FÍSICA (SEM FIRMA): Assinatura caneta sem selo.
       - NÃO ASSINADO: Em branco.
    3. Datas: Início e Fim da vigência.
    4. Partes: Locador e Locatário.

    ETAPA 2: CÁLCULO CUSTAS (Base = Aluguel x 12)
    Use a tabela abaixo para calcular a taxa de registro:
    - Até 3.200 -> 319,12
    - 3.200 a 8.000 -> 483,68
    - 8.000 a 12.000 -> 522,76
    - 12.000 a 16.000 -> 562,54
    - 16.000 a 24.000 -> 642,22
    - 24.000 a 32.000 -> 723,98
    - 32.000 a 47.000 -> 799,68
    - 47.000 a 63.000 -> 881,24
    - 63.000 a 78.000 -> 967,68
    - 78.000 a 118.000 -> 1.030,66
    - 118.000 a 160.000 -> 1.115,10
    - 160.000 a 235.000 -> 1.805,16
    - 235.000 a 350.000 -> 2.708,06
    - 350.000 a 530.000 -> 4.067,28
    - 530.000 a 800.000 -> 6.099,38
    - 800.000 a 1.2M -> 9.147,62
    - 1.2M a 1.8M -> 10.977,08
    - 1.8M a 2.7M -> 14.270,54
    - 2.7M a 4.0M -> 18.551,68
    - Acima de 4.0M -> 24.131,20

    RETORNE APENAS JSON:
    {{
      "status": "CATEGORIA",
      "data_evidencia": "DD/MM/AAAA",
      "descricao_prova": "O que você viu",
      "locador": "Nome",
      "locatario": "Nome",
      "data_inicio_contrato": "DD/MM/AAAA",
      "data_fim_contrato": "DD/MM/AAAA",
      "moeda": "BRL",
      "valor_aluguel_mensal_float": 0.00,
      "base_calculo_12_meses_float": 0.00,
      "custo_registro_cartorio_float": 0.00,
      "memoria_calculo": "Detalhe o cálculo"
    }}
    """

    # Monta o payload: Texto do Prompt + Lista de Imagens
    parts = [{"text": prompt_text}] + imagens_payload
    
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {"response_mime_type": "application/json"}
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            logging.error(f"Erro API Gemini ({response.status_code}): {response.text}")
            return None
    except Exception as e:
        logging.error(f"Erro Request: {e}")
        return None

def executar_producao():
    if not API_KEY:
        print(" Erro: GOOGLE_API_KEY não configurada.")
        return

    if not os.path.exists(DIR_ENTRADA):
        print(f" Diretório não encontrado: {DIR_ENTRADA}")
        return

    arquivos = [f for f in os.listdir(DIR_ENTRADA) if f.lower().endswith('.pdf')]
    total_arquivos = len(arquivos)
    
    print(" Iniciando Produção com Gemini 2.5 Flash")
    print(f" Arquivos: {total_arquivos}")
    print(f" Regra: Pausa de {TEMPO_ESPERA_SEGUNDOS}s a cada {ARQUIVOS_POR_LOTE} envios.\n")

    processados_no_lote = 0

    for i, arquivo in enumerate(arquivos):
        nome_safe = os.path.splitext(arquivo)[0]
        caminho_salvamento = os.path.join(DIR_SAIDA_BRUTA, f"{nome_safe}_RAW.json")

        # Verifica se já foi processado (Retomada Inteligente)
        if os.path.exists(caminho_salvamento):
            print(f" [{i+1}/{total_arquivos}] Pulando (Já existe): {arquivo}")
            continue

        # --- CONTROLE DE RATE LIMIT ---
        if processados_no_lote > 0 and processados_no_lote % ARQUIVOS_POR_LOTE == 0:
            print(f"\n Limite de lote atingido ({ARQUIVOS_POR_LOTE}).")
            print(f" Aguardando {TEMPO_ESPERA_SEGUNDOS} segundos para esfriar a API...")
            time.sleep(TEMPO_ESPERA_SEGUNDOS)
            print(" Retomando...\n")

        print(f" [{i+1}/{total_arquivos}] Processando: {arquivo}...")
        
        # 1. Converter PDF em Imagens
        imagens = converter_pdf_para_imagens_b64(os.path.join(DIR_ENTRADA, arquivo))
        
        if not imagens:
            logging.error(f"Falha ao gerar imagens para {arquivo}")
            continue

        # 2. Enviar para Gemini
        resultado_raw = consultar_gemini_vision(imagens, arquivo)

        if resultado_raw:
            pacote = {
                "arquivo_origem": arquivo,
                "modelo": MODELO_GEMINI,
                "timestamp": datetime.now().isoformat(),
                "resposta_ia_raw": resultado_raw
            }
            
            with open(caminho_salvamento, 'w', encoding='utf-8') as f:
                json.dump(pacote, f, indent=4, ensure_ascii=False)
            
            print("Sucesso! JSON Salvo.")
            processados_no_lote += 1
        else:
            print("    Falha na API.")

if __name__ == "__main__":
    try:
        executar_producao()
    except KeyboardInterrupt:
        print("\n Interrompido pelo usuário.")