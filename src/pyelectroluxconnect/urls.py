"""
List of some ECP URLs 
"""

import re
from urllib.parse import quote_plus

BASE_URL = "https://api.emea.ecp.electrolux.com"


def getEcpClientId(region):
    if region.lower() == "emea":
        return "714fc3c7-ad68-4c2f-9a1a-b3dbe1c8bb35"
    elif region.lower() == "apac":
        return "1c064d7a-c02e-438c-9ac6-78bf7311ba7c"
    elif region.lower() == "na":
        return "dc9cfac1-4a29-4509-9041-9ae4a0572aac"
    elif region.lower() == "latam":
        return "3aafa8f0-9fd8-454d-97f6-f46e87b280e2"
    else:
        return "714fc3c7-ad68-4c2f-9a1a-b3dbe1c8bb35"

#Authenticate (get Session key)
def login():
    return ["{base_url}/authentication/authenticate".format(
        base_url=BASE_URL),
        "POST"
        ]

#Get appliances list registered to account
def getAppliances(username):
    return ["{base_url}/user-appliance-reg/users/{username}/appliances".format(
        base_url=BASE_URL,
        username=re.sub("(?i)\%2f", "f", quote_plus(username))),
        "GET"
        ]

#Get general HACL map 
def getHaclMap():
    return ["{base_url}/config-files/haclmap".format(
        base_url=BASE_URL),
        "GET"
        ]

#Get list of supported appliances    
def getApplianceConfigurations():
    return ["{base_url}/config-files/configurations".format(
        base_url=BASE_URL),
        "GET"
        ]

#Get appliance connection state
def getApplianceConnectionState(appliance):
    return ["{base_url}/elux-ms/appliances/latest?pnc={pnc}&elc={elc}&sn={sn}&states=ConnectivityState&includeSubcomponents=false".format(
        base_url=BASE_URL,
        pnc=re.sub("(?i)\%2f", "f", quote_plus(appliance["pnc"])),
        sn=re.sub("(?i)\%2f", "f", quote_plus(appliance["sn"])),
        elc=re.sub("(?i)\%2f", "f", quote_plus(appliance["elc"]))),
        "GET"
        ]

#Get appliance parameter state
def getApplianceParameterState(appliance,parameter):
    return ["{base_url}/elux-ms/appliances/latest?pnc={pnc}&elc={elc}&sn={sn}&states={param}&includeSubcomponents=true".format(
        base_url=BASE_URL,
        pnc=re.sub("(?i)\%2f", "f", quote_plus(appliance["pnc"])),
        sn=re.sub("(?i)\%2f", "f", quote_plus(appliance["sn"])),
        elc=re.sub("(?i)\%2f", "f", quote_plus(appliance["elc"])),
        param=re.sub("(?i)\%2f", "f", quote_plus(parameter))),
        "GET"
        ]

#Get all appliance parameters state
def getApplianceAllStates(appliance):
    return ["{base_url}/elux-ms/appliances/latest?pnc={pnc}&elc={elc}&sn={sn}&includeSubcomponents=true".format(
        base_url=BASE_URL,
        pnc=re.sub("(?i)\%2f", "f", quote_plus(appliance["pnc"])),
        sn=re.sub("(?i)\%2f", "f", quote_plus(appliance["sn"])),
        elc=re.sub("(?i)\%2f", "f", quote_plus(appliance["elc"]))),
        "GET"
        ]

#Send command do appliance
def setApplianceCommand(appliance):
    return ["{base_url}/commander/remote/sendjson?pnc={pnc}&elc={elc}&sn={sn}&mac={mac}".format(
        base_url=BASE_URL,
        pnc=re.sub("(?i)\%2f", "f", quote_plus(appliance["pnc"])),
        sn=re.sub("(?i)\%2f", "f", quote_plus(appliance["sn"])),
        elc=re.sub("(?i)\%2f", "f", quote_plus(appliance["elc"])),
        mac=re.sub("(?i)\%2f", "f", quote_plus(appliance["mac"]))),
        "POST"
        ]

#Get selected appliance configuration
def getApplianceConfigurationVersion(appliance):
    return ["{base_url}/config-files/configurations/search?pnc={pnc}&elc={elc}&serial_number={sn}".format(
        base_url=BASE_URL,
        pnc=re.sub("(?i)\%2f", "f", quote_plus(appliance["pnc"])),
        sn=re.sub("(?i)\%2f", "f", quote_plus(appliance["sn"])),
        elc=re.sub("(?i)\%2f", "f", quote_plus(appliance["elc"]))),
        "GET"
        ]

#Download configuration file
def getApplianceConfigurationFile(configurationId):
    return ["{base_url}/config-files/configurations/{configurationId}/bundle".format(
        base_url=BASE_URL,
        configurationId=re.sub("(?i)\%2f", "f", quote_plus(configurationId))),
        "GET"
        ]
    
#Register Client to MQTT broker    
def registerMQTT():
    return ["{base_url}/livesubscribe/livestream/register".format(
        base_url=BASE_URL),
        "POST"
        ]

#Unregister Client from MQTT broker    
def unregisterMQTT():
    return ["{base_url}/livesubscribe/livestream/unregister".format(
        base_url=BASE_URL),
        "POST"
        ]