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
    condition_name = None

    # Format: OpenWeatherMap code, {OpenWeatherMap denomination, Snips codes}
    CONDITION_CODES = {
            200: {"owm":"thunderstorm with light rain", "snips":["de l'orage et un peu de pluie", "pleuvoir", "éclairs", "tonnerre", "orageux", "orage", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            201: {"owm":"thunderstorm with rain", "snips":["de l'orage et de la pluie", "pleuvoir", "éclairs", "tonnerre", "orageux", "orage", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            202: {"owm":"thunderstorm with heavy rain", "snips":["de l'orage et des grosses averses", "pleuvoir", "éclairs", "tonnerre", "orageux", "orage", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            210: {"owm":"light thunderstorm", "snips":["des petits orages", "éclairs", "tonnerre", "orageux", "orage"]},
            211: {"owm":"thunderstorm", "snips":["des orages", "éclairs", "tonnerre", "orageux", "orage"]},
            212: {"owm":"heavy thunderstorm", "snips":["de gros orages", "éclairs", "tonnerre", "orageux", "orage"]},
            221: {"owm":"ragged thunderstorm", "snips":["des orages irréguliers", "éclairs", "tonnerre", "orageux", "orage"]},
            230: {"owm":"thunderstorm with light drizzle", "snips":["des orages et une légère bruine", "pleuvoir", "éclairs", "tonnerre", "orageux", "orage", "dépression", "humide", "gris", "pluvieux", "pluie", "tempête"]},
            231: {"owm":"thunderstorm with drizzle", "snips":["des orages et de la bruine", "pleuvoir", "éclairs", "tonnerre", "orageux", "orage", "dépression", "humide", "gris", "pluvieux", "pluie", "tempête"]},
            232: {"owm":"thunderstorm with heavy drizzle", "snips":["des orages et de la grosse bruine", "pleuvoir", "éclairs", "tonnerre", "orageux", "orage", "dépression", "humide", "gris", "pluvieux", "pluie", "tempête"]},
            300: {"owm":"light intensity drizzle", "snips":["une petite bruine", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            301: {"owm":"drizzle", "snips":["de la bruine", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            302: {"owm":"heavy intensity drizzle", "snips":["de la grosse bruine", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            310: {"owm":"light intensity drizzle rain", "snips":["de la pluie de faible intensité", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            311: {"owm":"drizzle rain", "snips":["de la pluie", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            312: {"owm":"heavy intensity drizzle rain", "snips":["de la grosse pluie", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie", "tempête"]},
            313: {"owm":"shower rain and drizzle", "snips":["des averses de pluie", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            314: {"owm":"heavy shower rain and drizzle", "snips":["des grosses averses de pluie", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            321: {"owm":"shower drizzle", "snips":["des averses de bruine", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            500: {"owm":"light rain", "snips":["une légère pluie", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            501: {"owm":"moderate rain", "snips":["des précipitations modérées", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            502: {"owm":"heavy intensity rain", "snips":["de la grosse pluie", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            503: {"owm":"very heavy rain", "snips":["de l'énorme pluie", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie", "tempête"]},
            504: {"owm":"extreme rain", "snips":["le déluge", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie", "tempête"]},
            511: {"owm":"freezing rain", "snips":["de la pluie verglaçante", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            520: {"owm":"light intensity shower rain", "snips":["des petites averses", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            521: {"owm":"shower rain", "snips":["des averses", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            522: {"owm":"heavy intensity shower rain", "snips":["des grosses averses", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie", "tempête"]},
            531: {"owm":"ragged shower rain", "snips":["des averses éparses", "pleuvoir", "dépression", "humide", "gris", "pluvieux", "pluie"]},
            600: {"owm":"light snow", "snips":["un peu de neige", "chutes de neige", "dépression", "enneigé", "neige"]},
            601: {"owm":"Snow", "snips":["de la neige", "chutes de neige", "dépression", "enneigé", "neige"]},
            602: {"owm":"Heavy snow", "snips":["beaucoup de neige", "tempête de neige", "chutes de neige", "dépression", "enneigé", "neige", "tempête"]},
            611: {"owm":"Sleet", "snips":["de la neige fondue", "chutes de neige", "dépression", "enneigé", "neige"]},
            612: {"owm":"Light shower sleet", "snips":["des petites averses de neige fondue", "chutes de neige", "dépression", "enneigé", "neige"]},
            613: {"owm":"Shower sleet", "snips":["des averses de neige fondue", "chutes de neige", "dépression", "enneigé", "neige", "humide", "gris", "pluvieux", "pluie"]},
            615: {"owm":"Light rain and snow", "snips":["un peu de pluie et neige mélées", "pleuvoir", "chutes de neige", "dépression", "enneigé", "neige", "humide", "gris", "pluvieux", "pluie"]},
            616: {"owm":"Rain and snow", "snips":["de la pluie et neige mélées", "pleuvoir", "chutes de neige", "dépression", "enneigé", "neige", "humide", "gris", "pluvieux", "pluie"]},
            620: {"owm":"Light shower snow", "snips":["des petites averses de neige", "chutes de neige", "dépression", "enneigé", "neige"]},
            621: {"owm":"Shower snow", "snips":["des averses de neige", "chutes de neige", "dépression", "enneigé", "neige"]},
            621: {"owm":"Heavy shower snow", "snips":["des grosses averses de neige", "tempête de neige", "chutes de neige", "dépression", "enneigé", "neige", "tempête"]},
            701: {"owm":"mist", "snips":["de la brume", "brûme", "gris", "humide"]},
            711: {"owm":"Smoke", "snips":["de la fumée"]},
            721: {"owm":"Haze", "snips":["de la brume", "brûme", "gris", "humide"]},
            731: {"owm":"sand/ dust whirls", "snips":["des tourbillons de sable"]},
            741: {"owm":"fog", "snips":["du brouilard", "brouillard", "gris", "humide"]},
            751: {"owm":"sand", "snips":["du sable"]},
            761: {"owm":"dust", "snips":["de la poussière"]},
            762: {"owm":"volcanic ash", "snips":["de la cendre volcanique"]},
            771: {"owm":"squalls", "snips":["des rafales de vent"]},
            781: {"owm":"tornado", "snips":["des tornades", "cyclone"]},
            800: {"owm":"clear sky", "snips":["du soleil", "soleil", "ensoleillé", "anti-cyclone"]},
            801: {"owm":"few clouds: 11-25%", "snips":["quelques nuages", "nuageux", "nuage"]},
            802: {"owm":"scattered clouds: 25-50%", "snips":["des nuages épars", "nuageux", "nuage"]},
            803: {"owm":"broken clouds: 51-84%", "snips":["pas mal de nuages", "nuageux", "nuage", "gris", "couvert"]},
            804: {"owm":"overcast clouds: 85-100%", "snips":["un ciel couvert", "nuageux", "nuage", "gris", "couvert"]},
    }

    capital = None

    # Populate the parameters and sanitize them
    if len(intentMessage.slots['forecast_condition_name']) > 0:
        condition_name = intentMessage.slots['forecast_condition_name'].first().value
    if len(intentMessage.slots['forecast_start_datetime']) > 0:
        # This one is tricky, regarding the question it may be an InstantTimeValue or a TimeIntervalValue
        # In the last case, I take the start hour and add one hour to make a difference with 00:00 (see below how this is handled)
        # This should not affect the result, with the free API I can only get 3h-intervals
        startdate = intentMessage.slots['forecast_start_datetime'].first()
        if type(startdate) == hermes_python.ontology.dialogue.slot.InstantTimeValue:
            startdate = startdate.value
        elif type(startdate) == hermes_python.ontology.dialogue.slot.TimeIntervalValue:
            startdate = startdate.from_date
        startdate = re.sub(r'^([0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2} \+[0-9]{2}):([0-9]{2})$', r'\1\2', startdate)
        startdate = datetime.datetime.strptime(startdate, '%Y-%m-%d %H:%M:%S %z')
        if type(startdate) == hermes_python.ontology.dialogue.slot.TimeIntervalValue:
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
        answer = "Je ne peux pas encore te donner la météo d'un région"
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
    if startdate == rightnow:
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
        answer += "En ce moment, il y a "
    elif startdate.date() == rightnow.date() and startdate.time() > datetime.time(12, 0, 0) and startdate.time() < datetime.time(18, 0, 0):
        answer += "Cette après-midi il y aura "
    elif startdate.date() == rightnow.date() and startdate.time() < datetime.time(12, 0, 0) and startdate.time() >= datetime.time(6, 0, 0):
        answer += "Ce matin il il aura "
    elif startdate.date() == rightnow.date() and startdate.time() > datetime.time(18, 0, 0) and startdate.time() <= datetime.time(23, 59, 59):
        answer += "Ce soir il y aura "
    elif startdate.date() == rightnow.date() + datetime.timedelta(days=1) and startdate.time() > datetime.time(0, 0, 0) and startdate.time() < datetime.time(6, 0, 0):
        answer += "Cette nuit il y aura "
    elif startdate.date() == rightnow.date() + datetime.timedelta(days=1):
        if startdate.time() == datetime.time(12, 0, 0):
            answer += "Demain il y aura "
        elif startdate.time() >= datetime.time(6, 0, 0) and startdate.time() < datetime.time(12, 0, 0):
            answer += "Demain matin il y aura "
        elif startdate.time() > datetime.time(12, 0, 0) and startdate.time() < datetime.time(18, 0, 0):
            answer += "Demain après-midi il y aura "
        elif startdate.time() >= datetime.time(18, 0, 0) and startdate.time() <= datetime.time(23, 59, 59):
            answer += "Demain soir il y aura "
    else:
        dayofweek = startdate.strftime("%A")
        if startdate.time() == datetime.time(12, 0, 0):
            answer += "%s il y aura " % dayofweek
        elif startdate.time() < datetime.time(12, 0, 0):
            answer += "%s matin il y aura " % dayofweek
        elif startdate.time() > datetime.time(12, 0, 0) and startdate.time() < datetime.time(18, 0, 0):
            answer += "%s après-midi il y aura " % dayofweek
        elif startdate.time() >= datetime.time(18, 0, 0) and startdate.time() <= datetime.time(23, 59, 59):
            answer += "%s soir il y aura " % dayofweek

    et = ""
    if len(weather['list'][selected_forecast]['weather']) > 1:
        et = " et "
    non_array = [
            "Non. ",
            "Pas vraiment. ",
            "Il semblerait que non. ",
    ]
    oui_array = [
            "Oui. ",
            "En effet, ",
            "Effectivement, ",
    ]
    oui = random.choice(non_array)
    for w in weather['list'][selected_forecast]['weather']:
        answer += CONDITION_CODES[w['id']]['snips'][0] + et
        if condition_name is not None and condition_name in CONDITION_CODES[w['id']]['snips']:
            oui = random.choice(oui_array)
    if len(et) > 0:
        answer = answer[:-len(et)]
    answer += " "
    answer = oui + answer

    if locality != conf['secret']['default_location']:
        answer += "à %s" % locality

    hermes.publish_end_session(intentMessage.session_id, answer)
    

if __name__ == "__main__":
    f = open("/etc/snips.toml", "rt")
    config = toml.load(f)
    mqtt_opts = MqttOptions(username=config["snips-common"]["mqtt_username"], password=config["snips-common"]["mqtt_password"], broker_address=config["snips-common"]["mqtt"])
    with Hermes(mqtt_options=mqtt_opts) as h:
        h.subscribe_intent("Kilawyn:searchWeatherForecastCondition", subscribe_intent_callback) \
         .start()
