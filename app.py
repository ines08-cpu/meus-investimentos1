import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Investimentos Inês 2026", layout="wide")

# --- CSS para o Look & Feel do Wireframe ---
st.markdown("""
    <style>
    [data-testid="stMetricValue"] { font-size: 24px; color: #1E3A8A; }
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

def smart_read(file):
    """Lê o ficheiro ignorando linhas malformadas e detectando cabeçalhos."""
    content = file.getvalue().decode('utf-8', errors='ignore')
    sep = ';' if content.count(';') > content.count(',') else ','
    # On_bad_lines='skip' resolve o ParserError que tiveste
    df = pd.read_csv(io.StringIO(content), sep=sep, on_bad_lines='skip', engine='python')
    # Limpeza de colunas
    df.columns = [str(c).strip().upper() for c in df.columns]
    return df

def process_data(uploaded_files):
    assets, m = [], {'divs': 0.0, 'juros': 0.0, 'dep': 0.0, 'cash': 0.0}
    
    for file in uploaded_files:
        name = file.name.lower()
        df = smart_read(file)
        
        # 1. OFFLINE (Aforro/PPR) - Blindagem para o erro que deu
        if "offline" in name or 'APLICADO' in df.columns:
            # Filtra apenas onde a descrição não é nula
            valid_rows = df.dropna(subset=[df.columns[0]]) 
            for _, row in valid_rows.iterrows():
                estado = str(row.get('ESTADO', '')).upper()
                if 'ABERTO' in estado:
                    assets.append({
                        'Ativo': row.get('DESCRIÇÃO', 'PPR/Aforro'),
                        'Cat': row.get('ATIVO', 'PPR/Aforro'),
                        'Valor': clean_val(row.get('APLICADO', 0)),
                        'Fonte': 'Bancos/IGCP'
                    })

        # 2. XTB / FREEDOM (Posições)
        elif any(x in name for x in ["setorial", "usd", "ações", "sheet"]):
            t_col = next((c for c in df.columns if 'TICKER' in c), None)
            v_col = next((c for c in df.columns if any(x in c for x in ['INVESTIDO', 'EUROS', 'VALOR', 'TOTAL'])), None)
            
            if t_col and v_col:
                cat = 'ETFs' if 'SETORIAL' in name else 'Ações Individuais'
                fonte = 'XTB' if 'SHEET' not in name else 'Freedom24'
                for _, row in df.iterrows():
                    ticker = str(row[t_col]).strip().upper()
                    if len(ticker) > 1 and ticker not in ['TOTAL', 'NAN', 'TICKER']:
                        assets.append({'Ativo': ticker, 'Cat': cat, 'Valor': clean_val(row[v_col]), 'Fonte': fonte})

        # 3. RENDIMENTOS E CASH (Histórico)
        if "cash" in name or "operations" in name or "numerário" in name:
            type_col = next((c for c in df.columns if 'TYPE' in c or 'TRANSAÇÃO' in c), None)
            amt_col = next((c for c in df.columns if 'AMOUNT' in c or 'MONTANTE' in c), None)
            
            if type_col and amt_col:
                for _, row in df.iterrows():
                    t, v = str(row[type_col]).lower(), clean_val(row[amt_col])
                    m['cash'] += v # Saldo acumulado na corretora
                    if 'dividend' in t: m['divs'] += v
                    if 'interest' in t or 'juro' in t: m['juros'] += v
                    if any(x in t for x in ['deposit', 'transfer', 'depósito']): m['dep'] += abs(v)

    # Adicionar o Cash como ativo se houver saldo
    if m['cash'] > 1:
        assets.append({'Ativo': 'Cash / Fundo Emergência', 'Cat': 'Cash', 'Valor': m['cash'], 'Fonte': 'Corretoras'})

    return pd.DataFrame(assets), m

# --- INTERFACE (WIREFRAME) ---
st.title("📊 PORTFÓLIO DE INVESTIMENTOS DA INÊS")
st.caption("Maio 2026 • Visão Consolidada")

files = st.sidebar.file_uploader("Carregar base de dados (CSVs)", accept_multiple_files=True)

if files:
    df_res, metrics = process_data(files)
    
    if not df_res.empty:
        # Cálculos de Topo
        pat_total = df_res['Valor'].sum()
        capital_inv = metrics['dep']
        lucro_abs = pat_total - capital_inv
        lucro_perc = (lucro_abs / capital_inv * 100) if capital_inv > 0 else 0

        # [ 💰 VISAO GERAL ]
        st.write("### [ 💰 VISAO GERAL ]")
        c1, c2, c3 = st.columns(3)
        c1.metric("Património Total", f"€ {pat_total:,.2f}")
        c2.metric("Capital Investido", f"€ {capital_inv:,.2f}")
        color = "normal" if lucro_abs >= 0 else "inverse"
        c3.metric("Lucro / Prejuízo", f"€ {lucro_abs:,.2f}", f"{lucro_perc:+.1f}%", delta_color=color)

        c4, c5, c6 = st.columns(3)
        c4.metric("Yield Estimado (PPR/Dep)", "3.2%")
        c5.metric("Dividendos Recebidos", f"€ {metrics['divs']:,.2f}")
        c6.metric("Juros N/ Investido", f"€ {metrics['juros']:,.2f}")

        st.divider()

        # [ 🌍 DISTRIBUIÇÃO ]
        st.write("### [ 🌍 DISTRIBUIÇÃO E ALOCAÇÃO ]")
        filtro = st.segmented_control("Filtro de Origem:", ["Todos", "XTB", "Freedom24", "Bancos/IGCP"], default="Todos")
        
        df_viz = df_res if filtro == "Todos" else df_res[df_res['Fonte'] == filtro]
        
        col_pie1, col_pie2 = st.columns(2)
        with col_pie1:
            st.plotly_chart(px.pie(df_viz, values='Valor', names='Cat', hole=0.5, title="Classes de Ativos", 
                                   color_discrete_sequence=px.colors.qualitative.Pastel), use_container_width=True)
        with col_pie2:
            st.plotly_chart(px.pie(df_viz, values='Valor', names='Fonte', title="Distribuição por Instituição"), use_container_width=True)

        # [ 🏢 ANÁLISE SETORIAL ]
        st.write("### [ 🏢 ANÁLISE SETORIAL / CATEGORIA ]")
        df_bar = df_viz.groupby('Cat')['Valor'].sum().sort_values().reset_index()
        st.plotly_chart(px.bar(df_bar, x='Valor', y='Cat', orientation='h', text_auto='.2s', 
                               title="Volume por Categoria"), use_container_width=True)
