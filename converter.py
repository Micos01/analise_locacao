import os
import json
import re  # Importante para a correção de datas
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from llama_parse import LlamaParse
from openai import OpenAI

# Carrega variáveis de ambiente
load_dotenv()

# --- CONFIGURAÇÕES ---
PASTA_ENTRADA = os.getenv("PASTA_ENTRADA")
PASTA_SAIDA_JSON = os.getenv("PASTA_SAIDA_JSON")
PASTA_SAIDA_FINAL = os.getenv("PASTA_SAIDA_FINAL")


client = OpenAI(
    base_url="https://openrouter.ai/api/v1", 
    api_key=os.getenv("OPENROUTER_API_KEY")
)

def estruturar_dados_forense(texto_markdown, nome_arquivo):
    """
    Usa GPT-4o com Prompt Ajustado para detectar Gov.br e Selos Físicos.
    """
    
    prompt_system = """
    Você é um PERITO FORENSE DOCUMENTAL. Sua missão é validar assinaturas para a Lei Complementar 214/2025.
    
    ### SUAS REGRAS DE OURO:
    1. **CAÇA AO TESOURO DIGITAL**: Procure ativamente nas páginas finais por logotipos ou textos como "gov.br", "Documento assinado digitalmente", "Verifique em", "DocuSign", "ICP-Brasil". Se encontrar isso, É ASSINATURA VÁLIDA.
    2. **DATA É TUDO**: Se vir um selo de cartório ou um carimbo de tempo digital, EXTRAIA A DATA exata (DD/MM/AAAA).
    3. **CLASSIFICAÇÃO**:
       - **DIGITAL (GOV/ICP)**: Tem manifesto Gov.br, DocuSign ou similar. (Seguro se data <= 16/01/2025).
       - **FÍSICA (COM FIRMA)**: Tem carimbo/selo de cartório reconhecendo a firma.
       - **FÍSICA (SEM FIRMA)**: Assinatura à caneta SEM selo de cartório. (Risco).
       - **NÃO ASSINADO**: Apenas linhas em branco ou nomes digitados sem marca de validação.

    ### SAÍDA JSON OBRIGATÓRIA:
    {
        "locador": "Nome ou null",
        "locatario": "Nome ou null",
        "status_assinatura": "DIGITAL (GOV/ICP) | FÍSICA (COM FIRMA) | FÍSICA (SEM FIRMA) | NÃO ASSINADO",
        "evidencia_encontrada": "Cite o texto exato que prova a assinatura. Ex: 'Manifesto Gov.br na pág 10 datado de 15/07/2024'",
        "data_comprovada_str": "DD/MM/AAAA" (A data do selo ou do manifesto digital. Se não achar, null),
        "data_contrato_escrita": "DD/MM/AAAA" (Data digitada no cabeçalho/rodapé do contrato)
    }
    """

    # Aumentado para 90k caracteres para pegar páginas finais de contratos longos
    prompt_user = f"""
    Analise este documento: {nome_arquivo}
    
    --- INÍCIO DO CONTEÚDO ---
    {texto_markdown[:90000]} 
    --- FIM DO CONTEÚDO ---
    """

    try:
        response = client.chat.completions.create(
            model="anthropic/claude-3.5-sonnet", 
            messages=[
                {"role": "system", "content": prompt_system},
                {"role": "user", "content": prompt_user}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"❌ Erro na estruturação LLM: {e}")
        return None

def calcular_decisao_final(dados):
    """
    Lógica Híbrida: Usa Python + Regex para corrigir falhas da IA.
    """
    status = dados.get("status_assinatura", "NÃO ASSINADO")
    data_prova_str = dados.get("data_comprovada_str")
    evidencia = dados.get("evidencia_encontrada", "")
    
    # --- CORREÇÃO AUTOMÁTICA DE DATAS (REGEX) ---
    # Se a IA achou a evidência mas esqueceu de preencher a data, o Python extrai.
    if not data_prova_str and evidencia:
        # Procura padrões DD/MM/AAAA ou DD-MM-AAAA na evidência
        match = re.search(r"(\d{2}[/-]\d{2}[/-]\d{4})", evidencia)
        if match:
            data_prova_str = match.group(1).replace("-", "/")
            dados["data_comprovada_str"] = data_prova_str # Atualiza o JSON
            dados["nota_autocorrecao"] = "Data extraída via Regex da evidência."

    # Data de corte da LCP 214
    DATA_LEI = datetime(2025, 1, 16)
    
    acao = "MANUAL"
    motivo = ""

    # 1. Falta de Assinatura
    if status == "NÃO ASSINADO":
        return "🚨 ALERTA: NÃO ASSINADO", "Sem evidência de assinatura válida."

    # 2. Conversão da data
    data_prova = None
    if data_prova_str:
        try:
            data_prova = datetime.strptime(data_prova_str, "%d/%m/%Y")
        except:
            motivo = f"Data '{data_prova_str}' ilegível."

    # 3. Árvore de Decisão
    if "DIGITAL" in status or "COM FIRMA" in status:
        if data_prova:
            if data_prova <= DATA_LEI:
                acao = "✅ ARQUIVAR (SEGURO)"
                motivo = f"Data Certa {data_prova_str} confirmada (Anterior à Lei)."
            else:
                acao = "⚠️ ATENÇÃO (POSTERIOR)"
                motivo = f"Válido, mas data {data_prova_str} é posterior à Lei."
        else:
            # Se mesmo com Regex não achou data, mas é Digital/Firma
            acao = "⚠️ VERIFICAR MANUALMENTE"
            motivo = "Assinatura válida detectada, mas data ilegível."

    elif "SEM FIRMA" in status:
        acao = "🔥 REGISTRAR IMEDIATAMENTE (RTD)"
        motivo = "Assinatura física sem reconhecimento de firma (Risco Jurídico)."

    else:
        acao = "❓ REVISAR"
        motivo = f"Status desconhecido: {status}"

    return acao, motivo

def processar_arquivos():
    if not os.path.exists(PASTA_ENTRADA):
        print("Pasta de entrada não encontrada.")
        return

    arquivos = [f for f in os.listdir(PASTA_ENTRADA) if f.lower().endswith(('.pdf', '.docx'))]
    print(f"📂 Iniciando auditoria forense V3 em {len(arquivos)} arquivos...")

    # Instrução reforçada para o LlamaParse pegar páginas de assinatura
    parser = LlamaParse(
        api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
        result_type="markdown",
        verbose=True,
        parsing_instruction="EXTRAIR TODO O TEXTO. Importante: Incluir conteúdo de carimbos, rodapés, cabeçalhos e TODAS as páginas finais com manifestos de assinatura digital (Gov.br/DocuSign)."
    )

    lista_final = []
    os.makedirs(PASTA_SAIDA_JSON, exist_ok=True)

    for arq in arquivos:
        print(f"🔎 Periciando: {arq}...")
        try:
            docs = parser.load_data(os.path.join(PASTA_ENTRADA, arq))
            texto = "\n".join([d.text for d in docs])
            
            dados = estruturar_dados_forense(texto, arq)
            
            if dados:
                acao, motivo = calcular_decisao_final(dados)
                
                dados["DECISAO_FINAL"] = acao
                dados["MOTIVO_DECISAO"] = motivo
                dados["arquivo_origem"] = arq
                
                with open(os.path.join(PASTA_SAIDA_JSON, f"{arq}.json"), "w", encoding="utf-8") as f:
                    json.dump(dados, f, indent=4, ensure_ascii=False)
                
                lista_final.append(dados)
                print(f"   -> {acao} | Data: {dados.get('data_comprovada_str')}")
            
        except Exception as e:
            print(f"   ❌ Erro: {e}")

    if lista_final:
        df = pd.DataFrame(lista_final)
        # Ordenação inteligente das colunas
        cols = ["arquivo_origem", "DECISAO_FINAL", "status_assinatura", "data_comprovada_str", "MOTIVO_DECISAO", "evidencia_encontrada", "locador", "locatario"]
        df = df[[c for c in cols if c in df.columns]]
        
        path_excel = os.path.join(PASTA_SAIDA_FINAL, "Relatorio_Forense_Final.xlsx")
        os.makedirs(PASTA_SAIDA_FINAL, exist_ok=True)
        df.to_excel(path_excel, index=False)
        print(f"\n✅ Relatório Final gerado: {path_excel}")

if __name__ == "__main__":
    processar_arquivos()