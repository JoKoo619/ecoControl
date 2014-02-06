from device import Sensor, GeneratorDevice

class HeatStorage(Device.Device):

    def __init__(self, device_id):
        Device.Device.__init__(self, device_id)

        self.name = "HeatStorage"

        self.storage_capacity = 500 #l

        self.sensors = {"temperature":Sensor(name="temperature", id=0, value=30, unit=r"C", max_value=100,graph_id=2)}
        self.target_temperature =  90
        self.input_energy = 0
        self.output_energy = 0
        self.rising = True
        #specific heat capacity
        self.c = 0.00116 # kwh/l * K

    def add_energy(self,energy):
        self.input_energy += energy

    def consume_energy(self,energy):
        self.output_energy += energy

    def update(self,time_delta):
        energy_delta =  self.input_energy - self.output_energy
        #compute water temperature from energy
        self.sensors["temperature"].value +=  energy_delta / (self.storage_capacity * self.c)
        self.input_energy = 0
        self.output_energy = 0
        if self.sensors["temperature"].value >= self.target_temperature:
            self.rising = False
        elif not self.rising and self.sensors["temperature"].value < self.target_temperature - 30:
            self.rising = True

    def get_energy_demand(self):
        if self.rising:
            temperature_delta = self.target_temperature - self.sensors["temperature"].value
            energy = temperature_delta * self.c * self.storage_capacity
        else:
            energy = 0
        return energy
