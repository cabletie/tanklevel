#!/usr/bin/python3

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
import queue
import os
import csv
import logging
import configparser
from pep3143daemon import DaemonContext, PidFile


# Parse arguments
parser = argparse.ArgumentParser()
parser.add_argument("-V", "--debug", help="Turn on debugging to stderr", action="store_true")
parser.add_argument("-l", "--loglevel", help="Set logging level DEBUG,INFO,WARNING,ERROR,CRITICAL", 
    default='INFO', choices=['DEBUG','INFO','WARNING','ERROR','CRITICAL'])
parser.add_argument("-e", "--logfile", help="File to log system messages", default="/var/log/adcpiv2/adcpiv2.log")
parser.add_argument("-p", "--period", help="Time period  between when average readings are emitted (seconds)", 
    type=int)
parser.add_argument("-n", "--nsamples", help="Number of samples to average over", type=int)
parser.add_argument("-c", "--adcchannel", help="ADC Channel", type=int, default=8)
parser.add_argument("-d", "--datafile", help="csv file to log data to [adcpiv2.csv]", default="/var/local/adcpiv2/adcpiv2.csv")
parser.add_argument("-s", "--histfile", help="existing csv file with history data to load")
parser.add_argument("-b", "--dbname", help="sqlite3 database file to log data to", default="/var/local/adcpiv2/adcpiv2.db")
parser.add_argument("-q", "--initq", help="initialise sqlite3 database then quit", action="store_true")
parser.add_argument("-i", "--init", help="initialise sqlite3 database", action="store_true")
parser.add_argument("-t", "--test", help="Run in test mode - uses random data", action="store_true")
parser.add_argument("-g", "--debugport", help="Port to provide debug output (every reading)", 
    type=int) # default=12001
parser.add_argument("-o", "--port", help="Port to provide main output (gives latest reading and disconnects)", 
    type=int) # default=12000
parser.add_argument("-a", "--bindaddress", help="IP Address to bind to") # default='0.0.0.0'
parser.add_argument("-f", "--config", help="Use this config file", default='/etc/local/adcpiv2.conf')
parser.add_argument("-m", "--daemon", help="Run in daemon mode (background)", action="store_true")

# Go grab all the command line options
args = parser.parse_args()

# If daemon option was specified, background ourselves immediately
if (args.daemon):
    pid='/var/run/{}.pid'.format(os.path.basename(__file__))

    pidfile = PidFile(pid)
    daemon = DaemonContext(pidfile=pidfile,detach_process=False,stdout=sys.stdout,stderr=sys.stderr)
    # we could have written this also as:
    # daemon.pidfile = pidfile
    print ('{}: Backgrounding'.format(os.path.basename(__file__)))
    daemon.open()
else:
    print ('{}: Not backgrounding'.format(os.path.basename(__file__)))

print ('{} pid : {}'.format(os.path.basename(__file__),os.getpid()))
# Start logging
numeric_level = getattr(logging, args.loglevel.upper(), None)
if not isinstance(numeric_level, int):
    raise ValueError('Invalid log level: %s' % loglevel)

logFormatter = logging.Formatter('%(asctime)s %(filename)s %(process)s %(levelname)s %(message)s')

logging.basicConfig(filename=args.logfile,
                    format='%(asctime)s %(filename)s %(process)s %(levelname)s %(message)s',
                    level=numeric_level)
if(args.debug):
    # Add logging to stderr if --debug specified
    consoleHandler = logging.StreamHandler()
    #consoleHandler.setFormatter(logFormatter)
    logging.getLogger().addHandler(consoleHandler)

logging.info('Starting')

# Parse Config file
# Example config section:
#[ch7]
#name = Vcc
#address = 7
#zero = 0
#span = 5
#scale = 1
#units = Volts

# channelZero = {}
# channelNames = {}
# channelConfig = {}

def isChannelSection(sectionName):
    return re.match('ch\d',sectionName)

config = configparser.ConfigParser()
logging.info('Reading config file: {}'.format(args.config))
try:
    config.read(args.config)
    logging.debug(config.sections())
    # for s in filter(isChannelSection,config.sections()):
    #     channelConfig[s] = {}
    #     channelConfig[s]['Zero'] = c.get(s,'Zero')
    #     channelConfig[s]['Name'] = c.get(s,'Name')
    #     channelConfig[s]['Address'] = c.get(s,'Address')
    #     channelConfig[s]['Span'] = c.get(s,'Span')
    #     channelConfig[s]['Scale'] = c.get(s,'Scale')
    #     channelConfig[s]['Units'] = c.get(s,'Units')
except:
    logging.error('Error reading config file: {}'.format(args.config))
    sys.exit(1)


tableName = "adcpiv2"
tmpTableName = "tmptable"

con = sqlite3.connect(args.dbname)

# Always try to create tables if they're not there yet
with con:
    cur = con.cursor()
    sqlScript = """
        CREATE TABLE IF NOT EXISTS {tablename}(Id INTEGER PRIMARY KEY AUTOINCREMENT, DateTime CHAR(32), 
        Ch8Channel INTEGER, Ch8Value FLOAT, Ch8Units CHAR(32), Ch8Name CHAR(32), Ch8Voltage FLOAT, Ch8Zero FLOAT, Ch8Span FLOAT, Ch8Scale FLOAT
    );
        CREATE TABLE IF NOT EXISTS {tmptablename}(DateTime CHAR(32), Voltage FLOAT,AdcChannel INT);
        """.format(tablename=tableName,tmptablename=tmpTableName)
    cur.executescript(sqlScript)

# If we've been asked to initialise database, drop tables and load from csv file
if args.init | args.initq:
    logging.info('Initialising db') 
    with con:
        cur = con.cursor()
        #            DROP TABLE IF EXISTS {channelstablename};
        #            CREATE TABLE IF NOT EXISTS {channelstablename}(Id INT, Name CHAR(32), Address INT, Zero INT, Span INT, Convert INT, Units CHAR(32));
        sqlScript = """
            DROP TABLE IF EXISTS {tablename};
            DROP TABLE IF EXISTS {tmptablename};
            CREATE TABLE IF NOT EXISTS {tablename}(Id INTEGER PRIMARY KEY AUTOINCREMENT, DateTime CHAR(32), 
            Ch8Channel INTEGER, Ch8Value FLOAT, Ch8Units CHAR(32), Ch8Name CHAR(32), Ch8Voltage FLOAT, Ch8Zero FLOAT, Ch8Span FLOAT, Ch8Scale FLOAT
        );
            CREATE TABLE IF NOT EXISTS {tmptablename}(DateTime CHAR(32), Voltage FLOAT,AdcChannel INT);
            """.format(tablename=tableName,tmptablename=tmpTableName)
        cur.executescript(sqlScript)
        if args.histfile and os.path.isfile(args.histfile) and os.access(args.histfile, os.R_OK):
            # Open and read the csv into the tmpTable
            reader = csv.DictReader(open(args.histfile, 'r'), delimiter=',')
            for row in reader:
                #print >> sys.stderr, row['DateTime']
                to_db = [row['DateTime'], row['Voltage'], row['Channel']]
                #print >> sys.stderr, to_db
                cur.execute("INSERT INTO {tmptablename}(DateTime, Voltage, AdcChannel) VALUES (?, ?, ?);".format(tmptablename=tmpTableName), to_db)
                # Insert the whole tmpTable into the real table, this time allowing sqlite3 to add the AUTOINCREMENT Id field
                sqlScript = "INSERT INTO {tablename}(DateTime, Ch8Channel, Ch8Value, Ch8Units, Ch8Name, Ch8Voltage, Ch8Zero, Ch8Span, Ch8Scale) \
                    SELECT DateTime, 8, (Voltage-{zero})*{scale},'{units}','{name}', Voltage,'{zero}','{span}','{scale}' \
                    FROM {tmptablename};".format(
                        tablename=tableName,
                        tmptablename=tmpTableName,
                        zero=config['ch8']['Zero'],
                        scale=config['ch8']['Scale'],
                        units=config['ch8']['Units'],
                        name=config['ch8']['Name'],
                        span=config['ch8']['Span']
                        )
            logging.debug('Executing {}'.format(sqlScript))
            cur.execute(sqlScript)
            logging.info("Inserted {} rows.".format(cur.rowcount))
        else:
            logging.error("Datafile ({}) not found, not specified or not readable, creating empty database".format(args.histfile))
    # Finished doing db init and loading
    con.close()
    logging.info('Done initialising database')
    # Exit if we were asked to init and quit (--initq)
    if args.initq:
        logging.info('    exiting - initq specified')
        sys.exit(0)
  
# Setup to gracefully catch ^C and exit
def signal_handler(signal, frame):
    logging.info('Got SIGINT - Cleaning up')
    # Stop the sample timer
    rt.stop()
    # Close the raw data file
    df.close()
    logging.debug("   current raw readings: {}".format(rawReadings))
    logging.debug("   Current average: {}".format(average))
    # Close the TCP sockets
    for s in inputs:
        s.close()
    for s in outputs:
        s.close()
# Not convinvced this is needed - all should be closed by now 
# because main_outputs is a copy of some outputs
    for s in main_outputs:
        s.close()

    logging.info('   Exiting')
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

# Hardcode where we expect the ABElectronics library to be
sys.path.append('/usr/local/lib/ABElectronics_Python_Libraries/ABElectronics_ADCPi')
from ABElectronics_ADCPi import ADCPi

# Initialise the ADC device using the default addresses and sample rate, 
# change this value if you have changed the address selection jumpers
# Or it should be from options/config file
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

# Emit the current datetime and sample average to databse
# Done asychronously on a timer
last_df_write = ""
def emit(rawReadings,last_df_write):
    logging.debug('Emitting current data to db')
    average = math.fsum(rawReadings)/len(rawReadings)
    sampleTime = str(datetime.datetime.now())
    last_df_write = "{},{:.4f},{}\n".format(sampleTime,average,args.adcchannel)
    last_df_write = "'{datetime}', '{channel}', '{value:.4f}', '{units}','{name}','{voltage:.4f}','{zero}','{span}','{scale:.4f}'".format(
            datetime=sampleTime,
            channel=config['ch8']['Address'],
            value=(average-float(config['ch8']['Zero']))*float(config['ch8']['Scale']),
            units=config['ch8']['Units'],
            name=config['ch8']['Name'],
            voltage=average,
            zero=config['ch8']['Zero'],
            span=config['ch8']['Span'],
            scale=float(config['ch8']['Scale']))
    df.write(last_df_write)
    with rt.con:
        cur = rt.con.cursor()
        # Id INTEGER PRIMARY KEY AUTOINCREMENT, DateTime CHAR(32), 
        # Ch8Channel INTEGER, Ch8Value FLOAT, Ch8Units CHAR(32), Ch8Name CHAR(32), Ch8Voltage FLOAT, Ch8Zero FLOAT, Ch8Span FLOAT, Ch8Scale FLOAT
        sqlScript = "INSERT INTO {tablename}(DateTime,Ch8Channel, Ch8Value , Ch8Units, Ch8Name, Ch8Voltage, Ch8Zero , Ch8Span , Ch8Scale ) \
            VALUES ({datarow})".format(tablename=tableName,datarow=last_df_write)
        logging.debug("Executing SQL: {}".format(sqlScript))
        try:
            cur.execute(sqlScript)
        except sqlite3.Error as e:
            logging.error("Failed to write entry to database: {}\n".format(e.args[0]))
        logging.debug("Completed SQL")
	    
#    print >> sys.stderr, "Wrote {},{},{} to database\n".format(sampleTime,average,args.adcchannel)

try:
  df = open(args.datafile, "a", 1)
except:
  logging.error("Failed to open {} for writing",args.datafile)
  sys.exit(1)
 
period = 300
try:
    period = args.period or int(config['adcpiv2']['period'])
    #logging.error( "period using: {}".format(period))
except:
    logging.error( "failed period, using: {}".format(period))
 
# Save current average reading to database once per period
logging.info('Initialising emit timer at {:d} seconds'.format(period))

nsamples = 20
try:
    nsamples = args.nsamples or int(config['adcpiv2']['nsamples'])
    #logging.error( "nsamples using: {}".format(nsamples))
except:
    logging.error( "failed nsamples, using: {}".format(nsamples))
 
# Save current average reading to database once per period
logging.info('Initialising emit timer at {:d} seconds'.format(nsamples))

# Create a repeating time that grabs current average and emits to db or socket(s)
rt = RepeatedTimer(period, emit, rawReadings, last_df_write)

# Create a TCP/IP sockets, on efor main server, one for debug server
debug_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
debug_server.setblocking(0)
# Try to avoid address already in use problem when program closes and restarts
# see http://stackoverflow.com/questions/6380057/python-binding-socket-address-already-in-use
debug_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
main_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
main_server.setblocking(0)
# Try to avoid address already in use problem when program closes and restarts
# see http://stackoverflow.com/questions/6380057/python-binding-socket-address-already-in-use
main_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Bind the socket to the port
bindaddress = '0.0.0.0'
debugport = 12001
port = 12000
try:
    bindaddress = args.bindaddress or config['adcpiv2']['bindaddress']
    #logging.error( "bindaddress using: {}".format(bindaddress))
except:
    logging.error( "failed bindaddress, using: {}".format(bindaddress))
 
try:
    debugport = args.debugport or int(config['adcpiv2']['debugport'])
    #logging.error( "debugport using: {}".format(debugport))
except:
    logging.error( "failed debugport, using: {}".format(debugport))

try:
    port = args.port or int(config['adcpiv2']['port'])
    #logging.error( "port using: {}".format(port))
except:
    logging.error( "failed port, using: {}".format(port))

server_debug_address = (bindaddress , debugport )
logging.info('starting up debug server on {} port {}'.format(*server_debug_address))
try:
    debug_server.bind(server_debug_address)
except socket.error:
    df.close()
    rt.stop()
    logging.error('Failed to bind to debug port {}:{} - Quitting'.format(*server_debug_address))
    sys.exit(1)

# Bind the socket to the port, grab port def from options, config file or defaults (in that order)

server_main_address = (bindaddress , port) 
#server_main_address = (args.bindaddress, args.port)
logging.info('starting up main server on {} port {}'.format(*server_main_address))
try:
    main_server.bind(server_main_address)
except socket.error:
    df.close()
    rt.stop()
    debug_server.close()
    logging.error('Failed to bind to main port {}:{} - Quitting'.format(*server_main_address))
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

# Flag to know if we've emitted the first averaged readng we get or not
# This is so that we always send a value to db and datafile as soon as we can after startup
doneFirstEmit = False

logging.info('Starting main loop')

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
        if len(rawReadings) >= nsamples:
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

        # Write out the first averaged data point we get to the db
        if (len(rawReadings) == nsamples and not doneFirstEmit):
            # Flag that we've sent the first evraged sample now
            doneFirstEmit = True
            # Generate the string so we can use to send to TCP ports if/when needed
            last_df_write = "{},{:.4f},{}\n".format(str(datetime.datetime.now()),average,args.adcchannel)
            # Write out to datafile
            logging.debug("Writing first averaged sample since startup: {}".format(last_df_write))
            emit(rawReadings,last_df_write)
            df.write(last_df_write)

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
                message_queues[connection] = queue.Queue()

                # Add this connection queue to the list of outputs to service
                outputs.append(connection)
            else:
                if s is main_server:
                    # A "readable" main_server socket is ready to accept a connection
                    connection, client_address = s.accept()
                    logging.debug('main server new connection from {}:{}'.format(*client_address))
                    connection.setblocking(0)

                    # Give the connection a queue for data we want to send
                    message_queues[connection] = queue.Queue()
                    # Immediately put last record into send buffor for sending to this connection
                    con = sqlite3.connect(args.dbname,30)
                    cur = con.cursor()
                    try:
                        cur.execute('select * from adcpiv2 where rowid = (select seq from sqlite_sequence where name="adcpiv2");')
                    except sqlite3.Error as e:
                        logging.error("main_server: Failed to read last row from database: {}\n".format(e.args[0]))
                    try:
                        last_df_write = ",".join(str(i) for i in cur.fetchone())
                    except:
                        last_df_write = "No data"
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
            except queue.Empty:
                pn = s.getpeername()
                logging.info('output queue for {}:{} is empty'.format(*pn))
                # No messages waiting so stop checking for writability.
                #print >>sys.stderr, 'output queue for', s.getpeername(), 'is empty'
                #outputs.remove(s)
            else:
                try:
                    pn = s.getpeername()
                    s.send(bytes(next_msg,'UTF-8'))
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
    logging.warning('no more input sockets to process (this should never happen) - exiting.')
except:
    logging.error("Unexpected error: {}".format(sys.exc_info()[0]))
    #raise
# We got a ^C - close up shop cleanly
finally:
    logging.info('Cleaning up and Exiting - Bye')
    rt.stop()
    for s in inputs:
        s.close()
    for s in outputs:
        s.close()
    for s in main_outputs:
        s.close()
    df.close()


