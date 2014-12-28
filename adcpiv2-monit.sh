check process adcpiv2
with pidfile /var/run/adcpiv2.pid
#  every 24 cycles
start program = "/etc/init.d/adcpiv2 start"
stop program = "/etc/init.d/adcpiv2 stop"

if failed port 10000 with timeout 20 seconds then restart
