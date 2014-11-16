#!/usr/bin/python

from ABElectronics_ADCPi import ADCPi
import datetime
import time

# ================================================
# Based on
# ABElectronics ADC Pi 8-Channel ADC data-logger demo
# Version 1.0 Created 11/05/2014
#
# Requires python smbus to be installed
# run with: python tanklevel.py
# ================================================


# Initialise the ADC device using the default addresses and sample rate, change this value if you have changed the address selection jumpers
# Sample rate can be 12,14, 16 or 18
adc = ADCPi(0x68, 0x69, 18)

rv = adc.readRaw(8)
#print ("Pressure Sensor(raw): 0x%0x" % rv)
#print ("Pressure Sensor(raw): {0:016b}").format(rv)
print ("%04f" % adc.readVoltage(8))
#print ("Pressure Sensor: %04fV" % adc.readVoltage(8))
#print ("RPi Supply Voltage: %02f\n" % adc.readVoltage(7))
