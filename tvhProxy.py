#!/usr/bin/env python
from gevent import monkey
monkey.patch_all()

from dotenv import load_dotenv
from ssdp import SSDPServer
from flask import Flask, Response, request, jsonify, abort, render_template
from gevent.pywsgi import WSGIServer
import xml.etree.ElementTree as ElementTree
from datetime import timedelta, datetime, time
import logging
import socket
import threading
import requests
from requests.auth import HTTPDigestAuth
import os
import time
import sched

logging.basicConfig(level=logging.DEBUG)
load_dotenv(verbose=True)

app = Flask(__name__)
scheduler = sched.scheduler()

log_format = "[%(asctime)s: %(levelname)s/%(process)s:%(thread)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s"
logger = logging.getLogger()
logger.propagate = True
logger.setLevel(10)

host_name = socket.gethostname()
host_ip = socket.gethostbyname(host_name)

# URL format: <protocol>://<username>:<password>@<hostname>:<port>, example: https://test:1234@localhost:9981
config = {
    'deviceID': os.environ.get('DEVICE_ID') or '12345678',
    'bindAddr': os.environ.get('TVH_BINDADDR') or '',
    'tvhURL': os.environ.get('TVH_URL') or 'http://localhost:9981',
    'tvhUser': os.environ.get('TVH_USER') or 'test',
    'tvhPassword': os.environ.get('TVH_PASSWORD') or 'test',

    # only used if set (in case of forward-proxy), otherwise assembled from host + port bel
    'tvhProxyURL': os.environ.get('TVH_PROXY_URL'),
    'tvhProxyHost': os.environ.get('TVH_PROXY_HOST') or host_ip,
    'tvhProxyPort': os.environ.get('TVH_PROXY_PORT') or 5004,
    # number of tuners in tvh
    'tunerCount': os.environ.get('TVH_TUNER_COUNT') or 6,
    'tvhWeight': os.environ.get('TVH_WEIGHT') or 300,  # subscription priority
    # usually you don't need to edit this
    'chunkSize': os.environ.get('TVH_CHUNK_SIZE') or 1024*1024,
    # specifiy a stream profile that you want to use for adhoc transcoding in tvh, e.g. mp4
    'streamProfile': os.environ.get('TVH_PROFILE') or 'pass'
}

discoverData = {
    'FriendlyName': 'tvhProxy',
    'Manufacturer': 'Silicondust',
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
        'ScanPossible': 0,
        'Source': "Cable",
        'SourceList': ['Cable']
    })


@app.route('/lineup.json')
def lineup():
    lineup = []

    for c in _get_channels():
        if c['enabled']:
            url = '%s/stream/channel/%s?profile=%s&weight=%s' % (
                config['tvhURL'], c['uuid'], config['streamProfile'], int(config['tvhWeight']))

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
    return render_template('device.xml', data=discoverData), {'Content-Type': 'application/xml'}


@app.route('/epg.xml')
def epg():
    return _get_xmltv(), {'Content-Type': 'application/xml'}


def _get_channels():
    url = '%s/api/channel/grid?start=0&limit=999999' % config['tvhURL']
    logger.info('downloading channels from %s', url)
    
    try:
        r = requests.get(url, auth=HTTPDigestAuth(config['tvhUser'], config['tvhPassword']))
        r.raise_for_status()
    except requests.exceptions.Timeout:
        # Maybe set up for a retry, or continue in a retry loop
        logger.info('Timeout received from %s', url)
    except requests.exceptions.TooManyRedirects:
        # Tell the user their URL was bad and try a different one
        logger.info('Too many redirects received from %s', url)
    except requests.exceptions.HTTPError as e:
        raise SystemExit(e)
    except requests.exceptions.RequestException as e:
        # catastrophic error. bail.
        raise SystemExit(e)

    return r.json()['entries']

    #except Exception as e:
    #    logger.error('An error occured: %s' + repr(e))


def _get_xmltv():
    url = '%s/xmltv/channels' % config['tvhURL']
    logger.info('downloading xmltv from %s', url)
    try:
        r = requests.get(url, auth=HTTPDigestAuth(config['tvhUser'], config['tvhPassword']))
        r.raise_for_status()
        tree = ElementTree.ElementTree(
            ElementTree.fromstring(requests.get(url, auth=HTTPDigestAuth(config['tvhUser'], config['tvhPassword'])).content))
        root = tree.getroot()
        channelNumberMapping = {}
        channelsInEPG = {}
        for child in root:
            if child.tag == 'channel':
                channelId = child.attrib['id']
                channelNo = child[1].text
                channelNumberMapping[channelId] = channelNo
                if channelNo in channelsInEPG:
                    logger.error("duplicate channelNo: %s", channelNo)
                channelsInEPG[channelNo] = False
                child.remove(child[1])
                # FIXME: properly rewrite with TVH_URL or even proxy
                child[1].attrib['src'] = child[1].attrib['src']+".png"
                child.attrib['id'] = channelNo
            if child.tag == 'programme':
                child.attrib['channel'] = channelNumberMapping[child.attrib['channel']]
                channelsInEPG[child.attrib['channel']] = True
        for key in sorted(channelsInEPG):
            if channelsInEPG[key]:
                logger.debug("Programmes found for channel %s", key)
            else:
                channelName = root.find(
                    'channel[@id="'+key+'"]/display-name').text
                logger.error("No programme for channel %s: %s",
                             key, channelName)

                # create 2h programmes for 72 hours
                yesterday_midnight = datetime.combine(
                    datetime.today(), time.min) - timedelta(days=1)
                date_format = '%Y%m%d%H%M%S'

                for x in range(0, 36):
                    dummyProgramme = ElementTree.SubElement(root, 'programme')
                    dummyProgramme.attrib['channel'] = str(key)
                    dummyProgramme.attrib['start'] = (
                        yesterday_midnight + timedelta(hours=x*2)).strftime(date_format)
                    dummyProgramme.attrib['stop'] = (
                        yesterday_midnight + timedelta(hours=(x*2)+2)).strftime(date_format)
                    dummyTitle = ElementTree.SubElement(
                        dummyProgramme, 'title')
                    dummyTitle.attrib['lang'] = 'eng'
                    dummyTitle.text = channelName
                    dummyDesc = ElementTree.SubElement(dummyProgramme, 'desc')
                    dummyDesc.attrib['lang'] = 'eng'
                    dummyDesc.text = "No programming information"

        logger.info("returning epg")
        return ElementTree.tostring(root)
    except requests.exceptions.Timeout:
        # Maybe set up for a retry, or continue in a retry loop
        logger.info('Timeout received from %s', url)
    except requests.exceptions.TooManyRedirects:
        # Tell the user their URL was bad and try a different one
        logger.info('Too many redirects received from %s', url)
    except requests.exceptions.HTTPError as e:
        raise SystemExit(e)
    except requests.exceptions.RequestException as e:
        # catastrophic error. bail.
        raise SystemExit(e)
    except requests.exceptions.RequestException as e:  # This is the correct syntax
        logger.error('An error occured: %s' + repr(e))


def _start_ssdp():
    ssdp = SSDPServer()
    thread_ssdp = threading.Thread(target=ssdp.run, args=())
    thread_ssdp.daemon = True  # Daemonize thread
    thread_ssdp.start()
    ssdp.register('local',
                  'uuid:{}::upnp:rootdevice'.format(discoverData['DeviceID']),
                  'upnp:rootdevice',
                  'http://{}:{}/device.xml'.format(
                      config['tvhProxyHost'], config['tvhProxyPort']),
                  'SSDP Server for tvhProxy')


if __name__ == '__main__':
    http = WSGIServer((config['bindAddr'], config['tvhProxyPort']),
                      app.wsgi_app, log=logger, error_log=logger)
    logger.info('Starting server on host %s port %d.',config['bindAddr'], config['tvhProxyPort'])
    #_start_ssdp()
    http.serve_forever()
