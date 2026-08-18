# ETAPA 1 - CARREGAMENTO DOS DOCUMENTOS PDF

from langchain_community.document_loaders import PyPDFLoader
from pathlib import Path
import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

pasta_documentos = Path("Documentos")

arquivos_pdf = list(pasta_documentos.glob("*.pdf"))

documentos = []

for arquivo in arquivos_pdf:
    loader = PyPDFLoader(str(arquivo))
    documentos.extend(loader.load())



# ETAPA 2 - DIVISÃO DOS DOCUMENTOS EM CHUNKS

from langchain_text_splitters import RecursiveCharacterTextSplitter

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)

chunks = text_splitter.split_documents(documentos)


# ETAPA 3 - CRIAÇÃO DOS EMBEDDINGS

from langchain_huggingface import HuggingFaceEndpointEmbeddings

HF_TOKEN = os.getenv("HF_TOKEN")

embeddings_model = HuggingFaceEndpointEmbeddings(
    model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    huggingfacehub_api_token=HF_TOKEN
)

# ETAPA 4 - CRIAÇÃO DO VECTOR STORE

from langchain_core.vectorstores import InMemoryVectorStore

@st.cache_resource
def criar_vector_store(_embeddings_model, _chunks):
    vector_store = InMemoryVectorStore(_embeddings_model)
    vector_store.add_documents(_chunks)
    return vector_store

vector_store = criar_vector_store(
    embeddings_model,
    chunks
)


# CONFIGURAÇÃO DAS VARIÁVEIS DE AMBIENTE

from langchain_groq import ChatGroq

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ETAPA 5 - CONFIGURAÇÃO DO MODELO DE LINGUAGEM (LLM)

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
    groq_api_key=GROQ_API_KEY
)


# ETAPA 6 - FUNÇÃO DE RESPOSTA COM RAG

def responder_pergunta(pergunta, historico):

    historico_texto = "\n".join(
        f"{mensagem['role']}: {mensagem['content']}"
        for mensagem in historico
    )

    prompt_contextualizacao = f"""
Considere o histórico da conversa abaixo e a pergunta atual do usuário.

Reescreva a pergunta atual de forma independente e completa, mantendo
o mesmo significado.

Se a pergunta atual já for independente e não depender do histórico,
mantenha-a como está.

HISTÓRICO:
{historico_texto}

PERGUNTA ATUAL:
{pergunta}
"""

    pergunta_contextualizada = llm.invoke(prompt_contextualizacao).content
    
    retriever = vector_store.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": 10,
            "fetch_k": 20
    }
)
    documentos_relevantes = retriever.invoke(
        pergunta_contextualizada
)

    
    contexto = "\n\n".join(
        documento.page_content
        for documento in documentos_relevantes
    )

    prompt = f"""
    Você é o assistente virtual da Clínica Veterinária PetCare.

    Responda à pergunta do usuário utilizando APENAS as informações
    presentes no contexto abaixo.

    Se a resposta não estiver presente no contexto, informe que não encontrou
    essa informação nos documentos da Clínica Veterinária PetCare.

    Não invente valores, horários, serviços ou políticas.

    CONTEXTO:
    {contexto}

    PERGUNTA:
    {pergunta}

    Responda em português, de forma clara e objetiva.
    """

    resposta = llm.invoke(prompt)

    return resposta.content



# ETAPA 7 - INTERFACE COM STREAMLIT


st.set_page_config(
    page_title="Clínica Veterinária PetCare",
    page_icon="🐾",
    layout="centered"
)

st.title("🐾 Clínica Veterinária PetCare")

st.write(
    "Olá! Sou o assistente virtual da Clínica Veterinária PetCare. "
    "Como posso te ajudar hoje?"
)

with st.sidebar:
    st.header("🐾 PetCare")

    st.write(
        "Assistente virtual para dúvidas sobre serviços, valores, "
        "vacinação, exames, horários e políticas da clínica."
    )

    st.divider()

    st.write("**Atendimento**")
    st.write("Segunda a sexta: 08h às 20h")
    st.write("Sábado: 08h às 16h")

    st.divider()

    st.write("**Contato**")
    st.write("📞 (11) 3456-7890")
    st.write("📱 (11) 99876-5432")

st.info(
    "💡 Você pode perguntar sobre valores de consultas e vacinas, "
    "horários, formas de pagamento, serviços e agendamentos."
)

st.write("**Sugestões de perguntas:**")

col1, col2, col3 = st.columns(3)

pergunta_sugerida = None

with col1:
    if st.button("💉 Quanto custa a vacina V10?"):
        pergunta_sugerida = "Quanto custa a vacina V10?"

with col2:
    if st.button("🕐 Qual o horário de funcionamento?"):
        pergunta_sugerida = "Qual o horário de funcionamento?"

with col3:
    if st.button("💳 Quais são as formas de pagamento?"):
        pergunta_sugerida = "Quais são as formas de pagamento?"


# Cria o histórico de mensagens caso ele ainda não exista

if "mensagens" not in st.session_state:
    st.session_state.mensagens = []


# Exibe as mensagens que já estão no histórico

for mensagem in st.session_state.mensagens:

    avatar = "👤" if mensagem["role"] == "user" else "🐾"

    with st.chat_message(mensagem["role"], avatar=avatar):
        st.write(mensagem["content"])

# Botão para limpar o histórico da conversa

if st.session_state.mensagens:
    if st.button("🗑️ Limpar conversa"):
        st.session_state.mensagens = []
        st.rerun()

# Campo para o usuário digitar a pergunta

pergunta_digitada = st.chat_input(
    "Digite sua pergunta sobre a Clínica PetCare"
)

pergunta = pergunta_sugerida or pergunta_digitada

# Processa a pergunta do usuário

if pergunta:

    with st.chat_message("user", avatar="👤"):
        st.write(pergunta)

    resposta = responder_pergunta(
        pergunta,
        st.session_state.mensagens
    )

    st.session_state.mensagens.append({
        "role": "user",
        "content": pergunta
    })

    st.session_state.mensagens.append({
        "role": "assistant",
        "content": resposta
    })

    with st.chat_message("assistant", avatar="🐾"):
        st.write(resposta)

    st.rerun()

