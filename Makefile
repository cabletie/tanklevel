install: adcpiv2.py Makefile adcpiv2.conf adcpiv2-monit.sh adcpiv2-init.sh
	install --compare --verbose -m775 -o root -g root --directory /etc/local
	install --compare --verbose -m555 -o root -g root adcpiv2.py /usr/local/bin/adcpiv2
	install --compare --verbose -m644 -o root -g root adcpiv2.conf /etc/local/
	install --compare --verbose -m644 -o root -g root adcpiv2-monit.sh /etc/monit/conf.d/adcpiv2.sh
	rm /etc/monit/monitrc.d/adcpiv2.sh && ln -s ../conf.d/adcpiv2.sh /etc/monit/monitrc.d/adcpiv2.sh
	install --compare --verbose -m755 -o root -g root adcpiv2-init.sh /etc/init.d/adcpiv2
	install --compare --verbose -m775 -o root -g root --directory /var/local/adcpiv2
	install --compare --verbose -m775 -o root -g root --directory /var/log/adcpiv2
	cp -r ../ABElectronics_Python_Libraries /usr/local/lib/
	update-rc.d adcpiv2 defaults

.PHONY: install
