import M5
from M5 import *
import network
import ntptime
import requests2
import socket
import time
import ujson
import gc
import ubinascii
import urandom

try:
    from hardware import MatrixKeyboard
except Exception:
    MatrixKeyboard = None

try:
    from cap import GPSCap
except Exception:
    GPSCap = None

try:
    from base import AtomicGPSV2Base
except Exception:
    AtomicGPSV2Base = None


APP_VERSION = "DeskClock 0.1.02"
CONFIG_FILE = "deskclock_cfg.json"
DEFAULT_CALLSIGN_HOST = "172.20.10.2"
DEFAULT_CONFIG = {
    "wifi_ssid": "",
    "wifi_password": "",
    "city_name": "Sanya",
    "fixed_latitude": 18.12345,
    "fixed_longitude": 109.12345,
    "gps_enabled": False,
    "brightness_index": 0,
    "callsign_host": DEFAULT_CALLSIGN_HOST,
}
LOCAL_UTC_OFFSET_HOURS = 8
WEATHER_REFRESH_MS = 15 * 60 * 1000
CLOCK_REFRESH_MS = 1000
NETWORK_WAIT_MS = 12000
GPS_WAIT_MS = 2000
INPUT_POLL_MS = 30
HTTP_TIMEOUT_S = 8
COLOR_BG = 0x000000
COLOR_FG = 0x6EA536
COLOR_CALL = 0xFF4040
COLOR_DIM = 0x3C6321
COLOR_PANEL = 0x101010
COLOR_HL = 0x1D3410
COLOR_HL_TEXT = 0xD4F1A4
NTP_HOST = "pool.ntp.org"
DATE_RIGHT_EDGE_X = 228
DATE_Y = 8
WEEKDAY_Y = 22
BRIGHTNESS_LEVELS = (100, 75, 50, 25)
BRIGHTNESS_LABELS = ("100%", "75%", "50%", "25%")
WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&current=temperature_2m"
    "&daily=sunrise,sunset"
    "&timezone=auto"
)
CALLSIGN_HOST_CANDIDATES = (
    DEFAULT_CALLSIGN_HOST,
    "192.168.31.139",
    "fmo.local",
    "192.168.31.207",
)
CALLSIGN_PORT = 80
CALLSIGN_PATH = "/events"
CALLSIGN_RETRY_MS = 5000
CALLSIGN_CONNECT_TIMEOUT_S = 2.0
CALLSIGN_READ_TIMEOUT_S = 0.05
KEY_UP = 181
KEY_DOWN = 182
KEY_LEFT = 180
KEY_RIGHT = 183
KEY_ENTER = 13
KEY_TAB = 9
KEY_BACKSPACE = 8
KEY_ESC = 27
KEY_ENTER_VALUES = (10, 13, 0x28)
KEY_TAB_VALUES = (9, 0x2B)
KEY_BACKSPACE_VALUES = (8, 0x08, 0x2A, 0x7F)
KEY_ESC_VALUES = (27, 0x1B, 0x29)
KEY_UP_VALUES = (181, 0x52)
KEY_DOWN_VALUES = (182, 0x51, 0x50)
KEY_LEFT_VALUES = (180, 0x50)
KEY_RIGHT_VALUES = (183, 0x4F)

WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


label_time = None
label_date = None
label_weekday = None
label_utc = None
label_temp = None
label_weather = None
label_city = None
label_lat = None
label_lon = None
label_sunrise = None
label_sunset = None
label_status = None

kb = None
gps_device = None
wlan = None
config = {}
ui_mode = "clock"
settings_selected = 0
screen_off = False
last_clock_ms = 0
last_weather_ms = 0
weather_dirty = False
wifi_connected_last = False
weather_latitude = DEFAULT_CONFIG["fixed_latitude"]
weather_longitude = DEFAULT_CONFIG["fixed_longitude"]
resolved_city_name = DEFAULT_CONFIG["city_name"]
using_gps_location = False
last_key_code = None
display_time_text = ""
display_date_text = ""
display_weekday_text = ""
display_utc_text = ""
display_temp_text = "--C"
display_sunrise_text = "Sunrise  --:--"
display_sunset_text = "Sunset   --:--"
display_status_text = "Boot"
display_callsign_text = "Call:---"
current_callsign = ""
callsign_sock = None
callsign_host_index = 0
last_callsign_attempt_ms = 0
callsign_connected = False


def pad2(num):
    return "{:02d}".format(int(num))


def format_clock(ts):
    return "{}:{}".format(pad2(ts[3]), pad2(ts[4]))


def format_date(ts):
    return "{}-{}-{}".format(ts[0], pad2(ts[1]), pad2(ts[2]))


def get_weekday_name(ts):
    try:
        return WEEKDAYS[int(ts[6])]
    except Exception:
        return "---"


def get_epoch_seconds():
    try:
        return int(time.time())
    except Exception:
        return 0


def get_utc_now():
    return time.gmtime(get_epoch_seconds())


def get_local_now():
    return time.gmtime(get_epoch_seconds() + LOCAL_UTC_OFFSET_HOURS * 3600)


def format_coord(pos_prefix, neg_prefix, value):
    if value < 0:
        return "{} {:.5f}".format(neg_prefix, abs(value))
    return "{} {:.5f}".format(pos_prefix, value)


def extract_hhmm(text):
    try:
        if "T" in text:
            text = text.split("T", 1)[1]
        return text[:5]
    except Exception:
        return "--:--"


def get_text_width(text, font):
    try:
        return int(M5.Lcd.textWidth(str(text), font))
    except Exception:
        return len(str(text)) * 8


def set_right_aligned_text(label, text, right_x, y, font):
    text = str(text)
    x = right_x - get_text_width(text, font)
    if x < 0:
        x = 0
    try:
        label.setCursor(x=x, y=y)
    except Exception:
        pass
    try:
        label.setText(" ")
    except Exception:
        pass
    try:
        label.setCursor(x=x, y=y)
    except Exception:
        pass
    try:
        label.setText(text)
    except Exception:
        pass


def truncate_text(text, max_len):
    text = str(text)
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[: max_len - 3] + "..."


def refresh_label_text(label, text):
    try:
        label.setText(" ")
    except Exception:
        pass
    try:
        label.setText(str(text))
    except Exception:
        pass


def to_float(value, fallback):
    try:
        return float(value)
    except Exception:
        return fallback


def to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes", "on")
    return bool(value)


def normalize_key(key):
    if key is None:
        return None
    if key in KEY_ENTER_VALUES:
        return KEY_ENTER
    if key in KEY_TAB_VALUES:
        return KEY_TAB
    if key in KEY_BACKSPACE_VALUES:
        return KEY_BACKSPACE
    if key in KEY_ESC_VALUES:
        return KEY_ESC
    if key in KEY_UP_VALUES:
        return KEY_UP
    if key in KEY_DOWN_VALUES:
        return KEY_DOWN
    if key in KEY_LEFT_VALUES:
        return KEY_LEFT
    if key in KEY_RIGHT_VALUES:
        return KEY_RIGHT
    return key


def get_maidenhead_grid(latitude, longitude):
    try:
        lat = float(latitude)
        lon = float(longitude)
    except Exception:
        return "------"

    while lon < -180:
        lon += 360
    while lon >= 180:
        lon -= 360

    if lat >= 90:
        lat = 89.999999
    if lat < -90:
        lat = -89.999999

    lon += 180.0
    lat += 90.0

    field_lon = int(lon / 20)
    field_lat = int(lat / 10)
    square_lon = int((lon % 20) / 2)
    square_lat = int(lat % 10)
    subsquare_lon = int((lon % 2) * 12)
    subsquare_lat = int((lat % 1) * 24)

    field_chars = "ABCDEFGHIJKLMNOPQR"
    sub_chars = "ABCDEFGHIJKLMNOPQRSTUVWX"

    return "{}{}{}{}{}{}".format(
        field_chars[field_lon],
        field_chars[field_lat],
        square_lon,
        square_lat,
        sub_chars[subsquare_lon],
        sub_chars[subsquare_lat],
    )


def set_status(text):
    global display_status_text
    try:
        short_text = truncate_text(str(text), 8)
        display_status_text = short_text
        refresh_label_text(label_status, short_text)
    except Exception:
        pass


def collect_memory():
    try:
        gc.collect()
    except Exception:
        pass


def gen_ws_key():
    raw = bytes([urandom.getrandbits(8) for _ in range(16)])
    return ubinascii.b2a_base64(raw).strip().decode()


def decode_socket_text(data):
    if isinstance(data, bytes):
        try:
            return data.decode()
        except Exception:
            try:
                return data.decode("utf-8", "ignore")
            except Exception:
                return str(data)
    return str(data)


def close_callsign_socket():
    global callsign_sock, callsign_connected

    if callsign_sock is None:
        return

    try:
        callsign_sock.close()
    except Exception:
        pass
    callsign_sock = None
    callsign_connected = False


def update_callsign_label():
    global display_callsign_text

    display = truncate_text(current_callsign if current_callsign else "---", 8)
    display_callsign_text = "Call:{}".format(display)
    refresh_label_text(label_city, display_callsign_text)


def extract_json_objects(text):
    results = []
    start = -1
    depth = 0

    for idx in range(len(text)):
        ch = text[idx]
        if ch == "{":
            if depth == 0:
                start = idx
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    results.append(text[start : idx + 1])
                    start = -1
    return results


def get_qso_callsign_state(obj):
    try:
        if not isinstance(obj, dict):
            return None, None

        msg_type = str(obj.get("type", "")).lower()
        sub_type = str(obj.get("subType", "")).lower()
        if msg_type != "qso" or sub_type != "callsign":
            return None, None

        data = obj.get("data", {})
        if not isinstance(data, dict):
            return None, None

        callsign = str(data.get("callsign", "")).strip()
        is_speaking = bool(data.get("isSpeaking", False))
        return callsign, is_speaking
    except Exception:
        return None, None


def update_connection_status():
    try:
        if wlan is None or (not wlan.isconnected()):
            set_status("Offline")
            return
    except Exception:
        set_status("Offline")
        return

    if callsign_connected:
        set_status("WS OK")
    else:
        set_status("WS Off")


def is_socket_wait_error(err):
    try:
        code = err.args[0]
        if isinstance(code, int) and code in (11, 35, 110, 115, 116, 118):
            return True
    except Exception:
        pass

    try:
        err_text = str(err).lower()
        if (
            "timed out" in err_text
            or "eagain" in err_text
            or "would block" in err_text
            or "in progress" in err_text
        ):
            return True
    except Exception:
        pass

    return False


def schedule_callsign_reconnect():
    global last_callsign_attempt_ms

    close_callsign_socket()
    last_callsign_attempt_ms = 0
    try:
        if wlan is not None and wlan.isconnected():
            set_status("WS Try")
        else:
            update_connection_status()
    except Exception:
        update_connection_status()


def connect_callsign_socket():
    global callsign_sock, callsign_host_index, last_callsign_attempt_ms, callsign_connected

    last_callsign_attempt_ms = time.ticks_ms()
    close_callsign_socket()
    set_status("WS Try")

    preferred_host = str(config.get("callsign_host", DEFAULT_CALLSIGN_HOST)).strip()
    hosts = []
    if preferred_host and preferred_host != DEFAULT_CALLSIGN_HOST:
        hosts.append(preferred_host)
    else:
        for host_item in CALLSIGN_HOST_CANDIDATES:
            if host_item not in hosts:
                hosts.append(host_item)
    if not hosts:
        return False

    host = hosts[callsign_host_index % len(hosts)]
    callsign_host_index = (callsign_host_index + 1) % len(hosts)

    try:
        addr = socket.getaddrinfo(host, CALLSIGN_PORT)[0][-1]
        sock = socket.socket()
        sock.settimeout(CALLSIGN_CONNECT_TIMEOUT_S)
        sock.connect(addr)

        req = (
            "GET {} HTTP/1.1\r\n"
            "Host: {}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: {}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).format(CALLSIGN_PATH, host, gen_ws_key())
        sock.send(req.encode())

        try:
            sock.recv(512)
        except Exception:
            pass

        try:
            sock.settimeout(CALLSIGN_READ_TIMEOUT_S)
        except Exception:
            pass

        callsign_sock = sock
        callsign_connected = True
        update_connection_status()
        return True
    except Exception:
        close_callsign_socket()
        update_connection_status()
        collect_memory()
        return False


def ensure_callsign_socket():
    if callsign_sock is not None:
        return True

    if last_callsign_attempt_ms == 0:
        return connect_callsign_socket()

    if time.ticks_diff(time.ticks_ms(), last_callsign_attempt_ms) < CALLSIGN_RETRY_MS:
        return False

    return connect_callsign_socket()


def poll_callsign_socket():
    global current_callsign

    if callsign_sock is None:
        return False

    try:
        data = callsign_sock.recv(1024)
        if not data:
            close_callsign_socket()
            update_connection_status()
            return False
    except Exception as err:
        if is_socket_wait_error(err):
            return False
        close_callsign_socket()
        update_connection_status()
        return False

    try:
        text = decode_socket_text(data)
        payloads = extract_json_objects(text)
        if not payloads:
            return False

        updated = False
        for payload in payloads:
            try:
                obj = ujson.loads(payload)
            except Exception:
                continue

            callsign, is_speaking = get_qso_callsign_state(obj)
            if is_speaking is None:
                continue

            new_callsign = callsign if (is_speaking and callsign) else ""
            if new_callsign != current_callsign:
                current_callsign = new_callsign
                update_callsign_label()
                updated = True

        if updated:
            update_connection_status()
        return updated
    except Exception:
        return False


def get_battery_percent():
    try:
        if hasattr(M5, "Power") and hasattr(M5.Power, "getBatteryLevel"):
            value = M5.Power.getBatteryLevel()
            if value is not None:
                value = int(value)
                if value < 0:
                    value = 0
                if value > 100:
                    value = 100
                return value
    except Exception:
        pass

    try:
        if "Power" in globals() and hasattr(Power, "getBatteryLevel"):
            value = Power.getBatteryLevel()
            if value is not None:
                value = int(value)
                if value < 0:
                    value = 0
                if value > 100:
                    value = 100
                return value
    except Exception:
        pass

    return None


def show_battery_status():
    battery = get_battery_percent()
    if battery is None:
        set_status("BAT --")
    else:
        set_status("BAT{}%".format(battery))


def load_config():
    cfg = DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r") as fp:
            obj = ujson.loads(fp.read())
        if isinstance(obj, dict):
            cfg["wifi_ssid"] = str(obj.get("wifi_ssid", cfg["wifi_ssid"]))
            cfg["wifi_password"] = str(obj.get("wifi_password", cfg["wifi_password"]))
            cfg["city_name"] = str(obj.get("city_name", cfg["city_name"]))
            cfg["fixed_latitude"] = to_float(obj.get("fixed_latitude"), cfg["fixed_latitude"])
            cfg["fixed_longitude"] = to_float(obj.get("fixed_longitude"), cfg["fixed_longitude"])
            cfg["gps_enabled"] = to_bool(obj.get("gps_enabled", cfg["gps_enabled"]))
            cfg["brightness_index"] = int(obj.get("brightness_index", cfg["brightness_index"]))
            cfg["callsign_host"] = str(obj.get("callsign_host", cfg["callsign_host"]))
    except Exception:
        pass

    if cfg["brightness_index"] < 0 or cfg["brightness_index"] >= len(BRIGHTNESS_LEVELS):
        cfg["brightness_index"] = 0
    return cfg


def save_config():
    try:
        with open(CONFIG_FILE, "w") as fp:
            fp.write(ujson.dumps(config))
        return True
    except Exception:
        return False


def create_labels():
    global label_time, label_date, label_weekday, label_utc
    global label_temp, label_weather, label_city, label_lat, label_lon
    global label_sunrise, label_sunset, label_status

    Widgets.fillScreen(COLOR_BG)
    if label_time is None:
        label_time = Widgets.Label("00:00", 4, 0, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu72)
        label_date = Widgets.Label("2026-07-03", 124, 8, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu12)
        label_weekday = Widgets.Label("Fri", 186, 22, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu18)
        label_utc = Widgets.Label("UTC 00:00", 8, 56, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu18)
        label_temp = Widgets.Label("--C", 148, 56, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu18)
        label_city = Widgets.Label("Call:---", 8, 80, 1.0, COLOR_CALL, COLOR_BG, Widgets.FONTS.DejaVu18)
        label_weather = Widgets.Label("------", 140, 82, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu18)
        label_status = Widgets.Label("Boot", 170, 42, 1.0, COLOR_DIM, COLOR_BG, Widgets.FONTS.DejaVu12)
        label_lat = Widgets.Label("N 00.00000", 8, 104, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu12)
        label_lon = Widgets.Label("E 00.00000", 8, 118, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu12)
        label_sunrise = Widgets.Label("Sunrise  --:--", 140, 104, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu12)
        label_sunset = Widgets.Label("Sunset   --:--", 140, 118, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu12)
    else:
        try:
            label_city.setColor(COLOR_CALL)
        except Exception:
            pass


def apply_brightness():
    try:
        M5.Lcd.setBrightness(BRIGHTNESS_LEVELS[config["brightness_index"]])
    except Exception:
        try:
            Widgets.setBrightness(BRIGHTNESS_LEVELS[config["brightness_index"]])
        except Exception:
            pass


def cycle_brightness():
    config["brightness_index"] = (config["brightness_index"] + 1) % len(BRIGHTNESS_LEVELS)
    apply_brightness()
    save_config()
    set_status("BL {}".format(BRIGHTNESS_LABELS[config["brightness_index"]]))


def set_screen_power(on):
    global screen_off

    screen_off = not on
    try:
        if on:
            apply_brightness()
        else:
            M5.Lcd.setBrightness(0)
    except Exception:
        try:
            Widgets.setBrightness(BRIGHTNESS_LEVELS[config["brightness_index"]] if on else 0)
        except Exception:
            pass


def button_was_clicked(btn):
    if not btn:
        return False
    try:
        if hasattr(btn, "wasClicked") and btn.wasClicked():
            return True
    except Exception:
        pass
    try:
        if hasattr(btn, "wasPressed") and btn.wasPressed():
            return True
    except Exception:
        pass
    return False


def pump_input():
    M5.update()
    if kb:
        try:
            kb.tick()
        except Exception:
            pass


def read_keyboard_key_once():
    global last_key_code

    if kb:
        try:
            if kb.is_pressed():
                key = normalize_key(kb.get_key())
                if key is not None and key != last_key_code:
                    last_key_code = key
                    return key
            else:
                last_key_code = None
        except Exception:
            last_key_code = None
    return None


def read_key_once():
    pump_input()
    key = read_keyboard_key_once()
    if key is not None:
        return key

    if button_was_clicked(globals().get("BtnB")):
        return KEY_UP
    if button_was_clicked(globals().get("BtnC")):
        return KEY_DOWN
    if button_was_clicked(globals().get("BtnA")):
        return KEY_ENTER
    return None


def wait_key(timeout_ms=None):
    start = time.ticks_ms()
    while True:
        key = read_key_once()
        if key is not None:
            return key
        if timeout_ms is not None and time.ticks_diff(time.ticks_ms(), start) >= timeout_ms:
            return None
        time.sleep_ms(INPUT_POLL_MS)


def decode_ssid(raw):
    if isinstance(raw, bytes):
        try:
            return raw.decode()
        except Exception:
            try:
                return raw.decode("utf-8", "ignore")
            except Exception:
                return str(raw)
    return str(raw)


def scan_wifi_networks():
    networks = []
    seen = {}

    draw_text_screen("SCAN WIFI", ["Scanning..."], "Please wait")
    try:
        raw = wlan.scan()
    except Exception:
        raw = []

    for item in raw:
        try:
            ssid = decode_ssid(item[0]).strip()
            rssi = int(item[3])
            authmode = int(item[4])
        except Exception:
            continue

        if not ssid:
            continue

        old = seen.get(ssid)
        if old is None or rssi > old["rssi"]:
            seen[ssid] = {"ssid": ssid, "rssi": rssi, "authmode": authmode}

    for ssid in seen:
        networks.append(seen[ssid])

    networks.sort(key=lambda item: item["rssi"], reverse=True)
    collect_memory()
    return networks


def connect_wifi_saved():
    ssid = config.get("wifi_ssid", "")
    password = config.get("wifi_password", "")
    if not ssid:
        return False
    return connect_wifi(ssid, password)


def connect_wifi(ssid, password):
    global wlan

    if not ssid:
        return False

    try:
        if wlan is None:
            wlan = network.WLAN(network.STA_IF)
            wlan.active(True)
        wlan.config(reconnects=3)
    except Exception:
        pass

    try:
        if wlan.isconnected():
            try:
                wlan.disconnect()
                time.sleep_ms(300)
            except Exception:
                return True
    except Exception:
        pass

    set_status("WiFi...")
    draw_text_screen("WIFI", ["Connecting...", truncate_text(ssid, 22)], "Please wait")

    try:
        wlan.connect(ssid, password)
    except Exception:
        return False

    start_ms = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start_ms) < NETWORK_WAIT_MS:
        pump_input()
        try:
            if wlan.isconnected():
                config["wifi_ssid"] = ssid
                config["wifi_password"] = password
                save_config()
                set_status("WiFi OK")
                return True
        except Exception:
            pass
        time.sleep_ms(200)

    set_status("No WiFi")
    collect_memory()
    return False


def draw_text_screen(title, lines, footer=""):
    collect_memory()
    M5.Lcd.fillScreen(COLOR_BG)
    M5.Lcd.fillRoundRect(4, 4, 232, 127, 6, COLOR_PANEL)
    M5.Lcd.fillRect(8, 10, 96, 3, COLOR_FG)
    M5.Lcd.setTextSize(2)
    M5.Lcd.setTextColor(COLOR_FG, COLOR_PANEL)
    M5.Lcd.setCursor(10, 18)
    M5.Lcd.print(truncate_text(title, 18))

    M5.Lcd.setTextSize(1)
    M5.Lcd.setTextColor(0xFFFFFF, COLOR_PANEL)
    y = 48
    for line in lines[:5]:
        M5.Lcd.setCursor(10, y)
        M5.Lcd.print(truncate_text(line, 30))
        y += 16

    if footer:
        M5.Lcd.setTextColor(0x9AB977, COLOR_PANEL)
        M5.Lcd.setCursor(10, 116)
        M5.Lcd.print(truncate_text(footer, 30))


def draw_wifi_list(networks, selected, page_top):
    M5.Lcd.fillScreen(COLOR_BG)
    M5.Lcd.fillRoundRect(4, 4, 232, 127, 6, COLOR_PANEL)
    M5.Lcd.fillRect(8, 10, 88, 3, COLOR_FG)
    M5.Lcd.setTextSize(2)
    M5.Lcd.setTextColor(COLOR_FG, COLOR_PANEL)
    M5.Lcd.setCursor(10, 18)
    M5.Lcd.print("WIFI LIST")

    visible = networks[page_top : page_top + 4]
    y = 48
    for i, net in enumerate(visible):
        idx = page_top + i
        bg = COLOR_HL if idx == selected else 0x1B1B1B
        fg = COLOR_HL_TEXT if idx == selected else 0xFFFFFF
        M5.Lcd.fillRoundRect(10, y - 2, 220, 18, 3, bg)
        M5.Lcd.setTextSize(1)
        M5.Lcd.setTextColor(fg, bg)
        lock_mark = "*" if net["authmode"] != 0 else " "
        M5.Lcd.setCursor(14, y)
        M5.Lcd.print("{} {}".format(lock_mark, truncate_text(net["ssid"], 18)))
        M5.Lcd.setCursor(188, y)
        M5.Lcd.print(str(net["rssi"]))
        y += 20

    M5.Lcd.setTextColor(0x9AB977, COLOR_PANEL)
    M5.Lcd.setCursor(10, 116)
    M5.Lcd.print("UP/DN SEL ENT OK TAB RESCAN")


def select_wifi_network():
    selected = 0
    page_top = 0

    while True:
        networks = scan_wifi_networks()
        if not networks:
            draw_text_screen("NO WIFI", ["No network found"], "ENT rescan ESC back")
            key = wait_key()
            if key == KEY_ESC:
                return None
            continue

        while True:
            if selected < page_top:
                page_top = selected
            if selected > page_top + 3:
                page_top = selected - 3

            draw_wifi_list(networks, selected, page_top)
            key = wait_key()
            if key == KEY_UP and selected > 0:
                selected -= 1
            elif key == KEY_DOWN and selected < len(networks) - 1:
                selected += 1
            elif key == KEY_ENTER:
                draw_text_screen(
                    "WIFI PICK",
                    [truncate_text(networks[selected]["ssid"], 24), "Open password input"],
                    "Please wait",
                )
                time.sleep_ms(150)
                return networks[selected]
            elif key == KEY_TAB:
                break
            elif key == KEY_ESC:
                return None


def input_text_screen(title, current_text, hint, footer):
    draw_text_screen(
        title,
        [truncate_text(current_text if current_text else "_", 28), hint, "BKSP delete"],
        footer,
    )


def input_text_value(title, initial="", max_len=32, numeric_mode=False):
    text = str(initial)
    while True:
        input_text_screen(title, text, "Type on keyboard", "ENT save ESC back")
        key = wait_key()
        if key == KEY_ENTER:
            return text
        if key == KEY_ESC:
            return None
        if key == KEY_BACKSPACE:
            if text:
                text = text[:-1]
            continue
        if key is not None and 0x20 <= key <= 0x7E:
            ch = chr(key)
            if numeric_mode and ch not in "-.0123456789":
                continue
            if len(text) < max_len:
                text += ch


def is_valid_host_text(text):
    text = str(text).strip()
    if not text or len(text) > 63:
        return False
    for ch in text:
        code = ord(ch)
        if (48 <= code <= 57) or (65 <= code <= 90) or (97 <= code <= 122) or ch == "." or ch == "-":
            continue
        return False
    return True


def input_wifi_password(ssid):
    password = ""
    show_password = False

    while True:
        masked = password if show_password else ("*" * len(password))
        if not masked:
            masked = "_"
        draw_text_screen(
            "WIFI PASS",
            [truncate_text(ssid, 26), truncate_text(masked, 26), "TAB show/hide", "BKSP delete"],
            "ENT save ESC back",
        )
        key = wait_key()
        if key == KEY_ENTER:
            return password
        if key == KEY_ESC:
            return None
        if key == KEY_TAB:
            show_password = not show_password
            continue
        if key == KEY_BACKSPACE:
            if password:
                password = password[:-1]
            continue
        if key is not None and 0x20 <= key <= 0x7E and len(password) < 63:
            password += chr(key)


def ensure_wifi_ready(force_menu=False):
    if not force_menu and config.get("wifi_ssid"):
        draw_text_screen("WIFI", ["Try saved WiFi", truncate_text(config["wifi_ssid"], 24)], "Auto connect")
        if connect_wifi_saved():
            return True

    while True:
        draw_text_screen("WIFI SETUP", ["Saved WiFi unavailable", "Choose a new network"], "ENT select ESC skip")
        key = wait_key()
        if key == KEY_ESC:
            set_status("Offline")
            return False
        net = select_wifi_network()
        if not net:
            continue

        password = ""
        if net["authmode"] != 0:
            password = input_wifi_password(net["ssid"])
            if password is None:
                continue

        if connect_wifi(net["ssid"], password):
            return True

        draw_text_screen("WIFI FAIL", [truncate_text(net["ssid"], 24)], "ENT retry ESC back")
        key = wait_key()
        if key == KEY_ESC:
            return False


def sync_ntp():
    try:
        ntptime.host = NTP_HOST
        ntptime.settime()
        set_status("Clock OK")
        return True
    except Exception:
        set_status("Clock Loc")
        return False


def init_gps():
    global gps_device

    gps_device = None
    if GPSCap:
        try:
            gps_device = GPSCap(id=2)
            return
        except Exception:
            gps_device = None
    if AtomicGPSV2Base:
        try:
            gps_device = AtomicGPSV2Base(2, port=(22, 19))
            try:
                gps_device.set_time_zone(0)
            except Exception:
                pass
        except Exception:
            gps_device = None


def try_get_gps_location():
    if gps_device is None:
        return None

    start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), start) < GPS_WAIT_MS:
        pump_input()
        try:
            lat = float(gps_device.get_latitude())
            lon = float(gps_device.get_longitude())
            if abs(lat) > 0.0001 or abs(lon) > 0.0001:
                return {"lat": lat, "lon": lon}
        except Exception:
            pass
        time.sleep_ms(200)
    collect_memory()
    return None


def update_location_labels():
    update_callsign_label()
    refresh_label_text(label_lat, format_coord("N", "S", weather_latitude))
    refresh_label_text(label_lon, format_coord("E", "W", weather_longitude))
    refresh_label_text(label_weather, get_maidenhead_grid(weather_latitude, weather_longitude))


def resolve_active_location():
    global weather_latitude, weather_longitude, resolved_city_name, using_gps_location

    using_gps_location = False
    weather_latitude = to_float(config.get("fixed_latitude"), DEFAULT_CONFIG["fixed_latitude"])
    weather_longitude = to_float(config.get("fixed_longitude"), DEFAULT_CONFIG["fixed_longitude"])
    resolved_city_name = str(config.get("city_name", DEFAULT_CONFIG["city_name"]))

    if config.get("gps_enabled"):
        gps_pos = try_get_gps_location()
        if gps_pos is not None:
            weather_latitude = gps_pos["lat"]
            weather_longitude = gps_pos["lon"]
            using_gps_location = True
            resolved_city_name = "GPS"
            update_location_labels()
            return True
        set_status("GPS Fallback")

    update_location_labels()
    return True


def fetch_weather():
    global last_weather_ms, display_temp_text, display_sunrise_text, display_sunset_text

    resolve_active_location()
    url = WEATHER_URL.format(lat=weather_latitude, lon=weather_longitude)
    for attempt in range(2):
        response = None
        try:
            collect_memory()
            response = requests2.get(
                url,
                headers={"Content-Type": "application/json", "User-Agent": "DeskClock/0.1.02"},
                timeout=HTTP_TIMEOUT_S,
            )
            payload = ujson.loads(response.text)
            current = payload.get("current", {})
            daily = payload.get("daily", {})

            temp = "--C"
            sunrise = "--:--"
            sunset = "--:--"

            if "temperature_2m" in current:
                temp = "{}C".format(int(round(float(current.get("temperature_2m", 0)))))

            sunrise_list = daily.get("sunrise", [])
            sunset_list = daily.get("sunset", [])
            if sunrise_list:
                sunrise = extract_hhmm(sunrise_list[0])
            if sunset_list:
                sunset = extract_hhmm(sunset_list[0])

            display_temp_text = temp
            display_sunrise_text = "Sunrise  {}".format(sunrise)
            display_sunset_text = "Sunset   {}".format(sunset)
            refresh_label_text(label_temp, display_temp_text)
            refresh_label_text(label_sunrise, display_sunrise_text)
            refresh_label_text(label_sunset, display_sunset_text)
            set_status("Wx OK")
            last_weather_ms = time.ticks_ms()
            return True
        except Exception:
            if attempt == 0:
                time.sleep_ms(250)
            else:
                display_temp_text = "--C"
                display_sunrise_text = "Sunrise  --:--"
                display_sunset_text = "Sunset   --:--"
                refresh_label_text(label_temp, display_temp_text)
                refresh_label_text(label_sunrise, display_sunrise_text)
                refresh_label_text(label_sunset, display_sunset_text)
                set_status("Wx Off")
                last_weather_ms = time.ticks_ms()
                return False
        finally:
            try:
                if response is not None:
                    response.close()
            except Exception:
                pass
            collect_memory()


def update_clock_labels(force=False):
    global display_time_text, display_date_text, display_weekday_text, display_utc_text

    local_now = get_local_now()
    new_time_text = format_clock(local_now)
    new_date_text = format_date(local_now)
    new_weekday_text = get_weekday_name(local_now)
    new_utc_text = "UTC {}".format(format_clock(get_utc_now()))

    if force or new_time_text != display_time_text:
        display_time_text = new_time_text
        refresh_label_text(label_time, display_time_text)
    if force or new_date_text != display_date_text:
        display_date_text = new_date_text
        set_right_aligned_text(label_date, display_date_text, DATE_RIGHT_EDGE_X, DATE_Y, Widgets.FONTS.DejaVu12)
    if force or new_weekday_text != display_weekday_text:
        display_weekday_text = new_weekday_text
        set_right_aligned_text(label_weekday, display_weekday_text, DATE_RIGHT_EDGE_X, WEEKDAY_Y, Widgets.FONTS.DejaVu18)
    if force or new_utc_text != display_utc_text:
        display_utc_text = new_utc_text
        refresh_label_text(label_utc, display_utc_text)


def mark_weather_refresh():
    global weather_dirty
    weather_dirty = True
    set_status("Refresh")


def redraw_clock_screen():
    create_labels()
    update_location_labels()
    update_clock_labels(force=True)
    refresh_label_text(label_city, display_callsign_text)
    refresh_label_text(label_temp, display_temp_text)
    refresh_label_text(label_sunrise, display_sunrise_text)
    refresh_label_text(label_sunset, display_sunset_text)
    refresh_label_text(label_status, display_status_text)
    update_connection_status()
    collect_memory()


def get_settings_items():
    gps_text = "ON" if config.get("gps_enabled") else "OFF"
    return [
        "City: {}".format(truncate_text(config.get("city_name", ""), 12)),
        "Lat: {:.5f}".format(to_float(config.get("fixed_latitude"), 0.0)),
        "Lon: {:.5f}".format(to_float(config.get("fixed_longitude"), 0.0)),
        "GPS: {}".format(gps_text),
        "IP: {}".format(truncate_text(config.get("callsign_host", ""), 15)),
        "WiFi Setup",
        "Back",
    ]


def draw_settings_screen():
    items = get_settings_items()
    visible_rows = 4
    page_top = settings_selected
    if page_top > len(items) - visible_rows:
        page_top = len(items) - visible_rows
    if page_top < 0:
        page_top = 0

    M5.Lcd.fillScreen(COLOR_BG)
    M5.Lcd.fillRoundRect(4, 4, 232, 127, 6, COLOR_PANEL)
    M5.Lcd.fillRect(8, 10, 88, 3, COLOR_FG)
    M5.Lcd.setTextSize(1)
    M5.Lcd.setTextColor(COLOR_FG, COLOR_PANEL)
    M5.Lcd.setCursor(10, 16)
    M5.Lcd.print("SETTINGS")

    y = 32
    for row, item in enumerate(items[page_top : page_top + visible_rows]):
        idx = page_top + row
        bg = COLOR_HL if idx == settings_selected else 0x1B1B1B
        fg = COLOR_HL_TEXT if idx == settings_selected else 0xFFFFFF
        M5.Lcd.fillRoundRect(10, y - 2, 220, 16, 3, bg)
        M5.Lcd.setTextSize(1)
        M5.Lcd.setTextColor(fg, bg)
        M5.Lcd.setCursor(14, y)
        prefix = ">" if idx == settings_selected else " "
        M5.Lcd.print("{} {}".format(prefix, truncate_text(item, 25)))
        y += 17

    if page_top > 0:
        M5.Lcd.setTextColor(COLOR_DIM, COLOR_PANEL)
        M5.Lcd.setCursor(214, 16)
        M5.Lcd.print("^")
    if page_top + visible_rows < len(items):
        M5.Lcd.setTextColor(COLOR_DIM, COLOR_PANEL)
        M5.Lcd.setCursor(214, 84)
        M5.Lcd.print("v")

    M5.Lcd.setTextColor(0x9AB977, COLOR_PANEL)
    M5.Lcd.setCursor(10, 104)
    M5.Lcd.print(";/.:Move ENT:Edit")
    M5.Lcd.setCursor(10, 116)
    M5.Lcd.print("ESC:Exit")


def open_settings():
    global ui_mode, settings_selected

    ui_mode = "settings"
    settings_selected = 0
    draw_settings_screen()


def close_settings():
    global ui_mode

    ui_mode = "clock"
    redraw_clock_screen()
    mark_weather_refresh()


def edit_setting_item(index):
    global last_callsign_attempt_ms

    if index == 0:
        value = input_text_value("CITY", config.get("city_name", ""), 24, False)
        if value is not None:
            config["city_name"] = value.strip()
            save_config()
    elif index == 1:
        value = input_text_value("LATITUDE", str(config.get("fixed_latitude", "")), 16, True)
        if value is not None:
            config["fixed_latitude"] = to_float(value, config["fixed_latitude"])
            save_config()
    elif index == 2:
        value = input_text_value("LONGITUDE", str(config.get("fixed_longitude", "")), 16, True)
        if value is not None:
            config["fixed_longitude"] = to_float(value, config["fixed_longitude"])
            save_config()
    elif index == 3:
        config["gps_enabled"] = not config.get("gps_enabled")
        save_config()
    elif index == 4:
        value = input_text_value("CALLSIGN IP", config.get("callsign_host", ""), 31, False)
        if value is not None:
            value = value.strip()
            if is_valid_host_text(value):
                config["callsign_host"] = value
                save_config()
                schedule_callsign_reconnect()
                set_status("IP Saved")
            else:
                draw_text_screen("HOST IP", ["Invalid host/IP"], "ENT back")
                wait_key()
    elif index == 5:
        ensure_wifi_ready(force_menu=True)
    elif index == 6:
        close_settings()
        return

    draw_settings_screen()


def handle_settings_key(key):
    global settings_selected

    if (key == KEY_UP or key == ord(";")) and settings_selected > 0:
        settings_selected -= 1
        draw_settings_screen()
    elif (key == KEY_DOWN or key == ord(".")) and settings_selected < len(get_settings_items()) - 1:
        settings_selected += 1
        draw_settings_screen()
    elif key == KEY_ENTER:
        edit_setting_item(settings_selected)
    elif key == KEY_ESC:
        close_settings()


def handle_power_toggle_from_esc():
    if screen_off:
        set_screen_power(True)
        if ui_mode == "settings":
            draw_settings_screen()
        else:
            redraw_clock_screen()
    else:
        set_screen_power(False)


def process_key(key):
    if key is None:
        return

    upper_key = None
    if 0x20 <= key <= 0x7E:
        upper_key = chr(key).upper()

    if key == KEY_ESC and ui_mode == "clock":
        handle_power_toggle_from_esc()
        return

    if upper_key == "L":
        if screen_off:
            set_screen_power(True)
        cycle_brightness()
        if ui_mode == "settings":
            draw_settings_screen()
        return

    if upper_key == "S" and ui_mode == "clock":
        if screen_off:
            set_screen_power(True)
        open_settings()
        return

    if upper_key == "R" and ui_mode == "clock":
        if screen_off:
            set_screen_power(True)
        mark_weather_refresh()
        return

    if upper_key == "W" and ui_mode == "clock":
        if screen_off:
            set_screen_power(True)
        schedule_callsign_reconnect()
        return

    if upper_key == "B":
        if screen_off:
            set_screen_power(True)
        show_battery_status()
        if ui_mode == "settings":
            draw_settings_screen()
        return

    if ui_mode == "settings":
        if screen_off:
            set_screen_power(True)
        handle_settings_key(key)


def setup():
    global kb, wlan, config, last_clock_ms, last_weather_ms, wifi_connected_last

    config = load_config()

    M5.begin()
    try:
        M5.Lcd.setRotation(1)
    except Exception:
        pass

    if MatrixKeyboard:
        try:
            kb = MatrixKeyboard()
        except Exception:
            kb = None

    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
    except Exception:
        wlan = None

    init_gps()
    create_labels()
    apply_brightness()
    update_location_labels()
    update_clock_labels()
    set_status("Boot")

    if ensure_wifi_ready():
        sync_ntp()
        update_clock_labels()
        fetch_weather()
        ensure_callsign_socket()
        wifi_connected_last = True
    else:
        label_temp.setText(display_temp_text)
        label_sunrise.setText(display_sunrise_text)
        label_sunset.setText(display_sunset_text)
        wifi_connected_last = False

    redraw_clock_screen()
    last_clock_ms = time.ticks_ms()
    last_weather_ms = time.ticks_ms()
    collect_memory()


def loop():
    global last_clock_ms, last_weather_ms, weather_dirty, wifi_connected_last, current_callsign

    key = read_key_once()
    process_key(key)

    if ui_mode == "settings":
        time.sleep_ms(20)
        return

    now_ms = time.ticks_ms()

    if wlan is not None:
        try:
            connected_now = wlan.isconnected()
        except Exception:
            connected_now = False

        if connected_now and not wifi_connected_last:
            sync_ntp()
            update_clock_labels()
            fetch_weather()
            ensure_callsign_socket()
            update_connection_status()
            collect_memory()
        elif (not connected_now) and wifi_connected_last:
            close_callsign_socket()
            current_callsign = ""
            update_callsign_label()
            update_connection_status()

        wifi_connected_last = connected_now

        if connected_now:
            ensure_callsign_socket()
            poll_callsign_socket()

    if not screen_off and time.ticks_diff(now_ms, last_clock_ms) >= CLOCK_REFRESH_MS:
        update_clock_labels()
        last_clock_ms = now_ms

    if weather_dirty:
        weather_dirty = False
        try:
            if wlan is not None and wlan.isconnected():
                fetch_weather()
            else:
                set_status("No Net")
                last_weather_ms = now_ms
        except Exception:
            set_status("No Net")
            last_weather_ms = now_ms
        collect_memory()
        time.sleep_ms(20)
        return

    if time.ticks_diff(now_ms, last_weather_ms) >= WEATHER_REFRESH_MS:
        try:
            if wlan is not None and wlan.isconnected():
                fetch_weather()
            else:
                set_status("Wx Stale")
                last_weather_ms = now_ms
        except Exception:
            set_status("Wx Stale")
            last_weather_ms = now_ms
        collect_memory()

    time.sleep_ms(20)


if __name__ == "__main__":
    try:
        setup()
        while True:
            loop()
    except (Exception, KeyboardInterrupt) as e:
        try:
            from utility import print_error_msg

            print_error_msg(e)
        except ImportError:
            print("please update to latest firmware")
