#!/usr/bin/python

import datetime
import time
import signal
import sys
import math
import threading

# ================================================
# Based on
# ABElectronics ADC Pi 8-Channel ADC data-logger demo
# Version 1.0 Created 11/05/2014
#
# Requires python smbus to be installed
# run with: python tanklevel.py
# ================================================

# Setup to gracefully catch ^C and exit
def signal_handler(signal, frame):
	print >> sys.stderr, rawReadings
        print >> sys.stderr,'\nExiting'
        sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

sys.path.append('../ABElectronics_Python_Libraries/ABElectronics_ADCPi')
from ABElectronics_ADCPi import ADCPi

# Emit the current datetime and sample average
def emit():
  threading.Timer(5.0, emit, rawReadings).start()
  a = math.fsum(rawReadings)/len(rawReadings)
  print ("{},{:04f},{:04f}".format(str(datetime.datetime.utcnow()),a,v))

# Initialise the ADC device using the default addresses and sample rate, change this value if you have changed the address selection jumpers
# Sample rate can be 12,14, 16 or 18
adc = ADCPi(0x68, 0x69, 18)

# Initialise the raw readings array
rawReadings = [] 
timerNotStarted = True

emit()

while True:
  v = adc.readVoltage(8)
  if timerNotStarted and len(rawReadings) > 10: 
    emit()
    timerNotStarted = False
  if len(rawReadings) > 60:
    del rawReadings[0]
  rawReadings.append(v)
