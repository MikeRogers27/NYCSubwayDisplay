from typing import Any

from pyowm import OWM
from pyowm.utils import timestamps

# ---------- FREE API KEY examples ---------------------

owm: OWM = OWM("09e258070bffcd29e09274a8e3c53ada")
mgr: Any = owm.weather_manager()


# Search for current weather in London (Great Britain) and get details
observation: Any = mgr.weather_at_place("New York")
w: Any = observation.weather

_ = w.detailed_status
_ = w.wind()
_ = w.humidity
_ = w.temperature("celsius")
_ = w.rain
_ = w.heat_index
_ = w.clouds

# Will it be clear tomorrow at this time in Milan (Italy) ?
forecast: Any = mgr.forecast_at_place("New York", "3h")
answer: bool = forecast.will_be_clear_at(timestamps.tomorrow())

