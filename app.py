import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Investimentos Inês", layout="wide")

# Estilo para os cartões de métricas
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 26px; color: #1E3A8A; }
    .stMetric { background-color: #f8fafc; padding: 15px; border-radius: 10px; border: 1px solid #e2e8f0; }
    </style>
    """, unsafe_allow_html=True)

def clean_val(val):
    if pd.isna(val) or str(val).strip() == '': return 0.0
    s = str(val).replace('€', '').replace('$', '').replace('USD', '').replace('EUR', '').strip()
    if ',' in s and '.' in s: s = s.replace('.', '')
    s = s.replace(',', '.')
    s = re.sub(r'[^-0-9.]', '', s)
    try: return float(s)
    except: return 0.0

def read_file_robust(file):
    """A 'chave mestra' que recuperamos para ler os teus CSVs difíceis."""
    content = file.getvalue()
    for encoding in ['utf-8', 'latin-1', 'utf-16']:
        try:
            text = content.decode(encoding)
            sep = ';' if text.count(';') > text.count(',') else ','
            lines = text.split('\n')
            skip = 0
            # Procura a linha onde o cabeçalho real começa
            for i, line in enumerate(lines[:20]):
                l = line.lower()
                if any(k in l for k in ['ticker', 'tipo', 'type', 'montante', 'transação', 'descrição', 'ativo', 'dividendos', 'juros']):
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

        # 1. RENDIMENTOS EXTRA (Ficheiros 'Dividendos' e 'Juros' manuais)
        if 'dividendos recebidos' in df.columns:
            col_soma = 'total' if 'total' in df.columns else 'dividendos recebidos'
            m['divs'] += df[col_soma].apply(clean_val).sum()
            continue
        elif any('juros' in c for c in df.columns) and 'offline' not in fname:
            for col in df.columns:
                if 'unnamed' not in col or 'total' in col:
                    m['juros'] += df[col].apply(clean_val).sum()
            continue

        # 2. POSIÇÕES (XTB / FREEDOM / OFFLINE)
        if any(x in fname for x in ["setorial", "usd", "ações"]):
            t_col = next((c for c in df.columns if 'ticker' in c), None)
            v_col = next((c for c in df.columns if any(x in c for x in ['investido', 'euros', 'total', 'valor'])), None)
            if t_col and v_col:
                cat = 'ETFs' if 'setorial' in fname else 'Ações Individuais'
                for _, row in df.iterrows():
                    ticker = str(row[t_col]).strip().upper()
                    if len(ticker) > 1 and ticker not in ['TOTAL', 'NAN', 'TICKER']:
                        assets.append({'Ativo': ticker, 'Cat': cat, 'Valor': clean_val(row[v_col]), 'Fonte': 'XTB'})

        elif 'aplicado' in df.columns: # Offline
            for _, row in df[df.get('estado', '').astype(str).str.contains('aberto', na=False, case=False)].iterrows():
                assets.append({'Ativo': row['descrição'], 'Cat': row.get('ativo', 'PPR/Aforro'), 'Valor': clean_val(row['aplicado']), 'Fonte': 'Bancos/IGCP'})

        elif 'ticker' in df.columns and 'valor' in df.columns: # Freedom24
            for _, row in df.iterrows():
                assets.append({'Ativo': row['ticker'], 'Cat': 'Ações Individuais', 'Valor': clean_val(row['valor']), 'Fonte': 'Freedom24'})

        # 3. FLUXOS (Cash Operations e Transacções Numerário)
        if any(x in fname for x in ["cash", "operations", "numerário", "transacções"]):
            type_col = next((c for c in df.columns if 'type' in c or 'transação' in c), None)
            amt_col = next((c for c in df.columns if 'amount' in c or 'montante' in c), None)
            if type_col and amt_col:
                for _, row in df.iterrows():
                    t, v = str(row[type_col]).lower(), clean_val(row[amt_col])
                    m['cash'] += v 
                    if 'dividend' in t: m['divs'] += v
                    if 'interest' in t or 'juro' in t: m['juros'] += v
                    if any(x in t for x in ['deposit', 'transfer', 'depósito', 'transferência']): m['dep'] += abs(v)
                    if 'withdrawal' in t: m['dep'] -= abs(v)

    if m['cash'] > 1:
        assets.append({'Ativo': 'Cash em Conta', 'Cat': 'Cash / Fundo Emergência', 'Valor': m['cash'], 'Fonte': 'XTB/F24'})

    return pd.DataFrame(assets), m

# --- INTERFACE WIREFRAME ---
st.title("📊 PORTFÓLIO DE INVESTIMENTOS DA INÊS")
st.caption("Visão Consolidada • Maio 2026")

files = st.sidebar.file_uploader("Upload de CSVs", accept_multiple_files=True)

if files:
    df_res, met = process_data(files)
    if not df_res.empty:
        pat_total = df_res['Valor'].sum()
        lucro_abs = pat_total - met['dep']
        lucro_perc = (lucro_abs / met['dep'] * 100) if met['dep'] > 0 else 0

        st.subheader("[ 💰 VISAO GERAL ]")
        c1, c2, c3 = st.columns(3)
        c1.metric("Património Total", f"€ {pat_total:,.2f}")
        c2.metric("Capital Investido", f"€ {met['dep']:,.2f}")
        c3.metric("Lucro / Prejuízo", f"€ {lucro_abs:,.2f}", f"{lucro_perc:+.2f}%")

        c4, c5, c6 = st.columns(3)
        c4.metric("Yield Anual (PPR/Dep.)", "3.2%")
        c5.metric("Dividendos Recebidos", f"€ {met['divs']:,.2f}")
        c6.metric("Juros N/ Investido", f"€ {met['juros']:,.2f}")

        st.divider()
        st.subheader("[ 🌍 DISTRIBUIÇÃO E ALOCAÇÃO ]")
        f = st.radio("Origem:", ["Todos", "XTB", "Freedom24", "Bancos/IGCP"], horizontal=True)
        df_v = df_res if f == "Todos" else df_res[df_res['Fonte'] == f]
        
        col_p1, col_p2 = st.columns(2)
        with col_p1: st.plotly_chart(px.pie(df_v, values='Valor', names='Cat', hole=0.5, title="Classes de Ativos"), use_container_width=True)
        with col_p2: st.plotly_chart(px.pie(df_v, values='Valor', names='Fonte', title="Por Instituição"), use_container_width=True)

        st.subheader("[ 🏢 ANÁLISE CATEGORIA ]")
        st.plotly_chart(px.bar(df_v.groupby('Cat')['Valor'].sum().reset_index(), x='Valor', y='Cat', orientation='h'), use_container_width=True)
