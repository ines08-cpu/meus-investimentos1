import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Património Inês", layout="wide")
st.title("📊 Gestor de Investimentos")

# --- FUNÇÕES DE LIMPEZA ---
def clean_val(val):
    if pd.isna(val) or str(val).strip() == '': return 0.0
    s = str(val).replace('€', '').replace('$', '').replace('USD', '').replace('EUR', '').strip()
    if ',' in s and '.' in s: s = s.replace('.', '')
    s = s.replace(',', '.')
    s = re.sub(r'[^-0-9.]', '', s)
    try: return float(s)
    except: return 0.0

def process_data(uploaded_files):
    all_assets = []
    m = {'dividendos': 0.0, 'juros': 0.0, 'depositos': 0.0}
    
    for file in uploaded_files:
        name = file.name.lower()
        try:
            # Tentar ler o CSV (deteta automaticamente se é vírgula ou ponto e vírgula)
            df = pd.read_csv(io.StringIO(file.getvalue().decode('utf-8')), sep=None, engine='python')
            df.columns = [str(c).strip().lower() for c in df.columns]

            # 1. POSIÇÕES XTB (Ações USD e Setorial)
            if any(x in name for x in ["setorial", "usd", "ações"]):
                t_col = next((c for c in df.columns if 'ticker' in c or 'unnamed: 1' in c), None)
                v_col = next((c for c in df.columns if 'investido' in c or 'euros' in c or 'valor' in c), None)
                if t_col and v_col:
                    cat = 'ETF' if 'setorial' in name else 'Ação'
                    for _, row in df.iterrows():
                        ticker = str(row[t_col]).strip()
                        if ticker.upper() not in ['TICKER', 'TOTAL', 'SOMA', 'NAN'] and len(ticker) > 1:
                            all_assets.append({'Ativo': ticker, 'Cat': cat, 'Valor': clean_val(row[v_col]), 'Fonte': 'XTB'})

            # 2. POSIÇÕES FREEDOM24 (Ações Oferta)
            elif "sheet" in name:
                if 'ticker' in df.columns:
                    for _, row in df.iterrows():
                        all_assets.append({'Ativo': row['ticker'], 'Cat': 'Ação (F24)', 'Valor': clean_val(row.get('valor', 0)), 'Fonte': 'Freedom24'})

            # 3. OFFLINE (PPR/Certificados)
            elif "offline" in name:
                if 'aplicado' in df.columns:
                    temp = df[df['estado'].astype(str).str.contains('aberto', na=False, case=False)]
                    for _, row in temp.iterrows():
                        all_assets.append({'Ativo': row['descrição'], 'Cat': row.get('ativo', 'PPR/Outros'), 'Valor': clean_val(row['aplicado']), 'Fonte': 'Offline'})

            # 4. RENDIMENTOS (XTB Cash Operations)
            elif "cash" in name or "operations" in name:
                type_col = next((c for c in df.columns if 'type' in c or 'tipo' in c), 'type')
                val_col = next((c for c in df.columns if 'amount' in c or 'montante' in c), 'amount')
                for _, row in df.iterrows():
                    tipo = str(row.get(type_col, '')).lower()
                    valor = clean_val(row.get(val_col, 0))
                    if 'deposit' in tipo or 'transfer' in tipo: m['depositos'] += abs(valor)
                    if 'withdrawal' in tipo: m['depositos'] -= abs(valor)
                    if 'dividend' in tipo: m['dividendos'] += valor
                    if 'interest' in tipo: m['juros'] += valor

            # 5. RENDIMENTOS (Freedom24 Numerário)
            elif "transacções" in name or "numerário" in name:
                if 'transação' in df.columns:
                    for _, row in df.iterrows():
                        desc = str(row['transação'])
                        valor = clean_val(row['montante'])
                        moeda = str(row.get('moeda', 'EUR')).upper()
                        cambio = 0.92 if moeda == 'USD' else 1.0
                        if any(x in desc for x in ["Dividendos", "societárias", "Taxas"]):
                            m['dividendos'] += (valor * cambio)
                        if 'Transferência bancária' in desc:
                            m['depositos'] += abs(valor * cambio)

        except: continue
    return pd.DataFrame(all_assets), m

# --- INTERFACE ---
st.sidebar.header("Upload de Ficheiros")
files = st.sidebar.file_uploader("Arraste os CSVs aqui", accept_multiple_files=True)

if files:
    df_res, metrics = process_data(files)
    if not df_res.empty:
        # Métricas no Topo
        total = df_res['Valor'].sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Património Total", f"€ {total:,.2f}")
        c2.metric("Total Investido", f"€ {metrics['depositos']:,.2f}")
        c3.metric("Dividendos", f"€ {metrics['dividendos']:,.2f}")
        c4.metric("Juros", f"€ {metrics['juros']:,.2f}")

        st.divider()
        col1, col2 = st.columns([1, 1])
        with col1:
            st.plotly_chart(px.pie(df_res, values='Valor', names='Cat', title="Onde está o dinheiro?"), use_container_width=True)
        with col2:
            st.subheader("Lista de Ativos")
            st.dataframe(df_res.sort_values('Valor', ascending=False), hide_index=True)

        lucro_total = (total - metrics['depositos']) + metrics['dividendos'] + metrics['juros']
        st.info(f"**Performance Global: € {lucro_total:,.2f}**")
