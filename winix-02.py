#! /usr/bin/env python3
#
# winix-02.py
# 202012031810             
#

#
PROGRAM_NAME = "winix-02"
VERSION_MAJOR = "1"
VERSION_MINOR = "13"
WORKING_DIRECTORY = "/home/user/winix/"
# winix URL's
GET_STATUS_URL = "https://us.api.winix-iot.com/common/event/sttus/devices/"
COMMAND_URL = "https://us.api.winix-iot.com/common/control/devices/"

# 
# 
#

import sys
import cProfile

# check version of python
if not (sys.version_info.major == 3 and sys.version_info.minor >= 7):
    print("This script requires Python 3.7 or higher!")
    print("You are using Python {}.{}.".format(sys.version_info.major, sys.version_info.minor))
    sys.exit(1)
#print("{} {} is using Python {}.{}.".format(PROGRAM_NAME, PROGRAM_VERSION, sys.version_info.major, sys.version_info.minor))


import json
from urllib import request

import traceback
from pathlib import Path
import yaml
import queue
from dateutil.parser import parse
import paho.mqtt.client as mqtt
import time
from datetime import datetime
from timeloop import Timeloop
from datetime import timedelta
from dateutil import tz
import logging
import logging.handlers

# Logging setup

# select logging level
logging_level_file = logging.getLevelName('DEBUG')
#level_file = logging.getLevelName('DEBUG')
logging_level_rsyslog = logging.getLevelName('INFO')

# set local logging
LOG_FILENAME = PROGRAM_NAME + '.log'

root_logger = logging.getLogger()

#set loggers

# file logger
handler_file = logging.handlers.RotatingFileHandler(WORKING_DIRECTORY + LOG_FILENAME, backupCount=5)
handler_file.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)-8s ' + PROGRAM_NAME + ' ' + '%(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
handler_file.setLevel(logging_level_file)

root_logger.addHandler(handler_file)

# Roll over on application start
handler_file.doRollover()

# configure highest level combo logger, this is what we log to and it automagically goes to the log receivers that we have configured
# logging.getLogger("timeloop").setLevel(logging.CRITICAL)
my_logger = logging.getLogger(PROGRAM_NAME)

# read yaml config file which lists the air purifer units
try :
    raw_yaml = Path(WORKING_DIRECTORY + PROGRAM_NAME + ".yaml").read_text()
except Exception as e:
    my_logger.error("Error : configuration file : " + WORKING_DIRECTORY + PROGRAM_NAME + ".yaml" + " not found.")
    sys.exit(1)

try : 
    PROGRAM_CONFIG = yaml.load(Path(WORKING_DIRECTORY + PROGRAM_NAME + ".yaml").read_text(), Loader=yaml.FullLoader)
except Exception as e :
    my_logger.error("Error : YAML syntax problem in configuration file : " + WORKING_DIRECTORY + PROGRAM_NAME + ".yaml" + " .")
    sys.exit(1)

# read debug from YAML config file
# simple key value pair in YAML file : debug_level: "level" and set debug level
DEBUG_LEVEL = PROGRAM_CONFIG.get("debug_level", "")
if ( DEBUG_LEVEL == "" ) :
    DEBUG_LEVEL = "INFO"

logging_level_file = logging.getLevelName(DEBUG_LEVEL)
handler_file.setLevel(logging_level_file)

# read MQTT server info from YAML config file
# simple key value pair in YAML file : mqtt: "<mqtt server info>"
MQTT_SERVER = PROGRAM_CONFIG.get("mqtt", "")
if ( MQTT_SERVER == "" ) :
    MQTT_SERVER = "192.168.2.242"

# read MQTT server info from YAML config file
# simple key value pair in YAML file : mqtt: "<mqtt server info>"
MQTT_TOPIC_BASE = PROGRAM_CONFIG.get("mqtt_topic", "")
if ( MQTT_TOPIC_BASE == "" ) :
    MQTT_TOPIC_BASE = "winix"

# remove any forward slashes in value received from config file and just make it simple name with one following forward slash
MQTT_TOPIC_BASE = MQTT_TOPIC_BASE.strip( "/" ) + "/"

MQTT_CONTROL_TOPIC = "/control/"
MQTT_STATUS_TOPIC = ""

# read rsyslog info from YAML config file
# simple key value pair in YAML file : rsyslog: "<rsyslog server info>"
# simple string
RSYSLOG_SERVER = PROGRAM_CONFIG.get("rsyslog", "")
LOG_RSYSLOG = (RSYSLOG_SERVER, 514)

# rsyslog handler, if an IP address was specified in the YAML config file that configure to log to a RSYSLOG server
if (RSYSLOG_SERVER != "") :
    handler_rsyslog = logging.handlers.SysLogHandler(address = LOG_RSYSLOG)
    handler_rsyslog.setFormatter(logging.Formatter(fmt='%(asctime)s %(levelname)-8s ' + PROGRAM_NAME + ' ' + '%(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    handler_rsyslog.setLevel(logging_level_rsyslog)
    root_logger.addHandler(handler_rsyslog)


logging_level_file = logging.getLevelName('DEBUG')
root_logger.setLevel(logging_level_file)
# how often to check the winix cloud for updated from each unit, be careful to not be to quick at updates
# this is in minutes
CHECK_PERIOD_MINUTES = PROGRAM_CONFIG.get("check_interval", 5)

# delay in seconds between API calls, so as to not flood the cloud server
API_DELAY_SECONDS = 5

# winix units info from YAML config file
# dictionary of dictionaries
# units:
# example line : "SB01" : {"home" : "South Beach", "room" : "Living Room",   "key" : "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzz", , "mac_address" : "xx:xx:xx:xx:xx:xx"}
UNITS = PROGRAM_CONFIG.get("units", {})

# build another dictionary, so that we can lookup the unit's key by it's mac address
UNITS_BY_MAC = {}
for unit in UNITS :
    UNITS_BY_MAC[UNITS[unit]['mac_address']] = UNITS[unit]

# global dictionary to keep track of current state of each unit
UNITS_BY_MAC_STATE = {}

# debug, check that the YAML reads and massaging are correct
my_logger.debug("MQTT_SERVER          :" + str(MQTT_SERVER))
my_logger.debug("MQTT_TOPIC_BASE      :" + str(MQTT_TOPIC_BASE))
my_logger.debug("LOG_RSYSLOG          :" + str(LOG_RSYSLOG))
my_logger.debug("CHECK_PERIOD_MINUTES :" + str(CHECK_PERIOD_MINUTES))
my_logger.debug("UNITS                :" + str(UNITS))

# api topics

POWER = {"COMMAND" : "A02", "ON" : "1", "OFF" : "0"}
OPERATION_MODE = {"COMMAND" : "A03", "AUTO" : "01", "MANUAL" : "02"}
PLASMAWAVE = {"COMMAND" : "A07", "ON" : "1", "OFF" : "0"}
FAN_SPEED = {"COMMAND" : "A04", "100" : "05", "75" : "03", "50" : "02", "25" : "01", "SLEEP" : "06"}
SLEEP = {"COMMAND" : "A04", "SLEEP" : "06"}
AIR_QUALITY = {"COMMAND" : "S07", "GOOD" : "01", "FAIR" : "02", "POOR" : "03"}
FILTER_HOURS = {"COMMAND" : "A21"}
AMBIENT_LIGHT = {"COMMAND" : "S14"}
AIR_QUALITY_VALUE = {"COMMAND" : "S08"}

# device characteristics 

DEVICE_SPECIFICATION = {'manufacture' : ' WINIX', 'model' : 'C545', 'power' : '65 watts', 'room_size' : '360 sq. ft', 'weight' : '11.5 lbs'}


# setup timeloop, this allows to schedule the pull of units current status from winix cloud on regular basis
# https://github.com/sankalpjonn/timeloop
tl = Timeloop()

# create MQTT client globally
# connect to MQTT server
mqttc = mqtt.Client(PROGRAM_NAME)  # Create instance of client with client ID 
mqttc.connect(MQTT_SERVER, 1883)  # Connect to (broker, port, keepalive-time)

# setup a simple queue where we can put a request for an update to a winix unit from the winix cloud
queue_unit_request_update = queue.SimpleQueue() 

# functions to handle the command messages from MQTT sources

def message_to_or_from_unit(mosq, obj, msg) :
    # we have to check all MQTT messages for either a command to the unit from an MQTT source
    # or a status up MQTT message that was published by this routine (because the current state of a control,
    # might have been change by a interaction with front panel of unit, or command from the mobile phone app)

    global UNITS_BY_MAC_STATE

    msg_text = msg.payload.decode("utf-8")

    my_logger.debug("in messages_to_or_from_unit, message topic, qos, text: " + msg.topic + " " + str(msg.qos) + " " + msg_text)

    # if the message is a status message, aka has subtopic of "$SYS" we can skip
    if ( "$SYS" in msg.topic ) :
        return

    # get the MAC address of the unit that message is for or about
    unit_mac = (msg.topic).strip( MQTT_TOPIC_BASE )[ 0: 17]

    # key the unit key based on MAC address of unit
    unit_key = UNITS_BY_MAC[unit_mac].get('key', '')

    my_logger.debug("in messages_to_or_from_unit, UNIT MAC : |" + unit_mac + "|")
    my_logger.debug("in messages_to_or_from_unit, UNIT KEY : |" + unit_key + "|")

    msg_command = ""

    # if MQTT topic contains the topic for sending command to unit, then decode the command to send and parameters
    if ( MQTT_CONTROL_TOPIC in msg.topic ) :

        unit_url = ""

        if ( "power" in msg.topic ) :
            if ( msg_text == "ON" ) :
                msg_command = "1"
            else :
                msg_command = "0"

            # create control URL
            unit_url = COMMAND_URL + unit_key + "/A211/A02:" + msg_command

        if ( "mode" in msg.topic ) :
            if ( msg_text == "AUTO" ) :
                msg_command = "01"
            else :
                msg_command = "03"

            # create control URL
            unit_url = COMMAND_URL + unit_key + "/A211/A03:" + msg_command

        if ( "plasmawave" in msg.topic ) :
            if ( msg_text == "ON" ) :
                msg_command = "01"
            else :
                msg_command = "02"

            # create control URL
            unit_url = COMMAND_URL + unit_key + "/A211/A07:" + msg_command

        if ( "fan_speed" in msg.topic ) :
            msg_command = "01"
            if ( msg_text == "100" ) :
                msg_command = "05"
            if ( msg_text == "75" ) :
                msg_command = "03"
            if ( msg_text == "50" ) :
                msg_command = "02"
            if ( msg_text == "25" ) :
                msg_command = "01"

            # create control URL
            unit_url = COMMAND_URL + unit_key + "/A211/A04:" + msg_command

        if ( "sleep" in msg.topic ) :
            if ( msg_text == "ON" ) :
                msg_command = "06"
            else :
                msg_command = "01"

            # create control URL
            unit_url = COMMAND_URL + unit_key + "/A211/A04:" + msg_command

        # request undate from winix cloud for unit, no change command to send
        if ( "update" in msg.topic ) :
            my_logger.debug("Update from cloud requested for unit : " + unit_mac)
            unit_url = ""

        # if we received a valid MQTT command to send to winix cloud, do so
        # the 'update' topic does not request any change, so for that MQTT topic we just skip sending
        # and queue a status update
        if ( len(unit_url) > 0 ) :
            # send command to winix cloud for the unit
            try :
                my_logger.debug("Requested URL : " + unit_url)
                unit_raw_json = json.loads(request.urlopen(unit_url).read().decode())
                my_logger.debug("Returned data : " + str(unit_raw_json))
            except Exception as e:
                my_logger.error("Error : Unable to send Winix command URL : " + traceback.format_exc())
                sys.exit(1)

        # request the main loop do an update of the current status of this unit from winix cloud
        # rather than waiting for next periodic update
        my_logger.debug("command completed, queuing an update request for unit : " + unit_mac)
        queue_unit_request_update.put(unit_mac)

    # if not a control MQTT message then it is a status message that we requested from the winix cloud
    # check to see if any of the control states have changed from what we think they are and update
    # our local copy of current state of the unit
    #
    # NOTE: this is where the problem is, if a control state has changed, due to someone pressing buttons on front of unit
    # or sending a command to the unit from the winix mobile app, we need to update the state in HA, but if we sent
    # MQTT message with state control it comes back here a control message!!!!!
    else :
        msg_dict = json.loads(msg_text)
        if ( unit_mac not in UNITS_BY_MAC_STATE.keys() ) :
            UNITS_BY_MAC_STATE[unit_mac] = {"power_text": "UNKNOWN", "unit_mode_text": "UNKNOWN", "unit_plasmawave_text": "UNKNOWN", "unit_sleeping_text": "UNKNOWN", "unit_fan_speed_text": "UNKNOWN"}

        if ( UNITS_BY_MAC_STATE[unit_mac]["power_text"] != msg_dict.get("power_text", "UNKNOWN") ) :
            my_logger.debug("power_text changed : " + unit_mac)
            UNITS_BY_MAC_STATE[unit_mac]["power_text"] = msg_dict.get("power_text", "UNKNOWN")

        if ( UNITS_BY_MAC_STATE[unit_mac]["unit_mode_text"] != msg_dict.get("unit_mode_text", "UNKNOWN") ) :
            my_logger.debug("unit_mode_text changed : " + unit_mac)
            UNITS_BY_MAC_STATE[unit_mac]["unit_mode_text"] = msg_dict.get("unit_mode_text", "UNKNOWN")

        if ( UNITS_BY_MAC_STATE[unit_mac]["unit_plasmawave_text"] != msg_dict.get("unit_plasmawave_text", "UNKNOWN") ) :
            my_logger.debug("unit_plasmawave_text changed : " + unit_mac)
            UNITS_BY_MAC_STATE[unit_mac]["unit_plasmawave_text"] = msg_dict.get("unit_plasmawave_text", "UNKNOWN")

        if ( UNITS_BY_MAC_STATE[unit_mac]["unit_sleeping_text"] != msg_dict.get("unit_sleeping_text", "UNKNOWN") ) :
            my_logger.debug("unit_sleeping_text changed : " + unit_mac)
            UNITS_BY_MAC_STATE[unit_mac]["unit_sleeping_text"] = msg_dict.get("unit_sleeping_text", "UNKNOWN")

        if ( UNITS_BY_MAC_STATE[unit_mac]["unit_fan_speed_text"] != msg_dict.get("unit_fan_speed_text", "UNKNOWN") ) :
            my_logger.debug("unit_fan_speed_text changed : " + unit_mac)
            UNITS_BY_MAC_STATE[unit_mac]["unit_fan_speed_text"] = msg_dict.get("unit_fan_speed_text", "UNKNOWN")
    return

# function to request a status update for unit from winix cloud

def get_unit_update(unit_mac) :

    try:
        unit_key = UNITS_BY_MAC[unit_mac].get('key', '')
        unit_url = GET_STATUS_URL + unit_key
        my_logger.debug("Requested URL : " + unit_url)
        unit_raw_json = json.loads(request.urlopen(unit_url).read().decode())
        my_logger.debug("Returned data : " + str(unit_raw_json))
    except Exception as e:
        my_logger.error("Error : Unable to retrieve Winix status URL : " + traceback.format_exc())
        return
        # sys.exit(1)

    # time of getting the status of unit from web api, not that this is the retrieval time of data from the web server
    # the unit may not have updated the web server for a while
    unit_status_retrieval_ts = int(time.time())

    unit_body_json = unit_raw_json.get("body")
    unit_data_json = unit_body_json.get("data")
    unit_attributes_json = unit_data_json[0].get("attributes")

    unit_mac_address = unit_mac

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

    update_age_timedelta = datetime.fromtimestamp(unit_status_retrieval_ts) - datetime.fromtimestamp(unit_update_time_gmt_ts)
    update_age_text = str(update_age_timedelta)

    # if the unit is powered off, none of status is valid
    if unit_is_off :
        air_quality_ordinal = "-1"
        air_quality_text = "UNKNOWN"
        air_quality_value = "-1"
        unit_sleeping_text = "UNKNOWN"
        unit_plasmawave_ordinal = "-1"
        unit_plasmawave_text = "UNKNOWN"
        unit_mode_ordinal = "-1"
        unit_mode_text = "UNKNOWN"
        unit_fan_speed_ordinal = "-1"
        unit_fan_speed_text = "UNKNOWN"
        unit_filter_hours = "-1"
        unit_ambient_light = "-1"

    else :

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
        # air_quality_ordinal = "-1"
        # air_quality_text = "UNKNOWN"
        # air_quality_value = "-1"
        unit_plasmawave_ordinal = "-1"
        unit_plasmawave_text = "UNKNOWN"
        unit_mode_ordinal = "-1"
        unit_mode_text = "UNKNOWN"
        # unit_filter_hours = "-1"
        # unit_ambient_light = "-1"
        unit_fan_speed_ordinal = "-1"
        unit_fan_speed_text = "UNKNOWN"

    # create dictionary to be converted to JSON string
    message = {"timestamp": "{:d}".format(unit_status_retrieval_ts)}

    message["unit_update_ts"] = str(unit_update_time_gmt_ts)
    message["update_age_text"] = update_age_text
    message["unit_model"] = unit_model
    message["home"] = UNITS_BY_MAC[unit_mac]["home"]
    message["room"] = UNITS_BY_MAC[unit_mac]["room"]
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
    # doing the json.dumps forces single quotes to double quotes, which json likes better
    message_to_publish = json.dumps(message)
    mqttc.publish(MQTT_TOPIC_BASE + unit_mac_address + MQTT_STATUS_TOPIC, message_to_publish)
    my_logger.debug("publishing on topic : |" + MQTT_TOPIC_BASE + unit_mac_address + MQTT_STATUS_TOPIC + "|")
    my_logger.debug("publishing message : |" + str(message_to_publish) + "|")

    # don't call api too quickly
    time.sleep(API_DELAY_SECONDS)

    return

# using the timeloop scheduling tool, update all the units status from winix cloud on a regular basis
@tl.job(interval=timedelta(minutes=CHECK_PERIOD_MINUTES))
def periodic_update_units():

    # queue up a request for the current status of each unit
    for unit in UNITS :
        my_logger.debug("periodic update, queueing status update request for : " + UNITS[unit]['mac_address'])
        queue_unit_request_update.put(UNITS[unit]['mac_address'])

    return

def main():


    # keep track of transition to new day at midnight local time
    # at rollover, reset the tracking of duplicate incident id
    current_day = datetime.now().timetuple().tm_yday

    try :
        # # connect to MQTT server
        # mqttc = mqtt.Client(PROGRAM_NAME)  # Create instance of client with client ID 
        # mqttc.connect(MQTT_SERVER, 1883)  # Connect to (broker, port, keepalive-time)
        # Add message callbacks that will only trigger on a specific subscription match.
        mqttc.message_callback_add(MQTT_TOPIC_BASE + "#", message_to_or_from_unit)
        mqttc.subscribe(MQTT_TOPIC_BASE + "#", 0)

        message = {"timestamp": "{:d}".format(int(datetime.now().timestamp()))}
        message["program_version"] = PROGRAM_NAME + " Version : " + VERSION_MAJOR + "." + VERSION_MINOR
        message["status"] = "START"
        message["unit_check_interval"] = CHECK_PERIOD_MINUTES
        mqttc.publish(MQTT_TOPIC_BASE + "$SYS/STATUS", json.dumps(message))
        my_logger.info("Program start : " + PROGRAM_NAME + " Version : " + VERSION_MAJOR + "." + VERSION_MINOR)

        # Start mqtt
        mqttc.loop_start()

        # get the initial state of all the winix units from winix cloud
        periodic_update_units()

        # start timeloop thread to update units on periodic basis
        tl.start()

        # loop forever waiting for keyboard interrupt, seeing if there are unit update requests queued
        while True :

            # check if it is a new day, if so clear out the record of duplicate incidents published during prior day
            # publish to MQTT a stat about how many unique incidents were published in prior day
            if current_day != datetime.now().timetuple().tm_yday :
                my_logger.info("24 hour rollover")
                current_day = datetime.now().timetuple().tm_yday
            try :
                unit_mac = queue_unit_request_update.get(block=False)
                my_logger.debug("queue request for :" + unit_mac + " requesting update")
                get_unit_update(unit_mac)
            except queue.Empty :
                # break, continue and pass. pass seems the proper action for nothing in queue
                pass

            time.sleep(1)
        # end loop forever

    except KeyboardInterrupt :
        tl.stop()
        message = {"timestamp": "{:d}".format(int(datetime.now().timestamp()))}
        message["program_version"] = PROGRAM_NAME + " Version : " + VERSION_MAJOR + "." + VERSION_MINOR
        message["status"] = "STOP"
        mqttc.publish(MQTT_TOPIC_BASE + "$SYS/STATUS", json.dumps(message))
        mqttc.disconnect()
        mqttc.loop_stop()
        my_logger.info("Keyboard interrupt.")
        # sys.exit(0)

    except :
        tl.stop()
        my_logger.critical("Unhandled error : " + traceback.format_exc())
        sys.exit(1)

    # proper exit
    my_logger.info("Program end : " + PROGRAM_NAME + " Version : " + VERSION_MAJOR + "." + VERSION_MINOR)
    sys.exit(0)

if __name__ == '__main__':
   main()
# if __name__ == '__main__':
#     cProfile.run('main()')
