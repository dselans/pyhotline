#!/usr/bin/env python
#
# Copyright (c) 2013, Daniel Selans (daniel.selans@gmail.com)
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#	 * Redistributions of source code must retain the above copyright
#	   notice, this list of conditions and the following disclaimer.
#	 * Redistributions in binary form must reproduce the above copyright
#	   notice, this list of conditions and the following disclaimer in the
#	   documentation and/or other materials provided with the distribution.
#	 * Neither the name of the owner nor the names of its contributors may be
#      used to endorse or promote products derived from this software without
#      specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL DANIEL SELANS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from distutils.core import setup

import pyhotline

setup(  name = 'pyhotline',
	version = pyhotline.__version__,
	description = 'A python module for creating, managing and automating Asterisk hotlines',
    long_description = ' '.join(['Pyhotline is a python module that enables you to create',
        'automated receptionist style hotlines, that in turn, can be used by',
        'clients/employees to dispatch a trouble issue to scheduled on call contacts.']),
	author = 'Daniel Selans',
	author_email = 'daniel.selans@gmail.com',
	url = 'http://code.google.com/p/pyhotline/',
	license = 'New BSD License',
	platforms = 'Any',
	classifiers = [
		'Development Status :: 5 - Production/Stable',
		'Environment :: Other Environment',
		'Intended Audience :: Developers',
		'Intended Audience :: Telecommunications Industry',
		'License :: OSI Approved :: New BSD License',
		'Operating System :: OS Independent',
		'Topic :: Communications :: Internet Phone',
		'Topic :: Communications :: Telephony',
		'Topic :: Software Development :: Libraries'],
	py_modules = ['pyhotline'])
