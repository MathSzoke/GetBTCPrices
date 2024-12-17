import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from openai import OpenAI
import threading
import time
import os
import re

app = Flask(__name__)

# Configurações Twilio
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_client = Client(account_sid, auth_token)

# Configuração OpenAI
openai_api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai_api_key)

# Variáveis globais
btc_prices = []  # Histórico do preço do Bitcoin
notifications = {}  # Notificações configuradas: {"user_number": {"above": valor, "below": valor}}
user_settings = {}  # Configurações do usuário {"user_number": {"name": "nome", "response_type": "curta"}}


# ======================== FUNÇÕES AUXILIARES ==========================

# Função para obter o preço atual do Bitcoin em USD
def get_btc_price():
    try:
        url = "https://api.binance.com/api/v3/ticker/price"
        response = requests.get(url, params={"symbol": "BTCUSDT"}, timeout=5)
        response.raise_for_status()
        data = response.json()
        return float(data.get("price"))
    except Exception:
        return None


# Função para enviar mensagens no WhatsApp
def send_whatsapp_message(to, body):
    twilio_client.messages.create(
        from_="whatsapp:+14155238886",
        body=body,
        to=to
    )


# Função para gerar mensagens usando a API do ChatGPT
def generate_chatgpt_response(user_message, user_number):
    user_name = user_settings.get(user_number, {}).get("name", "usuário")
    response_type = user_settings.get(user_number, {}).get("response_type", "curta")

    prompt = f"""
    Você é um assistente para um bot de WhatsApp focado em informações sobre o Bitcoin.
    O usuário se chama '{user_name}' e prefere mensagens '{response_type}'.
    A mensagem do usuário foi: '{user_message}'.
    Responda de forma natural, com base nas informações que o bot pode obter, como preço do Bitcoin e outras funcionalidades.
    """

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_message}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()


# Função para monitorar notificações de preço do Bitcoin
def monitor_btc():
    while True:
        current_price = get_btc_price()
        if current_price:
            for user, targets in notifications.items():
                if "above" in targets and current_price >= targets["above"]:
                    response_text = generate_chatgpt_response(
                        f"O Bitcoin atingiu R${targets['above']:.2f}. Preço atual: R${current_price:.2f}.",
                        user
                    )
                    send_whatsapp_message(user, response_text)
                    del notifications[user]["above"]

                if "below" in targets and current_price <= targets["below"]:
                    response_text = generate_chatgpt_response(
                        f"O Bitcoin caiu para R${targets['below']:.2f}. Preço atual: R${current_price:.2f}.",
                        user
                    )
                    send_whatsapp_message(user, response_text)
                    del notifications[user]["below"]
        time.sleep(30)


# ======================== ENDPOINT DO WHATSAPP ========================

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming_msg = request.values.get("Body", "").strip()
    from_number = request.values.get("From", "").strip()

    resp = MessagingResponse()
    msg = resp.message()

    # Verificar se é configuração inicial
    if "configurar" in incoming_msg.lower():
        user_settings[from_number] = {"name": "Usuário", "response_type": "curta"}
        msg.body("🛠 Vamos configurar sua experiência!\n\nComo você gostaria que eu chamasse você?")
        return str(resp)

    elif from_number in user_settings and "name" not in user_settings[from_number]:
        user_settings[from_number]["name"] = incoming_msg
        msg.body(f"Ótimo, {incoming_msg}! Você prefere mensagens 'curtas' ou 'longas'?")
        return str(resp)

    elif from_number in user_settings and "response_type" not in user_settings[from_number]:
        response_type = "curta" if "curta" in incoming_msg.lower() else "longa"
        user_settings[from_number]["response_type"] = response_type
        msg.body("✅ Configuração concluída! Agora você pode me enviar comandos como:\n"
                 "- 'Qual o preço do Bitcoin?'\n"
                 "- 'Me avise quando o Bitcoin atingir 200 mil.'")
        return str(resp)

    # Detectar metas de notificação
    above_match = re.search(r"atingir\s*(\d+)", incoming_msg)
    below_match = re.search(r"abaixar\s*para\s*(\d+)", incoming_msg)

    if above_match:
        target = float(above_match.group(1))
        notifications.setdefault(from_number, {})["above"] = target
        msg.body(f"👍 Notificação configurada para quando o Bitcoin atingir R${target:.2f}.")
        return str(resp)

    elif below_match:
        target = float(below_match.group(1))
        notifications.setdefault(from_number, {})["below"] = target
        msg.body(f"👍 Notificação configurada para quando o Bitcoin cair para R${target:.2f}.")
        return str(resp)

    # Responder usando o ChatGPT
    response_text = generate_chatgpt_response(incoming_msg, from_number)
    msg.body(response_text)
    return str(resp)


# ========================= INICIALIZAÇÃO ==============================

if __name__ == "__main__":
    threading.Thread(target=monitor_btc, daemon=True).start()
    port = int(os.environ.get("PORT", 2041))
    app.run(host="0.0.0.0", port=port)
