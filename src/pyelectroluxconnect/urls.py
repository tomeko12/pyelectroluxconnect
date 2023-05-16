"""
List of some ECP URLs and strings 
"""

import re
from urllib.parse import quote_plus

BASE_URL = "https://api.eu.ecp.electrolux.com"
X_API_KEY = "epLN8yHKltFNEgdggmSFfG6AHHvPcd4k0xGqm830"
BRAND = "Electrolux"

_region_params = {
    "emea": ["https://api.eu.ecp.electrolux.com",
             "epLN8yHKltFNEgdggmSFfG6AHHvPcd4k0xGqm830",
             "Electrolux"],
    "apac": ["https://api.apac.ecp.electrolux.com",
             "1c064d7a-c02e-438c-9ac6-78bf7311ba7c",
             "Electrolux"],
    "na":   ["https://api.latam.ecp.electrolux.com",
             "dc9cfac1-4a29-4509-9041-9ae4a0572aac",
             "Electrolux-NA"],
    "latam": ["https://api.latam.ecp.electrolux.com",
              "3aafa8f0-9fd8-454d-97f6-f46e87b280e2",
              "Electrolux"],
    "frigidaire": ["https://api.latam.ecp.electrolux.com",
                   "7ff2358e-8d6d-4cf6-814a-fcb498fa2cf9",
                   "frigidaire"]
}


def getEcpClientUrl(region):
    if region.lower() in _region_params:
        return _region_params[region.lower()][0]
    else:
        return BASE_URL


def getEcpClientId(region):
    if region.lower() in _region_params:
        return _region_params[region.lower()][1]
    else:
        return X_API_KEY


def getEcpClientBrand(region):
    if region.lower() in _region_params:
        return _region_params[region.lower()][2]
    else:
        return BRAND


# Authenticate (get Session key)
def login():
    return ["{base_url}/authentication/authenticate".format(
        base_url=BASE_URL),
        "POST"
    ]

# Get appliances list registered to account


def getAppliances(username):
    return ["{base_url}/user-appliance-reg/users/{username}/appliances".format(
        base_url=BASE_URL,
        username=re.sub("(?i)\%2f", "f", quote_plus(username))),
        "GET"
    ]

# Get general HACL map


def getHaclMap():
    return ["{base_url}/config-files/haclmap".format(
        base_url=BASE_URL),
        "GET"
    ]

# Get list of supported appliances


def getApplianceConfigurations():
    return ["{base_url}/config-files/configurations".format(
        base_url=BASE_URL),
        "GET"
    ]

# Get appliance connection state


def getApplianceConnectionState(appliance):
    return ["{base_url}/elux-ms/appliances/latest?pnc={pnc}&elc={elc}&sn={sn}&states=ConnectivityState&includeSubcomponents=false".format(
        base_url=BASE_URL,
        pnc=re.sub("(?i)\%2f", "f", quote_plus(appliance["pnc"])),
        sn=re.sub("(?i)\%2f", "f", quote_plus(appliance["sn"])),
        elc=re.sub("(?i)\%2f", "f", quote_plus(appliance["elc"]))),
        "GET"
    ]

# Get appliance parameter state


def getApplianceParameterState(appliance, parameter):
    return ["{base_url}/elux-ms/appliances/latest?pnc={pnc}&elc={elc}&sn={sn}&states={param}&includeSubcomponents=true".format(
        base_url=BASE_URL,
        pnc=re.sub("(?i)\%2f", "f", quote_plus(appliance["pnc"])),
        sn=re.sub("(?i)\%2f", "f", quote_plus(appliance["sn"])),
        elc=re.sub("(?i)\%2f", "f", quote_plus(appliance["elc"])),
        param=re.sub("(?i)\%2f", "f", quote_plus(parameter))),
        "GET"
    ]

# Get all appliance parameters state


def getApplianceAllStates(appliance):
    return ["{base_url}/elux-ms/appliances/latest?pnc={pnc}&elc={elc}&sn={sn}&includeSubcomponents=true".format(
        base_url=BASE_URL,
        pnc=re.sub("(?i)\%2f", "f", quote_plus(appliance["pnc"])),
        sn=re.sub("(?i)\%2f", "f", quote_plus(appliance["sn"])),
        elc=re.sub("(?i)\%2f", "f", quote_plus(appliance["elc"]))),
        "GET"
    ]

# Send command do appliance


def setApplianceCommand(appliance):
    return ["{base_url}/commander/remote/sendjson?pnc={pnc}&elc={elc}&sn={sn}&mac={mac}".format(
        base_url=BASE_URL,
        pnc=re.sub("(?i)\%2f", "f", quote_plus(appliance["pnc"])),
        sn=re.sub("(?i)\%2f", "f", quote_plus(appliance["sn"])),
        elc=re.sub("(?i)\%2f", "f", quote_plus(appliance["elc"])),
        mac=re.sub("(?i)\%2f", "f", quote_plus(appliance["mac"]))),
        "POST"
    ]

# Get selected appliance configuration


def getApplianceConfigurationVersion(pnc, elc, sn):
    return ["{base_url}/config-files/configurations/search?pnc={pnc}&elc={elc}&serial_number={sn}".format(
        base_url=BASE_URL,
        pnc=re.sub("(?i)\%2f", "f", quote_plus(pnc)),
        sn=re.sub("(?i)\%2f", "f", quote_plus(sn)),
        elc=re.sub("(?i)\%2f", "f", quote_plus(elc))),
        "GET"
    ]

# Download configuration file


def getApplianceConfigurationFile(configurationId):
    return ["{base_url}/config-files/configurations/{configurationId}/bundle".format(
        base_url=BASE_URL,
        configurationId=re.sub("(?i)\%2f", "f", quote_plus(configurationId))),
        "GET"
    ]

# Register Client to MQTT broker


def registerMQTT():
    return ["{base_url}/livesubscribe/livestream/register".format(
        base_url=BASE_URL),
        "POST"
    ]

# Unregister Client from MQTT broker


def unregisterMQTT():
    return ["{base_url}/livesubscribe/livestream/unregister".format(
        base_url=BASE_URL),
        "POST"
    ]

# Find docs by PNC


def getDocsTable(pnc, elc):
    return ["https://www.electrolux-ui.com/SearchResults.aspx?PNC={_pnc}{_elc}&ModelDenomination=&Language=&DocumentType=&Brand=".format(
        _pnc=re.sub("(?i)\%2f", "f", quote_plus(pnc)),
        _elc=re.sub("(?i)\%2f", "f", quote_plus(elc))),
        "GET"
    ]
