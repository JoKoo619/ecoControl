import sys
import logging
from time import time
import calendar
from datetime import date
import json

from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.http import require_POST
from django.views.decorators.debug import sensitive_post_parameters
from django.utils.timezone import utc
from django.db.models import Count, Min, Sum, Avg
from django.db import connection

from server.models import Device, Configuration, DeviceConfiguration, Sensor, SensorValue, SensorValueHourly, SensorValueDaily, SensorValueMonthlySum, SensorValueMonthlyAvg, Threshold, Notification
from server.functions import get_configuration, get_past_time
from server.helpers import create_json_response, create_json_response_from_QuerySet


logger = logging.getLogger('django')


def get_totals(request):
    return create_json_response(request, {"status": "success"})


def get_infeed(request):
    feed_in_reward = get_configuration('feed_in_reward')
    return get_sum_response(request, Device.PM, 'fed_in_electricity', feed_in_reward)


def get_purchase(request):
    electrical_costs = get_configuration('electrical_costs')
    return get_sum_response(request, Device.PM, 'purchased', electrical_costs)


def get_thermal_consumption(request):
    return get_sum_response(request, Device.TC, 'get_consumption_power')


def get_warmwater_consumption(request):
    return get_sum_response(request, Device.TC, 'get_warmwater_consumption_power')


def get_electrical_consumption(request):
    return get_sum_response(request, Device.EC, 'get_consumption_power')


def get_maintenance_costs(request):
    return create_json_response(request, {"status": "success"})


def get_cu_consumption(request):
    return get_sum_response(request, Device.CU, 'current_gas_consumption')


def get_plb_consumption(request):
    return get_sum_response(request, Device.PLB, 'current_gas_consumption')


def get_sum_response(request, device_type, key, multiply_by=1):
    sensors = Sensor.objects.filter(
        device__device_type=device_type, key=key).values_list('id', flat=True)
    totals = list(SensorValueMonthly.objects.filter(sensor_id__in=sensors)
                  .values('date').annotate(total_sum=Sum('sum')))
    if len(totals) > 0:
        output = []
        for total in totals:
            output.append({
                'date': total['date'],
                'total': round(total['total_sum'] * multiply_by, 2)
            })
        return create_json_response(request, output)
    return create_json_response(request, {"status": "failed"})


def get_sums(request, sensor_id=None, year=None):
    if year is None:
        start = date(date.today().year, 1, 1)
        end = date(date.today().year, 12, 31)
    else:
        start = date(int(year), 1, 1)
        end = date(int(year), 12, 31)

    sensorvaluemonthlysum = SensorValueMonthlySum.objects.filter(
        date__gte=start, date__lte=end)

    if sensor_id is None:
        output = {}
        for sensor in Sensor.objects.all().values_list('id', flat=True):
            output[sensor] = list(sensorvaluemonthlysum.filter(
                sensor_id=sensor).values('date').annotate(total=Sum('sum')).order_by('date'))
    else:
        output = list(sensorvaluemonthlysum.filter(
            sensor_id=sensor_id).values('date').annotate(total=Sum('sum')).order_by('date'))

    return create_json_response(request, output)


def get_avgs(request, sensor_id=None, year=None):
    if year is None:
        start = date(date.today().year, 1, 1)
        end = date(date.today().year, 12, 31)
    else:
        start = date(int(year), 1, 1)
        end = date(int(year), 12, 31)

    sensorvaluemonthlyavg = SensorValueMonthlyAvg.objects.filter(
        date__gte=start, date__lte=end)

    if sensor_id is None:
        output = {}
        for sensor in Sensor.objects.all().values_list('id', flat=True):
            output[sensor] = list(sensorvaluemonthlyavg.filter(
                sensor_id=sensor).values('date').annotate(total=Avg('avg')).order_by('date'))
    else:
        output = list(sensorvaluemonthlyavg.filter(
            sensor_id=sensor_id).values('date').annotate(total=Avg('avg')).order_by('date'))

    return create_json_response(request, output)


def get_sensorvalue_history_list(request):
    cursor = connection.cursor()
    cursor.execute(
        '''SELECT DISTINCT date_part('year', server_sensorvaluemonthlysum.date) as year FROM server_sensorvaluemonthlysum ORDER BY year DESC''')

    output = [int(x[0]) for x in cursor.fetchall()]
    return create_json_response(request, output)


def get_detailed_sensor_values(request, sensor_id):
    start = get_past_time(days=1)
    output = list(SensorValue.objects.filter(
        sensor_id=sensor_id, timestamp__gte=start).values_list('timestamp', 'value'))

    return create_json_response(request, output)

def get_daily_loads(request):
    start = get_past_time(days=1)
    sensors = Sensor.objects.filter(device__device_type=Device.TC, key='get_consumption_power').values_list('id', flat=True)

    output = {
        'thermal': {},
        'warmwater': {},
        'electrical': {},
    }
    for sensor_id in sensors:
        output['thermal'][sensor_id] = list(SensorValue.objects.filter(sensor__id=sensor_id, timestamp__gte=start).values_list('timestamp', 'value'))

    sensors = Sensor.objects.filter(device__device_type=Device.TC, key='get_warmwater_consumption_power').values_list('id', flat=True)
    for sensor_id in sensors:
        output['warmwater'][sensor_id] = list(SensorValue.objects.filter(sensor__id=sensor_id, timestamp__gte=start).values_list('timestamp', 'value'))

    sensors = Sensor.objects.filter(device__device_type=Device.EC, key='get_consumption_power').values_list('id', flat=True)
    for sensor_id in sensors:
        output['electrical'][sensor_id] = list(SensorValue.objects.filter(sensor__id=sensor_id, timestamp__gte=start).values_list('timestamp', 'value'))

    return create_json_response(request, output)

def get_total_balance(request, year=None, month=None):
    try:
        year = int(year)
    except (TypeError, ValueError):
        current = get_past_time()
        year = current.year

    if month is None:
        months = [x for x in range(1, 13)]
    else:
        try:
            month = int(month)
        except (TypeError, ValueError):
            months = [current.month]

    output = {}
    for month in months:
        start = date(year, month, 1)
        end = date(year, month, calendar.mdays[month])

        key = str(month) + '-' + str(year)
        if month < 10:
            key = '0' + key

        output[key] = get_total_balance_by_date(month, year)

    return create_json_response(request, output)

def get_latest_total_balance(request):
    current = get_past_time()
    year = current.year
    month = current.month


    output = dict([('month', month), ('year', year)]
         + get_total_balance_by_date(month, year).items())

    return create_json_response(request, output)

def get_total_balance_by_date(month, year):
    
    start = date(year, month, 1)
    end = date(year, month, calendar.mdays[month])

    # calculate costs
    sensor_ids = Sensor.objects.filter(device__device_type__in=[Device.CU, Device.PLB]).values_list('id', flat=True)
    sensor_values = SensorValueMonthlySum.objects.filter(date__gte=start, date__lte=end, sensor_id__in=sensor_ids, sensor__key='current_gas_consumption')

    total_gas_consumption = 0
    for sensor_value in sensor_values:
        total_gas_consumption += sensor_value.sum

    costs = total_gas_consumption * get_configuration('gas_costs')

    # Calculate electrical purchase
    sensor_ids = Sensor.objects.filter(device__device_type=Device.PM).values_list('id', flat=True)
    sensor_values = SensorValueMonthlySum.objects.filter(date__gte=start, date__lte=end, sensor_id__in=sensor_ids, sensor__key='purchased')

    total_electrical_purchase = 0
    for sensor_value in sensor_values:
        total_electrical_purchase += sensor_value.sum

    costs += total_electrical_purchase * get_configuration('electrical_costs')

    # calculate rewards

    # thermal consumption
    sensor_ids = Sensor.objects.filter(device__device_type=Device.TC).values_list('id', flat=True)
    sensor_values = SensorValueMonthlySum.objects.filter(date__gte=start, date__lte=end, sensor_id__in=sensor_ids, sensor__key='get_consumption_power')

    total_thermal_consumption = 0
    for sensor_value in sensor_values:
        total_thermal_consumption += sensor_value.sum

    rewards = total_thermal_consumption * get_configuration('thermal_revenues')
    
    # warmwater consumption
    sensor_values = SensorValueMonthlySum.objects.filter(date__gte=start, date__lte=end, sensor_id__in=sensor_ids, sensor__key='get_warmwater_consumption_power')

    total_warmwater_consumption = 0
    for sensor_value in sensor_values:
        total_warmwater_consumption += sensor_value.sum

    rewards += total_warmwater_consumption * get_configuration('warmwater_revenues')

    # electrical consumption
    sensor_ids = Sensor.objects.filter(device__device_type=Device.EC).values_list('id', flat=True)
    sensor_values = SensorValueMonthlySum.objects.filter(date__gte=start, date__lte=end, sensor_id__in=sensor_ids, sensor__key='get_consumption_power')

    total_electrical_consumption = 0
    for sensor_value in sensor_values:
        total_electrical_consumption += sensor_value.sum

    rewards += total_electrical_consumption * get_configuration('electrical_revenues')

    # electrical infeed
    sensor_ids = Sensor.objects.filter(device__device_type=Device.PM).values_list('id', flat=True)
    sensor_values = SensorValueMonthlySum.objects.filter(date__gte=start, date__lte=end, sensor_id__in=sensor_ids, sensor__key='fed_in_electricity')

    total_electrical_infeed = 0
    for sensor_value in sensor_values:
        total_electrical_infeed += sensor_value.sum

    rewards += total_electrical_infeed * get_configuration('feed_in_reward')

    return {
        'costs': round(costs, 2),
        'rewards': round(rewards, 2),
        'balance': round(rewards-costs, 2)
    }
