import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import threading
import time
import os
import re
import logging

# Configuração do logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configurações Twilio
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_client = Client(account_sid, auth_token)

# Variáveis globais
btc_prices = []
notifications = {}
user_settings = {}


# ==================== FUNÇÕES AUXILIARES =====================
# Função para obter o preço do Bitcoin
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
    twilio_client.messages.create(from_="whatsapp:+14155238886", body=body, to=to)


# Função para gerar respostas usando o servidor LLaMA 2
def generate_llama_response(user_message):
    try:
        logger.info(f"Enviando mensagem para LLaMA: {user_message}")  # Log da mensagem enviada
        response = requests.post(
            f"http://localhost:{os.environ.get('PORT', 8000)}/generate",
            json={"message": user_message},
            timeout=10
        )
        logger.debug(f"Status da resposta: {response.status_code}")
        logger.debug(f"Resposta do servidor: {response.text}")

        if response.status_code == 200:
            llama_response = response.json().get("response", "Sem resposta.")
            logger.info(f"Resposta gerada pelo LLaMA: {llama_response}")
            return llama_response
        else:
            logger.error(f"Erro na resposta do LLaMA: {response.status_code} - {response.text}")
            return "❌ Erro ao gerar a resposta. Tente novamente."
    except Exception as e:
        logger.error(f"Falha na comunicação com o servidor FastAPI: {e}")
        return "❌ Erro ao processar sua solicitação. Tente novamente."



# ==================== MONITORAMENTO DO BITCOIN =====================
def monitor_btc():
    while True:
        current_price = get_btc_price()
        if current_price:
            for user, targets in notifications.items():
                if "above" in targets and current_price >= targets["above"]:
                    response_text = f"O Bitcoin atingiu R${targets['above']:.2f}. Preço atual: R${current_price:.2f}."
                    send_whatsapp_message(user, response_text)
                    del notifications[user]["above"]
                if "below" in targets and current_price <= targets["below"]:
                    response_text = f"O Bitcoin caiu para R${targets['below']:.2f}. Preço atual: R${current_price:.2f}."
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

    # Notificações
    above_match = re.search(r"atingir\s*(\d+)", incoming_msg)
    below_match = re.search(r"abaixar\s*para\s*(\d+)", incoming_msg)

    if above_match:
        target = float(above_match.group(1))
        notifications.setdefault(from_number, {})["above"] = target
        msg.body(f"👍 Notificação configurada para quando o Bitcoin atingir R${target:.2f}.")
        return str(resp)

    if below_match:
        target = float(below_match.group(1))
        notifications.setdefault(from_number, {})["below"] = target
        msg.body(f"👍 Notificação configurada para quando o Bitcoin cair para R${target:.2f}.")
        return str(resp)

    # Respostas pelo LLaMA 2
    response_text = generate_llama2_response(incoming_msg)
    msg.body(response_text)
    return str(resp)


# ========================= INICIALIZAÇÃO ==============================
if __name__ == "__main__":
    threading.Thread(target=monitor_btc, daemon=True).start()
    port = int(os.environ.get("PORT", 2041))
    app.run(host="0.0.0.0", port=port)
