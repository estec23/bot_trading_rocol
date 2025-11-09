# bot_v15_live.py - LIVE TRADING TESTNET (v15 +18.4%) - SIN VECENV, SIN ERRORES
import time, threading, requests, numpy as np, os
from binance.client import Client
from stable_baselines3 import PPO

# === CONFIGURACIÓN SEGURA ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SYMBOL = "BTCUSDT"
INITIAL_USD = 10000.0
LIVE = False

# BINANCE TESTNET
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

# Validación básica
if not all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, API_KEY, API_SECRET]):
    raise EnvironmentError("Faltan variables de entorno: TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, BINANCE_API_KEY, BINANCE_API_SECRET")

client = Client(API_KEY, API_SECRET, testnet=True)

# === ENTORNO SIMPLE (SIN GYM) ===
class SimpleEnv:
    def __init__(self):
        self.usd = INITIAL_USD
        self.btc = 0.0
        self.price = 0.0

    def reset(self):
        self.usd = INITIAL_USD
        self.btc = 0.0
        self.price = self.get_price()
        return np.array([self.price] + [0.0]*11, dtype=np.float32)

    def get_price(self):
        try:
            return float(client.get_symbol_ticker(symbol=SYMBOL)["price"])
        except Exception as e:
            print(f"Error precio: {e}")
            return 60000.0

    def step(self, action):
        self.price = self.get_price()
        act = action[0]
        if act > 0.1 and self.usd > 100:
            qty = (self.usd * act) / self.price
            self.btc += qty
            self.usd -= qty * self.price
        elif act < -0.1 and self.btc > 0.0001:
            qty = self.btc * (-act)
            self.usd += qty * self.price
            self.btc -= qty
        net = self.usd + self.btc * self.price
        reward = (net - INITIAL_USD) / INITIAL_USD
        return np.array([self.price] + [0.0]*11, dtype=np.float32), reward, False, False, {}

# === CARGAR MODELO ===
env = SimpleEnv()
try:
    model = PPO.load("models/MEJOR_MODELO.zip")
except Exception as e:
    raise FileNotFoundError(f"No se pudo cargar el modelo: {e}")

# Variables globales para /status
last_action = "N/A"
steps = 0
start_time = time.time()

# === TELEGRAM ===
def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
            timeout=10
        )
    except Exception as e:
        print(f"Error Telegram send: {e}")

def telegram():
    global LIVE
    last_update_id = None
    while True:
        try:
            params = {"offset": last_update_id + 1 if last_update_id else None, "timeout": 10}
            r = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params=params,
                timeout=15
            ).json()

            for update in r.get("result", []):
                last_update_id = update["update_id"]
                message = update.get("message", {})
                text = message.get("text", "").strip().lower()

                if text == "/start_live":
                    LIVE = True
                    send("LIVE INICIADO (v15 +18.4%)")
                elif text == "/stop_live":
                    LIVE = False
                    send("DETENIDO")
                elif text == "/balance":
                    net = env.usd + env.btc * env.price
                    send(f"USD: ${env.usd:.2f}\nBTC: {env.btc:.6f}\nPrecio: ${env.price:,.2f}\nNet: ${net:.2f}")
                elif text == "/status":
                    uptime = time.strftime("%H:%M:%S", time.gmtime(time.time() - start_time))
                    send(f"Estado: {'LIVE' if LIVE else 'STOP'}\nÚltima acción: {last_action}\nPasos: {steps}\nUptime: {uptime}")
                elif text == "/menu":
                    menu = (
                        "BOT TRADING v15\n\n"
                        "/start_live → Iniciar\n"
                        "/stop_live → Detener\n"
                        "/balance → Saldo\n"
                        "/status → Estado\n"
                        "/menu → Este menú"
                    )
                    send(menu)
        except Exception as e:
            print(f"Error Telegram loop: {e}")
        time.sleep(2)

# === LIVE LOOP ===
def live_loop():
    global last_action, steps, start_time
    start_time = time.time()
    steps = 0
    last_action = "N/A"
    obs = env.reset()
    send("Bot v15 LIVE listo. Usa /menu")
    while True:
        if LIVE:
            action, _ = model.predict(obs, deterministic=True)
            obs, _, _, _, _ = env.step(action)
            act_val = action[0]
            if act_val > 0.1:
                last_action = f"COMPRA {act_val:.2f}"
            elif act_val < -0.1:
                last_action = f"VENTA {act_val:.2f}"
            else:
                last_action = "HOLD"
            steps += 1
        time.sleep(60)

# === INICIAR ===
if __name__ == "__main__":
    threading.Thread(target=telegram, daemon=True).start()
    live_loop()