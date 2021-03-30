import http.client
import logging
import json
import datetime
import pytz

def PrettyStr(obj):
	return json.dumps(obj, sort_keys=True, indent=4)

def PrettyPrint(obj):
	print(PrettyStr(obj))

def tryToParseJson(res, field):
	data = res.read()
	dataStr = data.decode("utf-8")
	try:
		return json.loads(dataStr)[field]
	except:
		logging.error("Invalid JSON: %s" % js)
		return []

def GetAvailableLocations(stateAbbv):
	assert (len(stateAbbv)==2) # must be OH/MA/etc
	stateAbbv = stateAbbv.lower()

	payload = ''
	headers = {
	  'referer': 'https://www.cvs.com/immunizations/covid-19-vaccine',
	  'Cookie': '_abck=656A0664A5B9D332C43B7CE79052B9E4~-1~YAAQpCckF7z+Y3Z4AQAAkBA8fwXvm9GrA0kW5pnI67VQ7c8Cr4ZtjkcYvzos64aMBDmoTDIvIT0SU7JoOdI1u+Abhaw+iHDrgSav5ScFHzpkV243Qtzc31TctoVbNnG46xhiNjIvP+V7NvmghvBA0mxs9nWLC2CI8VVFzwpPGv90wDx0+gHagcIvd7Fq1/PjDNcwfjVEwt0nxIOtEizY+6j6DpoWY42AmJa7YL5tN7xcfCJi5K30w/lRcvN2tge7OWPxoF5N/uDaOUODhZktvTTHUqf++Yy2hr/jIuEzOLuJIOZh0j5ZmHLRSZhzRKjtWwVbVFPey1jOkTDkOOR9O0OADo2plL+jEpCwOQwUlU0d8SBKTBIHnc4raXyxt4Io8EZZPm16+13sIg3LGMKK1L5t7HUtHg==~-1~-1~-1; affinity="500cd8f8299e60ae"; pe=p1'
	}

	website = "www.cvs.com"
	relativePath = "/immunizations/covid-19-vaccine.vaccine-status.%s.json" % stateAbbv
	logging.debug("Connecting to: %s%s" % (website, website))

	conn = http.client.HTTPSConnection(website)
	conn.request("GET", relativePath, payload, headers)

	res = conn.getresponse()
	locJson = tryToParseJson(res, "responsePayloadData")
	if not locJson:
		return []

	data = locJson["data"][stateAbbv.upper()]
	logging.debug("Data: %s" % PrettyStr(data))
	available = list(filter(lambda listing: "Booked" not in listing["status"], data))
	logging.info("Available: %s" % PrettyStr(available))
	return available

## Get vaccine type info
def getVaccineTimes(storeId, dates):
	conn = http.client.HTTPSConnection("api.cvshealth.com")
	payload = ''
	headers = {
	  'authority': 'api.cvshealth.com',
	  'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36',
	  'x-api-key': 'rFd64We9AwyvAFzIXsoSp8bYuewNohOZ',
	  'content-type': 'application/json',
	  'origin': 'https://www.cvs.com',
	  'referer': 'https://www.cvs.com/',
	  'accept-language': 'en-US,en;q=0.9'
	}

	startDate = dates[0]
	endDate = startDate

	queryStr = "visitStartDate=%s&visitEndDate=%s&clinicId=CVS_%s" % (startDate, endDate, storeId)
	logging.info("Query string: %s" % queryStr)

	conn.request("GET", "/scheduler/v3/clinics/availabletimeslots?%s" % queryStr, payload, headers)
	res = conn.getresponse()
	times = tryToParseJson(res, "details")
	logging.info("Times: %s" % PrettyStr(times))

	# Convert timezones
	def toTime(dt):
		return dt.strftime("%I:%M%p")
	def toDay(dt):
		return dt.strftime("%m-%d-%Y")
	def parseUTC(str):
		return datetime.datetime.strptime(str, "%Y-%m-%dT%H:%M:%S.%fZ")

	def convert_time(t):
		slots = t["timeSlots"]
		date = toDay(parseUTC(slots[0]))

		timezone = pytz.timezone(t["timeZone"])
		cvt = lambda t: toTime(timezone.localize(parseUTC(t)))
		locSlots = list(map(cvt, slots))
		return {"Date" : date, "Times" : locSlots}

	localTimes = list(map(convert_time, times))
	return localTimes

def getStoreInfoFromResponse(vacs):
	stores = [];
	for loc in vacs["locations"]:
		store = {
			"Address" : "%s - %s, %s" % (loc["addressCityDescriptionText"], loc["addressLine"], loc["addressZipCode"]),
			"Dates" : sum(list(map(lambda x: x["availableDates"], loc["imzAdditionalData"])),[]),
			"StoreNumber" : loc["StoreNumber"],
			"Vaccine" : loc["mfrName"]
		}
		store["Times"] = getVaccineTimes(store["StoreNumber"], store["Dates"])
		stores.append(store)
	logging.info("Stores: %s" % PrettyStr(stores))
	return stores

def GetVaccineTypes(city, state):
	addressQuery = "%s, %s" % (city, state);
	conn = http.client.HTTPSConnection("www.cvs.com")
	payload = json.dumps({
	  "requestMetaData": {
	    "appName": "CVS_WEB",
	    "lineOfBusiness": "RETAIL",
	    "channelName": "WEB",
	    "deviceType": "DESKTOP",
	    "deviceToken": "7777",
	    "apiKey": "a2ff75c6-2da7-4299-929d-d670d827ab4a",
	    "source": "ICE_WEB",
	    "securityType": "apiKey",
	    "responseFormat": "JSON",
	    "type": "cn-dep"
	  },
	  "requestPayloadData": {
	    "selectedImmunization": [
	      "CVD"
	    ],
	    "distanceInMiles": 35,
	    "imzData": [
	      {
	        "imzType": "CVD",
	        "ndc": [
	          "59267100002",  # Pfizer
	          "59267100003",  # Pfizer
	          "59676058015",  # J&J
	          "80777027399"   # Moderna
	        ],
	        "allocationType": "1"
	      }
	    ],
	    "searchCriteria": {
	      "addressLine": addressQuery
	    }
	  }
	})
	headers = {
	  'referer': 'https://www.cvs.com/vaccine/intake/store/cvd-store-select/first-dose-select',
	  'authority': 'www.cvs.com',
	  'accept': 'application/json',
	  'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36',
	  'content-type': 'application/json',
	  'origin': 'https://www.cvs.com',
	  'Cookie': '_abck=656A0664A5B9D332C43B7CE79052B9E4~-1~YAAQJZQZuBmEFHd4AQAA/n9tgQU8ojZchwR02HvTHU1IbViFRVWLCwNh0Q5WE4vRW2FYokBIxsfmj4sSs6ZXwtETKehqFJoWGL3od6pohrDamZ3gkvcJgqAz3HYfmofFy6FxjWww/MPZeItVC/Uv2izCXXBo29rXys2UHCAmO0H7mrHgV02Pb55xGAI+z2Tlk5/Sp+KZueiMh4OTSfPSm70o97rfXdOgZuEPO9gzil//cUqWwFwNj6oZDKrmAI15KSzQTeWgkxvC7koI63FrhgmsPYo3uQXOof4yWD6G2olEKLlZbbNSzo1s2XpLh8WT5i7LeqRjjCiew0j8gOShwBwSTIVl3cq5ln07AFx4C5TRLOqQ62jaRa7khc6RXDg4g51k2yUAWvHrr3gBHeZDsD1tLYMH8g==~-1~-1~-1; bm_sz=CB5F4DC5901658B5AD302F4E092162FD~YAAQJZQZuBiEFHd4AQAA/n9tgQsHN3x9Cdh9D2qrCkRsnQKsRETCAQ2tyOa0Q6KuVIZVE+zeMgOiao3AIyme7oLWzBjmGldOYm04bEJYDdfy12EiPequzGAJJv99kvD6tpoib25ojWk5de/NVqZdYbYKLtrNaPX8lhCKslgwSluDcOnUYNMNZOlM4V8X; ADRUM_BT=R:75|i:1684|g:457b95ed-aed6-4163-9788-17fb1e1ad900169901|e:214|n:customer1_d6c575ca-3f03-4481-90a7-5ad65f4a5986; affinity="500cd8f8299e60ae"; pe=p1'
	}
	conn.request("POST", "/Services/ICEAGPV1/immunization/1.0.0/getIMZStores", payload, headers)
	res = conn.getresponse()
	vacs = tryToParseJson(res, "responsePayloadData")
	if not vacs:
		return []

	logging.info(PrettyStr(vacs))

	return getStoreInfoFromResponse(vacs);

def GetVaccineAvailabilityInState(state):
	locs = GetAvailableLocations(state)
	vaccines = list(map(lambda loc: GetVaccineTypes(loc["city"], loc["state"]), locs))
	return vaccines

def GetVaccineAvailabilityInCity(citylist, state):
	locs = list(map(lambda c: {"city": c, "state": state}, citylist))
	vaccines = list(map(lambda loc: GetVaccineTypes(loc["city"], loc["state"]), locs))
	return vaccines

def Test():
	#PrettyPrint(GetVaccineAvailabilityInState("MA"))
	PrettyPrint(GetVaccineAvailabilityInCity(["Boston"], "MA"))


logging.getLogger().setLevel(logging.ERROR)
Test()


# locs = GetAvailableLocations("OH")
# for loc in locs:
# 	state = loc["state"]
# 	city = loc["city"]
# 	GetVaccineTypes(city, state)