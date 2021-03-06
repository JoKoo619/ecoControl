import time
import logging
import calendar
from datetime import datetime
from threading import Thread
from collections import namedtuple

from server.models import Device, DeviceConfiguration, Configuration, Sensor, SensorValue
from server.devices import get_user_function, execute_user_function
from server.functions import get_configuration, parse_value
from server.helpers_thread import write_pidfile_or_fail

from server.forecasting.measurementstorage import MeasurementStorage

from server.devices.base import BaseEnvironment
from server.forecasting.simulation.devices.producers import SimulatedCogenerationUnit, SimulatedPeakLoadBoiler
from server.forecasting.simulation.devices.storages import SimulatedHeatStorage, SimulatedPowerMeter
from server.forecasting.simulation.devices.consumers import SimulatedThermalConsumer, SimulatedElectricalConsumer
from server.forecasting.optimizing.auto_optimization import auto_optimize

DEFAULT_FORECAST_INTERVAL = 14 * 24 * 3600.0
DEFAULT_FORECAST_STEP_SIZE = 15 * 60.0
logger = logging.getLogger('simulation')

""" Return the result of a forecast.
    For short-lived forecasts, call this. It will create a :class:`Forecast` 
    and block, until the forecast is finished. 
    For parameters see :class:`Forecast`"""
def get_forecast(initial_time, configurations=None, code=None, forward=None):
    forecast_object = Forecast(initial_time, configurations, code=code,
                               forecast=True, forward=forward)
    return forecast_object.run().get() #dont start in thread

def get_initialized_scenario(env, configurations):
        """ this function returns an initialized scenario. 
        It creates new simulated devices and connects the right devices.

        The devices are restored to the latest state of the |SensorValue|'s in the db,
        if there are no Values, a warning will be logged and the standard values are used.

        :param env: |env| for all Devices
        :param list configurations: the device configurations, which to set in the devices. 
            These are typically |DeviceConfiguration| objects.

        :returns: a :py:class:`namedtuple` of devices, with the acronym (f.e plb), as key
        """
        devices = list(Device.objects.all())
        device_list = []
        for device in devices:
            for device_type, class_name in Device.DEVICE_TYPES:
                if device.device_type == device_type:
                    device_class = globals()['Simulated%s' % class_name]
                    device_list.append(device_class(device.id, env))


        for device in device_list:
            # connect power devices
            device.attach_dependent_devices_in(device_list)
            if not device.connected():
                logger.error(
                    "Simulation: Device %s is not connected" % device.name)
                raise RuntimeError

            # configure devices
            for configuration in configurations:
                if configuration.device_id == device.id:
                    value = parse_value(configuration)
                    if configuration.key in device.config:
                        device.config[configuration.key] = value

            # load latest sensor values
            try:
                for sensor in Sensor.objects.filter(device_id=device.id):
                    value = SensorValue.objects.filter(
                        sensor=sensor).latest('timestamp').value
                    if sensor.setter != '':
                        callback = getattr(device, sensor.setter, None)
                        if callback is not None:
                            if hasattr(callback, '__call__'):
                                callback(value)
                            else:
                                setattr(device, sensor.setter, value)

            except SensorValue.DoesNotExist:
                logger.warning("Simulation: No sensor values \
                    found for sensor '%s' at device '%s'"
                               % (sensor.name, sensor.device.name))
            except Sensor.DoesNotExist:
                logger.warning(
                    'Could not find any sensor values to configure simulation')

            # re-calculate values
            device.calculate()
        # create high performance tuple with device acronyms as field names
        device_tuple = namedtuple("Devices", [dev.acronym for dev in device_list])(*device_list)
        
        return device_tuple


class ForecastQueue():
    """ A container, holding the running forecasts. Each forecast gets an id.

    Usage::

        q = ForecastQueue()
        f_id = q.schedule_new(initial_time=time.time())
        #... do other stuff, then retrieve forecast
        result = q.get_by_id(f_id)

    """
    forecasts = []
    id = 0

    def schedule_new(self, initial_time, **kwargs):
        """ start a new forecast and return its id.
        :param dict kwargs: the parameters for the :class:`Forecast`
        """
        self.id += 1
        forecast = Forecast(initial_time, **kwargs)
        self.forecasts.append((self.id,forecast))
        forecast.start()
        return self.id

    def get_by_id(self, forecast_id):
        """ get a forecast by its id. 
        Will return ``None``, if forecast is not completed.
        If the forecast is finished, the result is returned and deleted 
        from the ForecastQueue.
        """
        for index, (_id, forecast) in enumerate(self.forecasts):
            if _id == forecast_id:
                result = forecast.get()
                if result != None:
                    del self.forecasts[index]
                return result


class Forecast(Thread):
    """ Setup a Forecast Object. A new |env| and new Devices will be created.
    Forecasting can either be ran synchronous or asynchronous (threaded)::

        foocast = Forecast(time.time(), forward=10*24*3600)
        barcast = Forecast(time.time(), forward=2*24*3600)

        #run threaded
        barcast.start() 
        
        #wait until foocast is finished, then get result
        resultfoo = foocast.run().get() 
        
        # wait until barcast is finished
        while resultbar == None:
            resultbar = barcast.get()


    :param int initial_time: timestamp of the time, at which the forecast starts
    :param configurations: cached configurations, if ``None``, retrieve from database
    :param code: code to be executed
    :param int forward: Time to forecast. Uses `DEFAULT_FORECAST_INTERVAL` if ``None``
    :param boolean forecast: Passed to |env| forecast.
    """
    def __init__(self, initial_time, configurations=None, code=None, forward=None, forecast=True):
        Thread.__init__(self)
        self.daemon = True
        demomode = Configuration.objects.get(key='system_mode').value == "demo"

        self.env = BaseEnvironment(initial_time=initial_time, forecast=forecast,
                              step_size=DEFAULT_FORECAST_STEP_SIZE,demomode=demomode) #get_forecast

        if configurations is None:
            configurations = DeviceConfiguration.objects.all()

        self.devices = get_initialized_scenario(self.env, configurations)

        self.measurements = MeasurementStorage(self.env, self.devices)
        self.user_function = get_user_function(self.devices, code)
        self.progress = 0.0
        self.result = None
        self.forward = forward

        if forward == None:
            self.forward = DEFAULT_FORECAST_INTERVAL

        self.next_optimization = 0.0
        self.use_optimization = get_configuration('auto_optimization')

    def step(self):
        """ execute one step of the simulation.
        This steps all devices, auto-optimizes if needed and store the values
        """
        execute_user_function(self.env,self.env.forecast,self.devices,self.user_function)

        if self.use_optimization and self.next_optimization <= 0.0:
            auto_optimize(self)
            self.next_optimization = 3600.0

        # call step function for all devices
        for device in self.devices:
            device.step()

        self.store_values()

        self.env.now += self.env.step_size
        self.next_optimization -= self.env.step_size


    def run(self):
        """ run the main loop. Returns self after finishing.
        Results are obtained with :meth:`get`"""
        time_remaining = self.forward
        while time_remaining > 0:
            self.step()

            self.progress = (1.0 - time_remaining/float(self.forward)) * 100
            time_remaining -= self.env.step_size

        self.result =  {
            'start': datetime.fromtimestamp(self.env.initial_date).isoformat(),
            'step': DEFAULT_FORECAST_STEP_SIZE,
            'end': datetime.fromtimestamp(self.env.now).isoformat(),
            'sensors': self.measurements.get_cached()
        }

        return self

    def store_values(self):
        """ sample device values"""
        self.measurements.take_and_cache()

    def get(self):
        """ return the result of the forecast. 
        If the mainloop is still forecasting, ``None`` is returned.

        outputs a dict with::

            result = {start: datetime, 
                       step: stepsize, 
                        end: datetime, 
                    sensors: list with values per sensor (see MeasurementStorage)}

        """
        return self.result



class DemoSimulation(Forecast):
    """ A Forecast, which writes the values to the database. 
    It replaces the real devices and is used to develop and show the capabilities of ecoControl.
    It uses real electrical and weather values instead of forecasts, 
    the device simulation on the other hand is the same as in :class:`Forecast`.

    After calling start(), the simulation will currently run at 30 steps per second (or 30x speed).
    This is controlled by the `step_size` in |env|. 

    The simulation can be forwarded to a certain point by setting the `forward` variable in seconds > 0.
    It will then run at maximum speed. The simulation runs until the variable `running` is set to False.

    .. note:: DemoSimulations should generally be started with :meth:`start_or_get`
    """
    stored_simulation = None


    def __init__(self, initial_time, configurations=None):
        Forecast.__init__(self, initial_time, configurations, forward=0, forecast=False)

        self.steps_per_second = 3600.0  / self.env.step_size
        self.running = False

    @classmethod
    def start_or_get(cls, print_visible=False):
        """
        This method starts a new demo simulation
        if necessary and it makes sure that only
        one demo simulation can run at once.
        This is the preferred way to start the demo simulation.

        :returns: :class:`DemoSimulation` or ``None`` if system not in demo mode.
        """
        # Start demo simulation if in demo mode
        system_mode = Configuration.objects.get(key='system_mode')
        if system_mode.value != 'demo':
            return None

        if cls.stored_simulation == None:
            if print_visible:
                print "Starting demo simulation..."
            else:
                logger.debug("Starting demo simulation...")

            simulation = DemoSimulation(get_initial_time())
            simulation.use_optimization = get_configuration('auto_optimization')
            simulation.start()
            cls.stored_simulation = simulation

        return cls.stored_simulation


    def run(self):
        """ run while `running` is true, call the parent :meth:`step` method.
        This method must be called by :meth:`start`, otherwise it immediately returns"""
        while self.running:
            self.step()

            if self.forward > 0:
                self.forward -= self.env.step_size
            else:
                time.sleep(1.0 / self.steps_per_second)

    def store_values(self):
        """stores values in database. Overwrites parents saving method.
        Values are only stored every (simulated) minute"""
        if self.env.now % 60  != 0:
            return
        self.measurements.take_and_save()

    def start(self):
        "start the simulation in a seperate thread"
        self.running = True
        Thread.start(self)


def get_initial_time():
    "Return the time of the newest |SensorValue| in the database"
    try:
        latest_value = SensorValue.objects.latest('timestamp')
        return calendar.timegm(latest_value.timestamp.timetuple())
    except SensorValue.DoesNotExist:
        return 1356998400  # Tuesday 1st January 2013 12:00:00