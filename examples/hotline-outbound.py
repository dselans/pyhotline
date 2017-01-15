#!/usr/bin/env python
#
# pyhotline example outbound script
#

from pyhotline import Outbound

config = '/etc/pyhotline.conf'
group  = 'myhotline'

outbound_obj = Outbound(config, group)
outbound_obj.run()

