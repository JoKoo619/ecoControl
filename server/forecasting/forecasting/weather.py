import urllib2
import json
import time
import logging

from server.forecasting.systems.data import outside_temperatures_2013, outside_temperatures_2012
from server.forecasting.forecasting.helpers import cached_data

logger = logging.getLogger('simulation')

class WeatherForecast:

    def __init__(self, env=None):
        self.env = env

        self.forecast_query_date = None
        self.forecast_temperatures_3hourly = []
        self.forecast_temperatures_daily = []
        self.hourly = True

    def get_weather_forecast(self, hourly=True):
        self.hourly = hourly
        # only permit forecast queries every 30min, to save some api requests
        if self.forecast_query_date is not None and self.forecast_query_date - self.get_date() < 60 * 30:
            if hourly and self.forecast_temperatures_3hourly != []:
                return self.forecast_temperatures_3hourly
            elif not hourly and self.forecast_temperatures_daily != []:
                return self.forecast_temperatures_daily

        forecast_temperatures = []
        self.forecast_query_date = self.get_date()

        jsondata = cached_data('openweathermap', data_function=self.get_openweathermapdata, max_age=3600)
        data = json.loads(jsondata)

        for data_set in data["list"]:
            try:
                forecast_temperatures.append(data_set["main"]["temp"])
            except:
                logger.warning("WeatherForecast: Problems while json parsing")
                if "gdps" not in data_set:
                    logger.error("WeatherForecast: Couldn't read temperature values from openweathermap")
        logger.info("WeatherForecast: Fetched %d tempterature values" % len(forecast_temperatures))
        return forecast_temperatures

    def get_openweathermapdata(self):
        if self.hourly:
            # 3-hourly forecast for 5 days for Berlin
            url = "http://openweathermap.org/data/2.5/forecast/city?q=Berlin&units=metric&APPID=b180579fb094bd498cdeab9f909870a5&mode=json"
        else:
            url = "http://openweathermap.org/data/2.5/forecast/city?q=Berlin&units=metric&APPID=b180579fb094bd498cdeab9f909870a5?mode=daily_compact"
        try:
            return urllib2.urlopen(url).read()
        except urllib2.URLError, e:
            logger.error("WeatherForecast: URLError during API call")
            # Use history data
            result = []
            for i in range(0, 40):
                result.append(
                    self.get_average_outside_temperature(self.get_date(), i))
            return result

    def get_temperature_estimate(self, date):
        """get most accurate forecast for given date
        that can be derived from 5 days forecast, 14 days forecast or from history data"""
        history_data = self.get_average_outside_temperature(date)
        time_passed = (date - self.get_date()) / (60.0 * 60.0 * 24)  # in days
        if time_passed < 0.0 or time_passed > 13.0:
            return history_data

        forecast_data_hourly = self.get_forecast_temperature_hourly(date)
        forecast_data_daily = self.get_forecast_temperature_daily(date)
        if time_passed < 5.0:
            return forecast_data_hourly
        else:
            return forecast_data_daily

    def get_forecast_temperature_hourly(self, date):
        self.forecast_temperatures_3hourly = self.get_weather_forecast(
            hourly=True)
        time_passed = int((date - self.get_date()) / (60.0 * 60.0))  # in hours
        weight = (time_passed % 3) / 3.0
        t0 = min(int(time_passed / 3), len(
            self.forecast_temperatures_3hourly) - 1)
        t1 = min(t0 + 1, len(self.forecast_temperatures_3hourly) - 1)
        a0 = self.forecast_temperatures_3hourly[t0]
        a1 = self.forecast_temperatures_3hourly[t1]
        return self.mix(a0, a1, weight)

    def get_forecast_temperature_daily(self, date):
        self.forecast_temperatures_daily = self.get_weather_forecast(
            hourly=False)
        time_passed = int((date - self.get_date()) / (60.0 * 60.0))  # in days
        weight = (time_passed % 24) / 24.0
        t0 = min(int(time_passed / 24), len(
            self.forecast_temperatures_daily) - 1)
        t1 = min(t0 + 1, len(self.forecast_temperatures_daily) - 1)
        a0 = self.forecast_temperatures_daily[t0]
        a1 = self.forecast_temperatures_daily[t1]
        return self.mix(a0, a1, weight)

    def get_average_outside_temperature(self, date, offset_days=0):
        day = (time.gmtime(date).tm_yday + offset_days) % 365
        hour = time.gmtime(date).tm_hour
        d0 = outside_temperatures_2013[day * 24 + hour]
        d1 = outside_temperatures_2012[day * 24 + hour]
        return (d0 + d1) / 2.0

    def mix(self, a, b, x):
        return a * (1 - x) + b * x

    def get_date(self):
        return time.time()  # for debugging, use self.env.now
