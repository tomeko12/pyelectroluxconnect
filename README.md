# pyelectroluxconnect
> [!IMPORTANT]
> Electrolux has moved user accounts fom Electrolux Connectivity Platform (**ECP**) to OneApp (**OCP**) API used by Electrolux ([Google Play](https://play.google.com/store/apps/details?id=com.electrolux.oneapp.android.electrolux), [App Store](https://apps.apple.com/gb/app/electrolux/id1595816832)) and  AEG ([Google Play](https://play.google.com/store/apps/details?id=com.electrolux.oneapp.android.aeg), [App Store](https://apps.apple.com/gb/app/aeg/id1599494494)) Apps. OneApp API is not supported by this client. ECP access is disabled by Electrolux. This client don't work anymore.

Python client package to communicate with the Electrolux Connectivity Platform (**ECP**) used by some home appliances, Electrolux owned brands, like: **Electrolux**, **AEG**, **Frigidaire**, **Husqvarna**.
Tested with AEG washer-dryer, but probably could be used with some internet connected ovens, diswashers, fridges, airconditioners.  
It is general client, and all parameters (called HACL), that can be read or set, names and translations are dynamically generated, based on appliance profile file, downloaded from ECP servers. 

## Compatibility
This package is compatibile with home appliances registered with one of this ECP based mobile apps:  

- **EMEA region:**
  - My AEG Care ([Google Play](https://play.google.com/store/apps/details?id=com.aeg.myaeg), [App Store](https://apps.apple.com/gb/app/my-aeg-care/id1087824977))  
  - My Electrolux Care ([Google Play](https://play.google.com/store/apps/details?id=com.electrolux.myelx), [App Store](https://apps.apple.com/gb/app/my-electrolux-care/id1116118055))  
  - My AEG Kitchen ([Google Play](https://play.google.com/store/apps/details?id=com.aeg.myaeg.taste), [App Store](https://apps.apple.com/gb/app/my-aeg-kitchen/id1348681700))  
  - My Electrolux Kitchen ([Google Play](https://play.google.com/store/apps/details?id=com.electrolux.myelx.taste), [App Store](https://apps.apple.com/gb/app/my-electrolux-kitchen/id1348668617))  

- **APAC region:**
  - Electrolux Life ([Google Play](https://play.google.com/store/apps/details?id=com.electrolux.electroluxlife), [App Store](https://apps.apple.com/au/app/electrolux-life/id1352924780))  

- **LATAM region:**
  - Electrolux Home+ ([Google Play](https://play.google.com/store/apps/details?id=com.electrolux.revamp), [App Store](https://apps.apple.com/br/app/electrolux-home/id1598612686))  

- **NA region:**
  - Electrolux Oven ([Google Play](https://play.google.com/store/apps/details?id=com.electrolux.ecp.coreapp.na), [App Store](https://apps.apple.com/us/app/electrolux-oven/id1549973042))  

- **Frigidaire:**
  - Frigidaire 2.0 ([Google Play](https://play.google.com/store/apps/details?id=com.electrolux.ecp.coreapp.frigidaire.na), [App Store](https://apps.apple.com/us/app/frigidaire-2-0/id1500302958))  


## Unsupported devices
This package **is not** compatibile with appliances controlled with this mobile apps:  
- Electrolux ([Google Play](https://play.google.com/store/apps/details?id=com.electrolux.oneapp.android.electrolux), [App Store](https://apps.apple.com/gb/app/electrolux/id1595816832))  
- AEG ([Google Play](https://play.google.com/store/apps/details?id=com.electrolux.oneapp.android.aeg), [App Store](https://apps.apple.com/gb/app/aeg/id1599494494))  
- Frigidaire ([Google Play](https://play.google.com/store/apps/details?id=com.electrolux.oneapp.android.frigidaire), [App Store](https://apps.apple.com/us/app/frigidaire/id1599494923))  
- Electrolux Wellbeing ([Google Play](https://play.google.com/store/apps/details?id=com.electrolux.wellbeing), [App Store](https://apps.apple.com/gb/app/electrolux-wellbeing/id1436169315))  
- AEG Wellbeing ([Google Play](https://play.google.com/store/apps/details?id=com.aeg.wellbeing), [App Store](https://apps.apple.com/gb/app/aeg-wellbeing/id1494284929))  
- Electrolux Home Comfort ([Google Play](https://play.google.com/store/apps/details?id=com.electrolux.airconditioner), [App Store](https://apps.apple.com/gb/app/electrolux-home-comfort/id1318742765))  
- AEG Home Comfort ([Google Play](https://play.google.com/store/apps/details?id=com.aeg.airconditioner), [App Store](https://apps.apple.com/gb/app/aeg-home-comfort/id1320946491))  
- Electrolux AirCare ([Google Play](https://play.google.com/store/apps/details?id=com.aircare.electrolux), [App Store](https://apps.apple.com/gb/app/electrolux-aircare/id569837094))  
- Electrolux Wifi ControlBox ([Google Play](https://play.google.com/store/apps/details?id=com.electrolux.wifibox), [App Store](https://apps.apple.com/gb/app/electrolux-wifi-controlbox/id1095621521))  
    
## Features
- list appliances paired with Electrolux account
- get appliance profile with translations
- get appliance state
- send command to appliance
- register/unregister Client with Electrolux MQTT cloud based broker

## Usage
#### Initiate session
To use this library, there's an account with Electrolux/AEG/Frigidaire app must be created. By default, library is using EMEA region apps credentials. If account is created in other region app, `region` parameter must be set. If created account is not supported, You can manually set `regionServer`, `customApiKey` and `customApiBrand` parameters (from sniffed traffic or extracted from mobile app).

  
```python
import pyelectroluxconnect
ses = pyelectroluxconnect.Session(username, password, region="emea", tokenFileName = ".electrolux-token", country = "US", language = None, deviceId = "CustomDeviceId", verifySsl = True, regionServer=None, customApiKey=None, customApiBrand=None)
```

or minimal input set: 

```python
import pyelectroluxconnect
ses = pyelectroluxconnect.Session(username, password)
```

where:   
`username, password` - ECP (Electrolux site) credentials  
`tokenFileName` - file to store auth token (default: `~/.electrolux-token`)  
`region` - account region (defalt `emea`. Tested with `emea`, `apac`, `na`, `latam`, `frigidaire`)  
`country` - 2-char country code (default `US`)  
`language` - 3-char language code for translations (`All` - for all delivered languages, default: `None`)  
`deviceId` - custom id of client used in ECP, should be unique for every client instance (default: `CustomDeviceId`)  
`verifySsl` - verify ECP servers certs (default: `True`)  
`regionServer` - region server URL (default is based on selected region)   
`customApiKey` - custom value of "x-ibm-client-id" and "x-api-key" HTTP headers (default is based on selected region)   
`customApiBrand` - custom "brand" value (default is based on selected region)  



#### Login to ECP


```python
ses.login()
```

#### Get list of appliances registered to Electrolux account

```python
appllist = ses.getAppliances()
print(appllist)
```


#### Get appliances connection state

```python
for appliance in appllist:  
	print(ses.getApplianceConnectionState(appliance))
```


#### Get appliance profile 
List of parameters (HACL's) with allowed values, translations, etc... Note, that not all parameters can be read, or set over ECP.   
Each parameter is in "module:hacl" form. Module is internal appliance module symbol, hacl is parameter hex symbol, that can be read from or set to module.   
  	
```python
print(ses.getApplianceProfile(appliance))
```

     
#### Get appliance latest state from ECP
Get latest appliance state from ECP. When appliance is online, current state updates are available over Internet with [MQTT](https://en.wikipedia.org/wiki/MQTT) protocol. To get credentials to connect any MQTT client to ECP MQTT broker, use `registerMQTT()` method.
 

to get latest state from a platform:   

```python
print(ses.getApplianceState(appliance, paramName = None, rawOutput = False))
```

`paramName` - comma separated list of patrameter names (`None` (default) for all params)   
`rawOutput` - get list of parameters in received form. `False` (default): parse output to more friendly form (with translations, etc)   


#### Send param value to appliance
Send value to appliance (list of supported appliance destinations (`destination`) and parameters (`hacl`) with allowed values (`value`), You can get with `getApplianceProfile()` method):   
```python
ses.setHacl(appliance, hacl, value, destination)
```
  
`hacl` - hex number of param (HACL)  
`value` - value to set (it could be number or list of parameters (for container HACL type))   
`destination` - destination module name, from profile path (`NIU`, `WD1`, etc...)   
   
washer-dryer examples:
- set Wash+Dry "Cottons" program, with "Extra Dry" dryness Level:
 
```python
ses.setHacl(appliance, "0x1C09", [{"50":"0x0000"},{"12":"128"},{"6.32":1},{"6.33":1}], "WD1")
```

- pause program:

```python
ses.setHacl(appliance, "0x0403", 4, "WD1")
```


#### Register client to MQTT broker
  
```python
print(ses.registerMQTT())
```

returns parameters required to login to Electrolux MQTT broker with any MQTT client:   
`Url` - Host of MQTT broker (with port number)   
`OrgId` - Organization ID   
`ClientID` - MQTT Client ID   
`DeviceToken` - Token required to authentication (for IBM broker, use string `use-token-auth` as username, DeviceToken as password)   

List of MQTT topics (QoS = 0) to subscribe:
- `iot-2/cmd/live_stream/fmt/+`   
- `iot-2/cmd/feature_stream/fmt/+`   

#### Unregister client from MQTT broker
  
```python
ses.unregisterMQTT()
```
 
#### Parse received MQTT message

```python
print(ses.getMqttState(mqttJsonPayload))
```

Parse message from MQTT broker, and return in getApplianceState(...) like form.
`mqttJsonPayload` - MQTT message payload in JSON form.

#### Very simple MQTT example to receive online appliance state changes from ECP MQTT broker
*Please Note: Electrolux moved MQTT broker from IBM servers. After that, this code is not valid.*

```python
import paho.mqtt.client as mqtt
import pyelectroluxconnect

def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe("iot-2/cmd/live_stream/fmt/json", 0)

def on_message(client, userdata, msg):
    print(ses.getMqttState(msg.payload))

ses = pyelectroluxconnect.Session(login, passwd, language = "pol", region="emea",  deviceId='MQTTHA2')
ses.login()

mqtt_params = ses.registerMQTT()

client = mqtt.Client(client_id = mqtt_params["ClientID"])
client.tls_set(ca_certs = ses.getSSLCert())
client.username_pw_set("use-token-auth", mqtt_params["DeviceToken"])
    
client.on_connect = on_connect
client.on_message = on_message
    
client.connect(mqtt_params["Url"].split(":")[0], int(mqtt_params["Url"].split(":")[1]), 60)
    
while True:
    client.loop()
```

## Disclaimer
This library was not made by AB Electrolux. It is not official, not developed, and not supported by AB Electrolux.
