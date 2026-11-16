import base64
import json
from datetime import datetime
import io
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

st.set_page_config(page_title="Controle de Entrada e Saída", layout="centered")

SCOPES = [
    "https://www.googleapis.com" + "/auth/spreadsheets",
    "https://www.googleapis.com" + "/auth/drive",
]

@st.cache_resource
def conectar_google():
    creds_dict = json.loads(st.secrets["GCP_JSON"], strict=False)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    cliente_sheets = gspread.authorize(creds)
    servico_drive = build("drive", "v3", credentials=creds)
    return cliente_sheets, servico_drive


cliente_sheets, servico_drive = conectar_google()


ID_PLANILHA = st.secrets["ID_PLANILHA"]
ID_PASTA_DRIVE = st.secrets["ID_PASTA_DRIVE"]
aba_planilha = cliente_sheets.open_by_key(ID_PLANILHA).sheet1

def carregar_dados():
    registros = aba_planilha.get_all_records()
    if not registros:
        return pd.DataFrame(columns=[
            "Data", "Hora", "Movimentação", "Nome", "CPF", "Local",
            "Assunto", "Veículo", "Plantão", "Matrícula Operador",
            "Nome Operador", "Arquivo Foto"
        ])
    return pd.DataFrame(registros).astype(str)

def upload_foto_drive(bytes_imagem, nome_arquivo, mime_type="image/jpeg"):
    metadata = {"name": nome_arquivo, "parents": [ID_PASTA_DRIVE]}
    media = MediaIoBaseUpload(io.BytesIO(bytes_imagem), mimetype=mime_type, resumable=True)
    arquivo = servico_drive.files().create(body=metadata, media_body=media, fields="id").execute()
    file_id = arquivo.get("id")
    servico_drive.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
    ).execute()
    return "https://" + "drive.google.com" + f"/uc?export=view&id={file_id}"

LOCAIS_DISPONIVEIS = [
    "Selecione o local...",
    "AGCMG/CHEADV - Chefia da Advocacia Setorial",
    "AGCMG/CHEGAB - Chefia de Gabinete",
    "AGCMG/DIRADM - Diretoria Administrativa",
    "AGCMG/DIRCOP - Diretoria do Comando Operacional",
    "AGCMG/DIRSDS - Diretoria do Sistema de Defesa Social",
    "AGCMG/DIVCOM - Divisão de Comunicação Social",
    "AGCMG/DSTAS - Divisão de Segurança do Trabalho e Assistência Social",
    "AGCMG/GERADM - Gerência de Apoio Administrativo",
    "AGCMG/GERCCO - Gerência da Central de Controle Operacional",
    "AGCMG/GERFIN - Gerência de Finanças e Contabilidade",
    "AGCMG/GERGDP - Gerência de Gestão e Desenvolvimento de Pessoas",
    "AGCMG/GEROP - Gerência Operacional",
    "AGCMG/GERPLA - Gerência de Planejamento",
    "AGCMG/NIARME - Núcleo de Informação, Armamento e Estatística",
    "AGCMG/NPS - Núcleo de Projetos",
    "AGCMG/SECEXE - Secretaria Executiva",
    "AGCMG/SECGER - Secretaria Geral",
    "AGCMG/SETPAT - Setor de Material e Patrimônio",
    "Outro",
]

for campo, valor_padrao in [
    ("nome_pessoa", ""),
    ("cpf_pessoa", ""),
    ("veiculo_pessoa", ""),
    ("local_destino", LOCAIS_DISPONIVEIS[0]),
    ("assunto_registro", ""),
    ("fotos_anteriores", []),
    ("fotos_webcam_temp", []),
    ("uploader_key", 0),
    ("cam_key", 0),
    ("limpar_formulario", False),
]:
    if campo not in st.session_state:
        st.session_state[campo] = valor_padrao

if st.session_state.limpar_formulario:
    st.session_state.nome_pessoa = ""
    st.session_state.cpf_pessoa = ""
    st.session_state.veiculo_pessoa = ""
    st.session_state.local_destino = LOCAIS_DISPONIVEIS[0]
    st.session_state.assunto_registro = ""
    st.session_state.fotos_anteriores = []
    st.session_state.fotos_webcam_temp = []
    st.session_state.uploader_key += 1
    st.session_state.cam_key += 1
    st.session_state.limpar_formulario = False

st.title("📋 Controle de Entrada e Saída")

st.subheader("1. Identificação do Plantão")
col1, col2, col3 = st.columns(3)
with col1:
    plantao = st.selectbox("Plantão", ["24H-ALPHA", "24H-BRAVO", "24H-CHARLIE", "24H-DELTA"])
with col2:
    matricula_op = st.text_input("Matrícula do Operador")
with col3:
    nome_op = st.text_input("Nome do Operador")

st.divider()

st.subheader("2. Buscar Visitante Recorrente (Autopreenchimento)")
col_busca1, col_busca2 = st.columns([3, 1])
with col_busca1:
    cpf_busca = st.text_input("Digite o CPF para puxar dados anteriores", placeholder="Ex: 12345678900")
with col_busca2:
    st.write("")
    st.write("")
    btn_buscar = st.button("🔍 Puxar Dados", use_container_width=True)

df_historico = carregar_dados()

if btn_buscar:
    if not df_historico.empty and cpf_busca.strip() != "":
        cpf_limpo_busca = "".join(filter(str.isdigit, cpf_busca))
        df_historico["CPF_LIMPO"] = df_historico["CPF"].apply(lambda x: "".join(filter(str.isdigit, str(x))))
        resultados = df_historico[df_historico["CPF_LIMPO"] == cpf_limpo_busca]

        if not resultados.empty:
            ultimo = resultados.iloc[-1]
            st.session_state.nome_pessoa = ultimo["Nome"]
            st.session_state.cpf_pessoa = ultimo["CPF"]
            v = str(ultimo.get("Veículo", ""))
            st.session_state.veiculo_pessoa = "" if v in ["Não informado", "nan", ""] else v
            links_str = str(ultimo.get("Arquivo Foto", ""))
            if links_str and links_str != "Sem foto":
                st.session_state.fotos_anteriores = [l.strip() for l in links_str.split(" | ") if l.strip().startswith("http")]
            else:
                st.session_state.fotos_anteriores = []
            st.rerun()
        else:
            st.warning("Nenhum registro encontrado para este CPF. Preencha abaixo.")
            st.session_state.cpf_pessoa = cpf_busca
            st.session_state.nome_pessoa = ""
            st.session_state.veiculo_pessoa = ""
            st.session_state.fotos_anteriores = []
            st.rerun()
    else:
        st.warning("Base de dados vazia ou CPF não informado.")

st.divider()

st.subheader("3. Dados do Registro")
tipo_movimento = st.radio("Tipo de Movimentação", ["Entrada", "Saída"], horizontal=True)

col4, col5 = st.columns(2)
with col4:
    nome_pessoa = st.text_input("Nome Completo *", key="nome_pessoa")
with col5:
    cpf_pessoa = st.text_input("CPF *", key="cpf_pessoa")

col_loc, col_ass = st.columns(2)
with col_loc:
    local_destino = st.selectbox("Local / Setor *", LOCAIS_DISPONIVEIS, key="local_destino")
with col_ass:
    assunto_registro = st.text_input("Assunto *", placeholder="Ex: Reunião, Entrega...", key="assunto_registro")

veiculo_pessoa = st.text_input("Veículo - Placa / Modelo (Opcional)", placeholder="Ex: ABC-1234 / Gol Prata", key="veiculo_pessoa")

agora = datetime.now()
col6, col7 = st.columns(2)
with col6:
    data_registro = st.date_input("Data", value=agora.date())
with col7:
    hora_registro = st.time_input("Hora", value=agora.time())

if st.session_state.fotos_anteriores:
    st.info(f"📸 {len(st.session_state.fotos_anteriores)} foto(s) do cadastro anterior recuperada(s):")
    cols_ant = st.columns(min(len(st.session_state.fotos_anteriores), 4))
    for i, link_ant in enumerate(st.session_state.fotos_anteriores):
        with cols_ant[i % 4]:
            st.image(link_ant, width=150)

st.write("**Registro Fotográfico Atual (Múltiplas Fotos)**")
opcao_foto = st.radio(
    "Como deseja proceder com as fotos?",
    [
        "Manter foto(s) anterior(es) (se houver)",
        "Tirar nova(s) foto(s) pela Webcam",
        "Fazer upload de arquivo(s)",
    ],
    horizontal=True,
)

foto_cam = None
novas_fotos_upload = []

if opcao_foto == "Tirar nova(s) foto(s) pela Webcam":
    foto_cam = st.camera_input("Posicione e clique em 'Take Photo'", key=f"cam_{st.session_state.cam_key}")
    col_cam1, col_cam2 = st.columns(2)
    with col_cam1:
        if foto_cam is not None:
            if st.button("➕ Adicionar esta foto à lista", use_container_width=True):
                st.session_state.fotos_webcam_temp.append(foto_cam.getvalue())
                st.session_state.cam_key += 1
                st.rerun()
    with col_cam2:
        if st.session_state.fotos_webcam_temp:
            if st.button("🗑️ Limpar fotos tiradas", use_container_width=True):
                st.session_state.fotos_webcam_temp = []
                st.rerun()

    if st.session_state.fotos_webcam_temp:
        st.success(f"📷 {len(st.session_state.fotos_webcam_temp)} foto(s) pronta(s) para enviar:")
        cols_w = st.columns(min(len(st.session_state.fotos_webcam_temp), 4))
        for idx_w, img_bytes in enumerate(st.session_state.fotos_webcam_temp):
            with cols_w[idx_w % 4]:
                st.image(img_bytes, caption=f"Foto {idx_w + 1}", width=140)

elif opcao_foto == "Fazer upload de arquivo(s)":
    novas_fotos_upload = st.file_uploader(
        "Escolha uma ou mais imagens",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key=f"up_{st.session_state.uploader_key}",
    )
    if novas_fotos_upload:
        st.success(f"📁 {len(novas_fotos_upload)} arquivo(s) selecionado(s).")

st.divider()

if st.button("💾 Salvar Registro na Nuvem", type="primary", use_container_width=True):
    if not matricula_op or not nome_op or not nome_pessoa or not cpf_pessoa or local_destino == "Selecione o local..." or not assunto_registro.strip():
        st.error("Por favor, preencha todos os campos obrigatórios (Operador, Nome, CPF, Local e Assunto).")
    else:
        with st.spinner("Enviando dados e fotos para o Google Drive..."):
            links_salvos = []
            cpf_limpo = "".join(filter(str.isdigit, cpf_pessoa))
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            if opcao_foto == "Tirar nova(s) foto(s) pela Webcam":
                lista_bytes = list(st.session_state.fotos_webcam_temp)
                if foto_cam is not None:
                    lista_bytes.append(foto_cam.getvalue())
                for i, img_bytes in enumerate(lista_bytes, start=1):
                    nome_arq = f"{cpf_limpo}_{timestamp}_cam{i}.jpg"
                    link = upload_foto_drive(img_bytes, nome_arq, "image/jpeg")
                    links_salvos.append(link)

            elif opcao_foto == "Fazer upload de arquivo(s)":
                if novas_fotos_upload:
                    for i, arq in enumerate(novas_fotos_upload, start=1):
                        ext = arq.name.split(".")[-1].lower()
                        mime = "image/png" if ext == "png" else "image/jpeg"
                        nome_arq = f"{cpf_limpo}_{timestamp}_up{i}.{ext}"
                        link = upload_foto_drive(arq.getvalue(), nome_arq, mime)
                        links_salvos.append(link)

            elif opcao_foto == "Manter foto anterior (se houver)" and st.session_state.get("foto_anterior"):
                links_salvos.append(st.session_state.foto_anterior)

            foto_final_str = " | ".join(links_salvos) if links_salvos else "Sem foto"
            veiculo_final = veiculo_pessoa.strip() if veiculo_pessoa.strip() else "Não informado"

            nova_linha = [
                data_registro.strftime("%d/%m/%Y"),
                hora_registro.strftime("%H:%M:%S"),
                tipo_movimento,
                nome_pessoa.strip(),
                cpf_pessoa.strip(),
                local_destino,
                assunto_registro.strip(),
                veiculo_final,
                plantao,
                matricula_op.strip(),
                nome_op.strip(),
                foto_final_str,
            ]

            aba_planilha.append_row(nova_linha)

            st.session_state.fotos_webcam_temp = []
            st.session_state.limpar_formulario = True
            st.toast("✅ Registro salvo na nuvem com sucesso!", icon="✅")
            st.rerun()

st.divider()
st.subheader("🔎 Histórico e Consulta de Registros Salvos")

df_atual = carregar_dados()

if not df_atual.empty:
    col_pesq1, col_pesq2 = st.columns([2, 1])
    with col_pesq1:
        termo_pesquisa = st.text_input(
            "Pesquisar por Nome, CPF, Placa, Local ou Assunto",
            placeholder="Digite para filtrar..."
        )
    with col_pesq2:
        st.write("")
        filtrar_por_data = st.checkbox("Filtrar por data")
        if filtrar_por_data:
            data_pesquisa = st.date_input("Data", value=datetime.now().date(), key="data_pesq")

    df_filtrado = df_atual.copy()

    if filtrar_por_data:
        df_filtrado = df_filtrado[df_filtrado["Data"] == data_pesquisa.strftime("%d/%m/%Y")]

    if termo_pesquisa.strip():
        termo = termo_pesquisa.strip().lower()
        mascara = df_filtrado.apply(
            lambda linha: linha.astype(str).str.lower().str.contains(termo, regex=False).any(),
            axis=1
        )
        df_filtrado = df_filtrado[mascara]

    st.write(f"**Registros encontrados:** {len(df_filtrado)}")
    st.dataframe(df_filtrado.iloc[::-1], use_container_width=True)

    if not df_filtrado.empty:
        with st.expander("🖼️ Ver foto(s) de um registro localizado"):
            opcoes_vis = [
                f"{idx} - {row['Data']} {row['Hora']} | {row['Nome']} ({row['Movimentação']})"
                for idx, row in df_filtrado.iloc[::-1].iterrows()
            ]
            selecionado = st.selectbox("Selecione o registro:", opcoes_vis)
            idx_escolhido = int(selecionado.split(" - ")[0])
            campo_fotos = str(df_filtrado.loc[idx_escolhido, "Arquivo Foto"]).strip()

            if campo_fotos and campo_fotos != "Sem foto":
                lista_links = [lnk.strip() for lnk in campo_fotos.split("|") if lnk.strip()]
                cols_fotos = st.columns(min(len(lista_links), 3))
                for idx_f, url_foto in enumerate(lista_links):
                    with cols_fotos[idx_f % 3]:
                        st.image(url_foto, caption=f"Foto {idx_f + 1}", use_container_width=True)
            else:
                st.info("Este registro não possui fotos anexadas.")
else:
    st.info("Nenhum registro encontrado na planilha até o momento.")
