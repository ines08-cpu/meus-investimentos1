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
    # Lida com pontos de milhar e vírgulas decimais
    if ',' in s and '.' in s: s = s.replace('.', '')
    s = s.replace(',', '.')
    s = re.sub(r'[^-0-9.]', '', s)
    try: return float(s)
    except: return 0.0

def read_file_robust(file):
    """Tenta ler o ficheiro com diferentes encodings e separadores."""
    content = file.getvalue()
    for encoding in ['utf-8', 'latin-1', 'utf-16']:
        try:
            text = content.decode(encoding)
            # Deteta o separador
            sep = ';' if text.count(';') > text.count(',') else ','
            # Encontra onde começa o cabeçalho real
            lines = text.split('\n')
            skip = 0
            for i, line in enumerate(lines[:20]):
                l = line.lower()
                if any(k in l for k in ['ticker', 'tipo', 'type', 'montante', 'transação', 'descrição', 'ativo']):
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
            debug_info.append({"Ficheiro": file.name, "Status": "Erro de Leitura", "Tipo": "N/A"})
            continue

        cols = " | ".join(df.columns)
        detected_type = "Ignorado"

        # 1. OFFLINE (PPR/Aforro)
        if "offline" in fname or 'aplicado' in df.columns:
            detected_type = "Offline"
            col_val = next((c for c in df.columns if 'aplicado' in c), None)
            col_desc = next((c for c in df.columns if 'descrição' in c), None)
            if col_val and col_desc:
                temp = df[df.get('estado', '').astype(str).str.contains('aberto', na=False, case=False)]
                for _, row in temp.iterrows():
                    all_assets.append({'Ativo': row[col_desc], 'Cat': 'PPR/Outros', 'Valor': clean_val(row[col_val]), 'Fonte': 'Offline'})

        # 2. XTB POSIÇÕES (Ações/ETFs)
        elif any(x in fname for x in ["setorial", "usd", "ações"]):
            detected_type = "XTB Posição"
            t_col = next((c for c in df.columns if 'ticker' in c or 'unnamed' in c), None)
            v_col = next((c for c in df.columns if 'investido' in c or 'euros' in c or 'valor' in c), None)
            if t_col and v_col:
                cat = 'ETF' if 'setorial' in fname else 'Ação'
                for _, row in df.iterrows():
                    ticker = str(row[t_col]).strip()
                    if ticker.upper() not in ['TICKER', 'TOTAL', 'NAN', ''] and len(ticker) > 1:
                        all_assets.append({'Ativo': ticker, 'Cat': cat, 'Valor': clean_val(row[v_col]), 'Fonte': 'XTB'})

        # 3. FREEDOM24 POSIÇÕES
        elif "sheet" in fname or 'ticker' in df.columns and 'valor' in df.columns:
            detected_type = "F24 Posição"
            for _, row in df.iterrows():
                all_assets.append({'Ativo': row['ticker'], 'Cat': 'Ação (F24)', 'Valor': clean_val(row['valor']), 'Fonte': 'Freedom24'})

        # 4. RENDIMENTOS (XTB Cash Operations)
        elif "cash" in fname or "operations" in fname or 'type' in df.columns:
            detected_type = "XTB Fluxos"
            val_col = next((c for c in df.columns if 'amount' in c or 'montante' in c), None)
            type_col = next((c for c in df.columns if 'type' in c or 'tipo' in c), None)
            if val_col and type_col:
                for _, row in df.iterrows():
                    tipo = str(row[type_col]).lower()
                    valor = clean_val(row[val_col])
                    if 'dividend' in tipo: m['dividendos'] += valor
                    if 'interest' in tipo: m['juros'] += valor
                    if any(x in tipo for x in ['deposit', 'transfer']): m['depositos'] += abs(valor)
                    if 'withdrawal' in tipo: m['depositos'] -= abs(valor)

        # 5. RENDIMENTOS (F24 Numerário)
        elif "transacções" in fname or "numerário" in fname or 'transação' in df.columns:
            detected_type = "F24 Fluxos"
            for _, row in df.iterrows():
                desc = str(row.get('transação', '')).lower()
                valor = clean_val(row.get('montante', 0))
                cambio = 0.92 if str(row.get('moeda', '')).upper() == 'USD' else 1.0
                if any(x in desc for x in ["dividend", "societári", "taxa"]): m['dividendos'] += (valor * cambio)
                if 'transferência' in desc: m['depositos'] += abs(valor * cambio)

        debug_info.append({"Ficheiro": file.name, "Status": "Lido", "Tipo": detected_type, "Colunas": cols})

    return pd.DataFrame(all_assets), m, pd.DataFrame(debug_info)

# --- UI ---
st.sidebar.header("Configuração")
files = st.sidebar.file_uploader("Upload CSVs", accept_multiple_files=True)

if files:
    df_res, metrics, df_debug = process_data(files)
    
    if not df_res.empty:
        total = df_res['Valor'].sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Património Total", f"€ {total:,.2f}")
        c2.metric("Capital Injetado", f"€ {metrics['depositos']:,.2f}")
        c3.metric("Dividendos", f"€ {metrics['dividendos']:,.2f}")
        c4.metric("Juros", f"€ {metrics['juros']:,.2f}")

        st.divider()
        col1, col2 = st.columns([1, 1])
        with col1:
            st.plotly_chart(px.pie(df_res, values='Valor', names='Cat', hole=0.4), use_container_width=True)
        with col2:
            st.dataframe(df_res.sort_values('Valor', ascending=False), hide_index=True, use_container_width=True)
    
    # PAINEL DE DIAGNÓSTICO (Para sabermos o que falhou)
    with st.expander("🛠️ Painel de Diagnóstico (Verifica se os ficheiros foram detetados)"):
        st.table(df_debug)
