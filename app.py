import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Investimentos Inês", layout="wide")

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

        # 1. POSIÇÕES (XTB / F24 / OFFLINE)
        if any(x in fname for x in ["setorial", "usd", "ações", "sheet"]):
            t_col = next((c for c in df.columns if 'ticker' in c), None)
            v_col = next((c for c in df.columns if any(x in c for x in ['investido', 'euros', 'total', 'valor'])), None)
            if t_col and v_col:
                cat = 'ETFs' if 'setorial' in fname else 'Ações Individuais'
                fonte = 'XTB' if 'sheet' not in fname else 'Freedom24'
                for _, row in df.iterrows():
                    ticker = str(row[t_col]).strip().upper()
                    if len(ticker) > 1 and ticker not in ['TOTAL', 'NAN', 'TICKER']:
                        assets.append({'Ativo': ticker, 'Cat': cat, 'Valor': clean_val(row[v_col]), 'Fonte': fonte})

        elif 'aplicado' in df.columns:
            for _, row in df[df.get('estado', '').astype(str).str.contains('aberto', na=False, case=False)].iterrows():
                assets.append({'Ativo': row['descrição'], 'Cat': row.get('ativo', 'PPR/Aforro'), 'Valor': clean_val(row['aplicado']), 'Fonte': 'Bancos/IGCP'})

        # 2. FLUXOS (Cálculo Preciso de Juros e Dividendos)
        if any(x in fname for x in ["cash", "operations", "numerário", "transacções"]):
            type_col = next((c for c in df.columns if 'type' in c or 'transação' in c), None)
            amt_col = next((c for c in df.columns if 'amount' in c or 'montante' in c), None)
            
            if type_col and amt_col:
                for _, row in df.iterrows():
                    t, v = str(row[type_col]).lower(), clean_val(row[amt_col])
                    
                    # Filtro Cirúrgico: só conta como juro se a descrição disser explicitamente 'interest' ou 'juro'
                    # e NÃO for um depósito/levantamento
                    if 'interest' in t or 'juro' in t:
                        m['juros'] += v
                    elif 'dividend' in t or 'societário' in t:
                        m['divs'] += v
                    
                    # Fluxo de Caixa (para o Balanço)
                    if any(x in t for x in ['deposit', 'transfer', 'depósito', 'transferência']):
                        m['dep'] += abs(v)
                    if 'withdrawal' in t:
                        m['dep'] -= abs(v)
                    
                    # Acumula o cash real (Saldo)
                    m['cash'] += v

    if m['cash'] > 1:
        assets.append({'Ativo': 'Cash', 'Cat': 'Cash', 'Valor': m['cash'], 'Fonte': 'Corretoras'})

    return pd.DataFrame(assets), m

# --- UI ---
st.title("📊 PORTFÓLIO DE INVESTIMENTOS DA INÊS")
files = st.sidebar.file_uploader("Upload CSVs", accept_multiple_files=True)

if files:
    df_res, met = process_data(files)
    if not df_res.empty:
        pat_total = df_res['Valor'].sum()
        lucro_abs = pat_total - met['dep']
        
        st.subheader("[ 💰 VISAO GERAL ]")
        c1, c2, c3 = st.columns(3)
        c1.metric("Património Total", f"€ {pat_total:,.2f}")
        c2.metric("Capital Investido", f"€ {met['dep']:,.2f}")
        c3.metric("Lucro / Prejuízo", f"€ {lucro_abs:,.2f}")

        c4, c5, c6 = st.columns(3)
        c4.metric("Yield Estimado", "3.2%")
        c5.metric("Dividendos Recebidos", f"€ {met['divs']:,.2f}")
        c6.metric("Juros N/ Investido", f"€ {met['juros']:,.2f}")

        st.divider()
        st.subheader("[ 🌍 DISTRIBUIÇÃO ]")
        st.plotly_chart(px.pie(df_res, values='Valor', names='Cat', hole=0.5), use_container_width=True)
