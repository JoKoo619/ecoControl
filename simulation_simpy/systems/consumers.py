import math
import random
import datetime

from data import outside_temperatures_2013, daily_electric_demand
from helpers import sign


class SimpleThermalConsumer():

    def __init__(self, env, heat_storage):
        self.env = env
        self.heat_storage = heat_storage

        self.base_demand = 20.0  # kW
        self.varying_demand = 25.0  # kW

        self.total_consumption = 0.0  # kWh

        # list of 24 values representing relative demand per hour
        self.daily_demand = [50 / 350.0, 25 / 350.0, 10 / 350.0, 10 / 350.0, 5 / 350.0, 20 / 350.0, 250 / 350.0, 1, 320 / 350.0, 290 / 350.0, 280 / 350.0, 310 /
                             350.0, 250 / 350.0, 230 / 350.0, 225 / 350.0, 160 / 350.0, 125 / 350.0, 160 / 350.0, 200 / 350.0, 220 / 350.0, 260 / 350.0, 130 / 350.0, 140 / 350.0, 120 / 350.0]

    def get_consumption(self):
        # calculate variation using daily demand
        variation = self.daily_demand[self.env.get_hour_of_day()] * self.varying_demand
        current_consumption = self.base_demand + variation

        return current_consumption

    def update(self):
        while True:
            consumption = self.get_consumption()
            self.total_consumption += consumption / self.env.accuracy
            self.heat_storage.consume_energy(consumption)

            self.env.log('Thermal demand:', '%f kW' % consumption)
            self.env.log('HS level:', '%f kWh' %
                         self.heat_storage.energy_stored())

            yield self.env.timeout(self.env.step_size)


class ThermalConsumer():

    """ physically based heating, using formulas from 
    http://www.model.in.tum.de/um/research/groups/ai/fki-berichte/postscript/fki-227-98.pdf and
    http://www.inference.phy.cam.ac.uk/is/papers/DanThermalModellingBuildings.pdf """

    def __init__(self, env, heat_storage):
        self.env = env
        self.heat_storage = heat_storage

        self.target_temperature = 25
        self.total_consumption = 0
        self.temperature_room = 20

        # list of 24 values representing  target_temperature per hour
        self.daily_demand = [18, 18, 19, 18, 19, 18, 19, 20, 21,
                             24, 24, 25, 24, 25, 25, 25, 26, 25, 25, 24, 23, 22, 21, 20]

        #data from pamiru48
        #has 12 apartments with 22 persons
        self.room_volume = 650 #m^3
        #assume 100W heating demand per m^2, rule of thumb for new housings
        self.max_power = self.room_volume * 100  # W
        self.current_power = 0
        self.window_surface = 4 * 4 * 12  # m^2, avg per room, avg rooms per appartments, appartments

        specific_heat_capacity_brick = 1360 * 10 ** 2  # J/(m^3 * K)
        # J / K, approximation for 15m^2walls, 0.2m thickness, walls, ceiling,
        heat_cap_brick = specific_heat_capacity_brick * (4 * 3 * 5 * 0.2)

        #J /( m^3 * K)
        specific_heat_capacity_air = 1290

        self.heat_capacity = specific_heat_capacity_air * \
            self.room_volume + heat_cap_brick

    def simulate_consumption(self):
        # calculate variation using daily demand
        self.target_temperature = self.daily_demand[self.env.get_hour_of_day()]

        self.heat_loss()

        # slow rise and fall of heating
        change_speed = 1
        slope = change_speed * \
            sign(self.target_temperature - self.temperature_room)
        power_delta = slope * self.env.step_size

        self.current_power += power_delta
        # clamp to maximum power
        self.current_power = max(min(self.current_power, self.max_power), 0)
        self.heat_room()


    def get_consumption(self):
        return self.current_power / 1000.0

    def update(self):
        while True:
            self.simulate_consumption()
            consumption = self.current_power / 1000.0
            self.total_consumption += consumption / self.env.accuracy
            self.heat_storage.consume_energy(consumption)

            self.env.log('Thermal demand:', '%f kW' % consumption)
            self.env.log('HS level:', '%f kWh' %
                         self.heat_storage.energy_stored())

            yield self.env.timeout(self.env.step_size)

    def heat_loss(self):
        # assume cooling of power/2
        d = self.temperature_room - \
            self.env.get_outside_temperature()
        # heat transfer coefficient normal glas window, W/(m^2 * K)
        k = 5.9
        # in Watt
        cooling_rate = (self.window_surface * k / self.heat_capacity)
        self.temperature_room -= d * cooling_rate * self.env.step_size

    def heat_room(self):
        # 0.8 denotes heating power to thermal energy efficiency
        heating_efficiency = 0.8 / (self.heat_capacity)
        temperature_delta = self.current_power * \
            heating_efficiency * self.env.step_size
        self.temperature_room += temperature_delta


class SimpleElectricalConsumer():

    def __init__(self, env, power_meter):
        self.env = env
        self.power_meter = power_meter

        self.base_demand = 5.0  # kW
        self.varying_demand = 7.5  # kW

        self.total_consumption = 0.0  # kWh

        # list of 24 values representing relative demand per hour
        self.demand_variation = [1.0 for i in range(24)]

    def get_consumption(self):
        # calculate variation using daily demand
        hour = self.env.get_hour_of_day()
        quarter = int(self.env.get_min_of_hour() / 15.0)
        demand = daily_electric_demand[hour*4 + quarter]
        return demand * self.demand_variation[hour]

    def update(self):
        while True:
            consumption = self.get_consumption()
            self.total_consumption += consumption / self.env.accuracy
            self.power_meter.consume_energy(consumption)

            self.env.log('Electrical demand:', '%f kW' % consumption)
            self.env.log('Infeed Reward:', '%f Euro' %
                         self.power_meter.get_reward())

            yield self.env.timeout(self.env.step_size)
