#!/usr/bin/env python3

import requests
import json
import sys
import argparse

p = argparse.ArgumentParser()
p.add_argument("-o", "--output", help="Output file", required=False, default="")

outputfile = p.parse_args().output
myaddressdict = {}

try:
    response4 = requests.get('https://api.ipify.org?format=json')
except Exception as e:
    #print(e, sys.stderr)
    myaddressdict["ipv4"] = {'ip': None}
else:
  myaddressdict["ipv4"] = response4.json()

try:
    response6 = requests.get('https://api6.ipify.org?format=json')
except Exception as e:
    #print(e, sys.stderr)
    altresponse6 = {"ip": None}
    myaddressdict["ipv6"] = altresponse6
else:
  myaddressdict = response6.json()

outputlines = []
if outputfile.endswith(".md"):
    outputlines.append("```json")
jsonstring = json.dumps(myaddressdict, indent=4)
jsonlines = jsonstring.split("\n")
outputlines.extend(jsonlines)
if outputfile.endswith(".md"):
    outputlines.append("```")
if outputfile:
  with open(outputfile, "w") as f:
    f.write("\n".join(outputlines))
else:
  print("\n".join(outputlines))