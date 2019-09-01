#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import configparser
import hermes_python
from hermes_python.hermes import Hermes
from hermes_python.ffi.utils import MqttOptions
from hermes_python.ontology import *
import io
import toml

CONFIGURATION_ENCODING_FORMAT = "utf-8"
CONFIG_INI = "config.ini"

class SnipsConfigParser(configparser.SafeConfigParser):
    def to_dict(self):
        return {section : {option_name : option for option_name, option in self.items(section)} for section in self.sections()}


def read_configuration_file(configuration_file):
    try:
        with io.open(configuration_file, encoding=CONFIGURATION_ENCODING_FORMAT) as f:
            conf_parser = SnipsConfigParser()
            conf_parser.readfp(f)
            return conf_parser.to_dict()
    except (IOError, configparser.Error) as e:
        return dict()

def subscribe_intent_callback(hermes, intentMessage):
    conf = read_configuration_file(CONFIG_INI)
    action_wrapper(hermes, intentMessage, conf)


def action_wrapper(hermes, intentMessage, conf):
    """ Write the body of the function that will be executed once the intent is recognized. 
    In your scope, you have the following objects : 
    - intentMessage : an object that represents the recognized intent
    - hermes : an object with methods to communicate with the MQTT bus following the hermes protocol. 
    - conf : a dictionary that holds the skills parameters you defined. 
      To access global parameters use conf['global']['parameterName']. For end-user parameters use conf['secret']['parameterName'] 
     
    Refer to the documentation for further details. 
    """ 
    
    import requests
    import html
    import datetime
    import re

    locality = conf['default_location']
    country = conf['default_countrycode']
    geographical_poi = None
    region = None
    startdate = datetime.datetime.now()
    rightnow = startdate
    condition_name = None

    if len(intentMessage.slots['forecast_condition_name']) > 0:
        condition_name = intentMessage.slots['forecast_condition_name'].first().value
    if len(intentMessage.slots['forecast_start_datetime']) > 0:
        startdate = intentMessage.slots['forecast_start_datetime'].first()
        if type(startdate) == hermes_python.ontology.dialogue.slot.InstantTimeValue:
            startdate = startdate.value
        elif type(startdate) == hermes_python.ontology.dialogue.slot.TimeIntervalValue:
            startdate = startdate.from_date
        startdate = re.sub(r'^([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} \+[0-9]{2}):([0-9]{2})$', r'\1\2', startdate)
        startdate = datetime.datetime.strptime(startdate, '%Y-%m-%d %H:%M:%S %z')
        if type(startdate) == hermes_python.ontology.dialogue.slot.TimeIntervalValue:
            startdate += datetime.timedelta(hours=+1)
    if len(intentMessage.slots['forecast_geographical_poi']) > 0:
        geographical_poi = intentMessage.slots['forecast_geographical_poi'].first().value
    if len(intentMessage.slots['forecast_region']) > 0:
        region = intentMessage.slots['forecast_region'].first().value
    if len(intentMessage.slots['forecast_country']) > 0:
        country = intentMessage.slots['forecast_country'].first().value
        f = open("iso_3166.csv", 'rt')
        for line in f:
            line_list = line.split("\t")
            if line_list[1].strip().lower() == country.split(" ")[-1].strip().lower():
                country = line_list[2].lower().strip()
                break
        f.close()
    if len(intentMessage.slots['forecast_locality']) > 0:
        locality = intentMessage.slots['forecast_locality'].first().value

    answer = "J'attends encore les instructions"
    hermes.publish_end_session(intentMessage.session_id, answer)
    


if __name__ == "__main__":
    f = open("/etc/snips.toml", "rt")
    config = toml.load(f)
    mqtt_opts = MqttOptions(username=config["snips-common"]["mqtt_username"], password=config["snips-common"]["mqtt_password"], broker_address=config["snips-common"]["mqtt"])
    with Hermes(mqtt_options=mqtt_opts) as h:
        h.subscribe_intent("Kilawyn:searchWeatherForecastCondition", subscribe_intent_callback) \
         .start()
