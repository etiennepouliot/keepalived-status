# keepalived-status

One of the annoying think with keepalived it's there is no easy way to tell wich instance or ip is currently on this server.

Keepalived-status.py try to solve that.

Mostly based on  https://github.com/etsxxx/keepalived-tools

Ex :
```
keepalived-status.py
Config OK
Instance I_haproxy1:
    10.10.150.20 is on this host (Expected)
    10.10.150.21 is on this host (Expected)
Instance I_haproxy2:
    10.10.150.30 is on this host (Expected) 
Instance I_haproxy3:
    10.10.150.10 is on this host (Expected)
  
    
keepalived-status.py  --help
usage: keepalived-status [-h] [--file CONF_PATH] [--no-config-test]
                         [--no-status-test] [--verbose]
                         [--priority_master PRIORITY_MASTER]

Check configuration and status of keepalived

optional arguments:
  -h, --help            show this help message and exit
  --file CONF_PATH, -f CONF_PATH
                        set keepalived config file path. (default
                        /etc/keepalived/keepalived.conf
  --no-config-test, -c  Disable configuration test
  --no-status-test, -s  Disable status test
  --verbose, -v         verbose
  --priority_master PRIORITY_MASTER, -p PRIORITY_MASTER
                        value at wich ips should currently be master
```
