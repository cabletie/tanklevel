#!/usr/bin/python

import datetime
import time
import signal
import sys
import math
from threading import Timer
import argparse
import sqlite3
import select
import socket
from random import random, uniform
import Queue
import os
import csv
import logging
import ConfigParser

def isChannelSection(sectionName):
return re.match('ch\d',sectionName)

config = ConfigParser.ConfigParser()
logging.info('Reading config file: {}'.format(args.config))
try:
config.read(args.config)
#    channels = [i for i in config.sections() if re.match('ch\d',i)]
for s in filter(isChannelSection,config.sections()):
channelZero[s] = c.get(s,'Zero')
channelNames[s] = c.get(s,'Name')
except:
logging.error('Error reading config file: {}'.format(args.config))
sys.exit(1)
