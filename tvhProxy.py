from gevent import monkey; monkey.patch_all()

import sched
import time
import os
import requests
import threading
import socket
import logging
import xml.etree.ElementTree as ElementTree
from gevent.pywsgi import WSGIServer
from flask import Flask, Response, request, jsonify, abort, render_template
from ssdp import SSDPServer
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
load_dotenv(verbose=True)

app = Flask(__name__)
scheduler = sched.scheduler()
logger = logging.getLogger()

host_name = socket.gethostname()
host_ip = socket.gethostbyname(host_name) 

# URL format: <protocol>://<username>:<password>@<hostname>:<port>, example: https://test:1234@localhost:9981
config = {
    'deviceID': os.environ.get('DEVICE_ID') or '12345678',
    'bindAddr': os.environ.get('TVH_BINDADDR') or '',
    'tvhURL': os.environ.get('TVH_URL') or 'http://test:test@localhost:9981',
    'tvhProxyURL': os.environ.get('TVH_PROXY_URL'), # only used if set (in case of forward-proxy), otherwise assembled from host + port bel
    'tvhProxyHost': os.environ.get('TVH_PROXY_HOST') or host_ip,
    'tvhProxyPort': os.environ.get('TVH_PROXY_PORT') or 5004,
    'tunerCount': os.environ.get('TVH_TUNER_COUNT') or 6,  # number of tuners in tvh
    'tvhWeight': os.environ.get('TVH_WEIGHT') or 300,  # subscription priority
    'chunkSize': os.environ.get('TVH_CHUNK_SIZE') or 1024*1024,  # usually you don't need to edit this
    'streamProfile': os.environ.get('TVH_PROFILE') or 'pass'  # specifiy a stream profile that you want to use for adhoc transcoding in tvh, e.g. mp4
}

discoverData = {
    'FriendlyName': 'tvhProxy',
    'Manufacturer' : 'Silicondust',
    'ModelNumber': 'HDTC-2US',
    'FirmwareName': 'hdhomeruntc_atsc',
    'TunerCount': int(config['tunerCount']),
    'FirmwareVersion': '20150826',
    'DeviceID': config['deviceID'], 
    'DeviceAuth': 'test1234',
    'BaseURL': '%s' % (config['tvhProxyURL'] or "http://" + config['tvhProxyHost'] + ":" + str(config['tvhProxyPort'])),
    'LineupURL': '%s/lineup.json' % (config['tvhProxyURL'] or "http://" + config['tvhProxyHost'] + ":" + str(config['tvhProxyPort']))
}

@app.route('/discover.json')
def discover():
    return jsonify(discoverData)


@app.route('/lineup_status.json')
def status():
    return jsonify({
        'ScanInProgress': 0,
        'ScanPossible': 1,
        'Source': "Cable",
        'SourceList': ['Cable']
    })


@app.route('/lineup.json')
def lineup():
    lineup = []

    for c in _get_channels():
        if c['enabled']:
            url = '%s/stream/channel/%s?profile=%s&weight=%s' % (config['tvhURL'], c['uuid'], config['streamProfile'],int(config['tvhWeight']))

            lineup.append({'GuideNumber': str(c['number']),
                           'GuideName': c['name'],
                           'URL': url
                           })

    return jsonify(lineup)


@app.route('/lineup.post', methods=['GET', 'POST'])
def lineup_post():
    return ''

@app.route('/')
@app.route('/device.xml')
def device():
    return render_template('device.xml',data = discoverData),{'Content-Type': 'application/xml'}


def _get_channels():
    url = '%s/api/channel/grid?start=0&limit=999999' % config['tvhURL']

    try:
        r = requests.get(url)
        return r.json()['entries']

    except Exception as e:
        logger.error('An error occured: %s' + repr(e))


def _sync_xmltv():
    url = '%s/xmltv/channels' % config['tvhURL']
    logger.info('downloading xmltv from %s', url)
    r = requests.get(url)
    tree = ElementTree.ElementTree(
        ElementTree.fromstring(requests.get(url).content))
    root = tree.getroot()
    channelNumbers = {}
    for child in root:
        if child.tag == 'channel':
            channelId = child.attrib['id']
            channelNo = child[1].text
            channelNumbers[channelId] = channelNo

            child.remove(child[1])
            child.attrib['id'] = channelNo
        if child.tag == 'programme':
            child.attrib['channel'] = channelNumbers[child.attrib['channel']]
    tree.write("tvhProxy.xml")
    scheduler.enter(60, 1, _sync_xmltv)


def _start_ssdp():
	ssdp = SSDPServer()
	thread_ssdp = threading.Thread(target=ssdp.run, args=())
	thread_ssdp.daemon = True # Daemonize thread
	thread_ssdp.start()
	ssdp.register('local',
				  'uuid:{}::upnp:rootdevice'.format(discoverData['DeviceID']),
				  'upnp:rootdevice',
				  'http://{}:{}/device.xml'.format(config['tvhProxyHost'],config['tvhProxyPort']),
                  'SSDP Server for tvhProxy')


if __name__ == '__main__':
    http = WSGIServer((config['bindAddr'], config['tvhProxyPort']), app.wsgi_app, log=logger, error_log=logger)
    _start_ssdp()
    _sync_xmltv()
    http.serve_forever()
