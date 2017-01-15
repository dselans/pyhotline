pyhotline
=========

**NOTE**: This project is no longer maintained and is just an import from the now
default code.google.com/*

Last updated: 01/27/2013

Pyhotline is a python module that enables you to create automated receptionist
style hotlines, that in turn, can be used by clients/employees to dispatch a 
trouble issue to scheduled on call contacts.

Project home: http://code.google.com/p/pyhotline/

Requirements
------------
* Python 2.4+
* Python pysqlite2 module - http://trac.edgewall.org/wiki/PySqlite
* Python pyst module - http://sourceforge.net/projects/pyst/
* Python json module (or simplejson) - http://pypi.python.org/pypi/simplejson/
* Asterisk 1.6+
* Cepstral Swift TTS engine - http://www.cepstral.com/ 

Installation
------------
1. Unpack the source tarball
2. Install by running 'python setup.py install'

Documentation
-------------
Check the 'examples' directory (contains config, example scripts).
Check 'README.CONFIG' for an explanation of all config settings.
You may be able to find some additional (and possibly helpful) info in the 
module's docstrings (`pydoc pyhotline`).

Important Notes
---------------
Outbound channel is hard coded to 'Local/'. Generally, this shouldn't be a
problem, as you can still set the outbound context.

When setting up a new SQLite db via the 'create-database.py' script, a dummy
client entry is made - "Test Client", with a PIN set to '1111'.
This entry is added for testing purposes; feel free to remove it once you
are certain that the hotline is working as expected.

Use sqlite3 to add/remove clients from the hotline database.

Quickstart
----------
1.  Copy the 'pyhotline.conf' file from the examples dir to something like
    '/etc/pyhotline.conf'

2.  Edit the config and update all of the defined options.
        * Be sure to read through the README.CONFIG file for an explanation
          of all the settings.
        * The config utilizes JSON syntax - be careful, it is very easy to
          make mistakes.

3.  Create the initial SQLite db by running `./create-database.py db_file`.
    You can find this script in the examples directory.

4.  Copy 'hotline-inbound.py', 'hotline-outbound.py', 'hotline-queue.py' to
    your asterisk AGI bin directory (ie. '/var/lib/asterisk/agi-bin/')

5.  Edit each one of the files and update the 'config' and 'group' vars
    accordingly. 'group' is the name of the hotline that you defined in
    the config.

6.  Make sure to make the scripts executable (`chmod 755 hotline-*.py`)

7.  Test that your config and db are setup properly by executing the
    'hotline-queue.py' script. No output = good. If you see errors - they are
    likely due to problems with your config.

8.  Edit your asterisk extensions config and add either an extension or DID
    which will execute the inbound script via AGI.
    
    // Asterisk config example
    1234 => {
        Answer();
        AGI(hotline-inbound.py);
    }

9.  Create an outbound hotline context in your Asterisk configuration.

    // Asterisk config example
    context myhotline {
        s => {
            Answer();
            AGI(hotline-outbound.py);
        }
    }

10. Reload Asterisk config (asterisk -r; 'ael reload')

11. Test your newly created hotline by dialing the extension (or DID)
    that you defined in Asterisk. You should hear an automated greeting.

12. Once everything is verified to be working, add a new cron job, that is set
    to execute 'hotline-queue.py' every X minutes.

Credits
-------
Module written and maintained by Daniel Selans (daniel.selans@gmail.com).
Thanks to Paul Fleming (paul@shortestpathfirst.net) for assistance with
various Asterisk issues along the way.
