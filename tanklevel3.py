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
import configparser

if os.name != "nt":
    import fcntl
    import struct
    def get_interface_ip(ifname):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return socket.inet_ntoa(fcntl.ioctl(
                s.fileno(),
                0x8915,  # SIOCGIFADDR
                struct.pack('256s', ifname[:15])
            )[20:24])

def get_lan_ip():
    ip = socket.gethostbyname(socket.gethostname())
    if ip.startswith("127.") and os.name != "nt":
        interfaces = ["eth0","eth1","eth2","wlan0","wlan1","wifi0","ath0","ath1","ppp0"]
        for ifname in interfaces:
            try:
                ip = get_interface_ip(ifname)
                break;
            except IOError:
                pass
    return ip

# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("-d", "--debug", help="Turn on debugging to stderr", action="store_true")
parser.add_argument("-l", "--loglevel", help="Set logging level DEBUG,INFO,WARNING,ERROR,CRITICAL", 
    default='INFO', choices=['DEBUG','INFO','WARNING','ERROR','CRITICAL'])
parser.add_argument("-e", "--logfile", help="File to log system messages", default="adcpiv2.log")
parser.add_argument("-p", "--period", help="Time period  between when average readings are emitted (seconds)", 
    type=int, default=300)
parser.add_argument("-n", "--nsamples", help="Number of samples to average over", type=int, default=60)
parser.add_argument("-h", "--adcchannel", help="ADC Channel", type=int, default=8)
parser.add_argument("-f", "--datafile", help="csv file to log data to", default="adcpiv2.csv")
parser.add_argument("-s", "--histfile", help="existing csv file with history data to load", default="adcpiv2.csv")
parser.add_argument("-b", "--dbname", help="sqlite3 database file to log data to", default="adcpiv2.db")
parser.add_argument("-i", "--init", help="initialise sqlite3 database", action="store_true")
parser.add_argument("-t", "--test", help="Run in test mode - uses random data", action="store_true")
parser.add_argument("-g", "--debugport", help="Port to provide debug output (every reading)", type=int, default=10001)
parser.add_argument("-o", "--port", help="Port to provide main output (gives latest reading and disconnects)", 
    type=int, default=10000)
parser.add_argument("-a", "--bindaddress", help="IP Address to bind to", default=get_lan_ip())
parser.add_argument("-c", "--config", help="Use this config file", default='tanklevel.ini')

args = parser.parse_args()

# Parse Config file
channelZero = {}
channelNames = {}

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


numeric_level = getattr(logging, args.loglevel.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)

logging.basicConfig(filename=args.logfile,
    format='%(asctime)s %(filename)s %(process)s %(levelname)s %(message)s',
    level=numeric_level)

logging.info('Starting')

tableName = "adcpiv2"
tmpTableName = "tmptable"
#channelstablename = "channels"

con = sqlite3.connect(args.dbname)

# If we've been asked to initialise database
if args.init:
    logging.info('Initialising db') 
    with con:
        cur = con.cursor()
        #            DROP TABLE IF EXISTS {channelstablename};
        #            CREATE TABLE IF NOT EXISTS {channelstablename}(Id INT, Name CHAR(32), Address INT, Zero INT, Span INT, Convert INT, Units CHAR(32));
        sqlScript = """
            DROP TABLE IF EXISTS {tablename};
            DROP TABLE IF EXISTS {tmptablename};
            CREATE TABLE IF NOT EXISTS {tablename}(Id INTEGER PRIMARY KEY AUTOINCREMENT, DateTime CHAR(32), Voltage FLOAT,AdcChannel INT);
            CREATE TABLE IF NOT EXISTS {tmptablename}(DateTime CHAR(32), Voltage FLOAT,AdcChannel INT);
            """.format(tablename=tableName,tmptablename=tmpTableName)
        cur.executescript(sqlScript)
        if os.path.isfile(args.datafile) and os.access(args.datafile, os.R_OK):
            # Open and read the csv into the tmpTable
            reader = csv.reader(open(args.histfile, 'r'), delimiter=',')
            for row in reader:
                to_db = [unicode(row[0], "utf8"), unicode(row[1], "utf8"), unicode(row[2], "utf8")]
                cur.execute("INSERT INTO {tmptablename}(DateTime, Voltage, AdcChannel) VALUES (?, ?, ?);".format(tmptablename=tmpTableName), to_db)
            # Insert the whole tmpTable into the real table, this time allowing sqlite3 to add the AUTOINCREMENT Id field
            cur.execute("INSERT INTO {tablename}(DateTime, Voltage, AdcChannel) SELECT * FROM {tmptablename};".format(tablename=tableName,tmptablename=tmpTableName))
            logging.info("Inserted {} rows.".format(cur.rowcount))
        else:
            logging.error("Datafile ({}) not found or not readable, creating empty database".format(args.histfile))
    # Finished doing db init and loading
    con.close()
    logging.info('Done initialising database')
  
# Setup to gracefully catch ^C and exit
def signal_handler(signal, frame):
    logging.info('Got SIGINT - Cleaning up')
    rt.stop()
    df.close()
    logging.debug("   current raw readings: {}".format(rawReadings))
    logging.debug("   Current average: {}".format(average))
    for s in inputs:
        s.close()
    for s in outputs:
        s.close()

    logging.info('   Exiting')
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
        self.con        = None
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
            self.con = sqlite3.connect(args.dbname)

    def stop(self):
        self._timer.cancel()
#        self.con.close()
        self.is_running = False

# Initialise the raw readings array and initial average value
rawReadings = [] 
average = 0
sampleTime = ''

# Emit the current datetime and sample average
last_df_write = ""
def emit(rawReadings,last_df_write):
    logging.debug('Emitting current data to db')
    average = math.fsum(rawReadings)/len(rawReadings)
    sampleTime = str(datetime.datetime.now())
    last_df_write = "{},{:.4f},{}\n".format(sampleTime,average,args.adcchannel)
    df.write(last_df_write)
    with rt.con:
        cur = rt.con.cursor()
        sqlScript = "INSERT INTO {}(DateTime, Voltage, AdcChannel) VALUES ('{}', {:.4f}, {});".format(tableName,sampleTime,average,args.adcchannel)
        logging.debug("Executing SQL: {}".format(sqlScript))
        cur.execute(sqlScript)
#    print >> sys.stderr, "Wrote {},{},{} to database\n".format(sampleTime,average,args.adcchannel)

try:
  df = open(args.datafile, "a", 1)
except:
  logging.error("Failed to open {} for writing",args.datafile)
  sys.exit(1)
  
# Save current average reading to database once per period
logging.info('Initialising emit timer at {:d} seconds'.format(args.period))
rt = RepeatedTimer(args.period, emit, rawReadings, last_df_write)

# Create a TCP/IP sockets, on efor main server, one for debug server
debug_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
debug_server.setblocking(0)
main_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
main_server.setblocking(0)

# Bind the socket to the port
server_debug_address = (args.bindaddress, args.debugport)
logging.info('starting up debug server on {} port {}'.format(*server_debug_address))
try:
    debug_server.bind(server_debug_address)
except socket.error:
    df.close()
    rt.stop()
    logging.error('Failed to bind to debug socket - Quitting')
    sys.exit(1)

# Bind the socket to the port
server_main_address = (args.bindaddress, args.port)
logging.info('starting up main server on {} port {}'.format(*server_main_address))
try:
    main_server.bind(server_main_address)
except socket.error:
    df.close()
    rt.stop()
    debug_server.close()
    logging.error('Failed to bind to main socket - Quitting')
    sys.exit(1)

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

logging.debug('Starting main loop')

try:
    while inputs:

        # Main data collection loop
        # Generate a random value if in test mode, otherwise read current data from adc
        if args.test:
            v = uniform(0.4,5.05)
            time.sleep(1)
        else:
            v = adc.readVoltage(args.adcchannel)

        # Delet the oldest sample if we have nsamples or more
        if len(rawReadings) >= args.nsamples:
            del rawReadings[0]

        # Append the newest reading to the array
        rawReadings.append(v)

        # If we have more than zero readings, calculate average and update output string
        if len(rawReadings) > 0 : 
            average = math.fsum(rawReadings)/len(rawReadings)
#            last_df_write = "{},{:.4f},{}\n".format(str(datetime.datetime.now()),average,args.adcchannel)
            logging.debug("{:.4f},{:.4f}".format(v,average))

        # Handle feeding data to debug_outputs
        if outputs:
            for s in outputs:
                message_queues[s].put("{:.4f},{:.4f}\n".format(v,average))

#         # Write out the first data point we get
#         if len(rawReadings) == 1:
# #### Might neeed to change this to grab most recent db entry and send that instead
#             # Generate the string so we can use to send to TCP ports if/when needed
#             last_df_write = "{},{:.4f},{}\n".format(str(datetime.datetime.now()),average,args.adcchannel)
#             # Write out to datafile
#             df.write(last_df_write)

        # Wait for at least one of the sockets to be ready for processing
        # or timeout of 1 second
        # We really only ever expect connection requests
        logging.debug('waiting for the next event')
        readable, writable, exceptional = select.select(inputs, outputs, inputs, 1)

        if not (readable or writable or exceptional):
            continue # go back to "while inputs:"

        # Select gave us something to do
        logging.debug('   Select gave us something to do')

        # Handle "exceptional conditions"
        for s in exceptional:
            logging.debug('handling exceptional condition for {}', s.getpeername())
            # Stop listening for input on the connection
            inputs.remove(s)
            if s in outputs:
                outputs.remove(s)
            s.close()

            # Remove message queue
            del message_queues[s]

        # Handle inputs
        for s in readable:
            if s is debug_server:
                # A "readable" debug_server socket is ready to accept a connection
                connection, client_address = s.accept()
                logging.info('debug server new connection from {}:{}'.format(*client_address))
                connection.setblocking(0)

                # Give the connection a queue for data we want to send
                message_queues[connection] = Queue.Queue()

                # Add this connection queue to the list of outputs to service
                outputs.append(connection)
            else:
                if s is main_server:
                    # A "readable" main_server socket is ready to accept a connection
                    connection, client_address = s.accept()
                    logging.info('main server new connection from {}:{}'.format(*client_address))
                    connection.setblocking(0)

                    # Give the connection a queue for data we want to send
                    message_queues[connection] = Queue.Queue()
            	    # Immediately put last record into send buffor for sending to this connection
                    con = sqlite3.connect(args.dbname)
                    cur = con.cursor()
                    cur.execute('select * from adcpiv2 where rowid = (select seq from sqlite_sequence where name="adcpiv2");')
                    last_df_write = ",".join(str(i) for i in cur.fetchone())
                    logging.debug("Last db entry was {}".format(last_df_write))
                    message_queues[connection].put(last_df_write)
                    con.close()
            	    # Add this connection to the list of outputs to service
            	    outputs.append(connection)
            	    # Add this connection to the list of one-message-only outputs to service
            	    main_outputs.append(connection)
                else:
                    data = s.recv(1024)
                    if data:
                        # A readable client socket has data
                        logging.debug('received "{}" from {}:{} (ignored)',data, *s.getpeername())

        # Handle outputs
        for s in writable:
            try:
                next_msg = message_queues[s].get_nowait()
            except Queue.Empty:
                pn = s.getpeername()
                logging.info('output queue for {}:{} is empty'.format(*pn))
                # No messages waiting so stop checking for writability.
                #print >>sys.stderr, 'output queue for', s.getpeername(), 'is empty'
                #outputs.remove(s)
            else:
                try:
                    pn = s.getpeername()
                    s.send(next_msg)
                    logging.debug('sent "{}" to {}:{}'.format(next_msg, *pn))
 	           # If this is a once only connection, remove from output lists and close
                    if s in main_outputs:
                        sn = s.getsockname()
                        logging.debug('closing main_server socket connection on port {}:{}'.format(*sn))
                        outputs.remove(s)
                        main_outputs.remove(s)
                        s.close()
                except socket.error:
                    sn = s.getsockname()
                    logging.info('Connection reset by peer: {}:{}'.format(*sn))
                    if s in inputs:
                        inputs.remove(s)
                    if s in outputs:
                        outputs.remove(s)
                    s.close()
    # end while inputs
    logging.warning('no more input sockets to process - exiting.')
    

# We got a ^C - close up shop cleanly
finally:
    logging.info('Cleaning up and Exiting - Bye')
    for s in inputs:
        s.close()
    for s in outputs:
        s.close()
    df.close()
    rt.stop()

