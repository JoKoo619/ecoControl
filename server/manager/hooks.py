import logging
import calendar
from datetime import datetime

from django.db.models import Sum, Avg
from django.db import connection
from django.core.exceptions import PermissionDenied
from django.utils.timezone import utc

from server.models import Device, Sensor, SensorValue, SensorValueMonthlySum, SensorValueMonthlyAvg
from server.functions import get_configuration, get_past_time
from server.helpers import create_json_response
import functions

logger = logging.getLogger('django')


def get_sums(request, sensor_id=None, year=None):
    if not request.user.is_authenticated():
        raise PermissionDenied

    if year is None:
        start = datetime(datetime.today().year, 1, 1).replace(tzinfo=utc)
        end = datetime(datetime.today().year, 12, 31).replace(tzinfo=utc)
    else:
        start = datetime(int(year), 1, 1).replace(tzinfo=utc)
        end = datetime(int(year), 12, 31).replace(tzinfo=utc)

    sensorvaluemonthlysum = SensorValueMonthlySum.objects.filter(
        timestamp__gte=start, timestamp__lte=end)

    if sensor_id is None:
        output = {}
        for sensor in Sensor.objects.all().values_list('id', flat=True):
            output[sensor] = list(sensorvaluemonthlysum.filter(
                sensor_id=sensor).values('timestamp').annotate(total=Sum('sum')).order_by('timestamp'))
    else:
        output = list(sensorvaluemonthlysum.filter(
            sensor_id=sensor_id).values('timestamp').annotate(total=Sum('sum')).order_by('timestamp'))

    return create_json_response(output, request)


def get_avgs(request, sensor_id=None, year=None):
    if not request.user.is_authenticated():
        raise PermissionDenied

    if year is None:
        start = datetime(datetime.today().year, 1, 1).replace(tzinfo=utc)
        end = datetime(datetime.today().year, 12, 31).replace(tzinfo=utc)
    else:
        start = datetime(int(year), 1, 1).replace(tzinfo=utc)
        end = datetime(int(year), 12, 31).replace(tzinfo=utc)

    sensorvaluemonthlyavg = SensorValueMonthlyAvg.objects.filter(
        timestamp__gte=start, timestamp__lte=end)

    if sensor_id is None:
        output = {}
        for sensor in Sensor.objects.all().values_list('id', flat=True):
            output[sensor] = list(sensorvaluemonthlyavg.filter(
                sensor_id=sensor).values('timestamp').annotate(total=Avg('avg')).order_by('timestamp'))
    else:
        output = list(sensorvaluemonthlyavg.filter(
            sensor_id=sensor_id).values('timestamp').annotate(total=Avg('avg')).order_by('timestamp'))

    return create_json_response(output, request)


def get_sensorvalue_history_list(request):
    if not request.user.is_authenticated():
        raise PermissionDenied

    cursor = connection.cursor()
    cursor.execute(
        '''SELECT DISTINCT date_part('year', server_sensorvaluemonthlysum.timestamp) as year FROM server_sensorvaluemonthlysum ORDER BY year DESC''')

    output = [int(x[0]) for x in cursor.fetchall()]
    return create_json_response(output, request)


def get_detailed_sensor_values(request, sensor_id):
    if not request.user.is_authenticated():
        raise PermissionDenied

    start = get_past_time(days=1)
    sensor_values = list(SensorValue.objects.filter(
        sensor_id=sensor_id, timestamp__gte=start).values_list('timestamp', 'value'))

    return create_json_response(sensor_values, request)


def get_daily_loads(request):
    if not request.user.is_authenticated():
        raise PermissionDenied

    start = get_past_time(days=1)
    sensors = Sensor.objects.filter(
        device__device_type=Device.TC, key='get_consumption_power').values_list('id', flat=True)

    output = {
        'thermal': {},
        'warmwater': {},
        'electrical': {},
    }
    for sensor_id in sensors:
        output['thermal'][sensor_id] = list(SensorValue.objects.filter(
            sensor__id=sensor_id, timestamp__gte=start).values_list('timestamp', 'value'))

    sensors = Sensor.objects.filter(
        device__device_type=Device.TC, key='get_warmwater_consumption_power').values_list('id', flat=True)
    for sensor_id in sensors:
        output['warmwater'][sensor_id] = list(SensorValue.objects.filter(
            sensor__id=sensor_id, timestamp__gte=start).values_list('timestamp', 'value'))

    sensors = Sensor.objects.filter(
        device__device_type=Device.EC, key='get_consumption_power').values_list('id', flat=True)
    for sensor_id in sensors:
        output['electrical'][sensor_id] = list(SensorValue.objects.filter(
            sensor__id=sensor_id, timestamp__gte=start).values_list('timestamp', 'value'))

    return create_json_response(output, request)


def get_total_balance(request, year=None, month=None):
    if not request.user.is_authenticated():
        raise PermissionDenied

    current = get_past_time(use_view=True)
    try:
        year = int(year)
    except (TypeError, ValueError):
        year = current.year

    if month is None:
        months = [x for x in range(1, 13)]
    else:
        try:
            months = [int(month)]
        except (TypeError, ValueError):
            months = [current.month]

    output = []
    for month in months:
        start = datetime(year, month, 1).replace(tzinfo=utc)
        end = datetime(year, month, calendar.mdays[month]).replace(tzinfo=utc)

        output.append(functions.get_total_balance_by_date(month, year))

    return create_json_response(output, request)


def get_latest_total_balance(request):
    if not request.user.is_authenticated():
        raise PermissionDenied

    current = get_past_time(use_view=True)
    year = current.year
    month = current.month

    output = dict([('month', month), ('year', year)]
                  + functions.get_total_balance_by_date(month, year).items())

    return create_json_response(output, request)
