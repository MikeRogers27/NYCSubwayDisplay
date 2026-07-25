from typing import Any

from pyowm import OWM
from pyowm.utils import config
from pyowm.utils import timestamps

# ---------- FREE API KEY examples ---------------------

owm: OWM = OWM('09e258070bffcd29e09274a8e3c53ada')
mgr: Any = owm.weather_manager()


# Search for current weather in London (Great Britain) and get details
observation: Any = mgr.weather_at_place('New York')
w: Any = observation.weather

w.detailed_status         # 'clouds'
w.wind()                  # {'speed': 4.6, 'deg': 330}
w.humidity                # 87
w.temperature('celsius')  # {'temp_max': 10.5, 'temp': 9.7, 'temp_min': 9.0}
w.rain                    # {}
w.heat_index              # None
w.clouds                  # 75

# Will it be clear tomorrow at this time in Milan (Italy) ?
forecast: Any = mgr.forecast_at_place('New York', '3h')
answer: bool = forecast.will_be_clear_at(timestamps.tomorrow())

pass