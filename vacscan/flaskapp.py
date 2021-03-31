from flask import render_template
from . import lookup

import os
import logging
import json
import pytz
import datetime

# To avoid a lookup on every request, JSON data will be stored in a file
# with a timestamp, and if the timestamp is older than a timeout value
# the file will be updated
def getFileNameFromQuery(query):
	def replacePunct(str):
		return str.replace(" ", "_").replace(',','').replace('.','')
	logging.info("Query: " + lookup.PrettyStr(query))
	path = "vacscan/data/"
	kind = query["Kind"]
	state = query["State"]
	dose = query["Dose"]
	if kind == "state":
		return path + kind + "_" + replacePunct(state) + "_" + replacePunct(dose) + ".json"
	return path + kind + "_" + replacePunct(state) + '_' + replacePunct('_'.join(query["City"])) + "_" + replacePunct(dose) + ".json"

def getOrRefresh(query, timeout):
	def readJson(file):
		try:
			with open(file, 'r') as jsonFile:
				jsonStr = jsonFile.read()
				data = json.loads(jsonStr)
		except:
			data = {};
		return data;

	def lookupDataFromQuery(query):
		state = query["State"]
		city = query["City"]
		dose = query["Dose"]
		if query["Kind"] == "state":
			logging.info("Looking up by state: %s, %s" % (state, dose));
			return lookup.GetVaccineAvailabilityInState(state, dose)
		logging.info("Looking up by city: %s, %s, %s" % (city, state,dose));
		return lookup.GetVaccineAvailabilityInCity(city, state, dose)

	file = getFileNameFromQuery(query)
	logging.info("Query2File: %s -> %s" % (query, file))
	
	update = True
	if os.path.exists(file):
		# Check data timestamp compared to timeout
		data = readJson(file)
		if data and data["Timestamp"] + timeout > lookup.GetTimestamp():
			update = False


	if update or query["ForceRefresh"]:
		data = lookupDataFromQuery(query)
		with open(file, 'w') as jsonFile:
			jsonFile.write(lookup.PrettyStr(data))

	return data

# Process and display the vac scan page
def VacScanPage(request):
	logging.getLogger().setLevel(logging.DEBUG)

	def parseDebugLevel(args):
		if args.get("debug"):
			logging.getLogger().setLevel(logging.DEBUG)
		else:
			logging.getLogger().setLevel(logging.ERROR)
	def parseQueryKind(args): # no relative path traversals
		if args.get("kind", "state") == "state":
			return "state"
		return "city"
	def sanitize(name): # no relative path traversals
		if '/' in name:
			name = name[name.rfind('/'):]
		return name;

	args = request.args
	parseDebugLevel(args)
	queryKind = parseQueryKind(args);
	state = sanitize(args.get("state", "MA"));
	city = sanitize(args.get("city", "Boston" if queryKind=="city" else "")).split(",");
	dose = sanitize(args.get("dose", "first"))
	forceRefresh = args.get("forceRefresh", 0)

	query = {"Kind" : queryKind, "State":state, "City":city, "Dose":dose, "ForceRefresh":forceRefresh};
	logging.debug("VacScanPage Query: %s" % query)

	if len(city) > 8:
		data = {
    		"Data": [  { "Reason": "Error: Max of 8 city/zips at a time, %s city/zips provided. Remove a few values from search." % len(city), "Success": 0 } ],
    		"Timestamp": 1617209242.740845
		};
	else:
		data = getOrRefresh(query, 2*60) # refresh time 2mins

	def makeTimestamp(seconds):
		dt = datetime.datetime.fromtimestamp(seconds)
		tz = pytz.timezone("America/New_York")
		dt = tz.localize(dt)
		return dt.strftime("%m-%d-%Y %I:%M%p") + " EST"

	scan = {
		"Location" : "%s %s" % (city, state),
		"Data" : data,
		"Timestamp" : makeTimestamp(data["Timestamp"]),
		"Dose" : dose
	}
	logging.info("VacScanPage scan=%s" % scan)
	return render_template('base.html', title='Welcome', scan=scan)