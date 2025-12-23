import os
import json
import base64
import time
import logging
import fitz  
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURAÇÕES ---
DIR_ENTRADA = r"MVP\para_mvp"
DIR_SAIDA_BRUTA = r"MVP\para_mvp\dados_brutos_ia"
DIR_LOGS = r"outputs\logs"

# Configuração da API
CLIENTE_API = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    default_headers={"HTTP-Referer": "https://merca.com.br", "X-Title": "Auditor Contratos (Pedro)"}
)
MODELO_IA = "anthropic/claude-3.5-sonnet"

# Configuração de Logs e Pastas
os.makedirs(DIR_SAIDA_BRUTA, exist_ok=True)
os.makedirs(DIR_LOGS, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(DIR_LOGS, f"extracao_{datetime.now().strftime('%Y%m%d')}.log"),
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

def converter_pdf_para_vision(caminho_pdf):
    """Converte páginas do PDF em imagens Base64 para envio à IA."""
    imagens_b64 = []
    try:
        doc = fitz.open(caminho_pdf)
        total_pags = len(doc)
        
        # Estratégia de Economia: 2 primeiras (valores/prazo) + 3 últimas (assinaturas)
        if total_pags > 6:
            indices = list(range(3)) + list(range(total_pags - 2, total_pags))
        else:
            indices = range(total_pags)

        for i in indices:
            pagina = doc.load_page(i)
            # Zoom 2.0x essencial para ler números pequenos e tabelas
            pix = pagina.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            img_bytes = pix.tobytes("jpeg")
            b64_str = base64.b64encode(img_bytes).decode('utf-8')
            imagens_b64.append(f"data:image/jpeg;base64,{b64_str}")
            
        return imagens_b64
    except Exception as e:
        logging.error(f"Erro PDF {caminho_pdf}: {e}")
        return []

def consultar_claude_raw(imagens_b64, nome_arquivo):
    """Envia imagens para o Claude com o Prompt de Perito Calculista."""
    
    # --- PROMPT MANTIDO EXATAMENTE COMO SOLICITADO ---
    prompt_system = """
    Você é um perito forense e calculista judicial especializado em contratos de locação. Sua missão é validar contratos de aluguel e calcular as custas de registro em cartório com base no valor mensal do contrato.

### Seu Processo de Análise

#### Etapa 1: Extração de Dados do Contrato

Analise o documento fornecido e extraia as seguintes informações:

- **Valor do Aluguel Mensal**: Localize "Valor do Aluguel" ou "Aluguel Mensal" no contrato. Ignore completamente taxas de condomínio, IPTU ou outras despesas — foque apenas no aluguel puro.
- **Status de Assinatura**: Classifique como:
  - DIGITAL (GOV/ICP): Se houver logos Gov.br, DocuSign, ou certificação ICP-Brasil
  - FÍSICA (COM FIRMA): Se houver selos ou carimbos de cartório
  - FÍSICA (SEM FIRMA): Se houver apenas assinaturas à caneta
  - NÃO ASSINADO: Se o documento estiver em branco ou sem assinatura
- **Partes do Contrato**: Identifique o nome completo do locador e do locatário
- **Vigência**: Extraia a data de início e data de término do contrato

#### Etapa 2: Cálculo da Base de Cálculo Anual

Para fins de registro em cartório, a base de cálculo segue a regra de 12 meses:

Base de Cálculo Anual = Valor Aluguel Mensal × 12

#### Etapa 3: Consulta da Tabela de Custas de Registro

Use a Base de Cálculo Anual obtida na Etapa 2 e consulte a tabela abaixo para identificar a faixa correspondente e a taxa exata a pagar:

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
| de 530.000,01 a 800.000,00 | 6.099,38 |
| de 800.000,01 a 1.200.000,00  | 9.147,62 |
| de 1.200.000,01 a 4.000.000,00| 18.551,68|
|apartir de 4.000.000,01 | 24.117,28 |

### Formato de Retorno

Retorne APENAS o seguinte JSON (sem formatação markdown, sem explicações adicionais):

```json
{
  "status": "CATEGORIA_ASSINATURA",
  "data_evidencia": "DD/MM/AAAA ou null",
  "descricao_prova": "Descrição do que foi observado no documento",
  "locador": "Nome completo do locador",
  "locatario": "Nome completo do locatário",
  "data_inicio_contrato": "DD/MM/AAAA",
  "data_fim_contrato": "DD/MM/AAAA",
  "moeda": "BRL",
  "valor_aluguel_mensal_float": 0.00,
  "base_calculo_12_meses_float": 0.00,
  "custo_registro_cartorio_float": 0.00,
  "memoria_calculo": "Detalhamento: Aluguel [valor] × 12 = [base] → Faixa [intervalo] → Taxa [custo]"
}
```

### Informações a Processar

Proceda com a análise completa seguindo as três etapas acima e retorne apenas o JSON solicitado.
    """
    
    conteudo_msg = [{"type": "text", "text": f"Analise o contrato: {nome_arquivo}"}]
    for img in imagens_b64:
        conteudo_msg.append({"type": "image_url", "image_url": {"url": img}})

    for tentativa in range(3):
        try:
            response = CLIENTE_API.chat.completions.create(
                model=MODELO_IA,
                messages=[
                    {"role": "system", "content": prompt_system},
                    {"role": "user", "content": conteudo_msg}
                ],
                temperature=0.0,
                max_tokens=1000
            )
            
            # Retorna o conteúdo cru (Raw) para ser salvo no Data Lake
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
                
        except Exception as e:
            logging.warning(f"Erro API (Tentativa {tentativa+1}): {e}")
            time.sleep(2)
            
    return None

def executar_extracao():
    """Função principal que orquestra a leitura e envio."""
    if not os.path.exists(DIR_ENTRADA):
        print(f"❌ Diretório não encontrado: {DIR_ENTRADA}")
        return

    arquivos = [f for f in os.listdir(DIR_ENTRADA) if f.lower().endswith('.pdf')]
    logging.info(f"🚀 INICIANDO EXTRAÇÃO DE CUSTOS: {len(arquivos)} arquivos")
    print(f"🚀 Iniciando processamento de {len(arquivos)} arquivos...")

    for i, arquivo in enumerate(arquivos):
        nome_safe = os.path.splitext(arquivo)[0]
        caminho_salvamento = os.path.join(DIR_SAIDA_BRUTA, f"{nome_safe}_RAW.json")

        # Pula se já existe (Economia de API)
        if os.path.exists(caminho_salvamento):
            logging.info(f"⏩ Pulando: {arquivo}")
            print(f"⏩ [{i+1}/{len(arquivos)}] Pulando (Já existe): {arquivo}")
            continue

        logging.info(f"[{i+1}/{len(arquivos)}] Processando: {arquivo}")
        print(f"🔄 [{i+1}/{len(arquivos)}] Processando: {arquivo}...")
        
        imagens = converter_pdf_para_vision(os.path.join(DIR_ENTRADA, arquivo))
        if not imagens:
            logging.error(f"   ❌ Falha ao converter imagens: {arquivo}")
            continue

        resposta_raw = consultar_claude_raw(imagens, arquivo)

        if resposta_raw:
            pacote_dados = {
                "arquivo_origem": arquivo,
                "timestamp": datetime.now().isoformat(),
                "resposta_ia_raw": resposta_raw  # O texto exato que o Claude mandou
            }
            
            with open(caminho_salvamento, 'w', encoding='utf-8') as f:
                json.dump(pacote_dados, f, indent=4, ensure_ascii=False)
            
            logging.info(f"   💰 Custos calculados e salvos: {caminho_salvamento}")
            print(f"   ✅ Sucesso! Salvo em: {caminho_salvamento}")
        else:
            logging.error(f"   ❌ Falha na API: {arquivo}")
            print(f"   ❌ Erro na API para: {arquivo}")

if __name__ == "__main__":
    executar_extracao()