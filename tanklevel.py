#!/usr/bin/python

import datetime
import time
import signal
import sys
import math
from threading import Timer
import argparse

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("-d", "--debug", help="Turn on debugging to stderr", action="store_true")
parser.add_argument("-p", "--period", help="Time period  between readings in seconds", type=int, default=60)
parser.add_argument("-n", "--nsamples", help="Number of samples to average over", type=int, default=60)
parser.add_argument("-c", "--adcChannel", help="ADC Channel", type=int, default=8)
args = parser.parse_args()

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
	print >> sys.stderr, '\n', average
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
  average = math.fsum(rawReadings)/len(rawReadings)
  print ("{},{:.4f}".format(str(datetime.datetime.utcnow()),average))

# Initialise the raw readings array
rawReadings = [] 
average = 0

rt = RepeatedTimer(args.period, emit, rawReadings)

try:
  while True:
    v = adc.readVoltage(args.adcChannel)
    if len(rawReadings) >= args.nsamples:
      del rawReadings[0]
    rawReadings.append(v)
    if len(rawReadings) > 0 : 
      average = math.fsum(rawReadings)/len(rawReadings)
    if args.debug: 
      print >> sys.stderr, "{:.4f},{:.4f}".format(v,average)
    if len(rawReadings) == 1:
      print ("{},{:.4f}".format(str(datetime.datetime.utcnow()),average))
finally:
  rt.stop()
