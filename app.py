import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

# --- MAPEAMENTO DE SETORES (Baseado na tua carteira) ---
MAP_SETORES = {
    # ETFs - USA
    'SXR8': 'ETF - USA', 'VUAA': 'ETF - USA', 'VUSA': 'ETF - USA',
    # ETFs - Global
    'VWCE': 'ETF - Global', 'IWDA': 'ETF - Global', 'EUNA': 'ETF - Bonds',
    # ETFs - Tecnologia / Temáticos
    'SXRV': 'ETF - Tecnologia', '2B76': 'ETF - Automação', 'GOAI': 'ETF - IA', 
    'NUKL': 'ETF - Urânio', 'BTCE': 'Cripto - Bitcoin',
    # Commodities
    '4GLD': 'Commodities - Ouro', 'EGLN': 'Commodities - Prata',
    # Ações - Tecnologia
    'MSFT': 'Ação - Tecnologia', 'NVDA': 'Ação - Tecnologia', 'NFLX': 'Ação - Consumo',
    # Outros / Imobiliário
    'O': 'REITs - Imobiliário', 'IQQ6': 'REITs - Imobiliário',
}

def get_sector(ticker):
    return MAP_SETORES.get(ticker, 'Outros / Não Categorizado')

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
    assets, m = [], {'dep': 0.0, 'cash': 0.0}
    
    for file in uploaded_files:
        df = read_file_robust(file)
        if df is None: continue
        fname = file.name.lower()

        # POSIÇÕES (XTB / F24 / OFFLINE)
        if any(x in fname for x in ["setorial", "usd", "ações", "sheet"]):
            t_col = next((c for c in df.columns if 'ticker' in c), None)
            v_col = next((c for c in df.columns if any(x in c for x in ['investido', 'euros', 'total', 'valor'])), None)
            
            if t_col and v_col:
                for _, row in df.iterrows():
                    ticker = str(row[t_col]).strip().upper()
                    if len(ticker) > 1 and ticker not in ['TOTAL', 'NAN', 'TICKER']:
                        # AQUI É ONDE A MÁGICA ACONTECE:
                        assets.append({
                            'Ativo': ticker, 
                            'Setor': get_sector(ticker), 
                            'Valor': clean_val(row[v_col])
                        })

        elif 'aplicado' in df.columns: # PPR / Aforro
            for _, row in df[df.get('estado', '').astype(str).str.contains('aberto', na=False, case=False)].iterrows():
                assets.append({'Ativo': row['descrição'], 'Setor': 'PPR/Aforro', 'Valor': clean_val(row['aplicado'])})

    return pd.DataFrame(assets)

# --- UI STREAMLIT ---
st.title("🏢 ANÁLISE SETORIAL DE PORTFÓLIO")
files = st.sidebar.file_uploader("Upload CSVs", accept_multiple_files=True)

if files:
    df_res = process_data(files)
    if not df_res.empty:
        # Gráfico Circular Setorial
        st.subheader("Distribuição por Categoria Financeira")
        fig = px.pie(df_res, values='Valor', names='Setor', hole=0.4, 
                     color_discrete_sequence=px.colors.qualitative.Prism)
        st.plotly_chart(fig, use_container_width=True)

        # Tabela Detalhada
        st.subheader("Detalhe por Ativo")
        st.dataframe(df_res.sort_values('Valor', ascending=False), hide_index=True)
