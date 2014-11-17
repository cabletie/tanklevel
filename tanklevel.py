#!/usr/bin/python

import datetime
import time
import signal
import sys
import math
from threading import Timer

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

# Initialise the ADC device using the default addresses and sample rate, change this value if you have changed the address selection jumpers
# Sample rate can be 12,14, 16 or 18
adc = ADCPi(0x68, 0x69, 18)

class RepeatedTimer(object):
    def __init__(self, interval, function, *args, **kwargs):
        self._timer     = None
        self.interval   = interval
        self.function   = function
        self.args       = args
        self.kwargs     = kwargs
        self.is_running = False
        self.start()

    def _run(self):
        self.is_running = False
        self.start()
        self.function(*self.args, **self.kwargs)

    def start(self):
        if not self.is_running:
            self._timer = Timer(self.interval, self._run)
            self._timer.start()
            self.is_running = True

    def stop(self):
        self._timer.cancel()
        self.is_running = False

# Emit the current datetime and sample average
def emit(rawReadings):
  a = math.fsum(rawReadings)/len(rawReadings)
  print ("{},{:04f}".format(str(datetime.datetime.utcnow()),a))

# Initialise the raw readings array
rawReadings = [] 
timerNotStarted = True

rt = RepeatedTimer(60, emit, rawReadings)

try:
  while True:
    v = adc.readVoltage(8)
    if len(rawReadings) > 60:
      del rawReadings[0]
    rawReadings.append(v)
finally:
  rt.stop()
