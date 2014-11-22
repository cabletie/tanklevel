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

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("-d", "--debug", help="Turn on debugging to stderr", action="store_true")
parser.add_argument("-p", "--period", help="Time period  between readings in seconds", type=int, default=60)
parser.add_argument("-n", "--nsamples", help="Number of samples to average over", type=int, default=60)
parser.add_argument("-c", "--adcchannel", help="ADC Channel", type=int, default=7)
parser.add_argument("-f", "--datafile", help="file to log data to", default="adcpiv2.csv")
parser.add_argument("-b", "--dbname", help="sqlite3 database file to log data to", default="adcpiv2.db")
parser.add_argument("-i", "--init", help="initialise sqlite3 database", action="store_true")
parser.add_argument("-t", "--test", help="Run in test mode - uses random data", action="store_true")
parser.add_argument("-g", "--debugport", help="Port to provide debug output (every reading)", type=int, default=10001)
parser.add_argument("-o", "--port", help="Port to provide main output (gives latest reading and disconnects)", type=int, default=10000)

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
  df.write("{},{:.4f},{}\n".format(str(datetime.datetime.now()),average,args.adcchannel))

# Initialise the raw readings array
rawReadings = [] 
average = 0

try:
  df = open(args.datafile, "a", 1)
except:
  print >> sys.stderr, "Failed to open args.datafile for writing\n"
  sys.exit(1)
  
# Save current average reading to database once per period
rt = RepeatedTimer(args.period, emit, rawReadings)

# Create a TCP/IP sockets, on efor main server, one for debug server
debug_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
debug_server.setblocking(0)
main_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
main_server.setblocking(0)

# Bind the socket to the port
server_debug_address = ('localhost', args.debugport)
print >>sys.stderr, 'starting up debug on %s port %s' % server_debug_address
debug_server.bind(server_debug_address)

# Bind the socket to the port
server_main_address = ('localhost', args.port)
print >>sys.stderr, 'starting up on %s port %s' % server_main_address
main_server.bind(server_main_address)

# Listen for incoming connections on the two ports
debug_server.listen(5)
main_server.listen(5)

# Sockets from which we expect to read
inputs = [ debug_server, main_server ]

# Sockets to which we expect to write
outputs = [ ]

# Keep track of one-record-only sockets
main_outputs = [ ]

# Outgoing message queues (socket:Queue)
message_queues = {}

last_df_write = ""

try:
    while inputs:

        # Wait for at least one of the sockets to be ready for processing
        # or timeout of 1 second
        print >>sys.stderr, 'waiting for the next event'
        readable, writable, exceptional = select.select(inputs, outputs, inputs, 1)
        if not (readable or writable or exceptional):
            # Main data collection loop
            print >>sys.stderr, '   timed out, go collect some data'
            if args.test:
                v = uniform(0.4,5.05)
                time.sleep(1)
            else:
                v = adc.readVoltage(args.adcchannel)
            if len(rawReadings) >= args.nsamples:
                del rawReadings[0]
            rawReadings.append(v)
            if len(rawReadings) > 0 : 
                average = math.fsum(rawReadings)/len(rawReadings)
            if args.debug: 
                print >> sys.stderr, "{:.4f},{:.4f}".format(v,average)
            # Handle feeding data to main_outputs
            for s in outputs:
                try:
                    message_queues[s].put("{:.4f},{:.4f}".format(v,average))
                except:
                    # No messages waiting so stop checking for writability.
                    print >>sys.stderr, 'no debug outputs to feed'
        else:
            if len(rawReadings) == 1:
                last_df_write = "{},{:.4f},{}\n".format(str(datetime.datetime.now()),average,args.adcchannel)
                df.write(last_df_write)
            continue # go back to "while inputs:"

        # Select gave us something to do
        # Handle inputs
        for s in readable:
            if s is debug_server:
                # A "readable" debug_server socket is ready to accept a connection
                connection, client_address = s.accept()
                print >>sys.stderr, 'debug server new connection from', client_address
                connection.setblocking(0)

                # Give the connection a queue for data we want to send
                message_queues[connection] = Queue.Queue()
            else:
                if s is main_server:
                    # A "readable" main_server socket is ready to accept a connection
                    connection, client_address = s.accept()
                    print >>sys.stderr, 'main server new connection from', client_address
                    connection.setblocking(0)

                    # Give the connection a queue for data we want to send
                    message_queues[connection] = Queue.Queue()
            	    # Immediately put last record into send buffor for sending to this connection
                    message_queues[connection].put(last_df_write)
            	    # Add this connection to the list of outputs to service
            	    outputs.append(connection)
            	    # Add this connection to the list of one-message-only outputs to service
            	    main_outputs.append(connection)
                else:
                    data = s.recv(1024)
                    if data:
                        # A readable client socket has data
                        print >>sys.stderr, 'received "%s" from %s (ignored)' % (data, s.getpeername())

        # Handle outputs
        for s in writable:
            try:
                next_msg = message_queues[s].get_nowait()
            except Queue.Empty:
                # No messages waiting so stop checking for writability.
                print >>sys.stderr, 'output queue for', s.getpeername(), 'is empty'
                outputs.remove(s)
            else:
                print >>sys.stderr, 'sending "%s" to %s' % (next_msg, s.getpeername())
                s.send(next_msg)
    	    # If this is a once only connection, remove from output lists and close
                if s in main_outputs:
                    inputs.remove(s)
                    outputs.remove(s)
                    main_outputs.remove(s)
                    s.close()

        # Handle "exceptional conditions"
        for s in exceptional:
            print >>sys.stderr, 'handling exceptional condition for', s.getpeername()
            # Stop listening for input on the connection
            inputs.remove(s)
            if s in outputs:
                outputs.remove(s)
            s.close()

            # Remove message queue
            del message_queues[s]

# We got a ^C - close up shop cleanly
finally:
    for s in inputs:
        s.close()
    for s in outputs:
        s.close()
    df.close()
    rt.stop()

