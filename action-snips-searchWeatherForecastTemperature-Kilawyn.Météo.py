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
    
    import datetime
    import re
    import weather as wt
    import locale
    import random

    locale.setlocale(locale.LC_TIME,'')

    api_key = conf['secret']['api_key']
    locality = conf['secret']['default_location']
    country = conf['secret']['default_countrycode']
    geographical_poi = None
    region = None
    startdate = datetime.datetime.now()
    rightnow = startdate
    temperature_name = None
 
    capital = None

    # Populate the parameters and sanitize them
    if len(intentMessage.slots['forecast_temperature_name']) > 0:
        temperature_name = intentMessage.slots['forecast_temperature_name'].first().value
    if len(intentMessage.slots['forecast_start_datetime']) > 0:
        # This one is tricky, regarding the question it may be an InstantTimeValue or a TimeIntervalValue
        # In the last case, I take the start hour and add one hour to make a difference with 00:00 (see below how this is handled)
        # This should not affect the result, with the free API I can only get 3h-intervals
        startdate = intentMessage.slots['forecast_start_datetime'].first()
        is_interval = False
        if type(startdate) == hermes_python.ontology.dialogue.slot.InstantTimeValue:
            startdate = startdate.value
        elif type(startdate) == hermes_python.ontology.dialogue.slot.TimeIntervalValue:
            startdate = startdate.from_date
            is_interval = True
        startdate = re.sub(r'^([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} \+[0-9]{2}):([0-9]{2})$', r'\1\2', startdate)
        startdate = datetime.datetime.strptime(startdate, '%Y-%m-%d %H:%M:%S %z')
        rightnow = datetime.datetime.now(startdate.tzinfo)
        if is_interval:
            startdate += datetime.timedelta(hours=+1)
        # If only a day is asked, Snips will provide a time of 00:00:00 which is not interesting for weather.
        # So I offset that by 12 hours
        if startdate.time() == datetime.time(00, 00, 00):
            startdate += datetime.timedelta(hours=12)
    if len(intentMessage.slots['forecast_geographical_poi']) > 0:
        geographical_poi = intentMessage.slots['forecast_geographical_poi'].first().value
    if len(intentMessage.slots['forecast_region']) > 0:
        region = intentMessage.slots['forecast_region'].first().value
    if len(intentMessage.slots['forecast_country']) > 0:
        # OpenWeatherMap requests 2-letters ISO-3166 country codes. This is for the mapping fr->ISO-3166
        # Note that some countries may not work properly
        country = intentMessage.slots['forecast_country'].first().value
        f = open("iso_3166.csv", 'rt')
        for line in f:
            line_list = line.split("\t")
            if line_list[1].strip().lower() == country.split(" ")[-1].strip().lower():
                country = line_list[2].lower().strip()
                if len(line_list) >= 6:
                    capital = line_list[5].lower().strip()
                break
        f.close()
    if len(intentMessage.slots['forecast_locality']) > 0:
        locality = intentMessage.slots['forecast_locality'].first().value

    answer = "Je ne suis pas sûr de savoir quelle météo tu m'as demandée"

    # First of all, determine the location from which we want the weather
    if geographical_poi is not None:
        answer = "Désolé, je ne suis pas encore capable de récupérer un point d'intérêt"
        hermes.publish_end_session(intentMessage.session_id, answer)
        return
    elif region is not None:
        answer = "Je ne peux pas encore te donner la météo d'une région"
        hermes.publish_end_session(intentMessage.session_id, answer)
        return
    elif country != conf['secret']['default_countrycode'] and locality == conf['secret']['default_location']:
        if capital is None:
            answer = "J'ai besoin d'une ville dans le pays dont tu souhaites la météo"
            hermes.publish_end_session(intentMessage.session_id, answer)
            return
        else:
            locality = capital

    weather = wt.get_weather_data(locality, country, api_key)
    
    if weather is None or weather['cod'] != "200" and weather['cod'] != "404":
        answer = "Il y a un problème avec la récupération des infos météo"
        hermes.publish_end_session(intentMessage.session_id, answer)
        return
    elif weather['cod'] == "404":
        answer = "Je n'ai pas trouvé la ville que tu as demandé"
        hermes.publish_end_session(intentMessage.session_id, answer)
        return

    i = 0
    start_timestamp = startdate.timestamp()
    selected_forecast = None
    if startdate == rightnow or startdate - datetime.timedelta(hours=3) < rightnow:
        selected_forecast = 0
    else:
        for forecast in weather['list']:
            #print(start_timestamp)
            #print(forecast['dt'])
            # We have to take in account that the next forecast is already in the future (3h in the worst case scenario)
            if start_timestamp > forecast['dt'] and start_timestamp < forecast['dt'] + 10800: # 3-hour intervals
                selected_forecast = i
            i += 1
    if selected_forecast is None: # Nope, the date given is beyond the forecast or on a past value
        answer = "Il semblerait que la date que tu m'as demandée ne permette pas de récupérer d'info."
        hermes.publish_end_session(intentMessage.session_id, answer)
        return

    answer = ""
    if startdate == rightnow:
        answer += "En ce moment, il fait "
    elif startdate.date() == rightnow.date() and startdate.time() >= datetime.time(12, 0, 0) and startdate.time() < datetime.time(18, 0, 0):
        answer += "Cette après-midi il fera "
    elif startdate.date() == rightnow.date() and startdate.time() < datetime.time(12, 0, 0) and startdate.time() >= datetime.time(6, 0, 0):
        answer += "Ce matin il fera "
    elif startdate.date() == rightnow.date() and startdate.time() > datetime.time(18, 0, 0) and startdate.time() <= datetime.time(23, 59, 59):
        answer += "Ce soir il fera "
    elif startdate.date() == rightnow.date() + datetime.timedelta(days=1) and startdate.time() > datetime.time(0, 0, 0) and startdate.time() < datetime.time(6, 0, 0):
        answer += "Cette nuit il fera "
    elif startdate.date() == rightnow.date() + datetime.timedelta(days=1):
        if startdate.time() == datetime.time(12, 0, 0):
            answer += "Demain il fera "
        elif startdate.time() >= datetime.time(6, 0, 0) and startdate.time() < datetime.time(12, 0, 0):
            answer += "Demain matin il fera "
        elif startdate.time() > datetime.time(12, 0, 0) and startdate.time() < datetime.time(18, 0, 0):
            answer += "Demain après-midi il fera "
        elif startdate.time() >= datetime.time(18, 0, 0) and startdate.time() <= datetime.time(23, 59, 59):
            answer += "Demain soir il fera "
    else:
        dayofweek = startdate.strftime("%A")
        if startdate.time() == datetime.time(12, 0, 0):
            answer += "%s il fera " % dayofweek
        elif startdate.time() < datetime.time(12, 0, 0):
            answer += "%s matin il fera " % dayofweek
        elif startdate.time() > datetime.time(12, 0, 0) and startdate.time() < datetime.time(18, 0, 0):
            answer += "%s après-midi il fera " % dayofweek
        elif startdate.time() >= datetime.time(18, 0, 0) and startdate.time() <= datetime.time(23, 59, 59):
            answer += "%s soir il fera " % dayofweek

    if locality != conf['secret']['default_location']:
        answer += "à %s. " % locality

    temp = "%.2f degrés" % (weather['list'][selected_forecast]['main']['temp'] - 273.15) # The temperature is given in Kelvin
    answer += temp.replace('.', ' virgule ')
    if temperature_name is not None:
        tempDelta = 0
        if selected_forecast != 0:
            tempDelta = weather['list'][0]['main']['temp'] - weather['list'][selected_forecast]['main']['temp']
            temp = weather['list'][selected_forecast]['main']['temp']
        else:
            tempDelta = weather['list'][0]['main']['temp'] - weather['list'][8]['main']['temp'] # 8*3h = 24h
            temp = weather['list'][0]['main']['temp']
        if temperature_name in ['refroidir', 'plus froid']:
            if tempDelta < 0 and tempDelta > -5:
                answer += "Donc oui, il fera un peu plus frais"
            elif tempDelta < -5:
                answer += "Donc oui, il fera vraiment plus frais"
            else:
                answer += "Donc non, le temps va se réchauffer"
        elif temperature_name in ['réchauffer']:
            if tempDelta > 0 and tempDelta < 5:
                answer += "Donc oui, il fera un peu plus chaud"
            elif tempDelta > 5:
                answer += "Donc oui, il fera vraiment plus chaud"
            else:
                answer += "Donc non, le temps va se rafraîchir"
        elif temperature_name in ['estivale', 'bouillant', 'lourd', 'étouffant', 'chaud']:
            if temp > 28:
                answer += "En effet, le climat s'annonce estival"
            else:
                answer += "ça devrait aller"
        elif temperature_name in ['froid de canard', 'frisquet', 'frais', 'froid', 'glacial']:
            if temp < 10:
                answer += "En effet, la météo s'annonce bien fraîche"
            else:
                answer += "ça devrait aller"


    hermes.publish_end_session(intentMessage.session_id, answer)
    

if __name__ == "__main__":
    f = open("/etc/snips.toml", "rt")
    config = toml.load(f)
    mqtt_opts = MqttOptions(username=config["snips-common"]["mqtt_username"], password=config["snips-common"]["mqtt_password"], broker_address=config["snips-common"]["mqtt"])
    with Hermes(mqtt_options=mqtt_opts) as h:
        h.subscribe_intent("searchWeatherForecastTemperature", subscribe_intent_callback) \
         .start()
