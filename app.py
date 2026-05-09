import streamlit as st
import pandas as pd
import plotly.express as px
import io
import re

st.set_page_config(page_title="Investimentos Inês", layout="wide")
st.title("📊 Dashboard de Património - Consolidado")

def clean_val(val):
    if pd.isna(val) or str(val).strip() == '': return 0.0
    s = str(val).replace('€', '').replace('$', '').replace('USD', '').replace('EUR', '').strip()
    if ',' in s and '.' in s: s = s.replace('.', '')
    s = s.replace(',', '.')
    s = re.sub(r'[^-0-9.]', '', s)
    try: return float(s)
    except: return 0.0

def smart_read(file):
    content = file.getvalue().decode('utf-8')
    sep = ';' if content.count(';') > content.count(',') else ','
    lines = content.split('\n')
    skip = 0
    for i, line in enumerate(lines[:25]):
        if any(x in line.lower() for x in ['descrição', 'ticker', 'ativo', 'montante', 'transação', 'type', 'tipo', 'comentário']):
            skip = i
            break
    df = pd.read_csv(io.StringIO(content), sep=sep, skiprows=skip)
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

def process_data(uploaded_files):
    all_assets_list = []
    xtb_manual = {}
    xtb_auto = {}
    metrics = {'dividendos': 0.0, 'juros': 0.0, 'depositos': 0.0}
    
    for file in uploaded_files:
        name = file.name.lower()
        try:
            df = smart_read(file)
            
            # 1. OFFLINE (Aforro/PPR)
            if "offline" in name:
                temp = df[df['estado'].astype(str).str.contains('aberto', na=False, case=False)]
                for _, row in temp.iterrows():
                    all_assets_list.append({'Ativo': row['descrição'], 'Cat': row.get('ativo', 'Offline'), 'Valor': clean_val(row['aplicado']), 'Fonte': 'Offline'})

            # 2. XTB EXCEL (Base de Conhecimento)
            elif "setorial" in name or "usd" in name or "ações" in name:
                t_col = next((c for c in df.columns if 'ticker' in c or 'unnamed: 1' in c), None)
                v_col = next((c for c in df.columns if 'investido' in c or 'euros' in c or 'valor' in c), None)
                if t_col and v_col:
                    cat_nome = 'ETF' if 'setorial' in name else 'Ação'
                    for _, row in df.dropna(subset=[t_col]).iterrows():
                        ticker = str(row[t_col]).strip()
                        if ticker.lower() not in ['ticker', 'total', 'nan', 'soma'] and ticker:
                            xtb_manual[ticker] = {'Cat': cat_nome, 'Valor': clean_val(row[v_col])}

            # 3. FREEDOM24 (Ofertas)
            elif "sheet" in name:
                t_col = next((c for c in df.columns if 'ticker' in c), None)
                v_col = next((c for c in df.columns if 'valor' in c), df.columns[-1])
                for _, row in df.iterrows():
                    all_assets_list.append({'Ativo': row[t_col], 'Cat': 'Ação (Oferta)', 'Valor': clean_val(row[v_col]), 'Fonte': 'Freedom24'})

            # 4. FREEDOM24 (Rendimentos)
            elif "transacções" in name or "numerário" in name:
                for _, row in df.iterrows():
                    desc = str(row['transação']).lower()
                    valor = clean_val(row['montante'])
                    moeda = str(row.get('moeda', 'EUR')).upper()
                    cambio = 0.92 if moeda == 'USD' else 1.0
                    if any(x in desc for x in ["dividend", "societári", "soietári", "taxas do agente"]):
                        metrics['dividendos'] += (valor * cambio)
                    if 'transferência bancária' in desc:
                        metrics['depositos'] += abs(valor * cambio)

            # 5. XTB CASH OPERATIONS (A Fonte Principal)
            elif "cash" in name or "operations" in name:
                for _, row in df.iterrows():
                    tipo = str(row['type']).lower()
                    valor = clean_val(row['amount'])
                    comentario = str(row.get('comment', '')).strip()
                    
                    if 'deposit' in tipo or 'transfer' in tipo: metrics['depositos'] += abs(valor)
                    if 'withdrawal' in tipo: metrics['depositos'] -= abs(valor)
                    if 'dividend' in tipo: metrics['dividendos'] += valor
                    if 'interest' in tipo: metrics['juros'] += valor
                    
                    # Captura compras e identifica o ativo
                    if any(x in tipo for x in ['purchase', 'compra', 'open']):
                        # Limpa o ticker do comentário (Ex: "OPEN BUY 10 AAPL.US" -> "AAPL.US")
                        parts = comentario.split()
                        ativo = parts[-1] if parts else "Desconhecido"
                        if ativo not in xtb_auto: xtb_auto[ativo] = 0.0
                        xtb_auto[ativo] += (-valor) # Valor de compra vem negativo no CSV

        except: continue

    # Merge Inteligente
    for ativo, val_investido in xtb_auto.items():
        if val_investido > 0.5:
            match_key = next((k for k in xtb_manual.keys() if k in ativo or ativo in k), None)
            if match_key:
                val_final = max(xtb_manual[match_key]['Valor'], val_investido)
                cat = xtb_manual[match_key]['Cat']
                del xtb_manual[match_key]
            else:
                val_final = val_investido
                # Lógica simples de classificação
                cat = "ETF" if any(x in ativo.upper() for x in ["UCITS", "ETF", "LYXOR", "ISHRS"]) else "Ação"
            all_assets_list.append({'Ativo': ativo, 'Cat': cat, 'Valor': val_final, 'Fonte': 'XTB'})
            
    for ativo, data in xtb_manual.items():
        all_assets_list.append({'Ativo': ativo, 'Cat': data['Cat'], 'Valor': data['Valor'], 'Fonte': 'XTB'})

    return pd.DataFrame(all_assets_list), metrics

# --- UI ---
uploaded = st.sidebar.file_uploader("Upload CSVs", accept_multiple_files=True)
if uploaded:
    df_pos, m = process_data(uploaded)
    if not df_pos.empty:
        total_patrimonio = df_pos['Valor'].sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Património Total", f"€ {total_patrimonio:,.2f}")
        c2.metric("Injeção Capital", f"€ {m['depositos']:,.2f}")
        c3.metric("Dividendos Net", f"€ {m['dividendos']:,.2f}")
        c4.metric("Juros Líquidos", f"€ {m['juros']:,.2f}")
        
        st.divider()
        col_a, col_b = st.columns([1, 1])
        with col_a:
            st.plotly_chart(px.pie(df_pos, values='Valor', names='Cat', hole=0.4, title="Carteira"), use_container_width=True)
        with col_b:
            st.dataframe(df_pos.sort_values('Valor', ascending=False), use_container_width=True, hide_index=True)
        
        lucro = (total_patrimonio - m['depositos']) + m['dividendos'] + m['juros']
        st.success(f"**Balanço Global (Valorização + Rendimentos): € {lucro:,.2f}**")
