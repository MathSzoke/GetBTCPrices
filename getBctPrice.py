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

# Função para obter o preço do Bitcoin em USD com tratamento de erro
def get_btc_price():
    try:
        url = "https://api.binance.com/api/v3/ticker/price"
        response = requests.get(url, params={"symbol": "BTCUSDT"}, timeout=5)
        response.raise_for_status()  # Lança um erro se o status HTTP não for 200

        # Verificando o conteúdo da resposta
        data = response.json()
        print(f"[DEBUG] Resposta da API Binance: {data}")  # Log para depuração

        # Validando se a chave 'price' existe
        if "price" in data:
            price = float(data["price"])
            print(f"[INFO] Preço do BTC em USD: {price}")
            return price
        else:
            print("[ERRO] Chave 'price' não encontrada na resposta da Binance.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"[ERRO] Falha na requisição HTTP para Binance: {e}")
        return None
    except ValueError as ve:
        print(f"[ERRO] Falha ao converter resposta da Binance: {ve}")
        return None


# Função para obter taxas de câmbio USD -> outras moedas com tratamento de erro
def get_exchange_rates():
    try:
        url = "https://api.exchangerate-api.com/v4/latest/USD"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        rates = data.get("rates", {})
        if rates:
            print(f"[INFO] Taxas de câmbio obtidas: {rates}")  # Log para depuração
            return {
                "BRL": rates.get("BRL"),
                "EUR": rates.get("EUR"),
                "CAD": rates.get("CAD")
            }
        else:
            print("[ERRO] Nenhuma taxa de câmbio encontrada na resposta.")
            return None
    except Exception as e:
        print(f"[ERRO] Falha ao buscar taxas de câmbio: {e}")
        return None


# Função para obter o preço do Bitcoin em diversas moedas
def get_btc_prices_in_currencies():
    print("[DEBUG] Iniciando get_btc_prices_in_currencies...")  # Verifica se a função é chamada

    btc_usd = get_btc_price()
    print(f"[DEBUG] Retorno de get_btc_price: {btc_usd}")  # Log do retorno da função get_btc_price

    exchange_rates = get_exchange_rates()
    print(f"[DEBUG] Retorno de get_exchange_rates: {exchange_rates}")  # Log do retorno de taxas de câmbio

    if btc_usd is None:  # Teste explícito para None
        print("[ERRO] btc_usd é None. Problema na API da Binance ou na função get_btc_price.")
        return "❌ Erro ao obter o preço do Bitcoin em USD. Tente novamente mais tarde."

    if exchange_rates is None:  # Teste explícito para dicionário vazio
        print("[ERRO] exchange_rates está vazio. Problema na API de taxas de câmbio.")
        return "❌ Erro ao obter as taxas de câmbio. Tente novamente mais tarde."

    try:
        btc_prices = {
            "USD": btc_usd,
            "BRL": btc_usd * exchange_rates.get("BRL", 0),
            "EUR": btc_usd * exchange_rates.get("EUR", 0),
            "CAD": btc_usd * exchange_rates.get("CAD", 0)
        }

        print(f"[INFO] Preços calculados: {btc_prices}")  # Log dos preços calculados

        return (
            "💰 Valor atual do Bitcoin:\n\n"
            f"🇺🇸 USD: ${btc_prices['USD']:,.2f}\n"
            f"🇧🇷 BRL: R${btc_prices['BRL']:,.2f}\n"
            f"🇪🇺 EUR: €{btc_prices['EUR']:,.2f}\n"
            f"🇨🇦 CAD: C${btc_prices['CAD']:,.2f}"
        ).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception as e:
        print(f"[ERRO] Falha ao calcular os preços em outras moedas: {e}")
        return "❌ Erro ao calcular os preços do Bitcoin. Tente novamente mais tarde."



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


# Função para processar valores simplificados (650mil, 650k)
def parse_price(value):
    match = re.match(r"(\d+)\s*(mil|k)?", value, re.IGNORECASE)
    if match:
        base_value = int(match.group(1))
        if match.group(2):  # 'mil' ou 'k' presente
            base_value *= 1000
        return base_value
    return None


# ====================== DICIONÁRIO DE COMANDOS =========================

COMMANDS = {
    "resumo diário": get_daily_summary,
    "tendência do mercado": get_market_trend,
    "inscrever resumo": subscribe_summary,
    "notificar": configure_notification,
    "informe o valor do bitcoin": get_btc_prices_in_currencies,
    "valor do bitcoin": get_btc_prices_in_currencies,
    "preço do bitcoin": get_btc_prices_in_currencies
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
        if re.search(cmd, incoming_msg):
            if cmd == "notificar":
                response_text = func(incoming_msg, from_number)
            else:
                response_text = func()
            msg.body(response_text)
            return str(resp)

    # Comando desconhecido
    msg.body("❌ Comando não reconhecido. Tente:\n"
             "- 'Informe o valor do Bitcoin'\n"
             "- 'Resumo diário'\n"
             "- 'Tendência do mercado'\n"
             "- 'Inscrever resumo'")
    return str(resp)


# ========================= INICIALIZAÇÃO ==============================

if __name__ == "__main__":
    threading.Thread(target=monitor_btc, daemon=True).start()
    port = int(os.environ.get("PORT", 2041))
    app.run(host="0.0.0.0", port=port)
