import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Património Inês", layout="wide")

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
                if any(k in line.lower() for k in ['ticker', 'tipo', 'type', 'montante', 'transação', 'descrição']):
                    skip = i
                    break
            df = pd.read_csv(io.StringIO(text), sep=sep, skiprows=skip)
            df.columns = [str(c).strip().lower() for c in df.columns]
            return df
        except: continue
    return None

def process_data(uploaded_files):
    all_assets, m = [], {'dividendos': 0.0, 'juros': 0.0, 'depositos': 0.0, 'saldo_cash': 0.0}
    
    for file in uploaded_files:
        df = read_file_robust(file)
        if df is None: continue
        fname = file.name.lower()

        # 1. POSIÇÕES INVESTIDAS
        if any(x in fname for x in ["setorial", "usd", "ações"]):
            t_col = next((c for c in df.columns if 'ticker' in c), None)
            v_col = next((c for c in df.columns if any(x in c for x in ['investido', 'euros', 'total'])), None)
            if t_col and v_col:
                cat = 'ETF' if 'setorial' in fname else 'Ação'
                for _, row in df.iterrows():
                    ticker = str(row[t_col]).strip().upper()
                    if len(ticker) > 1 and ticker not in ['TOTAL', 'NAN']:
                        all_assets.append({'Ativo': ticker, 'Cat': cat, 'Valor': clean_val(row[v_col])})

        elif 'aplicado' in df.columns: # Offline
            for _, row in df[df.get('estado', '').astype(str).str.contains('aberto', na=False, case=False)].iterrows():
                all_assets.append({'Ativo': row['descrição'], 'Cat': 'PPR/Aforro', 'Valor': clean_val(row['aplicado'])})

        # 2. FLUXOS (Cálculo do Saldo em Cash e Depósitos)
        if 'cash' in fname or 'operations' in fname:
            for _, row in df.iterrows():
                tipo, valor = str(row.get('type', '')).lower(), clean_val(row.get('amount', 0))
                # O saldo em cash é a soma de TUDO o que acontece na conta (compras negativas, depósitos positivos)
                m['saldo_cash'] += valor 
                if 'dividend' in tipo: m['dividendos'] += valor
                if 'interest' in tipo: m['juros'] += valor
                if any(x in tipo for x in ['deposit', 'transfer']): m['depositos'] += abs(valor)
                if 'withdrawal' in tipo: m['depositos'] -= abs(valor)

    # Adicionar o Saldo Não Investido como um "Ativo" para o gráfico
    if m['saldo_cash'] > 0.1:
        all_assets.append({'Ativo': 'Dinheiro em Conta (XTB)', 'Cat': 'Cash', 'Valor': m['saldo_cash']})

    return pd.DataFrame(all_assets), m

# --- UI ---
st.title("📊 Gestão de Património")
files = st.sidebar.file_uploader("Upload CSVs", accept_multiple_files=True)

if files:
    df_res, metrics = process_data(files)
    if not df_res.empty:
        total_patrimonio = df_res['Valor'].sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Património Total", f"€ {total_patrimonio:,.2f}", help="Inclui Ações, ETFs e Dinheiro parado")
        c2.metric("Total que Investiu", f"€ {metrics['depositos']:,.2f}")
        c3.metric("Dividendos", f"€ {metrics['dividendos']:,.2f}")
        c4.metric("Juros", f"€ {metrics['juros']:,.2f}")
        
        st.divider()
        col1, col2 = st.columns([1, 1])
        with col1: st.plotly_chart(px.pie(df_res, values='Valor', names='Cat', hole=0.4), use_container_width=True)
        with col2: st.dataframe(df_res.sort_values('Valor', ascending=False), hide_index=True)
        
        # A conta agora é: (Tudo o que tenho - Tudo o que pus) + Rendimentos
        lucro_real = (total_patrimonio - metrics['depositos'])
        st.success(f"**Balanço Real (Valorização + Rendimentos): € {lucro_real:,.2f}**")
