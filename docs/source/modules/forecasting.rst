###########
Forecasting
###########
This package contains the simulation and methods for creating forecasts. They are split into statistical forecasts and weather forecast. 

..  toctree::
    
    simulation.rst
    statistical_forecasting.rst
    holt_winters.rst
    weather.rst
    forecasting_helpers.rst


Forecasts
=========



.. automodule:: server.forecasting
	
	.. autofunction:: get_forecast
	
	.. autoclass:: Forecast
		:show-inheritance:
		:members:

	.. autoclass:: DemoSimulation
		:show-inheritance:
		:members:
	
	.. autoclass:: ForecastQueue
		:members:

	.. autofunction:: get_initialized_scenario