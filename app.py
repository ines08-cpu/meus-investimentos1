import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Investimentos Inês 2026", layout="wide")

# --- 1. MAPEAMENTO DE SETORES ---
# Adiciona novos tickers aqui para eles saírem da lista de "Não Categorizados"
MAP_SETORES = {
    # ETFs
    'SXR8': 'ETF - USA', 'VUAA': 'ETF - USA', 'VUSA': 'ETF - USA',
    'VWCE': 'ETF - Global', 'IWDA': 'ETF - Global', 'EUNA': 'Bonds',
    'SXRV': 'ETF - Tecnologia/Robótica/AI', '2B76': 'ETF - Tecnologia/Robótica/AI', 'GOAI': 'ETF - Tecnologia/Robótica/AI', 
    'NUKL': 'ETF - Urânio', 'BTCE': 'Cripto',
    # Commodities
    '4GLD': 'Commodities', 'EGLN': 'Commodities',
    # Ações
    'MSFT': 'Ação - Tecnologia', 'NVDA': 'Ação - Tecnologia', 'NFLX': 'Ação - Consumo',
    'AAPL': 'Ação - Tecnologia', 'AMZN': 'Ação - Consumo',
    # Outros
    'O': 'REITs', 'IQQ6': 'REITs',
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
                l = line.lower()
                if any(k in l for k in ['ticker', 'tipo', 'type', 'montante', 'transação', 'descrição', 'ativo']):
                    skip = i
                    break
            df = pd.read_csv(io.StringIO(text), sep=sep, skiprows=skip, on_bad_lines='skip', engine='python')
            df.columns = [str(c).strip().lower() for c in df.columns]
            return df
        except: continue
    return None

def process_data(uploaded_files):
    assets, m = [], {'divs': 0.0, 'juros': 0.0, 'dep': 0.0, 'cash': 0.0}
    
    for file in uploaded_files:
        df = read_file_robust(file)
        if df is None: continue
        fname = file.name.lower()

        # A. POSIÇÕES (XTB / F24 / OFFLINE)
        if any(x in fname for x in ["setorial", "usd", "ações", "sheet"]):
            t_col = next((c for c in df.columns if 'ticker' in c), None)
            v_col = next((c for c in df.columns if any(x in c for x in ['investido', 'euros', 'total', 'valor'])), None)
            
            if t_col and v_col:
                cat_geral = 'ETFs' if 'setorial' in fname else 'Ações Individuais'
                for _, row in df.iterrows():
                    ticker = str(row[t_col]).strip().upper()
                    if len(ticker) > 1 and ticker not in ['TOTAL', 'NAN', 'TICKER']:
                        val = clean_val(row[v_col])
                        if val > 0:
                            assets.append({
                                'Ativo': ticker,
                                'Cat Geral': cat_geral,
                                'Setor': MAP_SETORES.get(ticker, '⚠️ Não Categorizado'),
                                'Valor': val
                            })

        elif 'aplicado' in df.columns: # PPR / Aforro
            for _, row in df[df.get('estado', '').astype(str).str.contains('aberto', na=False, case=False)].iterrows():
                desc = row['descrição']
                assets.append({
                    'Ativo': desc,
                    'Cat Geral': 'PPR / Aforro',
                    'Setor': 'PPR / Aforro',
                    'Valor': clean_val(row['aplicado'])
                })

        # B. FLUXOS (Juros, Dividendos e Balanço)
        if any(x in fname for x in ["cash", "operations", "numerário", "transacções"]):
            type_col = next((c for c in df.columns if 'type' in c or 'transação' in c), None)
            amt_col = next((c for c in df.columns if 'amount' in c or 'montante' in c), None)
            
            if type_col and amt_col:
                for _, row in df.iterrows():
                    t, v = str(row[type_col]).lower(), clean_val(row[amt_col])
                    if 'interest' in t or 'juro' in t: m['juros'] += v
                    elif 'dividend' in t or 'societário' in t: m['divs'] += v
                    
                    if any(x in t for x in ['deposit', 'transfer', 'depósito', 'transferência']): m['dep'] += abs(v)
                    if 'withdrawal' in t: m['dep'] -= abs(v)
                    m['cash'] += v

    if m['cash'] > 1:
        assets.append({'Ativo': 'Cash', 'Cat Geral': 'Cash', 'Setor': 'Cash', 'Valor': m['cash']})

    return pd.DataFrame(assets), m

# --- UI INTERFACE ---
st.title("📊 PORTFÓLIO CONSOLIDADO DA INÊS")
files = st.sidebar.file_uploader("Arraste os seus CSVs aqui", accept_multiple_files=True)

if files:
    df_res, met = process_data(files)
    
    if not df_res.empty:
        # 1. MÉTRICAS DE TOPO
        pat_total = df_res['Valor'].sum()
        lucro_abs = pat_total - met['dep']
        lucro_perc = (lucro_abs / met['dep'] * 100) if met['dep'] > 0 else 0

        st.subheader("[ 💰 VISAO GERAL ]")
        c1, c2, c3 = st.columns(3)
        c1.metric("Património Total", f"€ {pat_total:,.2f}")
        c2.metric("Capital Investido (Net)", f"€ {met['dep']:,.2f}")
        c3.metric("Lucro / Prejuízo", f"€ {lucro_abs:,.2f}", f"{lucro_perc:+.2f}%")

        c4, c5, c6 = st.columns(3)
        c4.metric("Yield Estimado", "3.2%")
        c5.metric("Dividendos Totais", f"€ {met['divs']:,.2f}")
        c6.metric("Juros de Capital", f"€ {met['juros']:,.2f}")

        st.divider()

        # 2. GRÁFICOS LADO A LADO
        st.subheader("[ 🌍 DISTRIBUIÇÃO E ALOCAÇÃO ]")
        col_left, col_right = st.columns(2)
        
        with col_left:
            fig1 = px.pie(df_res, values='Valor', names='Cat Geral', hole=0.5, title="Por Classe de Ativo")
            st.plotly_chart(fig1, use_container_width=True)
            
        with col_right:
            fig2 = px.pie(df_res, values='Valor', names='Setor', hole=0.5, title="Análise Setorial (Micro)")
            st.plotly_chart(fig2, use_container_width=True)

        # 3. TABELA DE AUDITORIA
        st.divider()
        st.subheader("🔍 Auditoria de Tickers")
        
        col_tab1, col_tab2 = st.columns([2, 1])
        with col_tab1:
            st.write("Todos os ativos detectados:")
            st.dataframe(df_res.sort_values('Valor', ascending=False), hide_index=True)
            
        with col_tab2:
            st.write("⚠️ Não Categorizados (Adicionar ao Código):")
            nao_cat = df_res[df_res['Setor'] == '⚠️ Não Categorizado']
            if not nao_cat.empty:
                st.warning(f"Tens {len(nao_cat)} ativos por classificar.")
                st.dataframe(nao_cat[['Ativo', 'Valor']], hide_index=True)
            else:
                st.success("Tudo categorizado! ✅")
