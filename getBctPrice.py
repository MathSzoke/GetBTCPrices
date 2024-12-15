import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import threading
import time
import os
from datetime import datetime, timedelta

app = Flask(__name__)

# Configuração do Twilio
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = Client(account_sid, auth_token)

# Variáveis globais
btc_prices = []  # Armazena os preços do Bitcoin para tendência de mercado
daily_summary = {}  # Armazena os dados de resumo diário
subscribed_users = set()  # Armazena os números dos usuários que recebem o resumo diário


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


# Função para calcular a média móvel simples
def calculate_simple_moving_average(prices):
    return sum(prices) / len(prices) if prices else 0


# Função para atualizar o resumo diário
def update_daily_summary():
    while True:
        price = get_btc_price()
        if price:
            if "max" not in daily_summary or price > daily_summary["max"]:
                daily_summary["max"] = price
            if "min" not in daily_summary or price < daily_summary["min"]:
                daily_summary["min"] = price
            daily_summary["current"] = price

            # Atualizar histórico de preços
            btc_prices.append(price)
            if len(btc_prices) > 10:  # Mantém apenas os últimos 10 preços
                btc_prices.pop(0)
        time.sleep(60)  # Atualiza a cada minuto


# Função para formatar o resumo diário
def get_daily_summary():
    if not daily_summary:
        return "❌ Resumo diário ainda não disponível. Tente novamente mais tarde."
    max_price = daily_summary.get("max", 0)
    min_price = daily_summary.get("min", 0)
    current_price = daily_summary.get("current", 0)
    variation = ((current_price - min_price) / min_price) * 100 if min_price else 0

    return (
        "🔔 Resumo Diário do Bitcoin:\n\n"
        f"💰 Preço atual: ${current_price:,.2f}\n"
        f"📈 Máximo: ${max_price:,.2f}\n"
        f"📉 Mínimo: ${min_price:,.2f}\n"
        f"📊 Variação: {variation:.2f}%"
    )


# Função para enviar mensagem no WhatsApp
def send_whatsapp_message(to, body):
    twilio_client.messages.create(
        from_="whatsapp:+14155238886",
        body=body,
        to=to
    )


# Função para agendar envio automático do resumo diário
def schedule_daily_summary():
    while True:
        now = datetime.now()
        next_midnight = datetime.combine(now + timedelta(days=1), datetime.min.time())
        seconds_until_midnight = (next_midnight - now).total_seconds()
        print(f"🕛 Aguardando {seconds_until_midnight:.0f} segundos até o envio do resumo diário...")
        time.sleep(seconds_until_midnight)

        # Enviar resumo diário para todos os usuários inscritos
        summary = get_daily_summary()
        for user in subscribed_users:
            send_whatsapp_message(user, summary)
        print("✅ Resumo diário enviado!")


# Endpoint principal do WhatsApp
@app.route("/whatsapp", methods=['POST'])
def whatsapp():
    incoming_msg = request.values.get('Body', '').strip().lower()
    from_number = request.values.get('From', '').strip()

    resp = MessagingResponse()
    msg = resp.message()

    # Comando: Resumo diário
    if "resumo diário" in incoming_msg:
        summary = get_daily_summary()
        msg.body(summary)

    # Comando: Tendência de mercado
    elif "tendência do mercado" in incoming_msg:
        if len(btc_prices) < 2:
            msg.body("❌ Não há dados suficientes para determinar a tendência do mercado.")
        else:
            current_price = btc_prices[-1]
            moving_average = calculate_simple_moving_average(btc_prices)
            if current_price > moving_average:
                msg.body(f"📈 Tendência de alta! Preço atual: ${current_price:,.2f}, acima da média de ${moving_average:,.2f}.")
            else:
                msg.body(f"📉 Tendência de baixa! Preço atual: ${current_price:,.2f}, abaixo da média de ${moving_average:,.2f}.")

    # Comando: Inscrever no resumo diário
    elif "inscrever resumo" in incoming_msg:
        subscribed_users.add(from_number)
        msg.body("✅ Você foi inscrito no resumo diário do Bitcoin! Aguarde o envio automático toda meia-noite.")

    # Comando padrão
    else:
        msg.body("❌ Comando não reconhecido. Tente:\n"
                 "- 'Resumo diário'\n"
                 "- 'Tendência do mercado'\n"
                 "- 'Inscrever resumo' (para receber o resumo diário automaticamente)")

    return str(resp)


# Iniciar monitoramento e agendamento em threads separadas
if __name__ == "__main__":
    summary_thread = threading.Thread(target=update_daily_summary, daemon=True)
    schedule_thread = threading.Thread(target=schedule_daily_summary, daemon=True)
    summary_thread.start()
    schedule_thread.start()

    port = int(os.environ.get('PORT', 2041))
    app.run(host='0.0.0.0', port=port)