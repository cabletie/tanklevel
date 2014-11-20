#!/usr/bin/python

import datetime
import time
import signal
import sys
import math
from threading import Timer
import argparse
import sqlite3

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("-d", "--debug", help="Turn on debugging to stderr", action="store_true")
parser.add_argument("-p", "--period", help="Time period  between readings in seconds", type=int, default=60)
parser.add_argument("-n", "--nsamples", help="Number of samples to average over", type=int, default=60)
parser.add_argument("-c", "--adcchannel", help="ADC Channel", type=int, default=8)
parser.add_argument("-f", "--datafile", help="file to log data to", default="rawdata.csv")
parser.add_argument("-b", "--dbname", help="sqlite3 database file to log data to", default="adcpiv2.db")
parser.add_argument("-i", "--init", help="initialise sqlite3 database", action="store_true")
args = parser.parse_args()

tableName = "adcpiv2"

con = sqlite3.connect(args.dbname)

# If we've been asked to initialise database
if args.init: 
  with con:
    cur = con.cursor()
    cur.executescript("""
          DROP TABLE IF EXISTS adcpiv2;
          DROP TABLE IF EXISTS tmpTable;
          CREATE TABLE IF NOT EXISTS adcpiv2(Id INTEGER PRIMARY KEY AUTOINCREMENT, DateTime CHAR(32), Voltage FLOAT,AdcChannel INT);
          CREATE TABLE IF NOT EXISTS tmpTable(DateTime CHAR(32), Voltage FLOAT,AdcChannel INT);
          """)
    if os.path.isfile(args.datafile) and os.access(args.datafile, os.R_OK):
      # Open and read the csv into the tmpTable
      reader = csv.reader(open(args.datafile, 'r'), delimiter=',')
      for row in reader:
        to_db = [unicode(row[0], "utf8"), unicode(row[1], "utf8"), unicode(row[2], "utf8")]
        cur.execute("INSERT INTO tmpTable(DateTime, Voltage, AdcChannel) VALUES (?, ?, ?);", to_db)
      # Intert the whole tmpTable into the real table, this time allowing sqlite3 to add the AUTOINCREMENT Id field
      cur.execute("INSERT INTO adcpiv2(DateTime, Voltage, AdcChannel) SELECT * FROM tmpTable;")
    else:
      print >> sys.stderr, "Datafile not found or not readable, creating empty database\n"

# Setup to gracefully catch ^C and exit
def signal_handler(signal, frame):
	df.close()
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
  df.write("{},{:.4f},{}\n".format(str(datetime.datetime.now()),average,args.adcChannel))

# Initialise the raw readings array
rawReadings = [] 
average = 0

try:
  df = open(args.datafile, "a", 1)
except:
  print >> sys.stderr, "Failed to open args.datafile for writing\n"
  sys.exit(1)
  
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
      df.write("{},{:.4f},{}\n".format(str(datetime.datetime.now()),average,args.adcChannel))
finally:
  df.close()
  rt.stop()
