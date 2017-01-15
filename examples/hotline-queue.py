#!/usr/bin/env python
#
# pyhotline example queue script
#

from pyhotline import Queue

config = '/etc/pyhotline.conf'
group  = 'myhotline'

queue_obj = Queue(config, group)
queue_obj.run()
