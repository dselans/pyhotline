#!/usr/bin/env python
#
# pyhotline example inbound script
#

from pyhotline import Inbound

config = '/etc/pyhotline.conf'
group  = 'myhotline'

inbound_obj = Inbound(config, group)
inbound_obj.run()
