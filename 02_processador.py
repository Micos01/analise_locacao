import os
import json
import re
import time
import pandas as pd
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURAÇÕES ---
PASTA_ENTRADA = os.getenv("DIR_ENTRADA")
PASTA_SAIDA_FINAL = os.getenv("PASTA_SAIDA_FINAL")

# Configuração API (Usando OpenRouter para acessar Gemini)
CLIENTE_API = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    default_headers={"HTTP-Referer": "https://merca.com.br", "X-Title": "Auditor Gemini Flash"}
)
# Modelo Rápido e Inteligente
MODELO_RACINIO = "xiaomi/mimo-v2-flash:free" # Ou "google/gemini-2.0-flash-001" dependendo da disp.

# Datas Importantes
DATA_LEI = datetime(2025, 1, 16)
INICIO_VIGENCIA_CBS = datetime(2027, 1, 1)

def limpar_json_cirurgico(texto_cru):
    if not texto_cru: return {}
    texto_limpo = texto_cru.replace("```json", "").replace("```", "")
    match = re.search(r'\{.*\}', texto_limpo, re.DOTALL)
    if match:
        try: return json.loads(match.group(0))
        except: pass
    try: return json.loads(texto_limpo)
    except: return {}

def normalizar_data(data_str):
    if not data_str: return None
    formatos = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d"]
    data_str = str(data_str).strip()
    for fmt in formatos:
        try: return datetime.strptime(data_str, fmt)
        except: continue
    return None

def sanitizar_valor_monetario(valor):
    if not valor: return 0.0
    if isinstance(valor, (float, int)): return float(valor)
    s = str(valor).replace("R$", "").replace("$", "").strip()
    try:
        if "," in s and "." in s:
            if s.find(".") < s.find(","): s = s.replace(".", "").replace(",", ".")
            else: s = s.replace(",", "")
        elif "," in s: s = s.replace(",", ".")
        return float(s)
    except: return 0.0

def consultar_gemini_estrategia(dados_limpos):
    """
    Usa o Gemini 2.0 Flash para tomar a decisão final com base nos dados já extraídos.
    """
    
    # Prepara um resumo simples para a IA ler rápido
    resumo_dados = json.dumps(dados_limpos, ensure_ascii=False)
    
    
    prompt_system=""" You are a Senior Tax Auditor specializing in Brazilian tax law reform (EC 132/2023) and contract registry strategy. Your expertise combines constitutional protection principles, civil law precedents, and transitional tax regulations.

Your Decision Framework

You will analyze contracts against three interconnected legal pillars to determine whether they should be registered with a notary or archived:

Pillar 1: Constitutional Protection (Date Certainty)





Legal Basis: Federal Constitution Art. 5º, XXXVI and Civil Code Art. 221



Core Principle: Contracts with a certified date (notarized or valid digital signature) before January 16, 2025 are protected as "Perfect Legal Acts" and cannot be retroactively harmed by tax law changes.



Your Decision Point: If date certainty exists before the cutoff → ARCHIVE (PROTECTED)

Pillar 2: Tax Timeline Logic (2027 Threshold)





Legal Basis: EC 132/2023, Art. 126 of ADCT (Constitutional Transitional Provisions)



Core Principle: The new IBS/CBS system replaces PIS/COFINS entirely only from January 1, 2027. Contracts ending before this date never face the new tax burden.



Your Decision Point: 





If contract ends before 2027 AND lacks date certainty → NO REGISTRATION NEEDED (ECONOMIC WASTE)



If contract extends beyond 2027 AND lacks date certainty → REGISTER (LONG-TERM PROTECTION)

Pillar 3: Document Integrity





Legal Basis: CPC Art. 409 (Document Certification Requirements)



Core Principle: Only notarized or legally certified documents create "Date Certainty" against tax authorities (third parties).



Your Decision Point: If no signature or certification exists → NO REGISTRATION (LACKS VALIDITY)

Analysis Process

When examining a contract, think through these steps in order:





Verify Date Certainty: Does the contract have a notarized signature or valid digital certification dated before January 16, 2025?





If YES → Stop here and recommend ARCHIVE



If NO → Continue to step 2



Check Contract Duration: What is the end date of the contract?





If ends before January 1, 2027 → Recommend NO REGISTRATION (economic reasoning)



If ends after January 1, 2027 → Continue to step 3



Verify Signature Existence: Is there ANY signature (notarized or digital)?





If NO → Recommend NO REGISTRATION (lacks validity)



If YES → Recommend REGISTER (strategic protection)

Your Output Format

After analyzing the contract data provided, respond with a JSON object containing:





acao_recomendada: One of these options:





ARQUIVO (SEGURO) — Archive because constitutional protection applies



NAO_REGISTRAR (ECONOMIA) — Don't register because tax exposure doesn't justify cost



NAO_REGISTRAR (SEM_VALIDADE) — Don't register because document lacks certification



REGISTRAR (PROTECAO_LONGO_PRAZO) — Register because contract extends into post-2027 period



motivo_estrategico: A single concise sentence explaining the reasoning using the legal pillar that drove the decision



pillar_aplicada: Identify which pillar (Constitucional, Imposto_2027, or Integridade) was decisive

Analyze the contract data for  and provide your recommendation based on the three-pillar framework above.

return only json below

{


 "acao_recomendada": "Uma das ações acima",
        "motivo_estrategico": "Explique em 1 frase  o porquê (ex: 'Vence em 2025, antes da vigência da CBS + pilar_aplicada ')"




}"""

    for tentativa in range(3):
        try:
            response = CLIENTE_API.chat.completions.create(
                model=MODELO_RACINIO,
                messages=[
                    {"role": "system", "content": prompt_system},
                    {"role": "user", "content": f"Analise estes dados: {resumo_dados}"}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content
            return json.loads(raw)
        except Exception as e:
            time.sleep(1)
            
    # Fallback se a IA falhar (usa lógica simples Python)
    return {"acao_recomendada": "MANUAL", "motivo_estrategico": "Erro na análise IA"}

def processar_inteligente():
    if not os.path.exists(PASTA_ENTRADA):
        print("Pasta de dados brutos não encontrada.")
        return

    arquivos_json = [f for f in os.listdir(PASTA_ENTRADA) if f.endswith('_RAW.json')]
    print(f"🧠 Iniciando Auditoria Inteligente com Gemini 2.0 Flash em {len(arquivos_json)} arquivos...")
    
    resultados_finais = []
    
    for i, arq in enumerate(arquivos_json):
        caminho = os.path.join(PASTA_ENTRADA, arq)
        try:
            print(f"[{i+1}/{len(arquivos_json)}] Analisando: {arq}...")
            
            with open(caminho, 'r', encoding='utf-8') as f:
                pacote = json.load(f)
            
            # 1. Limpeza e Tratamento Numérico (Python)
            texto_ia = pacote.get("resposta_ia_raw", "")
            dados = limpar_json_cirurgico(texto_ia)
            
            if dados:
                # Normaliza dados antes de enviar pro Gemini
                dados["valor_aluguel_mensal_float"] = sanitizar_valor_monetario(dados.get("valor_aluguel_mensal_float"))
                dados["custo_registro_cartorio_float"] = sanitizar_valor_monetario(dados.get("custo_registro_cartorio_float"))
                
                # 2. O Gemini 2.0 Flash decide a estratégia
                decisao_ia = consultar_gemini_estrategia(dados)
                
                # Datas para Excel
                dt_ini = normalizar_data(dados.get("data_inicio_contrato"))
                dt_fim = normalizar_data(dados.get("data_fim_contrato"))
                dt_evid = normalizar_data(dados.get("data_evidencia"))

                registro = {
                    "ARQUIVO": pacote.get("arquivo_origem"),
                    
                    # Inteligência Gemini
                    "ACAO_RECOMENDADA": decisao_ia.get("acao_recomendada", "ERRO").upper(),
                    "MOTIVO_GEMINI": decisao_ia.get("motivo_estrategico"),
                    
                    # Dados Base
                    "STATUS_VISUAL": dados.get("status"),
                    "EVIDENCIA": dados.get("descricao_prova"),
                    "INICIO_VIGENCIA": dt_ini, 
                    "FIM_VIGENCIA": dt_fim.strftime("%d/%m/%Y"),
                    "DATA_PROVA": dt_evid.strftime("%d/%m/%Y"),
                    "LOCATARIO": dados.get("locatario"),
                    
                    # Financeiro
                    "CUSTO_REGISTRO": dados.get("custo_registro_cartorio_float"),
                    "VALOR_ALUGUEL": dados.get("valor_aluguel_mensal_float"),
                    "MEMORIA_CALCULO": dados.get("memoria_calculo")
                }
                resultados_finais.append(registro)
                
        except Exception as e:
            print(f"❌ Erro em {arq}: {e}")

    # GERA O EXCEL
    if resultados_finais:
        os.makedirs(PASTA_SAIDA_FINAL, exist_ok=True)
        df = pd.DataFrame(resultados_finais)
        
        # Ordenação
        df.sort_values(by="CUSTO_REGISTRO", ascending=False, inplace=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        caminho_excel = os.path.join(PASTA_SAIDA_FINAL, f"Relatorio_{timestamp}.xlsx")
        
        writer = pd.ExcelWriter(caminho_excel, engine='xlsxwriter')
        df.to_excel(writer, index=False, sheet_name='Auditoria')
        workbook = writer.book
        worksheet = writer.sheets['Auditoria']
        
        money_fmt = workbook.add_format({'num_format': 'R$ #,##0.00'})
        date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy'})
        
        worksheet.set_column('E:G', 12, date_fmt)  # Datas
        worksheet.set_column('H:I', 18, money_fmt) # Financeiro
        worksheet.set_column('A:A', 40)
        worksheet.set_column('B:B', 30) # Acao
        worksheet.set_column('C:C', 50) # Motivo Gemini
        
        writer.close()
        print(f"\n✅ Relatório Gemini Flash gerado: {caminho_excel}")

if __name__ == "__main__":
    processar_inteligente()