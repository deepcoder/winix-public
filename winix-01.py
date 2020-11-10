#! /usr/bin/env python3
#

# winix-01.py
# 202011091518        
#
# read the latest information that each Winix unit has uploaded to their cloud and publish to MQTT for Home Assistant and Homebridge Homekit

#
PROGRAM_NAME = "winix-01"
PROGRAM_VERSION = "08"
WORKING_DIRECTORY = "/home/user/winix/"
# 
# 
#

import sys

# check version of python
if not (sys.version_info.major == 3 and sys.version_info.minor >= 5):
    print("This script requires Python 3.5 or higher!")
    print("You are using Python {}.{}.".format(sys.version_info.major, sys.version_info.minor))
    sys.exit(1)
#print("{} {} is using Python {}.{}.".format(PROGRAM_NAME, PROGRAM_VERSION, sys.version_info.major, sys.version_info.minor))

import json
from urllib import request


import traceback
from pathlib import Path
import yaml

from dateutil.parser import parse
import paho.mqtt.client as mqtt
import time
from datetime import datetime
from dateutil import tz
import logging
import logging.handlers

# mqtt server and topic base to publish info to
MQTT_SERVER = "192.168.1.242"
MQTT_TOPIC_BASE = "winix" + "/"

# how often to check for updates in minutes
CHECK_PERIOD_MINUTES = 5

# device characteristics, static from specs sheet
DEVICE_SPECIFICATION = {'manufacture' : ' WINIX', 'model' : 'C545', 'power' : '65 watts', 'room_size' : '360 sq. ft', 'weight' : '11.5 lbs'}

# Logging setup

# select logging level
logging_level_file = logging.getLevelName('INFO')
#level_file = logging.getLevelName('DEBUG')
logging_level_rsyslog = logging.getLevelName('INFO')

# log to both a local file and to a rsyslog server
LOG_FILENAME = PROGRAM_NAME + '.log'
LOG_RSYSLOG = ('192.168.1.5', 514)

root_logger = logging.getLogger()

#set loggers

# file logger
handler_file = logging.handlers.RotatingFileHandler(WORKING_DIRECTORY + LOG_FILENAME, backupCount=5)
handler_file.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)-8s ' + PROGRAM_NAME + ' ' + '%(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
handler_file.setLevel(logging_level_file)

root_logger.addHandler(handler_file)

# Roll over on application start
handler_file.doRollover()

# rsyslog handler
handler_rsyslog = logging.handlers.SysLogHandler(address = LOG_RSYSLOG)
handler_rsyslog.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)-8s ' + PROGRAM_NAME + ' ' + '%(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
handler_rsyslog.setLevel(logging_level_rsyslog)

root_logger.addHandler(handler_rsyslog)

my_logger = logging.getLogger(PROGRAM_NAME)
my_logger.setLevel(logging_level_file)


def main():

    # read yaml config file which lists the air purifer units
    try :
        raw_yaml = Path(WORKING_DIRECTORY + PROGRAM_NAME + ".yaml").read_text()
    except Exception as e:
        print("Error : configuration file : " + WORKING_DIRECTORY + PROGRAM_NAME + ".yaml" + " not found.")
        print(traceback.format_exc())
        my_logger.info("Error : configuration file : " + WORKING_DIRECTORY + PROGRAM_NAME + ".yaml" + " not found.")
        sys.exit(1)

    try : 
        PROGRAM_CONFIG = yaml.load(Path(WORKING_DIRECTORY + PROGRAM_NAME + ".yaml").read_text(), Loader=yaml.FullLoader)
    except Exception as e :
        print("Error : YAML syntax problem in configuration file : " + WORKING_DIRECTORY + PROGRAM_NAME + ".yaml" + " .")
        print(traceback.format_exc())
        my_logger.info("Error : YAML syntax problem in configuration file : " + WORKING_DIRECTORY + PROGRAM_NAME + ".yaml" + " .")
        sys.exit(1)

    # dictionary of dictionaries
    # example line : "NB01" : {"home" : "North Beach", "room" : "Living Room",   "key" : "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzz", , "mac_address" : "xx:xx:xx:xx:xx:xx"}
    UNITS = PROGRAM_CONFIG.get("units", {})

    # winix URL's for reading status and executing commands

    GET_STATUS_URL = "https://us.api.winix-iot.com/common/event/sttus/devices/"
    COMMAND_URL = "https://us.api.winix-iot.com/common/control/devices/"

    # map of topics in the returned JSON

    POWER = {"COMMAND" : "A02", "ON" : "1", "OFF" : "0"}
    OPERATION_MODE = {"COMMAND" : "A03", "AUTO" : "01", "MANUAL" : "02"}
    PLASMAWAVE = {"COMMAND" : "A07", "ON" : "1", "OFF" : "0"}
    FAN_SPEED = {"COMMAND" : "A04", "100" : "05", "75" : "03", "50" : "02", "25" : "01", "SLEEP" : "06"}
    SLEEP = {"COMMAND" : "A04", "SLEEP" : "06"}
    AIR_QUALITY = {"COMMAND" : "S07", "GOOD" : "01", "FAIR" : "02", "POOR" : "03"}
    FILTER_HOURS = {"COMMAND" : "A21"}
    AMBIENT_LIGHT = {"COMMAND" : "S14"}
    AIR_QUALITY_VALUE = {"COMMAND" : "S08"}

    # keep track of transition to new day at midnight local time

    current_day = datetime.now().timetuple().tm_yday

    try :
        # connect to MQTT server
        mqttc = mqtt.Client(PROGRAM_NAME)  # Create instance of client with client ID 
        mqttc.connect(MQTT_SERVER, 1883)  # Connect to (broker, port, keepalive-time)
        message = {"timestamp": "{:d}".format(int(datetime.now().timestamp()))}
        message["program_version"] = PROGRAM_NAME + " Version : " + PROGRAM_VERSION
        message["status"] = "START"
        mqttc.publish(MQTT_TOPIC_BASE + "$SYS/STATUS", json.dumps(message))
        my_logger.info("Program start : " + PROGRAM_NAME + " Version : " + PROGRAM_VERSION)

        # Start mqtt
        mqttc.loop_start()

        # loop forever waiting for keyboard interrupt
        while True :

            # publish to MQTT a stat about the prior day
            if current_day != datetime.now().timetuple().tm_yday :
                my_logger.info("24 hour rollover")
                current_day = datetime.now().timetuple().tm_yday

            # retrieve the current status of each unit
            for unit in UNITS :
                try:
                    unit_url = GET_STATUS_URL + UNITS[unit]['key']
                    my_logger.debug("Requested URL : " + unit_url)
                    unit_raw_json = json.loads(request.urlopen(unit_url).read().decode())
                    my_logger.debug("Returned data : " + str(unit_raw_json))
                except Exception as e:
                    print("Error : Unable to retrieve Winix status URL.")
                    print(traceback.format_exc())
                    my_logger.info("Error : Unable to retrieve Winix status URL : " + traceback.format_exc())
                    continue

                # time of getting the status of unit from web api, not that this is the retrieval time of data from the web server
                # the unit may not have updated the web server for a while
                unit_status_retrieval_ts = int(time.time())

                unit_body_json = unit_raw_json.get("body")
                unit_data_json = unit_body_json.get("data")
                unit_attributes_json = unit_data_json[0].get("attributes")

                unit_mac_address = UNITS[unit]['mac_address']

                unit_model = unit_data_json[0].get("modelId")

                unit_rssi = unit_data_json[0].get("rssi")

                unit_power_ordinal = unit_attributes_json.get("A02")
                unit_power_text = list(POWER.keys())[list(POWER.values()).index(unit_power_ordinal)]
                if unit_power_text == "OFF" :
                    unit_is_off = True
                else :
                    unit_is_off = False

                # this is the time the unit last sent its status up to the web server
                unit_update_time_gmt_ts = int(unit_data_json[0].get("utcTimestamp"))
                unit_update_time_local = datetime.fromtimestamp(unit_update_time_gmt_ts).strftime('%Y-%m-%d %H:%M')

                # create a text time delta to show how old the units update is
                update_age_timedelta = datetime.fromtimestamp(unit_status_retrieval_ts) - datetime.fromtimestamp(unit_update_time_gmt_ts)
                update_age_text = str(update_age_timedelta)

                # if the unit is powered off, none of status is valid
                if unit_is_off :
                    air_quality_ordinal = "-1"
                    air_quality_text = "UNKNOWN"
                    air_quality_value = "UNKNOWN"
                    unit_sleeping_text = "UNKNOWN"
                    unit_plasmawave_ordinal = "-1"
                    unit_plasmawave_text = "UNKNOWN"
                    unit_mode_ordinal = "-1"
                    unit_mode_text = "UNKNOWN"
                    unit_fan_speed_ordinal = "-1"
                    unit_fan_speed_text = "UNKNOWN"
                    unit_filter_hours = "UNKNOWN"
                    unit_ambient_light = "UNKNOWN"

                else :

                    # get attributes of current state in cloud for unit
                    air_quality_ordinal = unit_attributes_json.get("S07")
                    # do a value loop to find they key
                    air_quality_text = list(AIR_QUALITY.keys())[list(AIR_QUALITY.values()).index(air_quality_ordinal)]

                    air_quality_value = unit_attributes_json.get("S08")

                    # fan speed also signals the unit is sleeping
                    if unit_attributes_json.get("A04") == "06" :
                        unit_sleeping_text = "YES"
                    else :
                        unit_sleeping_text = "NO"

                    unit_plasmawave_ordinal = unit_attributes_json.get("A07")
                    unit_plasmawave_text = list(PLASMAWAVE.keys())[list(PLASMAWAVE.values()).index(unit_plasmawave_ordinal)]

                    unit_mode_ordinal = unit_attributes_json.get("A03")
                    unit_mode_text = list(OPERATION_MODE.keys())[list(OPERATION_MODE.values()).index(unit_mode_ordinal)]

                    unit_fan_speed_ordinal = unit_attributes_json.get("A04")
                    unit_fan_speed_text = list(FAN_SPEED.keys())[list(FAN_SPEED.values()).index(unit_fan_speed_ordinal)]

                    unit_filter_hours = unit_attributes_json.get("A21")

                    unit_ambient_light = unit_attributes_json.get("S14")

                # if the unit is sleeping, none of status is valid
                if unit_sleeping_text == "YES" :
                    air_quality_ordinal = "-1"
                    air_quality_text = "UNKNOWN"
                    air_quality_value = "UNKNOWN"
                    unit_plasmawave_ordinal = "-1"
                    unit_plasmawave_text = "UNKNOWN"
                    unit_mode_ordinal = "-1"
                    unit_mode_text = "UNKNOWN"
                    unit_filter_hours = "UNKNOWN"
                    unit_ambient_light = "UNKNOWN"

                # create dictionary to be converted to JSON string
                message = {"timestamp": "{:d}".format(unit_status_retrieval_ts)}

                message["unit_update_ts"] = str(unit_update_time_gmt_ts)
                message["update_age_text"] = update_age_text
                message["unit_model"] = unit_model
                message["home"] = UNITS[unit]['home']
                message["room"] = UNITS[unit]['room']
                message["unit_power_ordinal"] = str(int(unit_power_ordinal))
                message["power_text"] = unit_power_text
                message["unit_sleeping_text"] = unit_sleeping_text
                message["air_quality_ordinal"] = str(int(air_quality_ordinal))
                message["air_quality_text"] = air_quality_text
                message["air_quality_value"] = air_quality_value
                message["unit_plasmawave_ordinal"] = str(int(unit_plasmawave_ordinal))
                message["unit_plasmawave_text"] = unit_plasmawave_text
                message["unit_mode_ordinal"] = str(int(unit_mode_ordinal))
                message["unit_mode_text"] = unit_mode_text
                message["unit_fan_speed_ordinal"] = str(int(unit_fan_speed_ordinal))
                message["unit_fan_speed_text"] = unit_fan_speed_text
                message["unit_filter_hours"] = unit_filter_hours
                message["unit_ambient_light"] = unit_ambient_light
                message["unit_rssi"] = unit_rssi
                message["unit_body_json"] = unit_body_json

                # Publish message to topic
                # create JSON string
                message_to_publish = json.dumps(message)
                mqttc.publish(MQTT_TOPIC_BASE + unit_mac_address, message_to_publish)

                # don't call api too quickly
                time.sleep(5)

            # check the sensors every CHECK_PERIOD_MINUTES
            time.sleep(CHECK_PERIOD_MINUTES * 60)

        # end loop forever

    except KeyboardInterrupt :
        message = {"timestamp": "{:d}".format(int(datetime.now().timestamp()))}
        message["program_version"] = PROGRAM_NAME + " Version : " + PROGRAM_VERSION
        message["status"] = "STOP"
        mqttc.publish(MQTT_TOPIC_BASE + "$SYS/STATUS", json.dumps(message))
        mqttc.disconnect()
        mqttc.loop_stop()
        my_logger.info("Keyboard interrupt.")
        sys.exit(0)

    except :
        my_logger.critical("Unhandled error : " + traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
   main()

