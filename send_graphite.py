#!/usr/bin/python
"""Copyright 2008 Orbitz WorldWide

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License."""

import sys
import time
import os
import platform 
import subprocess
from socket import socket

CARBON_SERVER = 'tilaph'
CARBON_PORT = 2003

delay = 60 
if len(sys.argv) > 1:
  delay = int( sys.argv[1] )

def get_data():
  # For more details, "man proc" and "man uptime"  
  command = "nc localhost 12000"
# Sample output from nc command
# 202838,2015-05-31 18:32:26.127777,8,21137.9263,Litres,Tank level,4.9336,0.3819,5.0,4644.0066
  process = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True)
  result = os.waitpid(process.pid, 0)
  if result[1]:
    print "command failed: %s with error %d" % command,result[0]
    sys.exit(1)
  output = process.stdout.read().strip().split(',')
  #print "Output: %s" % output
  return output

sock = socket()
try:
  sock.connect( (CARBON_SERVER,CARBON_PORT) )
except:
  print "Couldn't connect to %(server)s on port %(port)d, is carbon-agent.py running?" % { 'server':CARBON_SERVER, 'port':CARBON_PORT }
  sys.exit(1)

while True:
  now = int( time.time() )
  lines = []
  #We're gonna report all three loadavg values
  tankdata = get_data()
  lines.append("adcpiv2.watertank.8.litres %s %d" % (tankdata[3],now))
  lines.append("adcpiv2.watertank.8.volts %s %d" % (tankdata[6],now))
  lines.append("adcpiv2.watertank.8.offset %s %d" % (tankdata[7],now))
  lines.append("adcpiv2.watertank.8.span %s %d" % (tankdata[8],now))
  lines.append("adcpiv2.watertank.8.scale %s %d" % (tankdata[9],now))
  message = '\n'.join(lines) + '\n' #all lines must end in a newline
  print "sending message\n"
  print '-' * 80
  print message
  print
  sock.sendall(message)
  time.sleep(delay)
