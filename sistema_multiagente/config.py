import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

# 1. Carrega as variáveis do arquivo .env para o ambiente
load_dotenv()

if not os.getenv("GOOGLE_API_KEY"):
    raise ValueError("Erro: GOOGLE_API_KEY não encontrada no arquivo .env")

# 2. A biblioteca do Google já lê automaticamente a variável GOOGLE_API_KEY do ambiente!
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0
)

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004"
)