Moodle Downloader (RUB)
========================

This utility downloads documents from the Moodle rooms of Ruhr University
 Bochum.

Currently it is only tested against the rooms of the first semester of Medicine.
Contributions that add support for differently structured course rooms are
 very welcome!

Use
===

Insert your Moodle credentials in config.ini.

Execute the script (./main.py). Files from the same course room are downloaded
 in parallel.

Run the script again to download new files. Files which have already been
 downloaded are not affected.

Dependencies
============

Python 3

For the remaining dependencies, execute:

``pip install -r requirements.txt``

Contributing
============

Pull requests are accepted! Feel especially free improve to "Pythonicness"
 of the code :)

Be sure to NOT accidentially commit your credentials (config.ini).

Roadmap
=======

Just a brain storming:

CLI (using Click)
UI (using PyQt?)
integrity checks (size and modification date of files)
