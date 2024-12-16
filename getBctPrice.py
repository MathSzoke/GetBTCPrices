import requests
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import threading
import time
import os
import re
from datetime import datetime, timedelta

app = Flask(__name__)

# Configuração do Twilio
account_sid = os.getenv('TWILIO_ACCOUNT_SID')
auth_token = os.getenv('TWILIO_AUTH_TOKEN')
twilio_client = Client(account_sid, auth_token)

# Variáveis globais
btc_prices = []  # Preços do Bitcoin para média móvel
daily_summary = {}  # Dados do resumo diário
user_above_targets = {}  # Notificações de alta
user_below_targets = {}  # Notificações de baixa
subscribed_users = set()  # Usuários inscritos no resumo diário


# ========================= FUNÇÕES AUXILIARES ==========================

# Função para obter o preço do Bitcoin em USD
def get_btc_price():
    url = "https://api.binance.com/api/v3/ticker/price"
    response = requests.get(url, params={"symbol": "BTCUSDT"})
    data = response.json()
    return float(data["price"]) if "price" in data else None

# Função para processar valores simplificados (650mil, 650k)
def parse_price(value):
    match = re.match(r"(\d+)\s*(mil|k)?", value, re.IGNORECASE)
    if match:
        base_value = int(match.group(1))
        if match.group(2):  # 'mil' ou 'k' presente
            base_value *= 1000
        return base_value
    return None

# Função para formatar valores como moeda
def format_currency(value):
    return f"R${value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Resumo diário
def get_daily_summary():
    if not daily_summary:
        return "❌ Resumo diário ainda não disponível."
    max_price = daily_summary.get("max", 0)
    min_price = daily_summary.get("min", 0)
    current_price = daily_summary.get("current", 0)
    variation = ((current_price - min_price) / min_price) * 100 if min_price else 0
    return (
        "🔔 Resumo Diário do Bitcoin:\n\n"
        f"💰 Preço atual: {format_currency(current_price)}\n"
        f"📈 Máximo: {format_currency(max_price)}\n"
        f"📉 Mínimo: {format_currency(min_price)}\n"
        f"📊 Variação: {variation:.2f}%"
    )

# Tendência do mercado
def get_market_trend():
    if len(btc_prices) < 2:
        return "❌ Não há dados suficientes para tendência do mercado."
    moving_avg = sum(btc_prices) / len(btc_prices)
    current_price = btc_prices[-1]
    trend = "📈 Alta" if current_price > moving_avg else "📉 Baixa"
    return f"{trend}! Preço atual: {format_currency(current_price)} | Média: {format_currency(moving_avg)}"

# Notificar metas de preço
def configure_notification(command, user_number):
    above_match = re.search(r"atingir\s+(\S+)", command)
    below_match = re.search(r"abaixar\s+para\s+(\S+)", command)

    if above_match:
        price = parse_price(above_match.group(1))
        if price:
            user_above_targets.setdefault(user_number, []).append(price)
            return f"👍 Notificação configurada! Avisa quando o Bitcoin atingir {format_currency(price)}."
    elif below_match:
        price = parse_price(below_match.group(1))
        if price:
            user_below_targets.setdefault(user_number, []).append(price)
            return f"👍 Notificação configurada! Avisa quando o Bitcoin abaixar para {format_currency(price)}."
    return "❌ Valor inválido. Use: '650mil' ou '650k'."

# Inscrever resumo diário
def subscribe_summary(user_number):
    subscribed_users.add(user_number)
    return "✅ Você foi inscrito no resumo diário do Bitcoin!"

# ====================== DICIONÁRIO DE COMANDOS =========================

COMMANDS = {
    "resumo diário": get_daily_summary,
    "tendência do mercado": get_market_trend,
    "inscrever resumo": subscribe_summary,
    "notificar": configure_notification
}

# ========================= SISTEMA DE MONITORAMENTO ====================

# Monitorar preço do Bitcoin
def monitor_btc():
    while True:
        price = get_btc_price()
        if price:
            daily_summary.setdefault("max", price)
            daily_summary.setdefault("min", price)
            daily_summary["current"] = price
            daily_summary["max"] = max(daily_summary["max"], price)
            daily_summary["min"] = min(daily_summary["min"], price)
            btc_prices.append(price)
            if len(btc_prices) > 10:
                btc_prices.pop(0)
        time.sleep(60)

# ========================= ENDPOINT DO WHATSAPP =======================

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    incoming_msg = request.values.get("Body", "").strip().lower()
    from_number = request.values.get("From", "").strip()

    resp = MessagingResponse()
    msg = resp.message()

    # Iterar pelos comandos no dicionário
    for cmd, func in COMMANDS.items():
        if cmd in incoming_msg:
            if cmd == "notificar":
                response_text = func(incoming_msg, from_number)
            else:
                response_text = func(from_number)
            msg.body(response_text)
            return str(resp)

    # Comando desconhecido
    msg.body("❌ Comando não reconhecido. Tente:\n- 'Resumo diário'\n- 'Tendência do mercado'\n- 'Inscrever resumo'")
    return str(resp)

# ========================= INICIALIZAÇÃO ==============================

if __name__ == "__main__":
    threading.Thread(target=monitor_btc, daemon=True).start()
    port = int(os.environ.get("PORT", 2041))
    app.run(host="0.0.0.0", port=port)
