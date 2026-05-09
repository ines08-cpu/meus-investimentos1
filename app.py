import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Dashboard Inês 2026", layout="wide")

# --- DICIONÁRIO DE INTELIGÊNCIA SETORIAL ---
# Adiciona aqui novos tickers conforme precises
MAP_SETORES = {
    'SXR8': 'ETF - USA', 'VUAA': 'ETF - USA', 'VUSA': 'ETF - USA',
    'VWCE': 'ETF - Global', 'IWDA': 'ETF - Global', 'EUNA': 'ETF - Bonds',
    'SXRV': 'ETF - Tecnologia', '2B76': 'ETF - Automação', 'GOAI': 'ETF - IA', 
    'NUKL': 'ETF - Urânio', 'BTCE': 'Cripto - Bitcoin',
    '4GLD': 'Commodities - Ouro', 'EGLN': 'Commodities - Prata',
    'MSFT': 'Ação - Tecnologia', 'NVDA': 'Ação - Tecnologia', 'AAPL': 'Ação - Tecnologia',
    'O': 'REITs - Imobiliário', 'IQQ6': 'REITs - Imobiliário'
}

def clean_val(val):
    if pd.isna(val) or str(val).strip() == '': return 0.0
    s = str(val).replace('€', '').replace('$', '').replace('USD', '').replace('EUR', '').strip()
    if ',' in s and '.' in s: s = s.replace('.', '')
    s = s.replace(',', '.')
    s = re.sub(r'[^-0-9.]', '', s)
    try: return float(s)
    except: return 0.0

def read_file_robust(file):
    content = file.getvalue()
    for encoding in ['utf-8', 'latin-1', 'utf-16']:
        try:
            text = content.decode(encoding)
            sep = ';' if text.count(';') > text.count(',') else ','
            lines = text.split('\n')
            skip = 0
            for i, line in enumerate(lines[:20]):
                if any(k in line.lower() for k in ['ticker', 'tipo', 'type', 'montante']):
                    skip = i
                    break
            df = pd.read_csv(io.StringIO(text), sep=sep, skiprows=skip, on_bad_lines='skip', engine='python')
            df.columns = [str(c).strip().lower() for c in df.columns]
            return df
        except: continue
    return None

def process_data(uploaded_files):
    assets = []
    for file in uploaded_files:
        df = read_file_robust(file)
        if df is None: continue
        fname = file.name.lower()

        # Captura de Posições
        if any(x in fname for x in ["setorial", "usd", "ações", "sheet"]):
            t_col = next((c for c in df.columns if 'ticker' in c), None)
            v_col = next((c for c in df.columns if any(x in c for x in ['investido', 'euros', 'total', 'valor'])), None)
            
            if t_col and v_col:
                for _, row in df.iterrows():
                    ticker = str(row[t_col]).strip().upper()
                    if len(ticker) > 1 and ticker not in ['TOTAL', 'NAN', 'TICKER']:
                        # Define a Classe (Gráfico 1) e o Setor (Gráfico 2)
                        classe = 'ETFs' if 'setorial' in fname else 'Ações Individuais'
                        setor = MAP_SETORES.get(ticker, '⚠️ Não Categorizado')
                        assets.append({
                            'Ativo': ticker, 
                            'Classe': classe, 
                            'Setor': setor, 
                            'Valor': clean_val(row[v_col])
                        })
        
        elif 'aplicado' in df.columns: # Offline (PPR/Aforro)
            for _, row in df[df.get('estado', '').astype(str).str.contains('aberto', na=False, case=False)].iterrows():
                assets.append({
                    'Ativo': row['descrição'], 
                    'Classe': 'PPR / Aforro', 
                    'Setor': 'PPR / Aforro', 
                    'Valor': clean_val(row['aplicado'])
                })

    return pd.DataFrame(assets)

# --- UI ---
st.title("📊 Análise de Portfólio Inês")
files = st.sidebar.file_uploader("Upload CSVs", accept_multiple_files=True)

if files:
    df_res = process_data(files)
    
    if not df_res.empty:
        # Layout de dois gráficos lado a lado
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("1. Por Classe de Ativos")
            fig1 = px.pie(df_res, values='Valor', names='Classe', hole=0.4, title="Distribuição Geral")
            st.plotly_chart(fig1, use_container_width=True)
            
        with col2:
            st.subheader("2. Análise Setorial Detalhada")
            fig2 = px.pie(df_res, values='Valor', names='Setor', hole=0.4, title="Exposição por Setor/Tipo")
            st.plotly_chart(fig2, use_container_width=True)

        st.divider()

        # SECÇÃO DE AUDITORIA: O que não está categorizado?
        st.subheader("🔍 Auditoria de Categorização")
        df_nao_cat = df_res[df_res['Setor'] == '⚠️ Não Categorizado']
        
        if not df_nao_cat.empty:
            st.warning(f"Foram detetados {len(df_nao_cat)} ativos sem categoria definida.")
            st.write("Lista de Tickers para adicionar ao código:")
            st.dataframe(df_nao_cat[['Ativo', 'Valor']], hide_index=True)
        else:
            st.success("✅ Todos os ativos estão devidamente categorizados!")
