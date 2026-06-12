from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from config import SYSTEM_INSTRUCTION
import os

app = Flask(__name__)
CORS(app)

# Inicializa o cliente do Gemini. 
# Ele busca automaticamente a variável de ambiente GEMINI_API_KEY.
# Se preferir passar direto, use: client = genai.Client(api_key="SUA_CHAVE")
client = genai.Client()

# Armazena histórico por sessão: { session_id: [mensagens_no_formato_gemini] }
sessions = {}

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()

    if not data or "message" not in data:
        return jsonify({"error": "Campo 'message' é obrigatório."}), 400

    user_message = data["message"].strip()
    session_id = data.get("session_id", "default")

    if not user_message:
        return jsonify({"error": "Mensagem não pode ser vazia."}), 400

    # Inicializa a sessão se não existir
    if session_id not in sessions:
        sessions[session_id] = []

    # O Gemini espera a estrutura com 'role' e 'parts'
    sessions[session_id].append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)]
        )
    )

    try:
        # Configuração do sistema e parâmetros
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            max_output_tokens=1024,
            # Você pode adicionar temperature=0.7 aqui se quiser mais criatividade
        )

        # Chamada da API usando o modelo mais rápido, eficiente e com cota gratuita
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=sessions[session_id],
            config=config,
        )

        assistant_message = response.text

        # Salva a resposta do assistente no histórico da sessão
        sessions[session_id].append(
            types.Content(
                role="model",  # O Gemini usa "model" em vez de "assistant"
                parts=[types.Part.from_text(text=assistant_message)]
            )
        )

        return jsonify({
            "session_id": session_id,
            "response": assistant_message,
        })

    except Exception as e:
        return jsonify({"error": f"Erro na API do Gemini: {str(e)}"}, 500)


@app.route("/reset", methods=["POST"])
def reset():
    data = request.get_json()
    session_id = data.get("session_id", "default") if data else "default"

    sessions.pop(session_id, None)
    return jsonify({"message": f"Sessão '{session_id}' encerrada."})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bot": "Debatedor Filosófico"})


if __name__ == "__main__":
    app = app