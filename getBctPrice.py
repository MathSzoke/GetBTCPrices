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

# Variáveis para armazenar metas e estados do usuário
user_targets = {}  # Metas de preço (dicionário: número -> lista de valores)
user_state = {}    # Estado da conversa (dicionário: número -> estado)


# Função para obter a taxa de câmbio USD para outra moeda
def get_btc_price():
    try:
        url = "https://api.binance.com/api/v3/ticker/price"
        params = {'symbol': 'BTCUSDT'}
        response = requests.get(url)
        data = response.json()

        if 'price' in data:
            return float(data['price'])
        else:
            print(f"Erro: Chave 'price' não encontrada na resposta da API Binance: {data}")
            return None
    except Exception as e:
        print(f"Erro ao obter o preço do Bitcoin: {e}")
        return None


def get_exchange_rate(target_currency):
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url)
        data = response.json()

        rates = data.get("rates", {})
        if target_currency.upper() in rates:
            return rates[target_currency.upper()]
        else:
            print(f"Erro: Taxa de câmbio para {target_currency} não encontrada. Resposta: {data}")
            return None
    except Exception as e:
        print(f"Erro ao obter a taxa de câmbio: {e}")
        return None


# Função para formatar valores com separadores de milhares
def format_currency(value, currency_symbol):
    return f"{currency_symbol}{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Endpoint do webhook para receber mensagens do WhatsApp
@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    incoming_msg = request.values.get('Body', '').strip().lower()
    from_number = request.values.get('From', '').strip()

    resp = MessagingResponse()
    msg = resp.message()

    # Verificar o estado da conversa do usuário
    if from_number in user_state:
        state = user_state[from_number]

        # Estado: usuário escolheu "Outro" e precisa informar a moeda
        if state == "custom_currency":
            currency = incoming_msg.upper()
            exchange_rate = get_exchange_rate(currency)
            if exchange_rate:
                btc_price_usd = get_btc_price()
                btc_price = btc_price_usd * exchange_rate
                msg.body(f"💰 O preço atual do Bitcoin em {currency} é {format_currency(btc_price, '')}.")
            else:
                msg.body(f"❌ Moeda '{currency}' não encontrada. Verifique o código e tente novamente.")

            del user_state[from_number]
            return str(resp)

        # Estado: usuário escolheu uma opção numérica
        elif state == "choose_currency":
            match incoming_msg:
                case "1":
                    currency = "BRL"
                    symbol = "R$"
                case "2":
                    currency = "USD"
                    symbol = "$"
                case "3":
                    currency = "CAD"
                    symbol = "C$"
                case "4":
                    msg.body("E qual moeda você deseja? Por favor, digite a abreviação da moeda, por exemplo: 'CAD'.")
                    user_state[from_number] = "custom_currency"
                    return str(resp)
                case _:
                    msg.body("❌ Opção inválida! Digite um número entre 1 e 4.")
                    return str(resp)

            # Obter valor do Bitcoin na moeda escolhida
            exchange_rate = get_exchange_rate(currency)
            btc_price_usd = get_btc_price()

            if exchange_rate and btc_price_usd:
                btc_price = btc_price_usd * exchange_rate
                msg.body(f"💰 O preço atual do Bitcoin em {currency} é {format_currency(btc_price, symbol)}.")
            else:
                msg.body("❌ Não foi possível obter o preço do Bitcoin ou a taxa de câmbio no momento.")

            del user_state[from_number]
            return str(resp)

    # Comandos principais
    if "informe o valor do bitcoin" in incoming_msg:
        user_state[from_number] = "choose_currency"
        msg.body("Qual moeda você deseja ver o valor do Bitcoin?\n1 - Reais\n2 - USD\n3 - CAD\n4 - Outro (informar)")

    elif re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', incoming_msg):
        price_str = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', incoming_msg).group(1)
        target_price = float(price_str.replace('.', '').replace(',', '.'))
        if from_number not in user_targets:
            user_targets[from_number] = []
        user_targets[from_number].append(target_price)
        msg.body(f"👍 Você será notificado quando o Bitcoin atingir {format_currency(target_price, 'R$')}.")

    else:
        msg.body("❌ Comando não reconhecido. Tente:\n"
                 "- 'Informe o valor do Bitcoin'\n"
                 "- 'Notificar quando o valor do Bitcoin atingir R$600.000,00'")

    return str(resp)


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 2041))
    app.run(host='0.0.0.0', port=port)
