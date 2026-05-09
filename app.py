import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Gestão de Património Inês", layout="wide")
st.title("📊 Dashboard de Investimentos")

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
                # Expandido o radar para detetar os teus novos nomes de colunas
                if any(k in l for k in ['ticker', 'tipo', 'type', 'montante', 'transação', 'descrição', 'ativo', 'dividendos', 'juros']):
                    skip = i
                    break
            df = pd.read_csv(io.StringIO(text), sep=sep, skiprows=skip)
            df.columns = [str(c).strip().lower() for c in df.columns]
            return df
        except:
            continue
    return None

def process_data(uploaded_files):
    all_assets = []
    m = {'dividendos': 0.0, 'juros': 0.0, 'depositos': 0.0}
    debug_info = []
    
    for file in uploaded_files:
        df = read_file_robust(file)
        fname = file.name.lower()
        if df is None:
            debug_info.append({"Ficheiro": file.name, "Status": "Erro", "Tipo": "N/A"})
            continue

        detected_type = "Ignorado"

        # 1. RENDIMENTOS MANUAIS (Os que estavam a dar 'Ignorado')
        if 'dividendos recebidos' in df.columns:
            detected_type = "Dividendos Extra"
            # Tenta somar a coluna 'total' ou a própria coluna de dividendos
            col_soma = 'total' if 'total' in df.columns else 'dividendos recebidos'
            m['dividendos'] += df[col_soma].apply(clean_val).sum()

        elif any('juros' in c for c in df.columns):
            detected_type = "Juros Extra"
            # Procura qualquer coluna que tenha valores numéricos para somar como juros
            for col in df.columns:
                if 'unnamed' not in col or 'total' in col:
                    m['juros'] += df[col].apply(clean_val).sum()

        # 2. XTB POSIÇÕES (Ações USD e ETFs)
        elif any(x in fname for x in ["setorial", "usd", "ações"]):
            detected_type = "XTB Posição"
            t_col = next((c for c in df.columns if 'ticker' in c), None)
            v_col = next((c for c in df.columns if any(x in c for x in ['investido', 'euros', 'total', 'valor'])), None)
            if t_col and v_col:
                cat = 'ETF' if 'setorial' in fname else 'Ação'
                for _, row in df.iterrows():
                    ticker = str(row[t_col]).strip().upper()
                    if ticker not in ['TICKER', 'TOTAL', 'NAN', ''] and len(ticker) > 1:
                        all_assets.append({'Ativo': ticker, 'Cat': cat, 'Valor': clean_val(row[v_col])})

        # 3. OFFLINE, FREEDOM24 e CASH OPERATIONS (Mantidos como estavam)
        elif 'aplicado' in df.columns:
            detected_type = "Offline"
            for _, row in df[df.get('estado', '').astype(str).str.contains('aberto', na=False, case=False)].iterrows():
                all_assets.append({'Ativo': row['descrição'], 'Cat': 'PPR/Aforro', 'Valor': clean_val(row['aplicado'])})

        elif 'ticker' in df.columns and 'valor' in df.columns:
            detected_type = "F24 Posição"
            for _, row in df.iterrows():
                all_assets.append({'Ativo': row['ticker'], 'Cat': 'Ação (F24)', 'Valor': clean_val(row['valor'])})

        elif 'type' in df.columns and 'amount' in df.columns:
            detected_type = "XTB Fluxos"
            for _, row in df.iterrows():
                tipo, valor = str(row['type']).lower(), clean_val(row['amount'])
                if 'dividend' in tipo: m['dividendos'] += valor
                if 'interest' in tipo: m['juros'] += valor
                if any(x in tipo for x in ['deposit', 'transfer']): m['depositos'] += abs(valor)
                if 'withdrawal' in tipo: m['depositos'] -= abs(valor)

        elif 'transação' in df.columns and 'montante' in df.columns:
            detected_type = "F24 Fluxos"
            for _, row in df.iterrows():
                desc, valor = str(row['transação']).lower(), clean_val(row['montante'])
                cambio = 0.92 if str(row.get('moeda', '')).upper() == 'USD' else 1.0
                if any(x in desc for x in ["dividend", "societári", "taxa"]): m['dividendos'] += (valor * cambio)
                if 'transferência' in desc: m['depositos'] += abs(valor * cambio)

        debug_info.append({"Ficheiro": file.name, "Status": "Lido", "Tipo": detected_type, "Colunas": " | ".join(df.columns[:5])})

    return pd.DataFrame(all_assets), m, pd.DataFrame(debug_info)

# --- UI ---
files = st.sidebar.file_uploader("Upload CSVs", accept_multiple_files=True)

if files:
    df_res, metrics, df_debug = process_data(files)
    if not df_res.empty:
        total = df_res['Valor'].sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Património Total", f"€ {total:,.2f}")
        c2.metric("Depósitos Líquidos", f"€ {metrics['depositos']:,.2f}")
        c3.metric("Dividendos", f"€ {metrics['dividendos']:,.2f}")
        c4.metric("Juros", f"€ {metrics['juros']:,.2f}")

        st.divider()
        col1, col2 = st.columns([1, 1])
        with col1:
            st.plotly_chart(px.pie(df_res, values='Valor', names='Cat', hole=0.4, title="Distribuição"), use_container_width=True)
        with col2:
            st.dataframe(df_res.sort_values('Valor', ascending=False), hide_index=True, use_container_width=True)
        
        st.success(f"**Balanço (Lucro/Prejuízo + Rendimentos): € {(total - metrics['depositos']) + metrics['dividendos'] + metrics['juros']:,.2f}**")
    
    with st.expander("🛠️ Painel de Diagnóstico"):
        st.table(df_debug)
