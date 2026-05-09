import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Investimentos Inês 2026", layout="wide")

# Estilo para os cartões de métricas
st.markdown("""
    <style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
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

def process_data(uploaded_files):
    all_assets, m = [], {'divs': 0.0, 'juros': 0.0, 'dep': 0.0, 'cash': 0.0}
    
    for file in uploaded_files:
        df = pd.read_csv(io.StringIO(file.getvalue().decode('utf-8', 'ignore')), sep=None, engine='python')
        df.columns = [str(c).strip().lower() for c in df.columns]
        fname = file.name.lower()

        # Lógica de Captura (XTB, F24, Offline)
        if any(x in fname for x in ["setorial", "usd", "ações"]):
            t_col = next((c for c in df.columns if 'ticker' in c), None)
            v_col = next((c for c in df.columns if any(x in c for x in ['investido', 'euros', 'total'])), None)
            if t_col and v_col:
                cat = 'ETFs' if 'setorial' in fname else 'Ações Individuais'
                for _, row in df.iterrows():
                    ticker = str(row[t_col]).strip().upper()
                    if len(ticker) > 1 and ticker not in ['TOTAL', 'NAN']:
                        all_assets.append({'Ativo': ticker, 'Cat': cat, 'Valor': clean_val(row[v_col]), 'Fonte': 'XTB'})

        elif 'aplicado' in df.columns: # Offline / Bancos
            for _, row in df[df.get('estado', '').astype(str).str.contains('aberto', na=False, case=False)].iterrows():
                cat_off = row.get('ativo', 'PPR/Aforro')
                all_assets.append({'Ativo': row['descrição'], 'Cat': cat_off, 'Valor': clean_val(row['aplicado']), 'Fonte': 'Bancos/IGCP'})

        elif 'cash' in fname or 'operations' in fname:
            for _, row in df.iterrows():
                tipo, valor = str(row.get('type', '')).lower(), clean_val(row.get('amount', 0))
                m['cash'] += valor 
                if 'dividend' in tipo: m['divs'] += valor
                if 'interest' in tipo: m['juros'] += valor
                if any(x in tipo for x in ['deposit', 'transfer']): m['dep'] += abs(valor)

    if m['cash'] > 0.1:
        all_assets.append({'Ativo': 'Cash', 'Cat': 'Cash / Fundo Emergência', 'Valor': m['cash'], 'Fonte': 'XTB'})

    return pd.DataFrame(all_assets), m

# --- INTERFACE ---
st.title("📊 PORTFÓLIO DE INVESTIMENTOS DA INÊS")
st.caption("Atualizado: Maio 2026")

files = st.sidebar.file_uploader("Arraste os seus ficheiros CSV", accept_multiple_files=True)

if files:
    df_res, met = process_data(files)
    
    if not df_res.empty:
        # [ 💰 VISAO GERAL ]
        pat_total = df_res['Valor'].sum()
        lucro_abs = pat_total - met['dep']
        lucro_perc = (lucro_abs / met['dep'] * 100) if met['dep'] != 0 else 0
        
        st.subheader("[ 💰 VISAO GERAL ]")
        c1, c2, c3 = st.columns(3)
        c1.metric("Património Total", f"€ {pat_total:,.2f}")
        c2.metric("Capital Investido", f"€ {met['dep']:,.2f}")
        c3.metric("Lucro / Prejuízo", f"€ {lucro_abs:,.2f}", f"{lucro_perc:+.2f}%")

        c4, c5, c6 = st.columns(3)
        c4.metric("Yield Estimado", "3.2%") # Valor exemplo conforme wireframe
        c5.metric("Dividendos Recebidos", f"€ {met['divs']:,.2f}")
        c6.metric("Juros N/ Investido", f"€ {met['juros']:,.2f}")

        st.divider()

        # [ 🌍 DISTRIBUIÇÃO ]
        st.subheader("[ 🌍 DISTRIBUIÇÃO E ALOCAÇÃO ]")
        filtro = st.radio("Filtros:", ["Todos", "XTB", "Bancos/IGCP"], horizontal=True)
        
        df_filtered = df_res if filtro == "Todos" else df_res[df_res['Fonte'] == filtro]
        
        col_graf1, col_graf2 = st.columns(2)
        with col_graf1:
            st.plotly_chart(px.pie(df_filtered, values='Valor', names='Cat', hole=0.5, title="Classes de Ativos"), use_container_width=True)
        with col_graf2:
            st.plotly_chart(px.pie(df_filtered, values='Valor', names='Fonte', title="Corretoras/Bancos"), use_container_width=True)

        # [ 🏢 ANÁLISE SETORIAL ]
        st.subheader("[ 🏢 ANÁLISE SETORIAL ]")
        # Agrupamos por Categoria para simular os setores do wireframe
        df_setor = df_filtered.groupby('Cat')['Valor'].sum().reset_index()
        st.plotly_chart(px.bar(df_setor, x='Valor', y='Cat', orientation='h', color='Cat'), use_container_width=True)

        # [ 📈 EVOLUÇÃO TEMPORAL ]
        st.subheader("[ 📈 EVOLUÇÃO TEMPORAL ]")
        st.info("Nota: Para o gráfico de linhas evolutivo, o código precisará de ler ficheiros de meses anteriores.")
