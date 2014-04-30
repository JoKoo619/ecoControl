import time
import logging

from server.models import Device, DeviceConfiguration, Sensor, SensorValue

from environment import ForwardableRealtimeEnvironment
from helpers import BulkProcessor, SimulationBackgroundRunner, MeasurementStorage, parse_value

from systems.code import CodeExecuter
from systems.producers import CogenerationUnit, PeakLoadBoiler
from systems.storages import HeatStorage, PowerMeter
from systems.consumers import ThermalConsumer, ElectricalConsumer


logger = logging.getLogger('simulation')

class Simulation(object):

    # initial_time = Tuesday 1st January 2013 12:00:00
    def __init__(self, configurations=DeviceConfiguration.objects.all(), demo=False, initial_time=1356998400):

        if initial_time % 3600 != 0.0:
            # ensure that initial_time always at full hour, to avoid
            # measurement bug
            logger.info("Simulation: Change initial time to full hour")
            initial_time = (int(initial_time) / 3600) * 3600.0
        # initialize real-time environment
        self.env = ForwardableRealtimeEnvironment(initial_time=initial_time)
        self.demo = demo

        self.devices = self.get_initialized_scenario()
        self.configure(configurations)

        self.measurements = MeasurementStorage(self.env, self.devices, demo=self.demo)
        self.env.register_step_function(self.measurements.take)

        self.thread = None
        self.running = False

        # initialize BulkProcessor and add it to env
        self.bulk_processor = BulkProcessor(self.env, self.devices)
        self.env.process(self.bulk_processor.loop())

    def get_initialized_scenario(self):
        devices = list(Device.objects.all())
        system_list = []
        for device in devices:
            for device_type, class_name in Device.DEVICE_TYPES:
                if device.device_type == device_type:
                    system_class = globals()[class_name]
                    system_list.append(system_class(device.id, self.env))

        # connect power systems
        for device in system_list:
            if isinstance(device, CogenerationUnit):
                for connected_device in system_list:
                    if isinstance(connected_device, HeatStorage):
                        device.heat_storage = connected_device
                    elif isinstance(connected_device, PowerMeter):
                        device.power_meter = connected_device
            elif isinstance(device, PeakLoadBoiler) or isinstance(device, ThermalConsumer):
                for connected_device in system_list:
                    if isinstance(connected_device, HeatStorage):
                        device.heat_storage = connected_device
            elif isinstance(device, ElectricalConsumer):
                for connected_device in system_list:
                    if isinstance(connected_device, PowerMeter):
                        device.power_meter = connected_device
            elif isinstance(device, CodeExecuter):
                device.register_local_variables(system_list)

            if not device.connected():
                logger.error("Simulation: Device %s is not connected" % device.name)
                raise RuntimeError

        return system_list

    def configure(self, configurations):
        simulation_config = []
        for configuration in configurations:
            value = parse_value(configuration.value, configuration.value_type)
            system = self.get_system(configuration.device_id)
            if system is not None and configuration.key in dir(system):
                setattr(system, configuration.key, value)

        for device in self.devices:
            # load latest sensor values
            if not self.demo:
                for sensor in Sensor.objects.filter(device_id=device.id):
                    try:
                        latest_sensor_value = SensorValue.objects.filter(sensor=sensor).latest('timestamp')
                        value = parse_value(latest_sensor_value.value, sensor.value_type)
                        if sensor.setter != '':
                            callback = getattr(device, sensor.setter, None)
                            if callback is not None:
                                if hasattr(value, '__call__'):
                                    callback(value)
                                else:
                                    setattr(device, sensor.setter, value)

                    except SensorValue.DoesNotExist:
                        logger.warning("Simulation: No sensor values \
                            found for sensor '%s' at device '%s'" \
                            % (sensor.name, sensor.device.name))

            # re-calculate values of ThermalConsumers
            if isinstance(device, ThermalConsumer):
                device.calculate()

    def get_system(self, device_id):
        for device in self.devices:
            if device.id == device_id:
                return device
        logger.warning("Simulation: Couldn't find device with id " + str(device_id))
        return None

    def start(self, blocking=False):
        self.thread = SimulationBackgroundRunner(self.env)
        self.thread.start()
        self.running = True
        if blocking:
            # wait on forwarding to end
            # cant use thread.join() here, because sim will not stop after
            # forward
            while self.is_forwarding():
                time.sleep(0.2)

    def forward(self, seconds, blocking=False):
        self.env.forward = seconds
        if self.thread == None or not self.thread.isAlive():
            self.start(blocking)

    def is_forwarding(self):
        return self.env.forward > 0.0

    def get_total_bilance(self):
        return self.cu.get_operating_costs() + self.plb.get_operating_costs() - \
            self.pm.get_reward() + self.pm.get_costs()

    def get_measurements(self, start=None):
        output = []
        # output = [
        #     ('cu_electrical_production',
        #      [round(self.cu.current_electrical_production, 2)]),
        #     ('cu_total_electrical_production',
        #      [round(self.cu.total_electrical_production, 2)]),
        #     ('cu_thermal_production',
        #      [round(self.cu.current_thermal_production, 2)]),
        #     ('cu_total_thermal_production',
        #      [round(self.cu.total_thermal_production, 2)]),
        #     ('cu_total_gas_consumption',
        #      [round(self.cu.total_gas_consumption, 2)]),
        #     ('cu_operating_costs', [round(self.cu.get_operating_costs(), 2)]),
        #     ('cu_power_ons', [self.cu.power_on_count]),
        #     ('cu_total_hours_of_operation',
        #      [round(self.cu.total_hours_of_operation, 2)]),
        #     ('plb_thermal_production',
        #      [round(self.plb.current_thermal_production, 2)]),
        #     ('plb_total_gas_consumption',
        #      [round(self.plb.total_gas_consumption, 2)]),
        #     ('plb_operating_costs',
        #      [round(self.plb.get_operating_costs(), 2)]),
        #     ('plb_power_ons', [self.plb.power_on_count]),
        #     ('plb_total_hours_of_operation',
        #      [round(self.plb.total_hours_of_operation, 2)]),
        #     ('hs_total_input', [round(self.hs.input_energy, 2)]),
        #     ('hs_total_output', [round(self.hs.output_energy, 2)]),
        #     ('hs_empty_count', [round(self.hs.empty_count, 2)]),
        #     ('total_thermal_consumption',
        #      [round(self.tc.total_consumption, 2)]),
        #     ('total_electrical_consumption',
        #      [round(self.ec.total_consumption, 2)]),
        #     ('infeed_reward', [round(self.pm.get_reward(), 2)]),
        #     ('infeed_costs', [round(self.pm.get_costs(), 2)]),
        #     ('total_bilance', [round(self.get_total_bilance(), 2)]),
        #     ('code_execution_status',
        #      [1 if self.ce.execution_successful else 0])]

        output += self.measurements.get(start)

        return dict(output)
