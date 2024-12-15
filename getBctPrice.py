import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import re
import os

app = Flask(__name__)

# Configuração do Twilio
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = Client(account_sid, auth_token)

# Variáveis para armazenar metas e estados do usuário
user_targets = {}  # Metas de preço (dicionário: número -> lista de valores)
user_state = {}    # Estado da conversa (dicionário: número -> estado)


# Função para obter o preço do Bitcoin em USD
def get_btc_price():
    try:
        url = "https://api.binance.com/api/v3/ticker/price"
        params = {'symbol': 'BTCUSDT'}
        response = requests.get(url)
        data = response.json()

        if response.status_code == 200 and 'price' in data:
            return float(data['price'])
        else:
            print(f"Erro: Binance API retornou {data}")
            return None
    except Exception as e:
        print(f"Erro ao obter o preço do Bitcoin: {e}")
        return None


# Função para obter a taxa de câmbio USD -> Outra moeda
def get_exchange_rate(target_currency):
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url)
        data = response.json()

        if response.status_code == 200 and "rates" in data:
            rates = data["rates"]
            if target_currency.upper() in rates:
                return rates[target_currency.upper()]
            else:
                print(f"Erro: Moeda {target_currency} não encontrada. Resposta: {data}")
                return None
        else:
            print(f"Erro: ExchangeRate API retornou {data}")
            return None
    except Exception as e:
        print(f"Erro ao obter a taxa de câmbio: {e}")
        return None


# Função para formatar valores monetários
def format_currency(value, currency_symbol):
    return f"{currency_symbol}{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# Endpoint do webhook para receber mensagens do WhatsApp
@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    incoming_msg = request.values.get('Body', '').strip().lower()
    from_number = request.values.get('From', '').strip()

    resp = MessagingResponse()
    msg = resp.message()

    # Verificar o estado da conversa
    if from_number in user_state:
        state = user_state[from_number]

        # Estado: O usuário informou "Outro" e precisa enviar uma moeda
        if state == "custom_currency":
            currency = incoming_msg.upper()
            exchange_rate = get_exchange_rate(currency)
            btc_price_usd = get_btc_price()

            if exchange_rate is None:
                msg.body(f"❌ Não foi possível encontrar a taxa de câmbio para '{currency}'.")
            elif btc_price_usd is None:
                msg.body("❌ Não foi possível obter o preço do Bitcoin no momento.")
            else:
                btc_price = btc_price_usd * exchange_rate
                msg.body(f"💰 O preço atual do Bitcoin em {currency} é {format_currency(btc_price, '')}.")
            del user_state[from_number]
            return str(resp)

        # Estado: O usuário escolheu uma moeda da lista
        elif state == "choose_currency":
            match incoming_msg:
                case "1":
                    currency, symbol = "BRL", "R$"
                case "2":
                    currency, symbol = "USD", "$"
                case "3":
                    currency, symbol = "CAD", "C$"
                case "4":
                    msg.body("E qual moeda você deseja? Digite a abreviação da moeda, como 'EUR'.")
                    user_state[from_number] = "custom_currency"
                    return str(resp)
                case _:
                    msg.body("❌ Opção inválida! Digite um número entre 1 e 4.")
                    return str(resp)

            # Buscar o preço do Bitcoin e taxa de câmbio
            exchange_rate = get_exchange_rate(currency)
            btc_price_usd = get_btc_price()

            if exchange_rate is None:
                msg.body("❌ Não foi possível obter a taxa de câmbio no momento.")
            elif btc_price_usd is None:
                msg.body("❌ Não foi possível obter o preço do Bitcoin no momento.")
            else:
                btc_price = btc_price_usd * exchange_rate
                msg.body(f"💰 O preço atual do Bitcoin em {currency} é {format_currency(btc_price, symbol)}.")
            del user_state[from_number]
            return str(resp)

    # Comando principal: Solicitar o valor do Bitcoin
    if "informe o valor do bitcoin" in incoming_msg:
        user_state[from_number] = "choose_currency"
        msg.body("Qual moeda você deseja ver o valor do Bitcoin?\n1 - Reais\n2 - USD\n3 - CAD\n4 - Outro (informar)")

    # Definir alertas de preço
    elif re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', incoming_msg):
        price_str = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', incoming_msg).group(1)
        target_price = float(price_str.replace('.', '').replace(',', '.'))
        if from_number not in user_targets:
            user_targets[from_number] = []
        user_targets[from_number].append(target_price)
        msg.body(f"👍 Você será notificado quando o Bitcoin atingir {format_currency(target_price, 'R$')}.")

    # Mensagem padrão
    else:
        msg.body("❌ Comando não reconhecido. Tente:\n"
                 "- 'Informe o valor do Bitcoin'\n"
                 "- 'Notificar quando o valor do Bitcoin atingir R$600.000,00'")
    return str(resp)


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 2041))
    app.run(host='0.0.0.0', port=port)
