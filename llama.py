import os
import json
import time
import logging
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from llama_parse import LlamaParse

# Carrega variáveis de ambiente
load_dotenv()

# --- CONFIGURAÇÕES VIA .ENV ---
# Usa os caminhos definidos no .env ou valores padrão (fallback)
DIR_ENTRADA = os.getenv("PASTA_ENTRADA")
DIR_SAIDA_BRUTA = os.getenv("PASTA_SAIDA_JSON")
DIR_LOGS = r"outputs\logs"

# Configuração API (Inteligência)
CLIENTE_API = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("JULLIANE"),
    default_headers={"HTTP-Referer": "https://merca.com.br", "X-Title": "Auditor LlamaParse"}
)
MODELO_IA = "xiaomi/mimo-v2-flash:free"

# Configuração LlamaParse (Leitura de PDF)
parser = LlamaParse(
    api_key=os.getenv("LLAMA_CLOUD_API_KEY_2"),
    result_type="markdown",  # Markdown preserva estrutura de tabelas
    language="pt",
    verbose=False
)

# Configuração de Logs
os.makedirs(DIR_SAIDA_BRUTA, exist_ok=True)
os.makedirs(DIR_LOGS, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(DIR_LOGS, f"extracao_llama_{datetime.now().strftime('%Y%m%d')}.log"),
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

def extrair_texto_llama(caminho_pdf):
    """
    Usa LlamaParse para converter PDF em Markdown estruturado.
    Ideal para documentos longos e tabelas.
    """
    try:
        # LlamaParse retorna uma lista de documentos (páginas)
        documentos = parser.load_data(caminho_pdf)
        
        # Concatena tudo em um texto único
        texto_completo = "\n\n".join([doc.text for doc in documentos])
        return texto_completo
    except Exception as e:
        logging.error(f"Erro LlamaParse ao ler {caminho_pdf}: {e}")
        return None

def consultar_claude_raw(texto_markdown, nome_arquivo):
    """
    Envia o TEXTO EXTRAÍDO para o Claude analisar.
    """
    prompt_system = """
    Você é um perito forense e calculista judicial especializado em contratos de locação. 
    
    ATENÇÃO: Você está analisando a TRANSCRIÇÃO DE TEXTO (OCR) de um documento.
    Sua missão é validar contratos de aluguel e calcular as custas de registro em cartório.

    ### Seu Processo de Análise

    #### Etapa 1: Extração de Dados do Contrato
    Analise o texto fornecido e extraia:
    - **Valor do Aluguel Mensal**: Localize "Valor do Aluguel" ou "Aluguel Mensal". Ignore condomínio/IPTU.
    - **Status de Assinatura**: Procure por indícios textuais:
      - DIGITAL (GOV/ICP): Termos como "Assinado digitalmente", "Gov.br", "ICP-Brasil", "Hash", "Carimbo de tempo".
      - FÍSICA (COM FIRMA): Termos como "Reconheço a firma", "Em testemunho da verdade", "Tabelionato", "Selo", "Dou fé".
      - FÍSICA (SEM FIRMA): Nomes dos signatários no final mas sem menção de cartório/digital.
      - NÃO ASSINADO: Se não houver campo de assinaturas preenchido.
    - **Partes**: Locador e Locatário.
    - **Vigência**: Data de início e fim.

    #### Etapa 2: Cálculo da Base de Cálculo Anual
    Base de Cálculo Anual = Valor Aluguel Mensal × 12

    #### Etapa 3: Consulta da Tabela de Custas de Registro
    Use a Base de Cálculo Anual na tabela abaixo:

    | Faixa de Valor da Base de Cálculo (R$) | Taxa a Pagar (R$) |
    |:---|:---|
    | Até 3.200,00 | 319,12 |
    | De 3.200,01 a 8.000,00 | 483,68 |
    | De 8.000,01 a 12.000,00 | 522,76 |
    | De 12.000,01 a 16.000,00 | 562,54 |
    | De 16.000,01 a 24.000,00 | 642,22 |
    | De 24.000,01 a 32.000,00 | 723,98 |
    | De 32.000,01 a 47.000,00 | 799,68 |
    | De 47.000,01 a 63.000,00 | 881,24 |
    | De 63.000,01 a 78.000,00 | 967,68 |
    | De 78.000,01 a 118.000,00 | 1.030,66 |
    | De 118.000,01 a 160.000,00 | 1.115,10 |
    | De 160.000,01 a 235.000,00 | 1.805,16 |
    | De 235.000,01 a 350.000,00 | 2.708,06 |
    | De 350.000,01 a 530.000,00 | 4.067,28 |
    | De 530.000,01 a 800.000,00 | 6.099,38 |
    | De 800.000,01 a 1.200.000,00 | 9.147,62 |
    | De 1.200.000,01 a 4.000.000,00| 18.551,68|
    | Acima de 4.000.000,01 | 24.117,28 |

    ### Formato de Retorno (JSON Puro)
    Retorne APENAS o JSON:
    ```json
    {
      "status": "CATEGORIA_ASSINATURA",
      "data_evidencia": "DD/MM/AAAA ou null (Data do selo ou assinatura)",
      "descricao_prova": "Trecho do texto que comprova a assinatura",
      "locador": "Nome completo",
      "locatario": "Nome completo",
      "data_inicio_contrato": "DD/MM/AAAA",
      "data_fim_contrato": "DD/MM/AAAA",
      "moeda": "BRL",
      "valor_aluguel_mensal_float": 0.00,
      "base_calculo_12_meses_float": 0.00,
      "custo_registro_cartorio_float": 0.00,
      "memoria_calculo": "Detalhamento: Aluguel [valor] × 12 = [base] → Faixa [intervalo] → Taxa [custo]"
    }
    ```
    """
    
    # Monta a mensagem com o texto extraído
    conteudo_msg = f"Analise o seguinte contrato (Texto Extraído):\n\n--- INICIO DO DOCUMENTO ---\n{texto_markdown}\n--- FIM DO DOCUMENTO ---"

    for tentativa in range(3):
        try:
            response = CLIENTE_API.chat.completions.create(
                model=MODELO_IA,
                messages=[
                    {"role": "system", "content": prompt_system},
                    {"role": "user", "content": conteudo_msg}
                ],
                temperature=0.0,
                max_tokens=1500
            )
            
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
                
        except Exception as e:
            logging.warning(f"Erro API (Tentativa {tentativa+1}): {e}")
            time.sleep(2)
            
    return None

def executar_extracao():
    if not os.path.exists(DIR_ENTRADA):
        print(f" Diretório de entrada não encontrado: {DIR_ENTRADA}")
        print("   -> Verifique a variável PASTA_ENTRADA no arquivo .env")
        return

    arquivos = [f for f in os.listdir(DIR_ENTRADA) if f.lower().endswith('.pdf')]
    logging.info(f" INICIANDO EXTRAÇÃO VIA LLAMAPARSE: {len(arquivos)} arquivos")
    print(f" Iniciando processamento de {len(arquivos)} arquivos (LlamaParse)...")
    print(f" Lendo de: {DIR_ENTRADA}")
    print(f" Salvando em: {DIR_SAIDA_BRUTA}")

    for i, arquivo in enumerate(arquivos):
        nome_safe = os.path.splitext(arquivo)[0]
        caminho_salvamento = os.path.join(DIR_SAIDA_BRUTA, f"{nome_safe}_RAW.json")

        if os.path.exists(caminho_salvamento):
            logging.info(f" Pulando: {arquivo}")
            print(f" [{i+1}/{len(arquivos)}] Pulando (Já existe): {arquivo}")
            continue

        logging.info(f"[{i+1}/{len(arquivos)}] Processando: {arquivo}")
        print(f" [{i+1}/{len(arquivos)}] Lendo PDF com LlamaParse: {arquivo}...")
        
        caminho_pdf = os.path.join(DIR_ENTRADA, arquivo)
        
        # 1. Extrai Texto (LlamaParse)
        texto_extraido = extrair_texto_llama(caminho_pdf)
        
        if not texto_extraido:
            logging.error(f"   Falha na extração de texto: {arquivo}")
            continue

        # 2. Analisa Texto (Claude)
        print("    Enviando texto para IA analisar...")
        resposta_raw = consultar_claude_raw(texto_extraido, arquivo)

        if resposta_raw:
            pacote_dados = {
                "arquivo_origem": arquivo,
                "metodo_extracao": "LlamaParse",
                "timestamp": datetime.now().isoformat(),
                "resposta_ia_raw": resposta_raw
            }
            
            with open(caminho_salvamento, 'w', encoding='utf-8') as f:
                json.dump(pacote_dados, f, indent=4, ensure_ascii=False)
            
            logging.info(f"    Sucesso: {caminho_salvamento}")
            print("    Salvo!")
        else:
            logging.error(f"    Falha na API IA: {arquivo}")
            print(f"    Erro na API para: {arquivo}")

if __name__ == "__main__":
    executar_extracao()