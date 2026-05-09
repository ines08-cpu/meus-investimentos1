import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Gestão de Património Inês", layout="wide")
st.title("📊 Dashboard de Investimentos Consolidado")

def clean_val(val):
    if pd.isna(val) or str(val).strip() == '': return 0.0
    s = str(val).replace('€', '').replace('$', '').replace('USD', '').replace('EUR', '').strip()
    if ',' in s and '.' in s: s = s.replace('.', '')
    s = s.replace(',', '.')
    s = re.sub(r'[^-0-9.]', '', s)
    try: return float(s)
    except: return 0.0

def extrair_ticker(texto):
    """Procura padrões como AAPL.US, VWCE.DE ou Tickers de 3-5 letras no comentário."""
    texto = str(texto).upper()
    # Tenta encontrar algo como XXXX.XX (Ticker com sufixo de bolsa)
    match = re.search(r'\b[A-Z0-9]{2,10}\.[A-Z]{2,}\b', texto)
    if match:
        return match.group(0)
    # Se não encontrar, tenta palavras que não sejam comandos da XTB
    for word in texto.split():
        if word not in ['OPEN', 'BUY', 'CLOSE', 'SELL', 'MARKET', 'ORD', 'ID', '@'] and word.isalpha() and len(word) >= 2:
            return word
    return "Ativo Indeterminado"

def process_data(uploaded_files):
    all_assets_list = []
    xtb_manual_data = {}
    xtb_investimento_real = {}
    metrics = {'dividendos': 0.0, 'juros': 0.0, 'depositos': 0.0}
    
    for file in uploaded_files:
        name = file.name.lower()
        try:
            df = pd.read_csv(io.StringIO(file.getvalue().decode('utf-8')), sep=None, engine='python')
            df.columns = [str(c).strip().lower() for c in df.columns]
            
            # --- 1. REFERÊNCIA DOS EXCEL (Para Categorias e Tickers conhecidos) ---
            if any(x in name for x in ["setorial", "usd", "ações"]):
                t_col = next((c for c in df.columns if 'ticker' in c or 'unnamed' in c), None)
                v_col = next((c for c in df.columns if 'investido' in c or 'euros' in c or 'valor' in c), None)
                if t_col and v_col:
                    cat = 'ETF' if 'setorial' in name else 'Ação'
                    for _, row in df.dropna(subset=[t_col]).iterrows():
                        ticker = str(row[t_col]).strip().upper()
                        if ticker not in ['TICKER', 'TOTAL', 'SOMA', 'NAN']:
                            xtb_manual_data[ticker] = {'Cat': cat, 'Valor': clean_val(row[v_col])}

            # --- 2. XTB CASH OPERATIONS (A Realidade dos Fluxos) ---
            elif "cash" in name or "operations" in name:
                # Identifica colunas Type, Amount e Comment
                type_col = next((c for c in df.columns if 'type' in c or 'tipo' in c), 'type')
                val_col = next((c for c in df.columns if 'amount' in c or 'montante' in c), 'amount')
                com_col = next((c for c in df.columns if 'comment' in c or 'comentário' in c), 'comment')

                for _, row in df.iterrows():
                    tipo = str(row.get(type_col, '')).lower()
                    valor = clean_val(row.get(val_col, 0))
                    comentario = str(row.get(com_col, ''))

                    # Depósitos e Levantamentos
                    if 'deposit' in tipo or 'transfer' in tipo: metrics['depositos'] += abs(valor)
                    if 'withdrawal' in tipo: metrics['depositos'] -= abs(valor)
                    
                    # Rendimentos
                    if 'dividend' in tipo: metrics['dividendos'] += valor
                    if 'interest' in tipo: metrics['juros'] += valor
                    
                    # Investimento em Ativos (Compras/Vendas)
                    if any(x in tipo for x in ['purchase', 'open', 'buy', 'sell', 'close']):
                        ticker = extrair_ticker(comentario)
                        if ticker != "Ativo Indeterminado":
                            if ticker not in xtb_investimento_real: xtb_investimento_real[ticker] = 0.0
                            # Nas compras o 'amount' é negativo, queremos o valor positivo investido
                            xtb_investimento_real[ticker] += (-valor)

            # --- 3. FREEDOM24 (Ações Oferta e Numerário) ---
            elif "sheet" in name or "transacções" in name or "numerário" in name:
                if 'ticker' in df.columns: # Posições
                    for _, row in df.iterrows():
                        all_assets_list.append({'Ativo': row['ticker'], 'Cat': 'Ação (Oferta)', 'Valor': clean_val(row.get('valor', 0)), 'Fonte': 'Freedom24'})
                elif 'transação' in df.columns: # Rendimentos
                    for _, row in df.iterrows():
                        desc = str(row['transação'])
                        valor = clean_val(row['montante'])
                        cambio = 0.92 if str(row.get('moeda', '')).upper() == 'USD' else 1.0
                        if any(x in desc for x in ["Dividendos", "Operações societárias", "Taxas do agente"]):
                            metrics['dividendos'] += (valor * cambio)
                        if 'Transferência bancária' in desc:
                            metrics['depositos'] += abs(valor * cambio)

            # --- 4. OFFLINE (Aforro/PPR) ---
            elif "offline" in name:
                if 'aplicado' in df.columns:
                    temp = df[df['estado'].astype(str).str.contains('aberto', na=False, case=False)]
                    for _, row in temp.iterrows():
                        all_assets_list.append({'Ativo': row['descrição'], 'Cat': row.get('ativo', 'PPR/Outros'), 'Valor': clean_val(row['aplicado']), 'Fonte': 'Offline'})

        except: continue

    # Consolidação Final XTB
    for ticker, val_investido in xtb_investimento_real.items():
        if val_investido > 1.0: # Filtra resíduos de cêntimos
            # Tenta encontrar nos dados manuais para herdar a categoria
            match = next((k for k in xtb_manual_data.keys() if k in ticker or ticker in k), None)
            if match:
                cat = xtb_manual_data[match]['Cat']
                valor = max(xtb_manual_data[match]['Valor'], val_investido)
                del xtb_manual_data[match]
            else:
                # Classificação inteligente automática
                cat = "ETF" if any(x in ticker for x in ["UCITS", "ETF", "VWCE", "EUNL", "LYX"]) else "Ação"
                valor = val_investido
            all_assets_list.append({'Ativo': ticker, 'Cat': cat, 'Valor': valor, 'Fonte': 'XTB'})

    # Adiciona o que sobrou dos Excels
    for ticker, info in xtb_manual_data.items():
        all_assets_list.append({'Ativo': ticker, 'Cat': info['Cat'], 'Valor': info['Valor'], 'Fonte': 'XTB'})

    return pd.DataFrame(all_assets_list), metrics

# --- UI ---
uploaded = st.sidebar.file_uploader("Carrega todos os ficheiros CSV", accept_multiple_files=True)

if uploaded:
    df_res, m = process_data(uploaded)
    if not df_res.empty:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Património Total", f"€ {df_res['Valor'].sum():,.2f}")
        c2.metric("Investimento Líquido", f"€ {m['depositos']:,.2f}")
        c3.metric("Dividendos Net", f"€ {m['dividendos']:,.2f}")
        c4.metric("Juros Líquidos", f"€ {m['juros']:,.2f}")
        
        st.divider()
        col_a, col_b = st.columns([1, 2])
        with col_a:
            fig = px.pie(df_res, values='Valor', names='Cat', hole=0.4, title="Alocação por Classe")
            st.plotly_chart(fig, use_container_width=True)
        with col_b:
            st.subheader("Detalhamento dos Ativos")
            st.dataframe(df_res.sort_values('Valor', ascending=False), use_container_width=True, hide_index=True)
            
        ganho = (df_res['Valor'].sum() - m['depositos']) + m['dividendos'] + m['juros']
        st.success(f"**Rentabilidade Total Estimada: € {ganho:,.2f}**")
