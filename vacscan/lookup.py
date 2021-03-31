import http.client
import logging
import json
import datetime
import pytz
import time

def PrettyStr(obj):
	return json.dumps(obj, sort_keys=True, indent=4)

def PrettyPrint(obj):
	print(PrettyStr(obj))

def GetTimestamp():
	ct = datetime.datetime.now()
	return ct.timestamp()

def tryToParseJson(res):
	data = res.read()
	dataStr = data.decode("utf-8")
	try:
		logging.debug("Received JSON: %s" % dataStr)
		return {"Success":1, "Data" : json.loads(dataStr) }
	except:
		logging.error("Invalid JSON: %s" % dataStr)
		return {"Success" : 0, "Reason":"Invalid JSON: %s" % dataStr};

def validateAndParse(js, queryStr):
	if js["Success"] and js["Data"].get("responseMetaData"):
		status = js["Data"]["responseMetaData"]["statusCode"]
		if "0000" in status:
			return {"Success":1, "Data" : js["Data"].get("responsePayloadData")};
		if "0001" in status:
			return {"Success" : 0, "Reason": "[%s] Error %s - Error looking up zip code, search by city name." % (queryStr, status), "Response" : PrettyStr(js) };
		if "1010" and "getStoreDetails" in js["Data"]["responseMetaData"]["statusDesc"]:
			return {"Success" : 0, "Reason": "[%s] Error %s - Zip code / city not found in state." % (queryStr, status) };
		return {"Success" : 0, "Reason": "[%s] Error %s - %s" % (queryStr, status, js["Data"]["responseMetaData"]["statusDesc"]),  "Response" : PrettyStr(js) };
	if "Your traffic behavior" in PrettyStr(js):
		return {"Success" : 0, "Reason": "[%s] %s" % (queryStr, "CVS hates us and blocked us for a minute. Wait a minute, and try searching again with less cities."),  "Response" : PrettyStr(js)};

	return {"Success" : 0, "Reason": "[%s] %s" % (queryStr, "Invalid CVS Response"),  "Response" : PrettyStr(js)};

def GetAvailableLocations(stateAbbv):
	logging.info("State: " + stateAbbv);
	assert (len(stateAbbv)==2) # must be OH/MA/etc
	stateAbbv = stateAbbv.lower()

	payload = ''
	headers = {
	  'referer': 'https://www.cvs.com/immunizations/covid-19-vaccine',
	  'Cookie': '_abck=656A0664A5B9D332C43B7CE79052B9E4~-1~YAAQpCckF7z+Y3Z4AQAAkBA8fwXvm9GrA0kW5pnI67VQ7c8Cr4ZtjkcYvzos64aMBDmoTDIvIT0SU7JoOdI1u+Abhaw+iHDrgSav5ScFHzpkV243Qtzc31TctoVbNnG46xhiNjIvP+V7NvmghvBA0mxs9nWLC2CI8VVFzwpPGv90wDx0+gHagcIvd7Fq1/PjDNcwfjVEwt0nxIOtEizY+6j6DpoWY42AmJa7YL5tN7xcfCJi5K30w/lRcvN2tge7OWPxoF5N/uDaOUODhZktvTTHUqf++Yy2hr/jIuEzOLuJIOZh0j5ZmHLRSZhzRKjtWwVbVFPey1jOkTDkOOR9O0OADo2plL+jEpCwOQwUlU0d8SBKTBIHnc4raXyxt4Io8EZZPm16+13sIg3LGMKK1L5t7HUtHg==~-1~-1~-1; affinity="500cd8f8299e60ae"; pe=p1'
	}

	website = "www.cvs.com"
	relativePath = "/immunizations/covid-19-vaccine.vaccine-status.%s.json" % stateAbbv
	logging.debug("Connecting to: %s%s" % (website,relativePath))

	conn = http.client.HTTPSConnection(website)
	conn.request("GET", relativePath, payload, headers)

	res = conn.getresponse()
	locJson = validateAndParse(tryToParseJson(res), stateAbbv)
	if not locJson["Success"]:
		return locJson
	data = locJson["Data"]["data"][stateAbbv.upper()]
	logging.debug("Data: %s" % PrettyStr(data))
	available = list(filter(lambda listing: "Booked" not in listing["status"], data))
	logging.info("Available: %s" % PrettyStr(available))
	return available

## Get vaccine type info
def getVaccineTimes(storeId, dates):
	if storeId == "0":
		return []

	conn = http.client.HTTPSConnection("api.cvshealth.com")
	payload = ''
	headers = {
	  'authority': 'api.cvshealth.com',
	  'pragma': 'no-cache',
	  'cache-control': 'no-cache',
	  'sec-ch-ua': '"Google Chrome";v="89", "Chromium";v="89", ";Not A Brand";v="99"',
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

	logging.debug("GetVaccineTimes with Query: %s" % queryStr)
	conn.request("GET", "/scheduler/v3/clinics/availabletimeslots?%s" % queryStr, payload, headers)
	res = conn.getresponse()

	times = tryToParseJson(res)
	if not times["Success"]:
		return times;

	times = times["Data"]["details"]
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
	logging.debug("getStoreInfoFromResponse vacs_input: %s\n\n" % vacs)
	stores = [];
	logging.debug(vacs)
	for loc in vacs["Data"]["locations"]:
		logging.debug("getStoreInfoFromResponse loc=%s" % (loc))
		zipCode = loc.get("addressZipCode", loc.get("zipCode", "NoZipCode"))
		dates =  loc.get("imzAdditionalData", [{"availableDates":["UnknownDate"]}])
		storeNumber = loc.get("StoreNumber", "0")
		vacName = loc.get("mfrName", "UnknownVaccineType")
		store = {
			"Address" : "%s - %s, %s" % (loc["addressCityDescriptionText"], loc["addressLine"], zipCode),
			"Dates" : sum(list(map(lambda x: x["availableDates"],dates)),[]),
			"StoreNumber" : storeNumber,
			"Vaccine" : vacName,
			"Success" : 1
		}
		store["Times"] = getVaccineTimes(store["StoreNumber"], store["Dates"])
		logging.info("getStoreInfoFromResponse res=: %s" % (store))
		stores.append(store)
	logging.info("getStoreInfoFromResponse results=: %s" % (stores))
	return stores

def GetVaccineTypes(city, state):
	time.sleep(0.25);
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
	          "59267100002",
	          "59267100003",
	          "59676058015",
	          "80777027399"
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
	  'authority': 'www.cvs.com',
	  'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36',
	  'content-type': 'application/json',
	  'origin': 'https://www.cvs.com',
	  'sec-fetch-site': 'same-origin',
	  'referer': 'https://www.cvs.com/vaccine/intake/store/cvd-store-select/first-dose-select',
	  'accept-language': 'en-US,en;q=0.9',
  	  'cookie': '_4c_mc_=f18fae86-4448-4bfe-bc39-e79d777d3347; AMCV_06660D1556E030D17F000101%40AdobeOrg=-179204249%7CMCIDTS%7C18582%7CMCMID%7C52373249726608440967873903711491311015%7CMCAID%7CNONE%7CMCOPTOUT-1605511063s%7CNONE%7CvVersion%7C3.1.2; CVPF=CT-2; DG_HID=799AB211-E23B-3FE2-8470-F344A470A980; DG_IID=D79BF3DA-A9B4-32C5-8797-F93DE6AE5828; DG_SID=24.63.107.0:XH1WV22Jb6Lz4C5VACIz0C1YaO4BgGVMO3PKVV+KUPk; DG_UID=EFEB6567-BE37-3622-BA26-8772D2538B94; DG_ZID=8A302E80-3059-3F1B-AE2C-044BB4EE211D; DG_ZUID=B5196E04-738E-3406-95B0-CE0D05AEB8BF; utag_main=v_id:0175ca33b912000ce19e0047cf3f03073005706b00bd0$_sn:4$_ss:1$_st:1605505633604$_pn:1%3Bexp-session$ses_id:1605503833604%3Bexp-session; aat1=on; adh_ps_pickup=on; echomeln6=off-p1; flipp2=on; gbi_visitorId=ckmhz6ha000013aedzthg8yd5; mc_home_new=off1; mc_ui_ssr=off-p0; mc_videovisit=on; pivotal_forgot_password=off-p0; pivotal_sso=off-p0; ps=on; rxm=on; rxm_phone_dob=off-p0; s2c_akamaidigitizecoupon=on; s2c_beautyclub=off-p0; s2c_digitizecoupon=on; s2c_dmenrollment=off-p0; s2c_herotimer=off-p0; s2c_newcard=off-p0; s2c_papercoupon=on; s2c_persistEcCookie=on; s2c_smsenrollment=on; sab_displayads=on; sftg=on; show_exception_status=on; pe=p1; acctdel_v1=on; adh_new_ps=on; adh_ps_refill=on; buynow=off; dashboard_v1=off; db-show-allrx=on; disable-app-dynamics=on; disable-sac=on; dpp_cdc=off; dpp_drug_dir=off; dpp_sft=off; getcust_elastic=on; enable_imz=on; enable_imz_cvd=on; enable_imz_reschedule_instore=on; enable_imz_reschedule_clinic=off; gbi_cvs_coupons=true; ice-phr-offer=off; v3redirecton=false; mc_cloud_service=on; mc_hl7=on; memberlite=on; pauth_v1=on; pbmplaceorder=off; pbmrxhistory=on; refill_chkbox_remove=off-p0; rxdanshownba=off; rxdfixie=on; rxd_bnr=on; rxd_dot_bnr=on; rxdpromo=on; rxduan=on; rxlite=on; rxlitelob=off; rxm_demo_hide_LN=off; rxm_phdob_hide_LN=on; rxm_rx_challenge=off; s2c_rewardstrackerbctile=on; s2c_rewardstrackerbctenpercent=on; s2c_rewardstrackerqebtile=on; s2cHero_lean6=on; sft_mfr_new=on; v2-dash-redirection=on; ak_bmsc=A31CA4BCE0A3DEC9E9576B7ACB681600172427A44B080000D117626030FB0B3E~plhEEAq/D9HYGHDRPV2NORuOOSfqG+iefezp88HiSn1ahppD7rf9If7Ub5SBpIB1iW0NKgwIVMrmwloOONyqveWdG91feXGrVVCP5LT8UnHyW8sJATeJzGPX1E8i99Fwa7XEzLLguaFc1vI1zk+LDW2dd+vhcddtWlcdssXNfwh0xWc8v1gmlO4Q0r2oWxQ5HVvBC6WEAq7Thlp6888hHzvTldQ4L9J5Dki43hjlPxFsk=; bm_sz=F7A09FA7C93A1C4808A4A37BE0E33E65~YAAQpCckFwTLY3Z4AQAAsgstfwuqhnUOqT7ytKE/08P4vlHj6gXKtLXlgUh8yxKvKC+QVzpZn33GPBq9SOsefmxGPawC5qw+1fRJtzivZylXeuh/e60RHgkyrJoprfhDxZrnZgdzQotimJUJwAh0OQBG6HYs0ExEl9uldBtk8r9xNvhn0RzQcPPqsDzK; _abck=656A0664A5B9D332C43B7CE79052B9E4~0~YAAQpCckFwXLY3Z4AQAAsgstfwVAogD9OGcypYASvJ2fZ6Mx7wNzMmhwzwTiHXGF1PIrpPe/Z0gdYN9S6GREnuMAuNzHjQME+aSv6j8WhFaXDoqAdqzH/OO8ISBEiikXbR69A4VjCbeIkBfMoTq1ItFs23sHZju30dj+fHhWPdvRlyWUTJjJZNCcveOIRcJ/1jfabi73ztQywdfYgahnd+e7JEt686pZHDBzV7ye4FhQr+tVao82jZM6nGOBNNKkDCsMnIunUj3XiCs/L4jWJfko15EJOYOuGkMAZDfb8JePtHdTgrAWWPYeG3g85u5TNAoj9rNCNZ/WyeP1bhRujJe22DjSCpL6VTJ9pD/pbFfbPwsqr1c8m4ZwFiUXNlApXds5Ss7xWonYyQSMz20nLfwZYBIM~-1~-1~-1; gbi_sessionId=ckmuwodh800003a764gwysab8; akavpau_vp_www_cvs_com_vaccine=1617042583~id=79a5de9d45f5e37ea7b292e802bf2cb7; akavpau_vp_www_cvs_com_vaccine_covid19=1617042583~id=79a5de9d45f5e37ea7b292e802bf2cb7; akavpau_www_cvs_com_general=1617042403~id=6c3b586e3c6b9b144c29c8ac7cad78fb; bm_sv=F4A36E329CB6669617D582E423215E6F~jdDB68Q1RHxn15JB5AVrNQujeffr16zs8rWs04CH9SgaeXBAGAtuMSdhGGjOkmTSYPoPVHaxsYigCIHRDnzfZrCTqkgMpx6/73Ix94sKmtaDqPSjl8aw1aC/Tj7Hz1MgCLIlQZEHdtvuihx9pPFlpQ==; _abck=656A0664A5B9D332C43B7CE79052B9E4~-1~YAAQpCckF44QfXZ4AQAASm/IiQUnbjPcOak/vKkMiXhoiG7ckVqHGisWPFdaF5qECoSiTgZ+TlmnZte0xwyPX4lLwReBN+IPHZ8l0HbQXEpoLlRYIDsOqNf4+s/KzBM9wVRtRS840X1HjAqUJ/STQ+mUAtF2oTszVlB6Ghzlr350hKB7txppDjxItvhgG7fmNK2o++41vc9lKrfV43o5hxTe0fOLEiSSw3l1FwPd2qzn0LQ0cXczsF17elp8oUnPa4jxcYVc2LxHoiZb11zvNOElPsVIQ+1HKMO3PzNBBdOD3NpmMlpJBcUDbZf8Yn8VZPkDZ1Aj3eqf1Wc70jFI3UTRBRFO6PWc8b1CsBJ1KCBNCMivvhAOBiQm9mjjoiYEBQG9UaGv1hebaQ==~0~-1~-1; bm_sv=65D7284C88833445C802A310F0AF0CBA~jdDB68Q1RHxn15JB5AVrNdMYmisQ731KU5m+rdWTOLfOA+sTSXvKYajcqD2s2U9aA3ZIZ/TnEmchDzaoiNtiI5zWRorl5EVRKvSeiR2Hf7ukq/GEsCwao/QPyhziCFstvgamy4i/v4fqbbl9PEB3Vg==; ADRUM_BT=R:75|i:1684|g:f0366647-2700-4f48-a5f8-b94461c4ea15636038|e:251|n:customer1_d6c575ca-3f03-4481-90a7-5ad65f4a5986; affinity="3ba9affc016951d6"; pe=p1'
  	}
	logging.debug("GetVaccineTypes for: %s, %s" % (city, state))
	conn.request("POST", "/Services/ICEAGPV1/immunization/1.0.0/getIMZStores", payload, headers)
	res = conn.getresponse()
	vacs = validateAndParse(tryToParseJson(res), "%s, %s" % (city, state))
	logging.debug("GetVaccineTypes vacs: %s" % (vacs))

	if not vacs["Success"]:
		return vacs;

	logging.info("GetVaccineTypes res=%s" % (vacs))

	return getStoreInfoFromResponse(vacs);

def getDataStruct(vacs):
	def flatten(vac):
		if isinstance(vac, list):
			return vac[0];
		return vac;
	vacs = list(map(flatten,vacs)) # flatten list of multiple searches
	return {"Timestamp":GetTimestamp(), "Data":vacs};

def GetVaccineAvailabilityInState(state):
	locs = GetAvailableLocations(state)
	vaccines = list(map(lambda loc: GetVaccineTypes(loc["city"], loc["state"]), locs))
	return getDataStruct(vaccines)

def GetVaccineAvailabilityInCity(citylist, state):
	def sleepAndSearch(loc):
		time.sleep(0.5);
		return GetVaccineTypes(loc["city"], loc["state"])
	locs = list(map(lambda c: {"city": c, "state": state}, citylist))
	vaccines = list(map(sleepAndSearch, locs))
	return getDataStruct(vaccines)

def Test():
	PrettyPrint(GetVaccineAvailabilityInState("OH"))
	#PrettyPrint(GetVaccineAvailabilityInCity(["Dayton"], "OH"))

# logging.getLogger().setLevel(logging.DEBUG)
# Test()
