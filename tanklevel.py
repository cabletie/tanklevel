#!/usr/bin/python

from ABElectronics_ADCPi import ADCPi
import datetime
import time
import signal
import sys
import math

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
        print rawReadings
        print('\nExiting')
        sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Initialise the ADC device using the default addresses and sample rate, change this value if you have changed the address selection jumpers
# Sample rate can be 12,14, 16 or 18
adc = ADCPi(0x68, 0x69, 18)

# Initialise the raw readings array
rawReadings = [] 
currentIndex = 0

while True:
  v = adc.readVoltage(8)
  if len(rawReadings) > 60:
    rawReadings[currentIndex] = v
  else :
    rawReadings.append(v)
  #print ("Current: %04f" % v)
  a = math.fsum(rawReadings)/len(rawReadings)
  print ("{:04f},{:04f}".format(a,v))
