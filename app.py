#!/usr/bin/env python3

import asyncio
import argparse, sys, traceback, os
import re

from lxml import html
import requests

from aiohttp import web

HOST = None
PORT = 15834
ENDPOINT = "http://10.0.0.1"
USERNAME = "admin"
PASSWORD = "password"

debug = False

last_session = None

def login():
  session = requests.Session()
  post = session.post(ENDPOINT + "/check.jst", data={'username': USERNAME, 'password': PASSWORD, 'locale': "false"})
  global last_session
  last_session = session
  return True

def get_status(session):
  status_page = session.get(ENDPOINT + "/network_setup.jst")
  status_page_html = html.fromstring(bytes(status_page.text, encoding='utf8'))
  return status_page_html

async def parse_status(status):
  data = dict()
  data = await parse_table_extra(data, status, "XFINITY Network", "1")
  data = await parse_table(data, status, "Downstream Channels", "1")
  data = await parse_table(data, status, "Upstream Channels", "2")
  data = await parse_table(data, status, "CM Error Codewords", "3")
  return data

async def parse_table_extra(data, status, table_name, table_id):
  data[table_name] = dict()
  valid_data = False
  for i, row in enumerate(status.xpath('//*[@id="content"]/div[contains(@class, "module forms")][' + table_id + ']/div')):
    values = row.xpath('span')
    data[table_name][values[0].text_content().strip()[:-1]] = values[1].text_content().strip()
    valid_data = True
  if not valid_data:
    raise RuntimeError("Unable to fetch data")
  return data

async def parse_table(data, status, table_name, table_id):
  data[table_name] = []
  columns = []
  valid_data = False
  for i, row in enumerate(status.xpath('//*[@id="content"]/div[@class="module"][' + table_id + ']/table/tbody/tr')):
    for j, col in enumerate(row):
      if j > 0:
        column_data = None
        if i > 0:
          column_data = data[table_name][j - 1]
        else:
          column_data = dict()
          data[table_name].append(column_data)
        column_data[columns[i]] = col.text_content().strip()
        valid_data = True
      else:
        columns.append(col.text_content().strip())
  if not valid_data:
    raise RuntimeError("Unable to fetch data")
  i = 0
  while i < len(data[table_name]):
    entry_empty = False
    for col in columns:
      if not data[table_name][i][col]:
        entry_empty = True
        break
    if entry_empty:
      data[table_name].pop(i)
    else:
      i = i + 1
  return data

async def fetch_data():
  try:
    if last_session is None:
      login()
    status = get_status(last_session)
    return await parse_status(status)
  except:
    if debug:
      print("Unable to fetch new data - trying again")
      print(traceback.format_exc())
      sys.stdout.flush()
  try:
    login()
    status = get_status(last_session)
    return await parse_status(status)
  except:
    if debug:
      print("Unable to fetch new data")
      print(traceback.format_exc())
      sys.stdout.flush()
  return None

def setup_web():
  app = web.Application()
  app.add_routes([web.get("/", landing_handler)])
  app.add_routes([web.get("/metrics", web_handler)])
  return app

async def landing_handler(request):
  if debug:
    print("Received landing GET from " + request.remote)
    sys.stdout.flush()
  return web.Response(content_type='text/html',body='<!DOCTYPE html><title>XFINITY Modem Exporter</title><h1>XFINITY Modem Exporter</h1><p><a href="/metrics">Metrics</a></p>')

def parse_frequency(text):
  if "mhz" in text.lower():
    return str(int(re.sub("[^0-9.\-]", "", text)) * 1000000)
  else:
    return re.sub("[^0-9.\-]", "", text)

async def web_handler(request):
  if debug:
    print("Received GET from " + request.remote)
    sys.stdout.flush()
  data_string = ""
  data = await fetch_data()
  if data is None:
    raise web.HTTPBadGateway()
  
  # Status
  data_string += "# HELP connectivity_state_status Modem connectivity status, 1 if connected" + "\n"
  data_string += "# TYPE connectivity_state_status untyped" + "\n"
  data_string += "connectivity_state_status " + ("1" if data["XFINITY Network"]["Internet"].lower() == "active" else "0") + "\n"
  
  # Downstream Channels
  data_string += "\n"
  data_string += "# HELP downstream_bonded_channel_frequency Channel frequency in Hz" + "\n"
  data_string += "# TYPE downstream_bonded_channel_frequency gauge" + "\n"
  for i, entry in enumerate(data["Downstream Channels"]):
    if entry["Modulation"] != "OFDM":
      data_string += "downstream_bonded_channel_frequency{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + parse_frequency(entry["Frequency"]) + "\n"
  data_string += "# HELP downstream_bonded_channel_power Channel power in dBmV" + "\n"
  data_string += "# TYPE downstream_bonded_channel_power gauge" + "\n"
  for i, entry in enumerate(data["Downstream Channels"]):
    if entry["Modulation"] != "OFDM":
      data_string += "downstream_bonded_channel_power{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + re.sub("[^0-9.\-]", "", entry["Power Level"]) + "\n"
  data_string += "# HELP downstream_bonded_channel_snr Channel SNR/MER in dB" + "\n"
  data_string += "# TYPE downstream_bonded_channel_snr gauge" + "\n"
  for i, entry in enumerate(data["Downstream Channels"]):
    if entry["Modulation"] != "OFDM":
      data_string += "downstream_bonded_channel_snr{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + re.sub("[^0-9.\-]", "", entry["SNR"]) + "\n"
  data_string += "# HELP downstream_bonded_channel_unerrored_codewords Total codewords received without error" + "\n"
  data_string += "# TYPE downstream_bonded_channel_unerrored_codewords counter" + "\n"
  for i, entry in enumerate(data["Downstream Channels"]):
    if entry["Modulation"] != "OFDM":
      data_string += "downstream_bonded_channel_unerrored_codewords{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + re.sub("[^0-9.\-]", "", data["CM Error Codewords"][i]["Unerrored Codewords"]) + "\n"
  data_string += "# HELP downstream_bonded_channel_correctable_codewords Total codewords received requiring correction" + "\n"
  data_string += "# TYPE downstream_bonded_channel_correctable_codewords counter" + "\n"
  for i, entry in enumerate(data["Downstream Channels"]):
    if entry["Modulation"] != "OFDM":
      data_string += "downstream_bonded_channel_correctable_codewords{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + re.sub("[^0-9.\-]", "", data["CM Error Codewords"][i]["Correctable Codewords"]) + "\n"
  data_string += "# HELP downstream_bonded_channel_uncorrectable_codewords Total codewords received uncorrectable" + "\n"
  data_string += "# TYPE downstream_bonded_channel_uncorrectable_codewords counter" + "\n"
  for i, entry in enumerate(data["Downstream Channels"]):
    if entry["Modulation"] != "OFDM":
      data_string += "downstream_bonded_channel_uncorrectable_codewords{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + re.sub("[^0-9.\-]", "", data["CM Error Codewords"][i]["Uncorrectable Codewords"]) + "\n"
  
  # Upstream Channels
  data_string += "\n"
  data_string += "# HELP upstream_bonded_channel_frequency Channel frequency in Hz" + "\n"
  data_string += "# TYPE upstream_bonded_channel_frequency gauge" + "\n"
  for i, entry in enumerate(data["Upstream Channels"]):
    if entry["Channel Type"] != "OFDMA":
      data_string += "upstream_bonded_channel_frequency{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\",channel_type=\"" + entry["Channel Type"] + "\"} " + parse_frequency(entry["Frequency"]) + "\n"
  data_string += "# HELP upstream_bonded_channel_power Channel power in dBmV" + "\n"
  data_string += "# TYPE upstream_bonded_channel_power gauge" + "\n"
  for i, entry in enumerate(data["Upstream Channels"]):
    if entry["Channel Type"] != "OFDMA":
      data_string += "upstream_bonded_channel_power{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\",channel_type=\"" + entry["Channel Type"] + "\"} " + re.sub("[^0-9.\-]", "", entry["Power Level"]) + "\n"
  data_string += "# HELP upstream_bonded_channel_symbol_rate Symbol rate in KSym/s" + "\n"
  data_string += "# TYPE upstream_bonded_channel_symbol_rate gauge" + "\n"
  for i, entry in enumerate(data["Upstream Channels"]):
    if entry["Channel Type"] != "OFDMA":
      data_string += "upstream_bonded_channel_symbol_rate{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\",channel_type=\"" + entry["Channel Type"] + "\"} " + re.sub("[^0-9.\-]", "", entry["Symbol Rate"]) + "\n"
  
  # Downstream OFDM Channels
  data_string += "\n"
  data_string += "# HELP downstream_ofdm_channel_frequency Channel frequency in Hz" + "\n"
  data_string += "# TYPE downstream_ofdm_channel_frequency gauge" + "\n"
  for i, entry in enumerate(data["Downstream Channels"]):
    if entry["Modulation"] == "OFDM":
      data_string += "downstream_ofdm_channel_frequency{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + parse_frequency(entry["Frequency"]) + "\n"
  data_string += "# HELP downstream_ofdm_channel_power Channel power in dBmV" + "\n"
  data_string += "# TYPE downstream_ofdm_channel_power gauge" + "\n"
  for i, entry in enumerate(data["Downstream Channels"]):
    if entry["Modulation"] == "OFDM":
      data_string += "downstream_ofdm_channel_power{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + re.sub("[^0-9.\-]", "", entry["Power Level"]) + "\n"
  data_string += "# HELP downstream_ofdm_channel_snr Channel SNR/MER in dB" + "\n"
  data_string += "# TYPE downstream_ofdm_channel_snr gauge" + "\n"
  for i, entry in enumerate(data["Downstream Channels"]):
    if entry["Modulation"] == "OFDM":
      data_string += "downstream_ofdm_channel_snr{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + re.sub("[^0-9.\-]", "", entry["SNR"]) + "\n"
  data_string += "# HELP downstream_ofdm_channel_unerrored_codewords Total codewords received without error" + "\n"
  data_string += "# TYPE downstream_ofdm_channel_unerrored_codewords counter" + "\n"
  for i, entry in enumerate(data["Downstream Channels"]):
    if entry["Modulation"] == "OFDM":
      data_string += "downstream_ofdm_channel_unerrored_codewords{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + re.sub("[^0-9.\-]", "", data["CM Error Codewords"][i]["Unerrored Codewords"]) + "\n"
  data_string += "# HELP downstream_ofdm_channel_correctable_codewords Total codewords received requiring correction" + "\n"
  data_string += "# TYPE downstream_ofdm_channel_correctable_codewords counter" + "\n"
  for i, entry in enumerate(data["Downstream Channels"]):
    if entry["Modulation"] == "OFDM":
      data_string += "downstream_ofdm_channel_correctable_codewords{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + re.sub("[^0-9.\-]", "", data["CM Error Codewords"][i]["Correctable Codewords"]) + "\n"
  data_string += "# HELP downstream_ofdm_channel_uncorrectable_codewords Total codewords received uncorrectable" + "\n"
  data_string += "# TYPE downstream_ofdm_channel_uncorrectable_codewords counter" + "\n"
  for i, entry in enumerate(data["Downstream Channels"]):
    if entry["Modulation"] == "OFDM":
      data_string += "downstream_ofdm_channel_uncorrectable_codewords{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\"} " + re.sub("[^0-9.\-]", "", data["CM Error Codewords"][i]["Uncorrectable Codewords"]) + "\n"
  
  # Upstream OFDMA Channels
  data_string += "\n"
  data_string += "# HELP upstream_ofdma_channel_frequency Channel frequency in Hz" + "\n"
  data_string += "# TYPE upstream_ofdma_channel_frequency gauge" + "\n"
  for i, entry in enumerate(data["Upstream Channels"]):
    if entry["Channel Type"] == "OFDMA":
      data_string += "upstream_ofdma_channel_frequency{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\",channel_type=\"" + entry["Channel Type"] + "\"} " + parse_frequency(entry["Frequency"]) + "\n"
  data_string += "# HELP upstream_ofdma_channel_power Channel power in dBmV" + "\n"
  data_string += "# TYPE upstream_ofdma_channel_power gauge" + "\n"
  for i, entry in enumerate(data["Upstream Channels"]):
    if entry["Channel Type"] == "OFDMA":
      data_string += "upstream_ofdma_channel_power{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\",channel_type=\"" + entry["Channel Type"] + "\"} " + re.sub("[^0-9.\-]", "", entry["Power Level"]) + "\n"
  data_string += "# HELP upstream_ofdma_channel_symbol_rate Symbol rate in KSym/s" + "\n"
  data_string += "# TYPE upstream_ofdma_channel_symbol_rate gauge" + "\n"
  for i, entry in enumerate(data["Upstream Channels"]):
    if entry["Channel Type"] == "OFDMA":
      data_string += "upstream_ofdma_channel_symbol_rate{number=\"" + str(i) + "\",channel_id=\"" + entry["Channel ID"] + "\",lock_status=\"" + ("0" if entry["Lock Status"].lower() != "locked" else "1") + "\",modulation=\"" + entry["Modulation"] + "\",channel_type=\"" + entry["Channel Type"] + "\"} " + re.sub("[^0-9.\-]", "", entry["Symbol Rate"]) + "\n"
  
  return web.Response(text=data_string)

async def main():
  global debug, USERNAME, PASSWORD, ENDPOINT, HOST, PORT
  parser = argparse.ArgumentParser()
  parser.add_argument('-d', '--debug', action='store_true')
  parser.add_argument('-u', '--user', dest='username', default=USERNAME)
  parser.add_argument('-p', '--pass', dest='password', default=PASSWORD)
  parser.add_argument('--endpoint', default=ENDPOINT)
  parser.add_argument('--host', default=HOST)
  parser.add_argument('--port', default=PORT)
  args = parser.parse_args()
  debug = args.debug
  try:
    USERNAME = os.environ['MODEM_USERNAME']
  except KeyError:
    USERNAME = args.username
  try:
    PASSWORD = os.environ['MODEM_PASSWORD']
  except KeyError:
    PASSWORD = args.password
  try:
    ENDPOINT = os.environ['MODEM_ENDPOINT']
  except KeyError:
    ENDPOINT = args.endpoint
  try:
    HOST = os.environ['SERVER_HOST']
  except KeyError:
    HOST = args.host
  if HOST == "None":
    HOST = None
  try:
    PORT = os.environ['SERVER_PORT']
  except KeyError:
    PORT = args.port
  if debug:
    print("Debug output enabled")
    sys.stdout.flush()
  runner = web.AppRunner(setup_web())
  if debug:
    print("Setting up web app")
    sys.stdout.flush()
  await runner.setup()
  site = web.TCPSite(runner, HOST, PORT)
  if debug:
    print("Starting web app at " + str(HOST) + ":" + str(PORT))
    sys.stdout.flush()
  await site.start()
  await asyncio.Event().wait()

if __name__ == '__main__':
  asyncio.run(main())
