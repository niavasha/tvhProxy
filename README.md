tvhProxy
========

A small flask app to proxy requests between Plex Media Server and Tvheadend. This repo adds a few critical improvements and fixes to the archived upstream version at [jkaberg/tvhProxy](https://github.com/jkaberg/tvhProxy):

- [SSDP](https://en.wikipedia.org/wiki/Simple_Service_Discovery_Protocol) Discovery. Fixes the issue of Plex randomly dropping the device.
- [XMLTV EPG](https://support.plex.tv/articles/using-an-xmltv-guide/)  EPG export, including adding dummy programme entries for channels without EPG so you can still use these channels in Plex (see below for Plex configuration URL)
- Configuration of variables via [dotenv](https://pypi.org/project/python-dotenv/) file

#### tvhProxy configuration
1. Check tvhProxy.py for configuration options and set them up them as ```KEY=VALUE``` pairs in a ```.env``` file.
2. Create a virtual enviroment: ```$ python3 -m venv .venv```
3. Activate the virtual enviroment: ```$ . .venv/bin/activate```
4. Install the requirements: ```$ pip install -r requirements.txt```
5. Finally run the app with: ```$ python tvhProxy.py```

#### systemd service configuration
A startup script for Ubuntu can be found in tvhProxy.service (change paths and user in tvhProxy.service to your setup), install with:

    $ sudo cp tvhProxy.service /etc/systemd/system/tvhProxy.service
    $ sudo systemctl daemon-reload
    $ sudo systemctl enable tvhProxy.service
    $ sudo systemctl start tvhProxy.service

#### Plex configuration
Enter the IP of the host running tvhProxy including port 5004, eg.: ```192.168.1.50:5004```, use ```http://192.168.1.50:5004/epg.xml``` for the EPG (see [Using XMLTV for guide data](https://support.plex.tv/articles/using-an-xmltv-guide/) for full instructions).

NickNote: This seems to cause an exception in tvhProxy. Simply using the tvheadend xml guide url also works: `http://user:password@192.168.1.50:9981/xmltv/channels`
