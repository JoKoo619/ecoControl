from flask import make_response
from functools import update_wrapper
import calendar

# CORS decorator
def crossdomain(origin=None):
	def decorator(f):
		def wrapped_function(*args, **kwargs):
			resp = make_response(f(*args, **kwargs))
			h = resp.headers
			h['Access-Control-Allow-Origin'] = origin
			return resp
		return update_wrapper(wrapped_function, f)
	return decorator

# converts SelectQuery to jsonify-able list
def convert_sql_to_list(sensor_entries, sensor_unit):
	return [{
		"value": str(item.value)+" "+sensor_unit,
		"timestamp": calendar.timegm(item.timestamp.utctimetuple())#str(item.timestamp)  
		} for item in sensor_entries]