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
	if kind == "state":
		return path + kind + "_" + replacePunct(query["State"]) + ".json"
	return path + kind + "_" + replacePunct(query["State"]) + '_' + replacePunct(query["City"]) + ".json"

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
		if query["Kind"] == "state":
			logging.info("Looking up by state: " + query["State"]);
			return lookup.GetVaccineAvailabilityInState(query["State"])
		logging.info("Looking up by city: %s, %s" % (query["City"], query["State"]));
		return lookup.GetVaccineAvailabilityInCity(query["City"].split(","), query["State"])

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
	city = sanitize(args.get("city", "Boston" if queryKind=="city" else ""));
	forceRefresh = args.get("forceRefresh", 0)

	query = {"Kind" : queryKind, "State":state, "City":city, "ForceRefresh":forceRefresh};
	data = getOrRefresh(query, 5*60) # refresh time 5mins

	def makeTimestamp(seconds):
		dt = datetime.datetime.fromtimestamp(seconds)
		tz = pytz.timezone("America/New_York")
		dt = tz.localize(dt)
		return dt.strftime("%m-%d-%Y %I:%M%p") + " EST"

	scan = {
		"Location" : "%s %s" % (city, state),
		"Data" : data,
		"Timestamp" : makeTimestamp(data["Timestamp"])
	}
	return render_template('base.html', title='Welcome', scan=scan)