from time import time, gmtime


class BaseDevice(object):
    """Represents a general interface to the energy-systems."""

    acronym = "base"

    def __init__(self, device_id, env):
        self.id = device_id #: `int` identifier
        self.env = env #: `:class:BaseEnvironment`

    def calculate(self):
        pass

    def attach_dependent_devices_in(self, device_list):
        pass

    def attach(self, device):
        pass

    def connected(self):
        return True




class BaseEnvironment(object):
    """This class manages the environment of the devices holds the simulated time as well as the mode, the devices are running in.
    All connected devices share one BaseEnvironment"""

    def __init__(self, initial_time=None, step_size=120, demomode=False, forecast=False):
        """ demomode indicates, if running in demomode, not if this is the demo simulation"""
        if initial_time is None:
            self.now = time()
        else:
            self.now = initial_time
        #: a unix timestamp representing the start of simulation
        #: if initial_time is `None` the current time is used
        self.initial_date = self.now
        #: `int` value of seconds how often the simulated devices calculate their state
        self.step_size = step_size

        self.demo_mode = demomode
        """ ======================================  =============================   =============================
            |dArr| `forecast` | `demo_mode` |rarr|           ``True``                         ``False``                                                                      
            ======================================  =============================   =============================
                ``True``                            forecast of simulated devices   forecast of real devices
                ``False``                           demo simulation                 real device (env not defined)
            ======================================  =============================   =============================
        """
        #: see `demo_mode`
        self.forecast = forecast

    def get_day_of_year(self):
        """Returns an `int` value of the current simulated day of the year"""
        return gmtime(self.now).tm_yday

    def is_demo_simulation(self):
        """ Returns, if this is the demo_simulation"""
        return self.demo_mode and not self.forecast