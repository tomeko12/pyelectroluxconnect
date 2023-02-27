# pyelectroluxconnect
Python client package to communicate with the Electrolux Connectivity Platform (**ECP**) used by some home appliances, Electrolux owned brands, like: **Electrolux**, **AEG**, **Frigidaire**, **Husqvarna**.
Tested with AEG washer-dryer, but probably could be used with some internet connected ovens, diswashers, fridges, airconditioners.  
It is general client, and all parameters (called HACL), that can be read or set, names and translations are dynamically generated, based on appliance profile file, downloaded from ECP servers. 
Appliance must be registered with one of the following ECP based applications: Electrolux Care, Electrolux Kitchen, Electrolux Life, Electrolux Oven, Electrolux Home+, AEG Care, AEG Kitchen, Frigidaire 2.0
    
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
Get latest appliance state from ECP. When appliance is online, current state updates are available over:
- LAN with [AllJoyn](https://en.wikipedia.org/wiki/AllJoyn) protocol
- Internet with [MQTT](https://en.wikipedia.org/wiki/MQTT) protocol. To get credentials to connect any MQTT client to ECP MQTT broker, use `registerMQTT()` method.
 

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

## Disclaimer
This library was not made by AB Electrolux. It is not official, not developed, and not supported by AB Electrolux.
