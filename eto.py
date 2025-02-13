"""
Penman-Monteith Equation implementation in Python.

Full implementation of Penman-Monteith ETo equation based on UAN-FAO
[Irrigation and Drainage Paper 56](http://www.fao.org/3/X0490E/x0490e00.htm)

Penman-Monteith equation is used to calculate reference crop evapotranspiration (ETo)
for a given location using available climate data. This method provides many ways of estimating
missing climate data using minimal data.

Homepage of the project: https://github.com/sherzodr/penmon

"""

import math
import datetime as dt
import warnings
CHECK_RADIATION_RANGE = True
CHECK_SUNSHINE_HOURS_RANGE = True

def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


class Station:
    """ Class that implements a weather station at a known latitude and elevation."""

    def __init__(self, latitude, longitude, altitude, anemometer_height=2, timezone_longitude=345):
        """
        Required parameters:

        :param latitude: latitude of the location in decimal format. For southern
            hemisphere negative number must be used
        :type latitude: float

        :param altitude: altitude (elevation) of the location in meters
        :type altitude: int

        :param anemometer_height=2: height of the anemometer (wind-speed)
            measuring device
        :type anemometer_height: int

        :param timezone_longitude=345 (degrees west of greenwhich, here set for UTC+1)

        Following are additional attributes that you can get/set on this station
        after instantiation:

         * latitude_rad - latitude in radian, alculated based on latitude
         * days - dictionary of days recorded (or calculated) by this station
         * climate - set to default **Climate()** instance
         * ref_crop - instance of **Crop** class, which sets default chracteristics
                      of the reference crop according to the paper.

        Should you wish to change assumes Climate and Crop characteristics
        you can do so after the object is innitialized, like so:

            station=Station(41.42, 109)
            station.ref_crop = Crop(albedo=0.25, height=0.35)
        """

        if not type(latitude) is float:
            raise TypeError("latitude must be a float")

        if not type(longitude) is float:
            raise TypeError("longitude must be a float")

        if latitude < -90.0 or latitude > 90.0:
            raise Exception("latitude must be between -90.0 and 90.0")

        if longitude < 0 or longitude > 360.0:
            raise Exception("longitude in degrees West of Greenwhich.")

        if not type(altitude) is int:
            raise TypeError("altitude must be an integer")

        if altitude < 0:
            raise Exception("'altitude' must be above 0")

        if (timezone_longitude < 0) or (timezone_longitude>359):
            raise Exception("'timezone_longitude in degrees West of Greenwhich.")

        self.latitude = latitude
        self.longitude = longitude

        self.altitude = altitude
        self.latitude_rad = round((math.pi / 180 * self.latitude), 3)
        self.longitude_rad = round((math.pi / 180 * self.longitude), 3)
        warnings.warn('timezone_longitude (longitude of center of local timezone) is set to 345° (for UTC+1). If location changes updating is necessary!')
        self.timezone_longitude = 345 # degrees west of greenwhich
        self.days = {}
        self.hours = {}
        # setting default parameters for the station
        self.anemometer_height = anemometer_height
        self.climate = Climate()
        self.ref_crop = Crop()

    def day_entry(self, day_number, date_template="%Y-%m-%d",
                temp_min=None,
                temp_max=None,
                temp_mean=None,
                wind_speed=None,
                humidity_mean=None,
                radiation_s=None,
                sunshine_hours=None
                ):
        """
        Given a day number (integer type from 1-366) returns a **StationDay*** instance for
        that day. Logs the day in *days* attribute of the **Station()** class.

        If it receives a string it expects it to be in "yyyy-mm-dd" format, in which case
        it parses the string into **datetime** and calculates day number

        If your date format is different than assumed, you can adjust *date_template*
        as the second parameter. For example, following all three lines are identical

            day = station.day_entry(229)
            day = station.day_entry("2020-08-16")
            day = station.day_entry('08/16/2020', '%m/%d/%Y')

        You can pass the following named-parameters to the method:

         - temp_min
         - temp_max
         - wind_speed
         - radiation_s
         - sunshine_hours

         If *radiation_s* and *sunshine_hours* is out of range for this location
         for this date (based on solar declination, sun-distance and daylight hours)
         raises ValueError exception.
        """

        if type(day_number) is str:
            try:
                dt1 = dt.datetime.strptime(day_number, date_template)
            except ValueError:
                raise ValueError(
                    "Date must be in YYYY-MM-DD format (ex: 2020-09-28)")

            dt0 = dt.datetime(dt1.year, 1, 1)
            dates_delta = dt1 - dt0
            day_number = dates_delta.days + 1

        if not type(day_number) is int:
           try:
               dt0 = dt.datetime(day_number.year, 1, 1)
               dates_delta = day_number - dt0
               day_number = dates_delta.days + 1
           except:
               raise TypeError("'day_number' must be an integer")

        if not (day_number >= 1 and day_number <= 366):
            raise Exception("'day_number' must be between in the range 1-366")

        day = DayEntry(day_number, self)

        self.days[day_number] = day
        day.temp_min = temp_min
        day.temp_max = temp_max
        day.temp_mean = temp_mean
        day.humidity_mean = humidity_mean
        day.wind_speed = wind_speed

        if radiation_s:
            if CHECK_RADIATION_RANGE:
                if radiation_s <= day.R_so():
                    day.radiation_s = radiation_s
                else:
                    raise ValueError("Raditaion out of range")
            else:
                day.radiation_s = radiation_s

        if sunshine_hours:
            if CHECK_SUNSHINE_HOURS_RANGE:
                if sunshine_hours <= day.daylight_hours():
                    day.sunshine_hours = sunshine_hours
                else:
                    raise ValueError("Sunshine hours out of range")
            else:
                day.sunshine_hours = sunshine_hours

        return day

    #get_day = day_entry

    def hour_entry(self, dt_hour, time_template="%Y-%m-%d %H:%M:%S",
                temp_min=None,
                temp_max=None,
                temp_mean=None,
                wind_speed=None,
                humidity_mean=None,
                radiation_s=None,
                ):
        """
        Given a hour (datetime) returns a **StationHour*** instance for
        that hour. Logs the hours in *hours* attribute of the **Station()** class.

        If it receives "directly" a datetime

        You can pass the following named-parameters to the method:

         - temp_min
         - temp_max
         - wind_speed
         - radiation_s

         If *radiation_s* is out of range for this location
         for this date (based on solar declination, sun-distance and daylight hours)
         raises ValueError exception.
        """

        if type(dt_hour) is str:
            try:
                dt_hour = dt.datetime.strptime(dt_hour, time_template)
            except ValueError:
                raise ValueError(
                    "Datetime must be in YYYY-MM-DD HH:mm:SS format (ex: 2020-09-28 00:00:00)")

            dt0 = dt.datetime(dt_hour.year, 1, 1)
            dates_delta = dt_hour - dt0
            day_number = dates_delta.days + 1

        if type(dt_hour) is int:
            raise TypeError("'dt_hour' must not be an integer")

        hour = HourEntry(dt_hour, self)

        self.hours[int(dt.datetime.timestamp(dt_hour)/3600)] = hour
        hour.temp_min = temp_min
        hour.temp_max = temp_max
        hour.temp_mean = temp_mean
        hour.humidity_mean = humidity_mean
        hour.wind_speed = wind_speed

        if radiation_s:
            if CHECK_RADIATION_RANGE:
                if radiation_s - hour.R_so() > 0.05*hour.R_so():
                    hour.radiation_s = radiation_s
                else:
                    raise ValueError("Radiation out of range")
            else:
                hour.radiation_s = radiation_s

        return hour

    #get_hour = hour_entry

    def atmospheric_pressure(self):
        """
        Calculates atmospheric pressure *in kPa* based on station's altitude. (Eq. 7)
        """
        return round(101.3 * ((293 - 0.0065 * self.altitude) / 293) ** 5.26, 2)

    def describe(self):
        """
        Describes the station and all its assumptions in human-friendly text
        """
        return self


class TimeEntry:
    """
    Represents a single day retrieved from the Station.

    This class is usually not instantiated directly. It's instantniated by the
    **Station()**'s day_entry() method, passing all reuqired state data.

    Since bulk of Penman-Moneith is concerned with a daily ETo **StationDay** is
    heart of the module. Penman-Monteith equatoin is implemented within the
    methods of **StationDay**.

    All meteorological data are stored within this class instance.
    """

    def __init__(self, time, station):
        """
        *time* and *station* are two required arguments passed to
        instantiate the class.
        *time* is a datetime.datetime instance representing time. It is used to caluclate day_number
        Alternatively *time* can be day_number (int), if daily scale is applied.

        Following attributes of the class are available. They can be both set
        and get.

        - time
        - day_number
        - station   - references **Station** class.
        - temp_min
        - temp_max
        - temp_mean
        - temp_dew
        - temp_dry
        - temp_wet
        - humidity_mean
        - humidity_min
        - humidity_max
        - vapour_pressure
        - logged_atmospheric_pressure
        - wind_speed
        - radiation_s
        - stephan_boltzman_constant
        - climate  - convenient reference to station.climate
        """
        if type(time) == int:
            self.day_number = time
        else:
            # calculate the day number
            dt0 = dt.datetime(time.year, 1, 1)
            dates_delta = time - dt0
            self.day_number = dates_delta.days + 1

        self.time = time
        self.station = station

        self.temp_min = None
        self.temp_max = None
        self.temp_mean = None
        self.humidity_mean = None
        self.humidity_min = None
        self.humidity_max = None
        self.wind_speed = None
        self.radiation_s = None
        self.temp_dew = None
        self.temp_dry = None
        self.temp_wet = None
        self.temp_soil = None
        self.climate = station.climate
        self.stephan_boltzmann_constant = 4.903 * (10 ** -9)
        self.logged_atmospheric_pressure = None
        self.vapour_pressure = None
        self.sunshine_hours = None

    def wind_speed_2m(self):
        """
        Returns wind speed at 2m height.

        If this information is already logged, returns as is. If anemometer of
        the Station is located higher and wind speed information is available it
        converts this information to wind speed as 2ms based on  logarithimc
        conversion (Eq. 47)

        If wind speed was not logged for this date, and if climate is known
        tries to rely on Climate data to estimate average wind speed
        """

        # if wind speed at 2m height is given, return it
        if self.wind_speed and (self.station.anemometer_height == 2):
            return self.wind_speed

        # if wind speed at height different than 2m is given, calculate wind
        # speed at 2m
        if self.wind_speed and self.station.anemometer_height != 2:
            return round(self.wind_speed * (4.87 /
                                            math.log(67.8 * self.station.anemometer_height - 5.42)), 1)

        # if we reach this far no wind information is available to work with. we
        # consult if station has any climatic data, in which case we try to
        # deduce information off of that:
        if self.station.climate:
            return self.station.climate.average_wind_speed

        return None

    def dew_point(self):
        """
        If *temp_dew* attribute is logged returns as is. If this data was not
        logged, but *temp_min* data is available tries to estimate *temp_dew*
        based on Station's Climate. If either is not possible returns *None*.
        """
        if self.temp_dew:
            return self.temp_dew

        if self.temp_min and self.climate:
            return self.temp_min - self.climate.dew_point_difference

    def atmospheric_pressure(self):
        """
        If *atmospheric_pressure* is logged return as is. Else
        Calculates atmospheric pressure *in kPa* based on station's altitude. (Eq. 7)
        """
        if self.logged_atmospheric_pressure:
            return self.logged_atmospheric_pressure
        else:
            return self.station.atmospheric_pressure()

    def latent_heat_of_vaporization(self):
        """
        constant *2.45*
        """
        return 2.45

    def specific_heat(self):
        """
       constant: 1.013*10**(-3)
        """
        return 1.013 * 10 ** (-3)

    def psychrometric_constant(self):
        """
        Calculates psychrometric constant based on Station's altitude (and
        atmospheric pressure). (Eq. 8)
        """
        return round(0.665 * 10 ** (-3) * self.atmospheric_pressure(), 6)

    def Tmean(self):
        """
        If *temp_mean* is logged returns is as is. If *temp_min* and *temp_max*
        are available computes *Tmean* based on these data. If none are
        available returns *None*. (Eq. 9)
        """
        if self.temp_mean:
            return self.temp_mean

        if self.temp_max and self.temp_min:
            return ((self.temp_max + self.temp_min) / 2)

        return None

    def saturation_vapour_pressure(self, T):
        """
        Calculates saturation vapour pressure for a given temperature. (Eq. 11)
        """
        return round((0.6108 * 2.7183 ** (17.27 * T / (T + 237.3))), 3)

    def mean_saturation_vapour_pressure(self):
        """
        Given *temp_max* and *temp_min* calculates mean saturation vapour pressure. (Eq. 12)
        """
        if self.temp_max and self.temp_min:
            vp_max = self.saturation_vapour_pressure(self.temp_max)
            vp_min = self.saturation_vapour_pressure(self.temp_min)
            return (vp_max + vp_min) / 2

        if self.temp_mean:
            return self.saturation_vapour_pressure(self.temp_mean)

    def slope_of_saturation_vapour_pressure(self, T):
        """
        Calculates slope of the saturation vapour pressure curve for a given
        temperature. It's the required information to calculate ETo. (Eq. 13)
        """
        return round((4098 * (0.6108 * 2.7183 ** (17.27 * T / (T + 237.3))))
                     / ((T + 237.3) ** 2), 6)

    def actual_vapour_pressure(self):
        """
        Attepmts to calculate vapour pressure based on several available weather
        data.

        If *temp_dry* and *temp_wet* data are logged (psychrometric data) uses
        (Eq. 15) to calculate actual vapour pressure. If only *temp_dew*
        information is logged uses (Eq. 14) to calculate actual vapour pressure.
        If *humidity_max* and *humidity_min* are logged uses (Eq. 17) to
        calculate vapour pressure. If only *humidity_max* is known uses (Eq. 18)
        to estimate actual vapour pressure. If only *humidity_mean* is known
        uses (Eq. 19) to estimate actual vapour pressure.
        """
        if self.vapour_pressure:
            return self.vapour_pressure

        if self.temp_dry and self.temp_wet:
            vp_wet = self.saturation_vapour_pressure(self.temp_wet)
            psychrometric_constant = self.psychrometric_constant()
            return round(vp_wet - psychrometric_constant *
                         (self.temp_dry - self.temp_wet), 3)

        if self.humidity_max and self.humidity_min and self.temp_max and self.temp_min:
            vp_min = self.saturation_vapour_pressure(self.temp_min)
            vp_max = self.saturation_vapour_pressure(self.temp_max)
            return round((vp_min * (self.humidity_max / 100) +
                          vp_max * (self.humidity_min / 100)) / 2, 3)

        if self.humidity_max and self.temp_min:
            vp_min = self.saturation_vapour_pressure(self.temp_min)
            return round(vp_min * (self.humidity_max / 100), 3)

        if self.humidity_mean and self.temp_max and self.temp_min:
            vp_min = self.saturation_vapour_pressure(self.temp_min)
            vp_max = self.saturation_vapour_pressure(self.temp_max)
            return round((self.humidity_mean / 100) * ((vp_max + vp_min) / 2), 3)

        if self.humidity_mean and self.temp_mean:
           vp = self.saturation_vapour_pressure(self.temp_mean)
           return round((self.humidity_mean / 100) * vp, 3)

        if self.dew_point():
            return round(self.saturation_vapour_pressure(self.dew_point()), 3)

    def vapour_pressure_deficit(self):
        vp = self.mean_saturation_vapour_pressure()
        actual_vp = self.actual_vapour_pressure()
        return round(vp - actual_vp, 3)

    def relative_sun_distance(self):
        """
        Eq. 23
        """
        return round(1 + 0.033 * math.cos((2 * math.pi / 365) * self.day_number), 3)

    def solar_declination(self):
        """
        Eq. 24
        """
        return round(0.409 * math.sin((2 * math.pi / 365) * self.day_number - 1.39), 3)

    def X(self):
        """
        Eq. 27
        """
        x = (1 - math.tan(self.station.latitutde_radians) *
             math.tan(self.solar_declination()))
        if x <= 0:
            x = 0.00001
        return x

    def sunset_hour_angle(self):
        """
        Eq. 25
        """

        return round(math.acos(-1 * math.tan(self.station.latitude_rad) *
                               math.tan(self.solar_declination())), 3)
        # return math.pi / 2 - math.atan(-1 *
        # math.tan(self.station.latitutde_radians) *
        # math.tan(self.solar_declination()) / ( self.X() ** 0.5 ))

    def R_a(self):
        """
        Extraterrestrial radiation for daily periods.( Eq. 21 ).
        """

        return round(
            24 * 60 / math.pi * 0.0820 * self.relative_sun_distance() *
            (
                (
                self.sunset_hour_angle() * math.sin(self.station.latitude_rad) *
                math.sin(self.solar_declination())
                ) +
                (
                 math.cos(self.station.latitude_rad) *
                 math.cos(self.solar_declination()) *
                 math.sin(self.sunset_hour_angle())
                )
             ),
            1)

    def R_a_in_mm(self):
        """
        Same as R_a(), but returns the result in mm-equivalents
        """
        return round(self.R_a() * 0.408, 1)

    def daylight_hours(self):
        """
        Eq. 34
        """
        return round((24 / math.pi) * self.sunset_hour_angle(), 1)

    def solar_radiation_in_mm(self):
        """
        Alias to *solar_radiation(n)* but converts the output to mm equivalent,
        rounded to 1 decimal.
        """
        rs = self.solar_radiation()
        return round(rs * 0.408, 1)

    # clear-skype solar radiation
    def R_so(self):
        """
        Calculates clear sky radiation when n=N. Uses (Eq. 36) for elevations
        below 100m. Above 100m uses (Eq. 37)
        """

        if self.station.altitude < 100:
            return round((0.25 + 0.50) * self.R_a(), 1)

        return round((0.75 + (2*10**(-5)) * self.station.altitude) * self.R_a(), 1)

    def R_ns(self):
        """
        Net solar or net shortwave radiation. Uses Crop's albedo in calculations. (Eq. 38).
        Return radiation in MJ/m2/day

        """
        ref_crop = self.station.ref_crop

        return round((1 - ref_crop.albedo) * self.solar_radiation(), 1)

    def R_nl(self):
        """
        Net longwave radiation. (Eq. 39)
        """

        if not (self.temp_max and self.temp_min):
            raise Exception(
                "Net longwave radiation cannot be calculated without min/max temperature")

        TmaxK = self.temp_max + 273.16
        TminK = self.temp_min + 273.16
        ea = self.actual_vapour_pressure()
        rs = self.solar_radiation()
        rso = self.R_so()

        sb_constant = self.stephan_boltzmann_constant
        return round(sb_constant * ((TmaxK ** 4 + TminK ** 4) / 2) *
                     (0.34 - 0.14 * math.sqrt(ea)) *
                     (1.35 * (rs / rso) - 0.35), 1)

    def net_radiation(self):
        """
        Net Radiation. (Eq. 40)
        """
        ns = self.R_ns()

        try:
            nl = self.R_nl()
        except Exception as e:
            raise(str(e))

        if (not ns is None) and (not nl is None):
            return round(ns - nl, 1)

    def net_radition_in_mm(self):
        """
        Same as *net_radiation()*, except returns results in mm-equivalents
        """
        net_radition = self.net_radiation()
        if net_radition:
            return round(net_radition * 0.408, 1)

    def RH(self, T):

        if not is_number(T):
            raise TypeError("Number is expected")

        """
        Calculates relative humidity of the air for certain temperature using vapour pressure
        """

        return round(100 * (self.actual_vapour_pressure() /
                            self.saturation_vapour_pressure(T)), 3)

    def RH_mean(self):

        if self.humidity_mean != None:
            return self.humidity_mean

        if self.temp_min and self.temp_max:
            return int(round(( self.RH(self.temp_min) + self.RH(self.temp_max) ) / 2, 0))


    def soil_heat_flux(self):
        """
        Soil heat flux. Returns 0.00 (daily coefficient)
        This is valid for daily resolution!
        """
        return 0.00

    def air_conductance_coefficient(self):
        #rho_times_cap_through_resistance_per_day = 24*3600*0.622/(1.01*0.287*208)
        return 900 # return the official approximation

    def eto_hargreaves(self):
        """
        ETo estimating using Hargreaves euqation. If wind and humidty information is
        available, or can be estimated thsi equation is not recommended. ( Eq. 52 )
        """
        Tmean = (self.temp_max + self.temp_min) / 2
        return round(0.0023 * (Tmean + 17.8) *
                     (self.temp_max - self.temp_min) ** 0.5 * self.R_a(), 2)

    def eto(self):
        """
        Eq. 6
        """

        # if we cannot get wind speed data we revert to Hargreaves formula.
        # Which is not ideal! This can happen only if user removed default 'climate'
        # reference
        if not self.wind_speed_2m():
            return self.eto_hargreaves()

        if self.Tmean() == None:
            raise Exception(
                "Cannot calculate eto(): temp_mean (mean temperature) is missing")

        try:
            net_radiation = self.net_radiation()
        except Exception as e:
            raise(str(e))

        Tmean = self.Tmean()
        slope_of_vp = self.slope_of_saturation_vapour_pressure(Tmean)
        G = self.soil_heat_flux()
        u2m = self.wind_speed_2m()
        air_cond_coeff = self.air_conductance_coefficient()
        eto_nominator = (0.408 * slope_of_vp * (net_radiation - G) +
                         self.psychrometric_constant() * (air_cond_coeff / (Tmean + 273)) * u2m *
                         self.vapour_pressure_deficit())
        if eto_nominator < 0:
            return 0

        eto_denominator = slope_of_vp + self.psychrometric_constant() * (1 + 0.34 * u2m)
        return round(eto_nominator / eto_denominator, 2)

class DayEntry(TimeEntry):
    # Rs
    def solar_radiation(self):
        """
        If *radiation_s* is logged, returns the value as is. If *sunshine_hours*
        attribute of the day class is set returns solar radiation amount in mJ/m2/day.
        To convert this number to W/m2 multiply multiply it by 11.57 or divide by
        0.0864. Uses Angstrom equation (Eq. 35).

        If climate data is available, and climate is *island* location and
        station elevation is between 0-100m it uses simplified (Eq. 51). This
        equation does not use temperature data, but just solar radiation and a
        coefficient.

        If station elevation is higher than 100m and/or location is not island
        it uses (Eq. 50) that calculates solar radiation by using temperature
        data along with a *krs* constant.

        If climate is not known it assumes **n=N**, meaning daily sunshine hours
        is the same as daylight hours for the given day and location.
        """

        if self.radiation_s:
            # We need to make sure that solar radiation if set, is not
            # larger than clear-sky solar radiation
            if CHECK_RADIATION_RANGE and (self.radiation_s > self.R_so()):
                raise ValueError(
                    "Solar radiation out ot range. Rso=" + str(self.R_so()))
            return self.radiation_s

        n = self.sunshine_hours
        if n == None:
            # if we are in island location we refer to equation 51 in UAN-FAO
            # paper 56
            if (self.station.climate and self.station.climate.island_location
                    and self.station.altitude < 100):
                Ra = self.R_a()
                return round((0.7 * Ra) - 4, 1)

            if self.station.climate and self.temp_min and self.temp_max:
                # We assume caller has only temperature informaiton, and no
                # information on overcast conditions. So we resort to Hargreaves
                # and Samani's radiation formula:
                climate = self.station.climate
                Ra = self.R_a()
                krs = 0.16
                if climate.coastal_location:
                    krs = 0.19
                elif climate.interior_location:
                    krs = 0.16

                return round(krs * math.sqrt(self.temp_max - self.temp_min) * Ra, 1)

            else:
                n = self.daylight_hours()

        if n and not is_number(n):
            raise TypeError("'n' must be a number")

        if n < 0:
            raise ValueError("Observed daylight hours cannot be less than 0")

        # n cannot be more than N, which is available daylight hours
        if (n > self.daylight_hours()) and CHECK_SUNSHINE_HOURS_RANGE:
            raise ValueError("Daylight hours out of range")

        a_s = 0.25
        b_s = 0.50
        N = self.daylight_hours()  # this is the maximum possible sunshine duration
        Ra = self.R_a()

        return round((a_s + b_s * n / N) * Ra, 1)


class HourEntry(TimeEntry):

    def soil_heat_flux(self):
        """
        Soil heat flux. Returns 0.1 * *Rn* at day and 0.5 * *Rn* at night.
        Approximation valid for hourly resolution
        """
        if self.radiation_s < 0.05: # MJ/m2/s
            G = 0.5*self.net_radiation()
        else:
            G = 0.1*self.net_radiation()
        return G


    def solar_time_angle(self):
        b = 2*math.pi*(self.day_number-81)/364
        season_correction = 0.1645*math.sin(2*b) - 0.1255*math.cos(b)-0.025*math.sin(b)
        w = math.pi / 12 * (
            ( self.time.hour+0.5 + 0.06667*( self.station.timezone_longitude - self.station.longitude )
              + season_correction) - 12)
        return w

    def R_a(self):
        ws = self.sunset_hour_angle()
        w = self.solar_time_angle()
        if ( (w < -ws) or (w > ws) ):
            return 0
        w1 = w - math.pi*1/24
        w2 = w + math.pi*1/24
        d = self.relative_sun_distance()
        delta = self.station.latitude_rad
        phi = self.solar_declination()
        Ra = 12*60/math.pi * 0.0820 * d *( (w2-w1)*math.sin(phi)*math.sin(delta)+math.cos(phi)*math.cos(delta)*(math.sin(w2)-math.sin(w1)))
        return round(Ra,3)

    def R_l_outgoing(self):
        eps = 1
        bz = self.stephan_boltzmann_constant/24
        return round(eps*bz*(self.temp_soil+273.16)**4, 1)

    def R_l_incoming(self):
        def clear_sky_emissivity(T):
            return round(8.733*10**(-3)*(T+273.16)**0.788,3)

        if self.R_so() == 0:
            warnings.warn("The nighttime cloudcover is not estimated but arbitrarily set to 0.5. Consider interpolating over night")
            f = 0.5 # this is for nighttime, so not so important. Just take average cloud cover
        else:
            radfrac = self.radiation_s/self.R_so()
            f = 1-radfrac
            if f < 0:
                f = 0
            elif f > 1:
                f = 1
        T = self.Tmean()
        eps_0 = clear_sky_emissivity(T)
        eps_star = eps_0*(1+0.26*f)
        bz = self.stephan_boltzmann_constant/24
        return round(eps_star*bz*(T+273.16)**4,1)

    def R_nl(self):
        """
        Net longwave radiation with Stephan-Bolzmann
        """

        if self.temp_soil == None:
            raise Exception(
                "Net longwave radiation cannot be calculated without soil temperature")
        R_ol = self.R_l_outgoing()
        R_il = self.R_l_incoming()
        return (R_ol - R_il)

     # Rs
    def solar_radiation(self):
        """
        If *radiation_s* is logged, returns the value as is.
        Otherwise raise exception. For hourly values of eto radiation is required.
        For daily values of eto, radiation can be computed (see class DayEntry)

        """

        if not self.radiation_s is None:
            # We need to make sure that solar radiation if set, is not
            # larger than clear-sky solar radiation
            if CHECK_RADIATION_RANGE:
                Rso = self.R_so()
                if (Rso == 0) and (self.radiation_s > 0.05):
                    raise ValueError(
                        "'Lunar' radiation out ot range. radiation =" + str(self.radiation_s) + " should be near 0.")

                elif (Rso>0) and ( (self.radiation_s-Rso)/Rso > 0.05):
                    raise ValueError(
                        "Solar radiation out ot range. Rso=" + str(Rso))
            return self.radiation_s
        else:
            raise(Exception(
                "Cannot calculate eto(): radiation_s (Solar radiation) is missing"))

    def air_conductance_coefficient(self):
        #rho_times_cap_through_resistance_per_hour = 3600*0.622/(1.01*0.287*208)
        return 37 # return the official approximation

class Climate:
    """
    Represents a default climate according to *UN-FAO Paper 56*. If
    module has to make any assumptions regarding the climate it consults
    this class for any clues. If you wish to not use any assumptions and
    rely soleley on logged station data (if such is available) you may set
    Station's *climate* attribute to *None*.

        station = Station(latitude=-20.5, altitude=200)
        station.climate = None

    If you want to set a new climate:

        humid_climate = Climate().humid().coastal().moderate_winds()

        station = Station(latitude=-20.5, altitude=200)
        station.climate = humid_climate
    """

    def __init__(self):
        """
        Accepts no arguments. Default initialization is as follows:

            - interior_location
            - arid_climate
            - dew_point_difference = 2
            - average_wind_speed = 2.0 m/s
            - k_rs = 0.16


        To affect these values use respected methods documented below.
        """
        self.interior_location = True
        self.coastal_location = False
        self.island_location = False

        self.arid_climate = True
        self.humid_climate = False

        # Assining default values for the climatic condition to be able to
        # calculate missing data accurately
        self.dew_point_difference = 2
        self.average_wind_speed = 2.0
        self.k_rs = 0.16

    def light_winds(self):
        """
        Sets *average_wind_speed* to 0.5m/s
        """
        self.average_wind_speed = 0.5
        return self

    def moderate_winds(self):
        """
        Sets *average_wind_speed* to 2.0m/s
        """
        self.average_wind_speed = 2
        return self

    def strong_winds(self):
        """
        Sets average_wind_speed to 4m/s
        """
        self.average_wind_speed = 4
        return self

    def arid(self):
        """
        Sets *arid_climate*, sets *dew_point_difference* to 2
        """
        self.arid_climate = True
        self.humid_climate = False
        self.dew_point_difference = 2
        return self

    def humid(self):
        """
        Sets *humid_climate*, *dew_point_difference* to 0
        """
        self.arid_climate = False
        self.humid_climate = True
        self.dew_point_difference = 0
        return self

    def interior(self):
        """
        Sets *interior_location*, *k_rs* coefficient to *0.16*
        """
        self.interior_location = True
        self.coastal_location = False
        self.island_location = False
        self.k_rs = 0.16
        return self

    def coastal(self):
        """
        Sets *coastal_location*, *k_rs* to *0.19*
        """
        self.interior_location = False
        self.coastal_location = True
        self.island_location = False
        self.k_rs = 0.19
        return self

    def island(self):
        """ Sets *island_location*. Sets *k_rs* to 0.19 """
        self.interior_location = False
        self.coastal_location = False
        self.island_location = True
        self.k_rs = 0.19
        return self

    """
    def set_location(self, location):
        if location == "coastal":
            return self.coastal()

        if location == "interior":
            return self.interior()

        if location == "island":
            return self.island()

        return self
    """

    def describe(self):
        location = ""
        if self.interior_location:
            location = "interior"
        else:
            location = "coastal"

        humidity = ""
        if self.arid_climate:
            humidity = "arid, or semi-arid region"
        else:
            humidity = "humid, or sub-humid region"

        return f"""
Climate can be described as located in {location} area, {humidity}.
Average wind speeds are estimated at {self.average_wind_speed}.
Dew point temperature is usually runs {self.dew_point_difference}C lower than
day's minimal observed temperature"""


class Crop:
    """ Represents reference crop as assumed by Penman-Monteith equation."""

    def __init__(self, resistance_a=208, albedo=0.23, height=0.12):
        """
        Reference crop is instantiated with the following assumptions:
        - resistance_a = 208 (aerodynamic resistance)
        - albedo = 0.23
        - height - 0.12
        """
        self.resistance_a = resistance_a
        self.albedo = albedo
        self.height = height


class StationDay(DayEntry):
    """
    Left here for backwards-compatability with earlier versions of
    the library
    """

    pass


class MonthEntry:
    def __init__(self):
        pass


class WeekEntry:
    def __init__(self):
        pass
