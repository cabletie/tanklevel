install: adcpiv2.py Makefile adcpiv2.conf adcpiv2-monit.sh adcpiv2-init.sh
	install --verbose -m775 -o root -g root --directory /etc/local
	install --verbose -m555 -o root -g root adcpiv2.py /usr/local/bin
	install --verbose -m644 -o root -g root adcpiv2.conf /etc/local/
	install --verbose -m644 -o root -g root adcpiv2-monit.sh /etc/monit/conf.d/adcpiv2.sh
	ln -s ../conf.d/adcpiv2.sh /etc/monit/monitrc.d/adcpiv2.sh
	install --verbose -m755 -o root -g root adcpiv2-init.sh /etc/init.d/adcpiv2
	install --verbose -m775 -o root -g root --directory /var/local/adcpiv2
	install --verbose -m775 -o root -g root --directory /var/log/adcpiv2
	cp -r ../ABElectronics_Python_Libraries /usr/local/lib/
