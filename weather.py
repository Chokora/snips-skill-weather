#!/usr/bin/env python3

import os
import json
import re
import datetime
import requests

def get_weather_data(locality, country, api_key):
    weather = None
    if not os.path.isdir("cache"):
        os.mkdir('cache')
    regex = re.compile(r'^(?P<time>[0-9]+)_(?P<city>[\w-]+)_(?P<country>[A-Za-z ]{2})\.json$')
    for f in os.listdir('cache'):
        file_attrs = re.match(regex, f)
        if file_attrs is not None:
            dtime = datetime.datetime.fromtimestamp(float(file_attrs.group('time')))
            if dtime < datetime.datetime.now() - datetime.timedelta(minutes=10):
                os.unlink(os.path.join('cache', f))
            elif file_attrs.group('city') == locality and file_attrs.group('country') == country:
                new_f = open(os.path.join('cache', f), 'rt')
                weather = json.loads(new_f.read())
                new_f.close()
    if weather is None:
        r = requests.get("https://api.openweathermap.org/data/2.5/forecast?q=%s,%s&APPID=%s" % (locality, country, api_key))
        weather = r.json()
        if weather['cod'] != "200" and weather['cod'] != "404":
            return None
        weather_txt = json.dumps(weather)
        timestamp = "%d_%s_%s.json" % (datetime.datetime.now().timestamp(), locality, country)
        f = open(os.path.join('cache', timestamp), 'wt')
        f.write(weather_txt)
        f.close()
    return weather

