# pyelectroluxconnect
Python client package to communicate with the Electrolux Connectivity Platform (**ECP**) used by some home appliances, Electrolux owned brands, like: **Electrolux**, **AEG**, **Frigidaire**, **Husqvarna**.
Tested with AEG washer-dryer, but probably could be used with some internet connected ovens, diswashers, fridges, airconditioners.  
It is general client, and all parameters (called HACL), that can be read or set, names and translations are dynamically generated, based on appliance profile file, downloaded from ECP servers. 
    
## Features
- list appliances paired with Electrolux account
- get appliance profile with translations
- get appliance state
- send command to appliance
- register/unregister Client with Electrolux MQTT cloud based broker

## Usage
#### Initiate session
  
```python
import pyelectroluxconnect
ses = pyelectroluxconnect.Session(username, password, tokenFileName = ".electrolux-token", country = "US", language = None, deviceId = "CustomeDeviceId", raw = False, verifySsl = True, regionServer= "https://api.emea.ecp.electrolux.com")
```

or minimal input set: 

```python
import pyelectroluxconnect
ses = pyelectroluxconnect.Session(username, password)
```

where:   
`username, password` - ECP (Electrolux site) credentials  
`tokenFileName` - file to store auth token (default: `~/.electrolux-token`)  
`country` - 2-char country code (default `US`)  
`language` - 3-char language code for translations (`All` - for all delivered languages, default: `None`)  
`deviceId` - custom id of client used in ECP, should be unique for every client instance (default: `CustomDeviceId`)  
`raw` - display HTTP requests/responses (default: `False`)  
`verifySsl` - verify ECP servers certs (default: `True`)  
`regionServer` - region server URL (default, tested EMEA server `https://api.emea.ecp.electrolux.com`. Other supported regional servers can be set)   



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

```python
ses.setHacl(appliance, hacl, value)
```
  
`hacl` - hex number of param (HACL)  
`value` - value to set (it could be number or list of parameters (for container HACL type))
   
washer-dryer examples:
- set Wash+Dry "Cottons" program, with "Extra Dry" dryness Level:
 
```python
ses.setHacl(appliance, "0x1C09", [{"50":"0x0000"},{"12":"128"},{"6.32":1},{"6.33":1}])
```

- pause program:

```python
ses.setHacl(appliance, "0x0403", 4)
```


#### Register client to MQTT broker
  
```python
print(ses.registerMQTT())
```

returns parameters required to login to Electrolux MQTT broker with any MQTT client:   
`Url` - Host of MQTT broker (with port number)   
`OrgId` - Organization ID   
`ClientId` - MQTT Client ID   
`DeviceToken` - Token required to authentication (for IBM broker, use `use-token-auth` as username, DeviceToken as password)   

List of MQTT topics (QoS = 0) to subscribe:
- `iot-2/cmd/live_stream/fmt/+`   
- `iot-2/cmd/feature_stream/fmt/+`   

#### Unregister client from MQTT broker
  
```python
ses.unregisterMQTT()
```
 
## Disclaimer
This library was not made by AB Electrolux. It is not official, not developed, and not supported by AB Electrolux.