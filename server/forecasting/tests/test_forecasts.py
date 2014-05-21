import unittest
from datetime import datetime
import os

from server.forecasting.forecasting import Forecast
from server.forecasting.forecasting.dataloader import DataLoader
from server.forecasting.environment import ForwardableRealtimeEnvironment
from server.forecasting.forecasting.helpers import approximate_index


class ForecastTests(unittest.TestCase):

    def setUp(self):
        # dataset containing one year of data, sampled in 10 minute intervals
        DataLoader.cached_csv = {} #really important to reset, because other systems could have added data which is unwanted
        path = os.path.join(os.path.realpath('server'), "forecasting/tools/Electricity_2013.csv")
        raw_dataset = DataLoader.load_from_file(path, "Strom - Verbrauchertotal (Aktuell)", "\t")
        #cast to float and convert to kW
        self.dataset = [float(val) / 1000.0 for val in raw_dataset]
    
    def setup_forecast(self):
        hourly_data = Forecast.make_hourly(self.dataset, 6)
        self.env = ForwardableRealtimeEnvironment()
        self.forecast = Forecast(self.env, hourly_data, 1, None, (0.0000000, 0.0,1.0), hw_optimization="RMSE")
        

    def test_data(self):
        print "--------- test data ------------------"
        path = os.path.join(os.path.realpath('server'), "forecasting/tools/Electricity_2013.csv")
        date_dataset = DataLoader.load_from_file(path, "Datum", "\t")
        ten_min = 10 * 60
        epsilon = 599  # maximal 599 seconds deviatiation from samplinginterval
        print len(date_dataset)
        for index, date in enumerate(date_dataset):
            if index < len(date_dataset) - 1:
                diff = int(date_dataset[index + 1]) - int(date_dataset[index])
                if abs(diff - ten_min) > 1000:
                    print index, diff
                self.assertTrue(abs(diff - ten_min) < epsilon, "a jump of " + str(
                    diff - ten_min) + " seconds at index " + str(index))

    def test_make_hourly(self):
        print "--------- test make_hourly ------------------"
        hourly_data = Forecast.make_hourly(self.dataset, 6)

        average = 0
        for i in range(6):
            average += self.dataset[i]
        average /= 6

        self.assertEqual(hourly_data[0], average, 
                         "calculated average not the same as function average")
        self.assertAlmostEqual(len(hourly_data), 24 * 365, delta=23,
                               msg="data for " + str(len(hourly_data) / 24) + " days")

    def test_split_week_data(self):
        print "--------- test split_week_data ------------------"
        hourly_data = Forecast.make_hourly(self.dataset, 6)
        env = ForwardableRealtimeEnvironment()
        fc = Forecast(env, hourly_data, hw_optimization="MASE", try_cache=False)

        self.assertTrue(
            len(fc.demands) == 7, "week_split does not contain 7 series")
        
        
        self.assertTrue(len(fc.demands[0]) / 24 >= fc.input_weeks, "the day series only contains " + str(
            len(fc.demands[0]) / 24) + " days, not " + str(fc.input_weeks) + " (or at least more than 50)")
        
        for i in range(7):
            self.assertTrue(fc.calculated_parameters[i]["mase"] < 20.0, "MASE of " + str(
                fc.calculated_parameters[i]["mase"]) + "for day" + str(i) + " is way too high")
            
    def test_forecast_at(self):
        print "--------- test forecast_at ------------------"
        self.setup_forecast()
        (at_now, week_index, hour_index)  = self.forecast._forecast_at(self.env.now)
        
        self.assertTrue(week_index == 0, "day should be 0 but was " +str(week_index))
        self.assertTrue(hour_index == 0, "day should be 0 but was " +str(hour_index))
        
        hour = 60 * 60
        forward =  (24 * 7 +  2) * hour
        
        (at_now, week_index, hour_index)  = self.forecast._forecast_at(self.env.now + forward)
        
        self.assertTrue(week_index == 1, "week should be 1 but was " +str(week_index))
        self.assertTrue(hour_index == 2, "hour should be 2 but was " +str(hour_index))
        
    def test_append_data(self):
        print "--------- test append_values ------------------"
        self.setup_forecast()
        path = os.path.join(os.path.realpath('server'), "forecasting/tools/Electricity_until_may_2014.csv")
        raw_dataset_2014 = DataLoader.load_from_file(path, "Strom - Verbrauchertotal (Aktuell)", "\t")

        #cast to float and convert to kW
        dataset_2014 =  Forecast.make_hourly([float(val) / 1000.0 for val in raw_dataset_2014], 6)
        
        start = datetime(year=2014,month=1,day=1)
        split_demands14 = Forecast.split_weekdata(dataset_2014, 1, start)
        
        self.forecast.append_values(dataset_2014,start)
        
        four_weeks = 24 *4
        #check that arrays on same weekdays are equal
        self.assertSequenceEqual(self.forecast.demands[start.weekday()][-four_weeks:], split_demands14[start.weekday()][-four_weeks:])


        self.assertSequenceEqual(self.forecast.demands[3][-four_weeks:], split_demands14[3][-four_weeks:])
        
    def test_approximate_index(self):
        data = [1,2,3,5,6,7,8]
        self.assertTrue( approximate_index(data, 4) in [2,3], "index approximation was wrong" )
        print  approximate_index(data, 8)
        self.assertTrue( approximate_index(data, 8) == data.index(8))
        self.assertTrue( approximate_index(data, 9) == -1)
        self.assertTrue( approximate_index(data, 1.2436) == 0)
        self.assertTrue( approximate_index(data, 0) == -1)
        
        