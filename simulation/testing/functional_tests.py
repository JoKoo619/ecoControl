import unittest

import start
from forecasting_script import Forecast


class ForecastTestCase(unittest.TestCase):

    def test_forecast_api_provides_inaccuracy(self):
        rv = start.app.test_client().get('/api/forecasts/')
        self.assertIn('forecast_inaccuracy', rv.data, 
            "the forecast data should contain a value for the inaccuracy of the forecast")

    def test_forecast_has_inaccuracy(self):
        fcast = Forecast()
        try:
            inaccuracy = fcast.get_current_inaccurency()
        except AttributeError:
            self.fail(
                "the forecasting should have the method get_current_inaccurency'")
                

        
