""" Implements API wrapper to Electolux Connectivity Platform """

import hashlib
import json
import os
import requests
import time
import urllib3
import zipfile

from pyelectroluxconnect import urls
from pathlib import Path


def _validate_response(response):
    """ Verify that response is OK """
    if response.status_code == 200:
        return
    raise ResponseError(response.status_code, response.text)

class Error(Exception):
    """ Session error """
    pass

class RequestError(Error):
    """ Wrapped requests.exceptions.RequestException """
    pass


class LoginError(Error):
    """ Login failed """
    pass

class ResponseError(Error):
    """ Unexcpected response """
    def __init__(self, status_code, text):
        super(ResponseError, self).__init__(
            "Invalid response"
            ", status code: {0} - Data: {1}".format(
                status_code,
                text))
        self.status_code = status_code
        self.text = text


class Session(object):
    """
    Session object
    """


    def __init__(
            self, 
            username, 
            password, 
            tokenFileName="~/.electrolux-token", 
            country="US",
            language=None, 
            deviceId="CustomDeviceId", 
            raw=False,  
            verifySsl=True,
            region="emea",
            regionServer=None):
        """
        username, password - Electrolux platform credentials
        country - 2-char country code
        language - 3-char language code for translations (All - for all delivered languages)
        tokenFileName - file to store auth token
        deviceId - custom id of Electrolux platform client
        raw - display HTTP requests/responses
        verifySsl - verify Electrolux platform servers certs
        region = region name (currently tested: "emea", "apac")
        regionServer - region server URL (default - EMEA server)
        """

        self._username = username
        self._password = password
        self._country = country
        self._raw = raw
        self._language = language
        self._region = region
        self._deviceId = deviceId
        self._tokenFileName = os.path.expanduser(tokenFileName)
        self._sessionToken = None
        self._applianceIndex = {}
        self._applianceProfiles = {}
        self._applianceTranslations = {}

        if verifySsl == False:
            urllib3.disable_warnings(
                urllib3.exceptions.InsecureRequestWarning)
            self._verifySsl = verifySsl
        else:
            self._verifySsl = os.path.join(os.path.dirname(__file__),
                    "certificatechain.pem")
        
        if regionServer is not None:
            urls.BASE_URL = regionServer
        elif self._region == "emea":
           urls.BASE_URL = "https://api.emea.ecp.electrolux.com"
        elif self._region == "apac":
           urls.BASE_URL = "https://api.apac.ecp.electrolux.com"
        elif self._region == "latam":
            urls.BASE_URL = "https://api.latam.ecp.electrolux.com"
        


    def __enter__(self):
        self.login()
        return self



    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()
        self.unregisterMQTT()



    def _headers(self):
        headers = {
            "x-ibm-client-id": urls.getEcpClientId(),
            "x-api-key": urls.getEcpClientId(),
            "Content-Type": "application/json"
        }
        if self._sessionToken:
            headers["session_token"] = self._sessionToken
        return headers
    
    

    def _createToken(self):
        """
        Creating token by authenticate
        """
        
        _payload = {
                "country": self._country,
                "deviceId": self._deviceId,
                "password": self._password,
                "username": self._username
        }

        if self._raw: 
            print("--- creating token by authentication")
        try:
            loginResp = json.loads(
                self._requestHttp(
                    urls.login(),_payload).text)
            if loginResp["status"] == "OK":
                self._sessionToken = loginResp["data"]["sessionKey"]
            else:
                raise Error(loginResp["message"])
                    
        except ResponseError as ex:
            if(ex.status_code == 401 
               and json.loads(ex.text)["code"] == "AER0802"):
                raise LoginError(json.loads(ex.text)["message"]) from None


    def _getAppliancesList(self):
        """ 
        Get user registered appliances list
        """

        _json = json.loads(
            self._requestHttp(
                urls.getAppliances(self._username)).text)

        if(_json["status"] == "ERROR"):
            raise ResponseError(_json["code"], _json["message"])

        for device in _json["data"]:
            if device:
                self._applianceIndex[device["appliance_id"]] = {
                    "alias": device["nickname"], 
                    "pnc": device["pnc"], 
                    "elc": device["elc"], 
                    "sn": device["sn"], 
                    "mac": device["mac"], 
                    "cpv": device["cpv"],
                    }
                self._getApplianceConfiguration(device['appliance_id'])



    def _getApplianceConfiguration(self, applianceId):
        """
        Get appliance configuration file 
        """
        
        appliance = self._applianceIndex.get(applianceId)

        if(appliance):
            _json = json.loads(
                self._requestHttp(
                    urls.getApplianceConfigurationVersion(appliance)).text)

            if(_json["status"] == "OK"):
                applianceConfigFileName =  list(
                    _json["data"][0]["configuration_file"])[0]
                deviceConfigId = _json["data"][0]["configuration_id"]
                applianceConfigFilePath = os.path.join(str(Path.home()),applianceConfigFileName)
                
                """ Checking proper appliance configuration file exists"""
                if not((os.path.exists(applianceConfigFilePath) 
                        and (f"md5-{hashlib.md5(open(applianceConfigFilePath,'rb').read()).hexdigest()}" ==
                              _json["data"][0]["configuration_file"][applianceConfigFileName]["digest"]))):
                    try:
                        _zipFile = self._requestHttp(urls.getApplianceConfigurationFile(deviceConfigId))
                        open(applianceConfigFilePath, 'wb').write(_zipFile.content)
                    except requests.exceptions.RequestException as ex:
                        raise RequestError(ex)
 
                    
                if(os.path.exists(applianceConfigFilePath) 
                   and (f"md5-{hashlib.md5(open(applianceConfigFilePath,'rb').read()).hexdigest()}" ==
                         _json["data"][0]["configuration_file"][applianceConfigFileName]["digest"])):
                    with zipfile.ZipFile(applianceConfigFilePath, 'r') as archive:
                        self._applianceTranslations[id] = {}

                        _json = json.loads(
                            archive.read(
                                f"{archive.namelist()[0]}profile.json"))
                        _profile = self._parseProfileFile(_json, applianceId)

                        _json = json.loads(
                            archive.read(
                                f"{archive.namelist()[0]}{next(item for item in _json['bundles'] if item['type'] == 'Localization')['path']}"))

                        self._applianceTranslations[applianceId] = self._parseLocale_bundleFile(_json)
                        self._applianceProfiles[applianceId] = self._createApplianceProfile(
                            applianceId,
                            _profile
                            )
                else:
                    raise Exception("Unable to get device configuration file.")
            else:
                raise Exception (_json["message"])
            
            

    def _parseProfileFile(self, _json, applianceId):
        """
        Parse device profile.json file
        """
        result = {}
        self._applianceIndex[applianceId]["brand"] = _json["brand"] 
        self._applianceIndex[applianceId]["group"] = _json["group"] 
        self._applianceIndex[applianceId]["model"] = _json["model_name"] 

        result["id"] = []
        for modules in _json["modules"]:
            for component in modules["components"]:
                if "hacl" in component:
                    result[component["hacl"]["name"]] = self._parseProfileFileEntry(modules["path"],component)
                elif "id" in component and "parent_interfaces" in component:
                    _identry = self._parseProfileFileEntry(modules["path"],component)
                    _identry["id"] = component["id"]
                    _identry["parent_interfaces"] = component["parent_interfaces"]
                    result["id"].append(_identry)
        
        return result
                        
                        
                        
    def _parseProfileFileEntry(self, path, component):
        result = {key: component[key] for 
                         key in component if key in 
                         [
                            "name",
                            "namespace",
                            "type",
                            "data_format",
                            "visibility",
                            "access",
                            "min_value",
                            "max_value",
                            "increment",
                            "type"
                            ]
                        }
        result["path"] = path 
        result["data_format"] =  component["data_format"]["format"]
        if "unit" in component:
            result["unit"] = component["unit"]["source_format"]
        if "metadata" in component:
            if "localization_key" in component["metadata"]:
                result["locale_key"] = component["metadata"]["localization_key"]
            else:
                result["locale_key"] = ""
        else:
            result["locale_key"] = ""
        if "steps" in component:
            _compsteps = {}
            for step in component["steps"]:
                _compsteps[step["value"]] = {}
                if "metadata" in step:
                    if "localization_key" in step["metadata"]:
                        _compsteps[step["value"]]["locale_key"] = step["metadata"]["localization_key"]
                else:
                    _compsteps[step["value"]]["locale_key"] = ""
                if "key" in step:
                    _compsteps[step["value"]]["key"] = step["key"]

            if len(_compsteps) > 0:
                    result["steps"] = _compsteps
        if "permissions" in component:
            _compperm = {}
            for _permission in component["permissions"]:
                    if _permission["ability"] in ["visibility","access"]:
                        _compperm[_permission["ability"]] = _permission["value"]
            if len(_compperm) > 0:
                    result.update(_compperm)
        return result
                                


    def _parseLocale_bundleFile(self, _json):
        """
        Parse device locale_bundle.json file
        """
        result = {}
        for item in _json["locale_bundles"]:
            result[item["locale_key"]] = {}
            for transitem in item["localizations"]:
                result[item["locale_key"]][transitem["locale"]] = transitem["translation"]
        return result
    
    
    
    
    def _parseApplianceProfileContainer(self, applianceId, profileContainer, applianceParsedProfile):
        result = {}
        _idlists = list(filter(lambda item: f"{profileContainer['namespace']}.{profileContainer['name']}" in item["parent_interfaces"], 
                               applianceParsedProfile["id"]))
        for _idlist in _idlists:
            result[_idlist["id"]] = {key: _idlist[key] for 
                                        key in _idlist if key in 
                                        [
                                            "name",
                                            "visibility",
                                            "access",
                                            "unit",
                                            "min_value",
                                            "max_value",
                                            "increment"
                                            "type",
                                            "data_format",
                                            ]
                                        } 
            if(_idlist["type"] == "Container"):
                _subcontainer = self._parseApplianceProfileContainer(applianceId, _idlist, applianceParsedProfile)
                result[_idlist["id"]].update(_subcontainer)
            elif(_idlist["data_format"] == "array(struct)"):
                _subcontainer = {}
                _subcontainer["list"] = self._parseApplianceProfileContainer(applianceId, _idlist, applianceParsedProfile)
                result[_idlist["id"]].update(_subcontainer)
            else:    
                result[_idlist["id"]]["data_format"] = _idlist["data_format"] 
            
            if("steps" in _idlist):
                result[_idlist["id"]]["steps"] = {}
                for _containerstepkey,_containerstepvalue  in _idlist["steps"].items():
                    result[_idlist["id"]]["steps"][_containerstepkey] = {}
                    if("locale_key" in _containerstepvalue):
                        result[_idlist["id"]]["steps"][_containerstepkey]["transl"] = self._getTranslation(applianceId, _containerstepvalue["locale_key"])
                    if("key" in _containerstepvalue):
                        result[_idlist["id"]]["steps"][_containerstepkey]["key"] = _containerstepvalue["key"]
            if _idlist["locale_key"] in self._applianceTranslations[applianceId]:
                result[_idlist["id"]]["nameTransl"] = self._getTranslation(applianceId,_idlist["locale_key"])
        return result
                


    def _createApplianceProfile(self, 
                                applianceId, 
                                applianceParsedProfile):
        result = {}
        if(len(applianceParsedProfile) == 0):
            return None
            
        for _profkey, _profval in applianceParsedProfile.items():
            if ("0x" in _profkey):
                result[_profkey] = {key: _profval[key] for 
                         key in _profval if key in 
                         [
                            "name",
                            "data_format",
                            "visibility",
                            "access",
                            "unit",
                            "min_value",
                            "max_value",
                            "increment",
                            "path",
                            "type",
                            ]
                        } 
                if _profval["locale_key"] in self._applianceTranslations[applianceId]:
                    result[_profkey]["nameTransl"] = self._getTranslation(applianceId,_profval["locale_key"])
                if("steps" in _profval):
                    result[_profkey]["steps"] = []
                    for _stepval, _steplangkey in _profval["steps"].items():
                        if("locale_key" in _steplangkey and _steplangkey["locale_key"] in self._applianceTranslations[applianceId]):
                            result[_profkey]["steps"].append({_stepval:self._getTranslation(applianceId,_steplangkey["locale_key"])})
                if("type" in _profval and (_profval["type"] == "Container" or _profval["data_format"] == "array(struct)")):
                    result[_profkey]["container"] = []
                    _container = self._parseApplianceProfileContainer(applianceId, _profval, applianceParsedProfile)
                    result[_profkey]["container"].append(_container)
        return result
                

           
    def _parseApplianceState(self, 
                          stats, 
                          applianceId, 
                          raw = False):
        result = {}
        if(not raw and len(stats) > 0):
            for _item in stats:
                _hexHacl = f"0x{_item['haclCode']}"
                result[_hexHacl] = {key: _item[key] for 
                                    key in _item if key not in 
                                    [
                                        "haclCode", 
                                        "containers", 
                                        "description"
                                    ]}
                if(_hexHacl in self._applianceProfiles[applianceId]):
                    result[_hexHacl].update(
                        {key: self._applianceProfiles[applianceId][_hexHacl][key] for 
                         key in self._applianceProfiles[applianceId][_hexHacl] if key in 
                         [
                            "name",
                            "visibility",
                            "access",
                            "unit",
                            "nameTransl"
                            ]
                        })

                    if("steps" in self._applianceProfiles[applianceId][_hexHacl]):
                        for _step in self._applianceProfiles[applianceId][_hexHacl]["steps"]:
                            if str(_item["numberValue"]) in _step:
                                result[_hexHacl]["valueTransl"] = _step[str(_item["numberValue"])]
                if("containers" in _item and len(_item["containers"]) > 0):
                    result[_hexHacl]["container"] = self._parseApplianceStateContainer(
                             _item["containers"],
                             self._applianceProfiles[applianceId][_hexHacl]["container"],
                             )
        else:
            result = stats
        return result                

        

    def _parseApplianceStateItem(self, 
                              profileItem, 
                              stateItem):
        result = {}
        result[profileItem[0]] = {key:profileItem[1][key] for 
            key in profileItem[1] if key not in 
            [
                "steps", 
                "increment", 
                "min_value", 
                "max_value"]}
        result[profileItem[0]].update({key:stateItem[key] for 
                key in stateItem if key not in 
                [
                    "translation"]})
        if ("steps" in profileItem[1]):
            stepKey = None
            if (stateItem["numberValue"] in profileItem[1]["steps"]):
                stepKey = stateItem["numberValue"]
            elif (str(stateItem["numberValue"]) in profileItem[1]["steps"]):
                stepKey = str(stateItem["numberValue"])
            elif (("0x" + format(stateItem["numberValue"], "04X")) in profileItem[1]["steps"]):
                stepKey = "0x" + format(stateItem["numberValue"], "04X")
            if (stepKey != None and stepKey != "0" and 
                profileItem[1]["steps"][stepKey] not in ["", "UNIT"]):
                result[profileItem[0]]["valTransl"] = profileItem[1]["steps"][stepKey]["transl"]
        if ("unit" in profileItem[1]):
            result[profileItem[0]]["unit"] = profileItem[1]["unit"]
        if(profileItem[1]["data_format"] == "array(struct)"):
            self._parseApplianceStateItem(result, profileItem[1][key], stateItem)
        return result



    def _parseApplianceStateContainer(self, 
                                   stateContainer, 
                                   profileContainer):
        result = {}
        if(stateContainer):
            for profileItem in profileContainer[0].items():
                if(profileItem[1]["name"] != "List"):
                    for stateItem in stateContainer:
                        if stateItem["propertyName"] == profileItem[1]["name"]:
                            result.update(
                                self._parseApplianceStateItem(profileItem, stateItem)
                                )
                else:
                    result["list"] = {}
                    for profileListItem in profileItem[1]["list"].items():
                        for stateItem in stateContainer:
                            if stateItem["propertyName"] == profileListItem[1]["name"]:
                                result["list"].update(
                                    self._parseApplianceStateItem(profileListItem, stateItem)
                                    )
        return result



    def _sendApplianceCommand(self, 
                              applianceId, 
                              params, 
                              destination, 
                              source = "RP1", 
                              operationMode = "EXE", 
                              version = "ad"):
        """
        Send command to Electolux platform
        """
        appliance = self._applianceIndex.get(applianceId)
        
        components = []

        for param in params:
            if(not isinstance(param, dict)):
                raise Error("Parameters to send must be list of dicts")
            for key in param:
                if(param[key] == "Container"):
                    components.append({"name":key.removeprefix("0x"), "value":"Container"})
                else:
                    _intVal = 0
                    if(isinstance(param[key], str)
                       and param[key].startswith("0x")):
                        _intVal = int(param[key].removeprefix("0x"),16)
                    elif(isinstance(param[key], str)):
                        _intVal = int(param[key], 10)
                    else:
                        _intVal = param[key]
                    components.append({"name":key.removeprefix("0x"), "value":_intVal})
        if(appliance):
            _payload = {
                "components":components,
                "destination":destination,
                "operationMode":operationMode,
                "source":source,
                "timestamp":str(int(time.time())),
                "version":version
            }
            print(_payload)
            _json = json.loads(self._requestHttp(urls.setApplianceCommand(appliance),_payload).text)
            
            if(_json["status"] != "OK"):
                raise Error(_json["message"])

    def _getTranslation(self, applianceId, langKey):
        """
        Getting translation based on selected languages
        """
        
        if(langKey == None or langKey == ""):
            return ""
        _translation = None
        if(langKey in self._applianceTranslations[applianceId]):
            if(self._language == "All"):
                _translation = self._applianceTranslations[applianceId][langKey]
            elif(self._language in self._applianceTranslations[applianceId][langKey] 
                 and self._applianceTranslations[applianceId][langKey][self._language] != ""):
                _translation = self._applianceTranslations[applianceId][langKey][self._language]
            elif("eng" in self._applianceTranslations[applianceId][langKey]):
                _translation = self._applianceTranslations[applianceId][langKey]["eng"]
        return _translation


    def _requestHttp(self, operation, payload = None):
        """
        Request to Electrolux cloud
        """

        if(self._raw is True):
                print(f"--- url: {operation[1]!s} {operation[0]!s}")
                if(payload):
                    print("--- request body ---")
                    print(payload)
                    print("--- end request body ---")
        try:
            if (operation[1] == "GET"):
                response = requests.get(operation[0],
                                        headers=self._headers(), verify=self._verifySsl)
            elif (operation[1] == "POST"):
                response = requests.post(operation[0], json=payload,
                                        headers=self._headers(), verify=self._verifySsl)
            else:
                raise Error("Bad request definition")
            
            if(self._raw is True):
                print("--- respose body---")
                print(response.text)
                print("--- raw ending ---")
        
            if 2 != response.status_code // 100:
                raise ResponseError(response.status_code, response.text)

        except requests.exceptions.RequestException as ex:
            raise RequestError(ex)

        _validate_response(response)
        return response
           
    
    def login(self):
        """ 
        Login to API
        """
        if(os.path.exists(self._tokenFileName)):
            with open(self._tokenFileName, 'r') as cookieFile:
                self._sessionToken = cookieFile.read().strip()

            if(self._raw): print("--- token file found")

            try:
                self._getAppliancesList()

            except ResponseError as ErrorArg:
                if(ErrorArg.status_code == "ECP0105"):
                    if(self._raw): print("--- token probably expired")
                    self._sessionToken = None
                    os.remove(self._tokenFileName)
                else:
                    raise Exception(ErrorArg.text) from None

        if(self._sessionToken is None):
            self._createToken()
            with open(self._tokenFileName, 'w') as tokenFile:
                tokenFile.write(self._sessionToken)

            self._getAppliancesList()

            

    def getAppliances(self):
        """
        Get user registered appliances
        """
        if(self._sessionToken is None or
           self._applianceIndex is None):
            self.login()

        return self._applianceIndex
    
    

    def getApplianceConnectionState(self, 
            applianceId):
        """
        Get appliance connection state
        """
        appliance = self._applianceIndex.get(applianceId)

        if(appliance):
            _json = json.loads(self._requestHttp(urls.getApplianceConnectionState(appliance)).text)

            if(_json["status"] == "OK"):
                return {
                    'id': applianceId,
                    'status': _json["data"][0]["stringValue"],
                    'timestamp': _json["data"][0]["spkTimestamp"]
                }
            else:
                raise Exception (_json["message"])

        return None

    

    def getApplianceState(self, 
            applianceId, 
            paramName = None, 
            rawOutput = False):
        """
        Get appliance latest state from Electrolux platform
        paramName - comma separated list of patrameter names (None for all params)
        rawOutput - False: parse output
        """
        appliance = self._applianceIndex.get(applianceId)

        if(appliance):
            if(paramName):
                response = self._requestHttp(
                    urls.getApplianceParameterState(appliance, paramName))
            else:
                response = self._requestHttp(
                    urls.getApplianceAllStates(appliance))
            _json = json.loads(response.text)

            if(_json["status"] == "OK"):
                return self._parseApplianceState(
                    _json["data"], applianceId, raw = rawOutput)
            else:
                raise Exception (_json["message"])
        return None


    
    def getApplianceProfile(self, 
            applianceId):
        """
        Get appliance profile (params used by appliance, supported hacl's, and Id's, with translations)
        """
        if(self._applianceProfiles is None or
           self._applianceIndex is None):
            self.login()
            
        return self._applianceProfiles[applianceId]
    
    def setHacl(self,
            applianceId,
            hacl,
            haclValue,
            ):
        """
        send hacl value to appliance 
        hacl - parameter (hex format hacl - 0x0000)
        haclValue - value to set (for Container type, list of {Id: value} is required)
        """
        _paramslList = []
        if(self._applianceProfiles[applianceId][hacl]["access"] == "read"):
            raise Exception("Read-Only parameter")
        if("container" in self._applianceProfiles[applianceId][hacl]):
            if(not isinstance(haclValue, list)):
                raise Exception("Container type hacl, value must be list of dicts")
            else:
                _paramsList = [{hacl:"Container"}]
                _paramsList.extend(haclValue)
        else:
            _paramsList = [{hacl:haclValue}]
        print(_paramsList)  
        _dest = self._applianceProfiles[applianceId][hacl]["path"].split('/')[-1:][0]
        print(_dest)
        self._sendApplianceCommand(
            applianceId, 
            _paramsList, 
            _dest
            )

                            

    def registerMQTT(self):
        """
        Register device in Electrolux MQTT broker
        returns:
        Url - Host of MQTT broker (with port number)
        OrgId - Organization ID
        ClientId - MQTT Client ID
        DeviceToken - Token required to authentication
                        for IBM broker, use 'use-token-auth' as username, 
                        DeviceToken as password
                        
        """
        _json = json.loads(self._requestHttp(urls.registerMQTT(),None).text)
        
        if(_json["status"] == "ERROR"):
            if(_json["code"] == "ECP0206"):
                """ Device registered already, unregister first to get new token """
                self.unregisterMQTT()
                _json = json.loads(self._requestHttp(urls.registerMQTT(),None).text)
            else:
                raise Exception(_json["message"])

        if(_json["status"] == "OK"):
            return {
                'Url': _json["data"]["MQTTURL"],
                'OrgId': _json["data"]["ECP_org_id"],
                'DeviceToken': _json["data"]["DeviceToken"],
                'ClientID': _json["data"]["ClientID"],
            }
        else:
            raise Exception (_json["message"])
    

    
    def unregisterMQTT(self):
        """
        Unregister device from Electrolux MQTT broker
        """
        self._requestHttp(urls.unregisterMQTT(),None)

        
