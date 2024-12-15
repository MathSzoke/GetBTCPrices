import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import re
from time import sleep
import threading
import os

app = Flask(__name__)

# Configuração do Twilio
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = Client(account_sid, auth_token)

# Variável para armazenar as metas dos usuários (dicionário: número -> lista de valores)
user_targets = {}


# Função para obter a taxa de câmbio USD para BRL
def get_usd_to_brl_rate():
    url = "https://api.exchangerate-api.com/v4/latest/USD"
    response = requests.get(url)
    data = response.json()
    return data['rates']['BRL']


# Função para obter o preço do Bitcoin em USD
def get_btc_price():
    url = "https://api.binance.com/api/v3/ticker/price"
    params = {'symbol': 'BTCUSDT'}
    response = requests.get(url, params=params)
    data = response.json()
    return float(data['price'])


# Função para formatar valores com separadores de milhares
def format_currency(value):
    return f"R${value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# Função de monitoramento em background
def monitor_btc_price():
    while True:
        # Obter preço atual
        usd_to_brl_rate = get_usd_to_brl_rate()
        btc_price_usd = get_btc_price()
        btc_price_brl = btc_price_usd * usd_to_brl_rate

        print(f"Preço atual do Bitcoin: {format_currency(btc_price_brl)}")

        # Verificar todos os valores configurados pelos usuários
        for user_number, targets in list(user_targets.items()):
            for target_price in targets:
                if btc_price_brl >= target_price:
                    # Enviar mensagem
                    twilio_client.messages.create(
                        from_='whatsapp:+14155238886',
                        body=f"🚨 O Bitcoin atingiu o valor desejado de {format_currency(target_price)}! Preço atual: {format_currency(btc_price_brl)}",
                        to=user_number
                    )
                    # Remover o valor atingido da lista
                    user_targets[user_number].remove(target_price)

            # Remover o usuário caso não haja mais metas
            if not user_targets[user_number]:
                del user_targets[user_number]

        sleep(30)  # Verifica a cada 30 segundos


# Endpoint do webhook para receber mensagens do WhatsApp
@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    incoming_msg = request.values.get('Body', '').strip()
    from_number = request.values.get('From', '').strip()

    resp = MessagingResponse()
    msg = resp.message()

    # Processar mensagem do usuário
    match = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', incoming_msg)
    if match:
        price_str = match.group(1).replace('.', '').replace(',', '.')
        target_price = float(price_str)

        # Adicionar o valor ao dicionário de metas
        if from_number not in user_targets:
            user_targets[from_number] = []
        user_targets[from_number].append(target_price)

        msg.body(f"👍 Você será notificado quando o Bitcoin atingir {format_currency(target_price)}.")
    else:
        msg.body("❌ Formato inválido! Envie: 'Notificar quando o valor do Bitcoin atingir R$600.000,00'.")

    return str(resp)


if __name__ == "__main__":
    # Iniciar monitoramento em background
    monitor_thread = threading.Thread(target=monitor_btc_price, daemon=True)
    monitor_thread.start()

    port = int(os.environ.get('PORT', 2041))  # Pega a porta do Render ou usa 2041 como padrão
    app.run(host='0.0.0.0', port=port)
