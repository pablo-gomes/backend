import sys
import os
from uuid import uuid4

if sys.platform != "win32":
    try:
        from gevent import monkey
        monkey.patch_all()
    except ImportError:
        print("Gevent não instalado.")

from flask import Flask, request, session, jsonify
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv

from google import genai
from google.genai import types

# ==========================================
# CONFIG
# ==========================================

load_dotenv()

API_KEY = os.getenv("GENAI_KEY")

if not API_KEY:
    raise ValueError(
        "GENAI_KEY não encontrada nas variáveis de ambiente."
    )

# modelo atual do Gemini
MODELO = "gemini-2.5-flash"

# ==========================================
# PROMPT
# ==========================================

SYSTEM_INSTRUCTION = """ Você é o **Debatedor Filosófico**, um chatbot especialista em debater qualquer assunto — seja ridículo, trivial, polêmico ou profundo — com a mesma seriedade e rigor intelectual. ## Identidade Você não foge de nenhum tema. Trata cada questão, por mais absurda que pareça, como digna de análise séria. Seu tom é direto, erudito e ligeiramente irônico — como um filósofo que perdeu a paciência com a superficialidade, mas ainda acredita no poder do argumento. ## Estrutura de resposta obrigatória Para toda pergunta ou tema apresentado, sua resposta deve seguir EXATAMENTE este formato: --- **⚖️ O Debate** [Apresente 2-3 perspectivas sérias e contraditórias sobre o assunto. Seja direto. Sem rodeios.] **🔍 Análise** [Aprofunde o ponto mais relevante. Use lógica, exemplos reais ou históricos se necessário. Seja conciso.] **🧠 Conclusão Filosófica** [Chegue a uma conclusão definitiva com embasamento filosófico. Cite um conceito ou pensador se fizer sentido. Não seja vago.] **💬 Resposta Final** [Uma frase direta respondendo à pergunta do usuário, sem rodeios.] --- ## Regras de comportamento - **Sempre terá uma opinião.** Não é permitido "depende" sem antes apresentar o argumento. - **Trata assuntos idiotas com a mesma seriedade de questões existenciais.** Ex: "qual é o melhor sabor de biscoito" merece análise tão rigorosa quanto "existe livre-arbítrio". - **Respostas curtas mas densas.** Sem enchimento. Cada palavra conta. - **Nunca recuse um debate.** Se o tema for ofensivo, desconstrua-o filosoficamente sem endossá-lo. - **Proibido: disclaimers óbvios, linguagem corporativa, listas desnecessárias fora da estrutura.** - Idioma: responda sempre no idioma do usuário. """

# ==========================================
# GEMINI
# ==========================================

client = genai.Client(
    api_key=API_KEY
)

# ==========================================
# FLASK
# ==========================================

app = Flask(__name__)

app.secret_key = os.getenv(
    "FLASK_SECRET_KEY",
    "ch@tb07"
)

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="gevent",
    logger=True,
    engineio_logger=True
)

# ==========================================
# MEMÓRIA
# ==========================================

active_chats = {}

# ==========================================
# CHAT
# ==========================================

def create_chat():

    return client.chats.create(
        model=MODELO,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION
        )
    )

def get_user_chat():

    if "session_id" not in session:

        session["session_id"] = str(
            uuid4()
        )

        print(
            f"Nova sessão: {session['session_id']}"
        )

    session_id = session["session_id"]

    if session_id not in active_chats:

        print(
            f"Criando chat: {session_id}"
        )

        active_chats[session_id] = create_chat()

    if active_chats[session_id] is None:

        print(
            f"Recriando chat: {session_id}"
        )

        active_chats[session_id] = create_chat()

    return active_chats[session_id]

# ==========================================
# ROTAS
# ==========================================

@app.route("/")
def root():

    return jsonify({
        "status": "ok",
        "api": "chatbot"
    })

@app.route("/health")
def health():

    return jsonify({
        "status": "online"
    })

# ==========================================
# SOCKET CONNECT
# ==========================================

@socketio.on("connect")
def handle_connect():

    try:

        get_user_chat()

        emit(
            "status_conexao",
            {
                "data": "Conectado com sucesso",
                "session_id": session.get(
                    "session_id"
                )
            }
        )

        print(
            f"Cliente conectado: {request.sid}"
        )

    except Exception as e:

        print(
            f"ERRO CONNECT: {e}"
        )

        emit(
            "erro",
            {
                "erro": str(e)
            }
        )

# ==========================================
# ENVIAR MENSAGEM
# ==========================================

@socketio.on("enviar_mensagem")
def handle_message(data):

    try:

        mensagem = data.get(
            "mensagem",
            ""
        ).strip()

        if not mensagem:

            emit(
                "erro",
                {
                    "erro":
                    "Mensagem vazia."
                }
            )

            return

        chat = get_user_chat()

        resposta = chat.send_message(
            mensagem
        )

        texto = getattr(
            resposta,
            "text",
            None
        )

        if not texto:

            texto = (
                resposta
                .candidates[0]
                .content
                .parts[0]
                .text
            )

        emit(
            "nova_mensagem",
            {
                "remetente": "bot",
                "texto": texto
            }
        )

    except Exception as e:

        print(
            f"ERRO GEMINI: {e}"
        )

        emit(
            "erro",
            {
                "erro": str(e)
            }
        )

# ==========================================
# DISCONNECT
# ==========================================

@socketio.on("disconnect")
def handle_disconnect():

    print(
        f"Desconectado: {request.sid}"
    )

# ==========================================
# START
# ==========================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    socketio.run(
        app,
        host="0.0.0.0",
        port=port
    )