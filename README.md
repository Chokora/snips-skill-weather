# Snips Joke Skill

This is a Python3 skill allowing to retrieve information about 
weather. It based on OpenWeatherMap, so it requires an API key.

Go to https://openweathermap.org/ for more information about the API 
and API Key.

## Setup

This app requires some python dependencies to work properly, these are
listed in the `requirements.txt`. You can use the `setup.sh` script to
create a python virtualenv that will be recognized by the skill server
and install them in it.

## Executables

This dir contains a number of python executables named `action-*.py`.
One such file is generated per intent supported. These are standalone
executables and will perform a connection to MQTT and register on the
given intent using the `hermes-python` helper lib.
