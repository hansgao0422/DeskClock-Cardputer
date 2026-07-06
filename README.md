# DeskClock-Cardputer
CardPuter上的桌面时钟

-------------------------------------------------------------------------
import M5
from M5 import *
import network
import ntptime
import requests2
import time
import ujson


WIFI_SSID = "BG7YVZ"
WIFI_PASSWORD = "nishengri"
LOCAL_UTC_OFFSET_HOURS = 8
CITY_NAME = "Sanya"
LATITUDE = 18.2738
LONGITUDE = 109.4360
WEATHER_REFRESH_MS = 15 * 60 * 1000
CLOCK_REFRESH_MS = 1000
NETWORK_WAIT_MS = 12000
COLOR_BG = 0x000000
COLOR_FG = 0x6EA536
COLOR_DIM = 0x3C6321
NTP_HOST = "pool.ntp.org"
DATE_RIGHT_EDGE_X = 228
DATE_Y = 8
WEEKDAY_Y = 22
WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude={lat}&longitude={lon}"
    "&current=temperature_2m,weather_code"
    "&daily=sunrise,sunset"
    "&timezone=auto"
)


WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
WEATHER_CODES = {
    0: "Clear",
    1: "MostlyClr",
    2: "P.Cloudy",
    3: "Cloudy",
    45: "Fog",
    48: "RimeFog",
    51: "LtDrizzle",
    53: "Drizzle",
    55: "HvDrizzle",
    56: "FrzDrzl",
    57: "HvFrzDrzl",
    61: "LtRain",
    63: "Rain",
    65: "HvRain",
    66: "FrzRain",
    67: "HvFrzRain",
    71: "LtSnow",
    73: "Snow",
    75: "HvSnow",
    77: "SnwGrains",
    80: "Showers",
    81: "HvShowers",
    82: "VioShower",
    85: "SnwShower",
    86: "HvSnwShow",
    95: "T-Storm",
    96: "T-StormH",
    99: "HvTStormH",
}


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

wlan = None
last_clock_ms = 0
last_weather_ms = 0
weather_dirty = False
wifi_connected_last = False
weather_latitude = LATITUDE
weather_longitude = LONGITUDE
resolved_city_name = CITY_NAME


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


def get_epoch_seconds():
    try:
        return int(time.time())
    except Exception:
        return 0


def get_utc_now():
    return time.gmtime(get_epoch_seconds())


def get_local_now():
    return time.gmtime(get_epoch_seconds() + LOCAL_UTC_OFFSET_HOURS * 3600)


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
    label.setText(text)


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

    subsquare_lon = int(((lon % 2) * 12))
    subsquare_lat = int(((lat % 1) * 24))

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


def update_location_labels():
    label_city.setText("City:{}".format(resolved_city_name))
    label_lat.setText(format_coord("N", "S", weather_latitude))
    label_lon.setText(format_coord("E", "W", weather_longitude))
    label_weather.setText(get_maidenhead_grid(weather_latitude, weather_longitude))


def resolve_city_location(force=False):
    global weather_latitude, weather_longitude, resolved_city_name
    resolved_city_name = CITY_NAME
    weather_latitude = LATITUDE
    weather_longitude = LONGITUDE
    update_location_labels()
    return True


def connect_wifi():
    global wlan

    if not WIFI_SSID or WIFI_SSID == "YOUR_WIFI_SSID":
        set_status("Set WiFi")
        return False

    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        wlan.config(reconnects=3)

        if wlan.isconnected():
            set_status("WiFi OK")
            return True

        set_status("WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)

        start_ms = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_ms) < NETWORK_WAIT_MS:
            M5.update()
            if wlan.isconnected():
                set_status("WiFi OK")
                return True
            time.sleep_ms(200)
    except Exception:
        pass

    set_status("Offline")
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


def fetch_weather():
    global last_weather_ms

    resolve_city_location()
    url = WEATHER_URL.format(lat=weather_latitude, lon=weather_longitude)
    try:
        response = requests2.get(url, headers={"Content-Type": "application/json"})
        payload = ujson.loads(response.text)

        temp = "--"
        sunrise = "--:--"
        sunset = "--:--"

        current = payload.get("current", {})
        daily = payload.get("daily", {})

        if "temperature_2m" in current:
            temp = "{}C".format(int(round(float(current.get("temperature_2m", 0)))))

        sunrise_list = daily.get("sunrise", [])
        sunset_list = daily.get("sunset", [])

        if sunrise_list and len(sunrise_list) > 0:
            sunrise = extract_hhmm(sunrise_list[0])
        if sunset_list and len(sunset_list) > 0:
            sunset = extract_hhmm(sunset_list[0])

        label_temp.setText(temp)
        label_sunrise.setText("Sunrise  {}".format(sunrise))
        label_sunset.setText("Sunset   {}".format(sunset))
        set_status("Weather OK")
        last_weather_ms = time.ticks_ms()
        return True
    except Exception:
        label_temp.setText("--C")
        label_sunrise.setText("Sunrise  --:--")
        label_sunset.setText("Sunset   --:--")
        set_status("Wx Offline")
        last_weather_ms = time.ticks_ms()
        return False


def update_clock_labels():
    local_now = get_local_now()
    date_text = format_date(local_now)
    weekday_text = get_weekday_name(local_now)

    label_time.setText(format_clock(local_now))
    set_right_aligned_text(label_date, date_text, DATE_RIGHT_EDGE_X, DATE_Y, Widgets.FONTS.DejaVu12)
    set_right_aligned_text(
        label_weekday, weekday_text, DATE_RIGHT_EDGE_X, WEEKDAY_Y, Widgets.FONTS.DejaVu18
    )

    utc_now = get_utc_now()
    label_utc.setText("UTC {}".format(format_clock(utc_now)))


def set_status(text):
    try:
        short_text = str(text)
        status_alias = {
            "Weather OK": "Wx OK",
            "Wx Offline": "Wx Off",
            "Weather stale": "Wx Stale",
            "WiFi connecting": "WiFi...",
            "WiFi connected": "WiFi OK",
            "Clock synced": "Clk OK",
            "Clock local": "Clk Loc",
        }
        if short_text in status_alias:
            short_text = status_alias[short_text]
        if len(short_text) > 6:
            short_text = short_text[:6]
        label_status.setText(short_text)
    except Exception:
        pass


def mark_weather_refresh():
    global weather_dirty
    weather_dirty = True
    set_status("Refresh")


def create_labels():
    global label_time, label_date, label_weekday, label_utc
    global label_temp, label_weather, label_city, label_lat, label_lon
    global label_sunrise, label_sunset, label_status

    Widgets.fillScreen(COLOR_BG)

    label_time = Widgets.Label("00:00", 4, 0, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu72)
    label_date = Widgets.Label("2026-07-03", 124, 8, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu12)
    label_weekday = Widgets.Label("Fri", 186, 22, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu18)
    label_utc = Widgets.Label("UTC 00:00", 8, 56, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu18)
    label_temp = Widgets.Label("--C", 148, 56, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu18)
    label_city = Widgets.Label("City:{}".format(CITY_NAME), 8, 80, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu18)
    label_weather = Widgets.Label("------", 140, 82, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu18)
    label_status = Widgets.Label("Boot", 170, 42, 1.0, COLOR_DIM, COLOR_BG, Widgets.FONTS.DejaVu12)
    label_lat = Widgets.Label(format_coord("N", "S", LATITUDE), 8, 104, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu12)
    label_lon = Widgets.Label(format_coord("E", "W", LONGITUDE), 8, 118, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu12)
    label_sunrise = Widgets.Label("Sunrise  --:--", 140, 104, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu12)
    label_sunset = Widgets.Label("Sunset   --:--", 140, 118, 1.0, COLOR_FG, COLOR_BG, Widgets.FONTS.DejaVu12)


def setup():
    global last_clock_ms, last_weather_ms, wifi_connected_last

    M5.begin()
    try:
        M5.Lcd.setRotation(1)
    except Exception:
        pass

    create_labels()
    update_location_labels()
    update_clock_labels()

    if connect_wifi():
        sync_ntp()
        update_clock_labels()
        fetch_weather()
        wifi_connected_last = True
    else:
        label_temp.setText("--C")
        label_sunrise.setText("Sunrise  --:--")
        label_sunset.setText("Sunset   --:--")
        wifi_connected_last = False

    last_clock_ms = time.ticks_ms()
    last_weather_ms = time.ticks_ms()


def loop():
    global last_clock_ms, last_weather_ms, weather_dirty, wifi_connected_last

    M5.update()

    if BtnA.wasPressed():
        mark_weather_refresh()

    now_ms = time.ticks_ms()

    if wlan is not None:
        connected_now = wlan.isconnected()
        if connected_now and not wifi_connected_last:
            sync_ntp()
            update_clock_labels()
            fetch_weather()
        elif (not connected_now) and wifi_connected_last:
            set_status("Offline")
        wifi_connected_last = connected_now

    if time.ticks_diff(now_ms, last_clock_ms) >= CLOCK_REFRESH_MS:
        update_clock_labels()
        last_clock_ms = now_ms

    if weather_dirty:
        weather_dirty = False
        if wlan is not None and wlan.isconnected():
            fetch_weather()
        else:
            set_status("No Net")
            last_weather_ms = now_ms
        return

    if time.ticks_diff(now_ms, last_weather_ms) >= WEATHER_REFRESH_MS:
        if wlan is not None and wlan.isconnected():
            fetch_weather()
        else:
            set_status("Wx Stale")
            last_weather_ms = now_ms

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
