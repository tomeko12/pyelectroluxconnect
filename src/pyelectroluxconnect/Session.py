""" Implements API wrapper to Electolux Connectivity Platform """

import hashlib
import json
import os
import requests
import time
import urllib3
import zipfile
import logging

from pyelectroluxconnect import urls
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

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
            verifySsl=True,
            region="emea",
            regionServer=None,
            customApiKey=None,
            customApiBrand=None):
        """
        username, password - Electrolux platform credentials
        country - 2-char country code
        language - 3-char language code for translations (All - for all delivered languages)
        tokenFileName - file to store auth token
        deviceId - custom id of Electrolux platform client
        verifySsl - verify Electrolux platform servers certs
        region = region name (currently tested: "emea", "apac", "latam", "na", "frigidaire")
        regionServer - region server URL (default - EMEA server)
        customApiKey - custom value of "x-ibm-client-id" and "x-api-key" HTTP headers
        customApiBrand - custom "brand" value (default is based on selected region) 
        """

        self._username = username
        self._password = password
        self._country = country
        self._language = language
        self._region = region
        self._deviceId = deviceId
        self._tokenFileName = os.path.expanduser(tokenFileName)
        self._sessionToken = None
        self._applianceIndex = {}
        self._applianceProfiles = {}
        self._applianceTranslations = {}

        if verifySsl is False:
            urllib3.disable_warnings(
                urllib3.exceptions.InsecureRequestWarning)
            self._verifySsl = verifySsl
        else:
            self._verifySsl = os.path.join(os.path.dirname(__file__),
                                           "certificatechain.pem")

        if regionServer is not None:
            urls.BASE_URL = regionServer
        elif region is not None:
            urls.BASE_URL = urls.getEcpClientUrl(region)

        if customApiKey is not None:
            urls.X_API_KEY = customApiKey

        if customApiBrand is not None:
            urls.BRAND = customApiBrand

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()
        self.unregisterMQTT()

    def _headers(self):
        headers = {
            "x-ibm-client-id": urls.getEcpClientId(self._region),
            "x-api-key": urls.getEcpClientId(self._region),
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
            "brand": urls.getEcpClientBrand(self._region),
            "country": self._country,
            "deviceId": self._deviceId,
            "password": self._password,
            "username": self._username
        }

        _LOGGER.debug("Getting new auth token")

        try:
            loginResp = json.loads(
                self._requestHttp(
                    urls.login(), _payload).text)
            if loginResp["status"] == "OK":
                self._sessionToken = loginResp["data"]["sessionKey"]
            else:
                _LOGGER.error(f'Unable to get session token: {loginResp["message"]}')
                raise Error(loginResp["message"])

        except ResponseError as ex:
            if(ex.status_code == 401
               or json.loads(ex.text)["code"] == "AER0802"
               or json.loads(ex.text)["code"] == "ECP0108"):
                _LOGGER.error(f'Login error: {json.loads(ex.text)["message"]}')
                raise LoginError(json.loads(ex.text)["message"]) from None
            else:
                _LOGGER.error(f'Authenticate error: {json.loads(ex.text)["message"]}')
                raise Error(json.loads(ex.text)["message"]) from None

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
					key: device[key] for
                      key in device if key in ["pnc", "elc", "sn", "mac", "cpv"]
                }

                if "nickname" in device:
                    self._applianceIndex[device["appliance_id"]]["alias"] = device["nickname"]
                else:
                    self._applianceIndex[device["appliance_id"]]["alias"] = ""

                self._getApplianceConfiguration(device["appliance_id"])

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
                applianceConfigFileName = list(
                    _json["data"][0]["configuration_file"])[0]
                deviceConfigId = _json["data"][0]["configuration_id"]
                applianceConfigFilePath = os.path.join(
                    str(Path.home()), applianceConfigFileName)

                """ Checking proper appliance configuration file exists"""
                if not((os.path.exists(applianceConfigFilePath)
                        and f'md5-{hashlib.md5(open(applianceConfigFilePath,"rb").read()).hexdigest()}' ==
                        _json["data"][0]["configuration_file"][applianceConfigFileName]["digest"])):
                    try:
                        _zipFile = self._requestHttp(
                            urls.getApplianceConfigurationFile(deviceConfigId))
                        open(applianceConfigFilePath, "wb").write(
                            _zipFile.content)
                    except requests.exceptions.RequestException as ex:
                        _LOGGER.error(f'Request error: {str(ex)}')
                        raise RequestError(ex)

                if(os.path.exists(applianceConfigFilePath)
                   and f'md5-{hashlib.md5(open(applianceConfigFilePath,"rb").read()).hexdigest()}' ==
                        _json["data"][0]["configuration_file"][applianceConfigFileName]["digest"]):
                    with zipfile.ZipFile(applianceConfigFilePath, "r") as archive:
                        self._applianceTranslations[id] = {}

                        _json = json.loads(
                            archive.read(
                                f'{archive.namelist()[0]}profile.json'))
                        _profile = self._parseProfileFile(_json, applianceId)

                        _json = json.loads(
                            archive.read(
                                f'{archive.namelist()[0]}{next(item for item in _json["bundles"] if item["type"] == "Localization")["path"]}'))

                        self._applianceTranslations[applianceId] = self._parseLocale_bundleFile(
                            _json)
                        self._applianceProfiles[applianceId] = self._createApplianceProfile(
                            applianceId,
                            _profile
                        )
                else:
                    _LOGGER.error("Unable to get device configuration file.")
                    raise Exception("Unable to get device configuration file.")
            else:
                _LOGGER.error(f"Unable to get configuration file version: {_json['message']}")
                raise Exception(_json["message"])

    def _parseProfileFile(self, _json, applianceId):
        """
        Parse device profile.json file
        """
        result = {}

        self._applianceIndex[applianceId]["group"] = _json["group"]
        if("brand" in _json and _json["brand"] != ""):
            self._applianceIndex[applianceId]["brand"] = _json["brand"]
        else:
            self._applianceIndex[applianceId]["brand"] = "Electrolux"
        if(_json["model_name"] == ""):
            _LOGGER.info("No model name in profile file, try to find in other sites")
            self._applianceIndex[applianceId]["model"] = self._findModel(
                applianceId)
        else:
            self._applianceIndex[applianceId]["model"] = _json["model_name"]

        result["id"] = []
        for modules in _json["modules"]:
            self._parseProfileModule(result, modules)

        return result

    def _parseProfileModule(self, result, modules):
        moduleName = modules["path"].split("/")[-1]
        for component in modules["components"]:
            if "hacl" in component:
                result[f'{moduleName}:{component["hacl"]["name"]}'] = self._parseProfileFileEntry(
                    modules["path"], component)
                result[f'{moduleName}:{component["hacl"]["name"]}']["source"] = moduleName
            elif "id" in component and "parent_interfaces" in component:
                _identry = self._parseProfileFileEntry(
                    modules["path"], component)
                _identry["id"] = component["id"]
                _identry["parent_interfaces"] = component["parent_interfaces"]
                result["id"].append(_identry)
        if("modules" in modules):
            for innermodules in modules["modules"]:
                self._parseProfileModule(result, innermodules)

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
        result["data_format"] = component["data_format"]["format"]
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
                if step["value"] not in _compsteps:
                    _compsteps[step["value"]] = {}
                    if "metadata" in step:
                        if "localization_key" in step["metadata"]:
                            _compsteps[step["value"]
                                       ]["locale_key"] = step["metadata"]["localization_key"]
                    else:
                        _compsteps[step["value"]]["locale_key"] = ""
                    if "key" in step:
                        _compsteps[step["value"]]["key"] = step["key"]

            if len(_compsteps) > 0:
                result["steps"] = _compsteps
        if "permissions" in component:
            _compperm = {}
            for _permission in component["permissions"]:
                if _permission["ability"] in ["visibility", "access"]:
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
                result[item["locale_key"]][transitem["locale"]
                                           ] = transitem["translation"]
        return result

    def _parseApplianceProfileContainer(self, applianceId, profileContainer, applianceParsedProfile):
        result = {}
        _idlists = list(filter(lambda item: f'{profileContainer["namespace"]}.{profileContainer["name"]}' in item["parent_interfaces"],
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
                "increment",
                "type",
                "data_format",
            ]
            }
            if(_idlist["type"] == "Container"):
                _subcontainer = self._parseApplianceProfileContainer(
                    applianceId, _idlist, applianceParsedProfile)
                result[_idlist["id"]].update(_subcontainer)
            elif(_idlist["data_format"] == "array(struct)"):
                _subcontainer = {}
                _subcontainer["list"] = self._parseApplianceProfileContainer(
                    applianceId, _idlist, applianceParsedProfile)
                result[_idlist["id"]].update(_subcontainer)
            else:
                result[_idlist["id"]]["data_format"] = _idlist["data_format"]

            if("steps" in _idlist):
                result[_idlist["id"]]["steps"] = {}
                for _containerstepkey, _containerstepvalue in _idlist["steps"].items():
                    result[_idlist["id"]]["steps"][_containerstepkey] = {}
                    if("locale_key" in _containerstepvalue):
                        result[_idlist["id"]]["steps"][_containerstepkey]["transl"] = self._getTranslation(
                            applianceId, _containerstepvalue["locale_key"])
                    if("key" in _containerstepvalue):
                        result[_idlist["id"]
                               ]["steps"][_containerstepkey]["key"] = _containerstepvalue["key"]
            if _idlist["locale_key"] in self._applianceTranslations[applianceId]:
                result[_idlist["id"]]["nameTransl"] = self._getTranslation(
                    applianceId, _idlist["locale_key"])
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
                    "source",
                ]
                }
                if _profval["locale_key"] in self._applianceTranslations[applianceId]:
                    result[_profkey]["nameTransl"] = self._getTranslation(
                        applianceId, _profval["locale_key"])
                if("steps" in _profval):
                    result[_profkey]["steps"] = []
                    for _stepval, _steplangkey in _profval["steps"].items():
                        if("locale_key" in _steplangkey and _steplangkey["locale_key"] in self._applianceTranslations[applianceId]):
                            result[_profkey]["steps"].append(
                                {_stepval: self._getTranslation(applianceId, _steplangkey["locale_key"])})
                if("type" in _profval and (_profval["type"] == "Container" or _profval["data_format"] == "array(struct)")):
                    result[_profkey]["container"] = []
                    _container = self._parseApplianceProfileContainer(
                        applianceId, _profval, applianceParsedProfile)
                    result[_profkey]["container"].append(_container)
        return result

    def _parseApplianceState(self,
                             stats,
                             applianceId,
                             rawOutput=False):
        result = {}
        if(not rawOutput and len(stats) > 0):
            for _item in stats:
                _hexHacl = f'{_item["source"]}:0x{_item["haclCode"]}'
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
                            if "numberValue" in _item and str(_item["numberValue"]) in _step:
                                result[_hexHacl]["valueTransl"] = _step[str(
                                    _item["numberValue"])]
                            elif "stringValue" in _item and _item["stringValue"] in _step:
                                result[_hexHacl]["valueTransl"] = _step[_item["stringValue"]]
                if("containers" in _item and len(_item["containers"]) > 0 and
                    _hexHacl in self._applianceProfiles[applianceId] and
                    "container" in self._applianceProfiles[applianceId][_hexHacl]
                   ):
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
        result[profileItem[0]] = {key: profileItem[1][key] for
                                  key in profileItem[1] if key not in
                                  [
            "steps",
            "increment",
            "min_value",
            "max_value"]}
        result[profileItem[0]].update({key: stateItem[key] for
                                       key in stateItem if key not in
                                       [
            "translation"]})
        if ("steps" in profileItem[1]):
            stepKey = None
            if (stateItem["numberValue"] in profileItem[1]["steps"]):
                stepKey = stateItem["numberValue"]
            elif (str(stateItem["numberValue"]) in profileItem[1]["steps"]):
                stepKey = str(stateItem["numberValue"])
            elif (f'0x{format(stateItem["numberValue"], "04X")}' in profileItem[1]["steps"]):
                stepKey = f'0x{format(stateItem["numberValue"], "04X")}'
            if (stepKey is not None and stepKey in profileItem[1]["steps"] and
                    profileItem[1]["steps"][stepKey] not in ["", "UNIT"]):
                result[profileItem[0]
                       ]["valTransl"] = profileItem[1]["steps"][stepKey]["transl"]
        if ("unit" in profileItem[1]):
            result[profileItem[0]]["unit"] = profileItem[1]["unit"]
        if(profileItem[1]["data_format"] == "array(struct)"):
            result[profileItem[0]]["list"] = self._parseApplianceStateItem(
                profileItem[1][key], stateItem)
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
                                self._parseApplianceStateItem(
                                    profileItem, stateItem)
                            )
                else:
                    result["list"] = {}
                    for profileListItem in profileItem[1]["list"].items():
                        for stateItem in stateContainer:
                            if stateItem["propertyName"] == profileListItem[1]["name"]:
                                result["list"].update(
                                    self._parseApplianceStateItem(
                                        profileListItem, stateItem)
                                )
        return result

    def _sendApplianceCommand(self,
                              applianceId,
                              params,
                              destination,
                              source="RP1",
                              operationMode="EXE",
                              version="ad"):
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
                    components.append(
                        {"name": key.removeprefix("0x"), "value": "Container"})
                else:
                    _intVal = 0
                    if(isinstance(param[key], str)
                       and param[key].startswith("0x")):
                        _intVal = int(param[key].removeprefix("0x"), 16)
                    elif(isinstance(param[key], str)):
                        _intVal = int(param[key], 10)
                    else:
                        _intVal = param[key]
                    components.append(
                        {"name": key.removeprefix("0x"), "value": _intVal})
        if(appliance):
            _payload = {
                "components": components,
                "destination": destination,
                "operationMode": operationMode,
                "source": source,
                "timestamp": str(int(time.time())),
                "version": version
            }
            _json = json.loads(self._requestHttp(
                urls.setApplianceCommand(appliance), _payload).text)

            if(_json["status"] != "OK"):
                raise Error(_json["message"])

    def _getTranslation(self, applianceId, langKey):
        """
        Getting translation based on selected languages
        """

        if(langKey is None or langKey == ""):
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

    def _requestHttp(self, operation, payload=None, verifySSL=None):
        """
        Request to Electrolux cloud
        """

        if (verifySSL is None):
            verifySSL = self._verifySsl

        _LOGGER.debug(f'URL: {operation[1]!s} {operation[0]!s}')
        if(payload):
            _LOGGER.debug(f"Request body: {str(payload).replace(self._password,'MaskedPassword').replace(self._username,'MaskedUsername')}")
        try:
            if (operation[1] == "GET"):
                response = requests.get(operation[0],
                                        headers=self._headers(), verify=verifySSL)
            elif (operation[1] == "POST"):
                response = requests.post(operation[0], json=payload,
                                         headers=self._headers(), verify=verifySSL)
            else:
                _LOGGER.error(f"Unsupported request definition: {operation[1]}")
                raise Error(f"Unsupported request definition: {operation[1]}")

            _LOGGER.debug(f"Respose body: {response.text}")

            if 2 != response.status_code // 100:
                raise ResponseError(response.status_code, response.text)

        except requests.exceptions.RequestException as ex:
            _LOGGER.error(f'Request error: {str(ex)}')
            raise RequestError(ex)

        _validate_response(response)
        return response

    def _findModel(self, applianceId):
        """
        Find model on https://www.electrolux-ui.com/ website
        """
        try:
            from bs4 import BeautifulSoup

            appliance = self._applianceIndex.get(applianceId)
            _LOGGER.info(f"Trying to get model {appliance['pnc']}_{appliance['elc']} info from https://www.electrolux-ui.com/ website")

            if(appliance):
                _html = self._requestHttp(
                    urls.getDocsTable(appliance), verifySSL=True).text

                soup = BeautifulSoup(_html, "html.parser")
                cols = soup.find("table", {"class": "SearchGridView"}).find(
                    "tr", {"class": "bottomBorder"}).find_all("td")
                if(cols[0].get_text().strip().startswith(f'{appliance["pnc"]}{appliance["elc"]}')):
                    return cols[1].get_text().strip()
                else:
                    return ""
        except Exception:
            return ""

    def login(self):
        """ 
        Login to API
        """
        if(os.path.exists(self._tokenFileName)):
            with open(self._tokenFileName, "r") as cookieFile:
                self._sessionToken = cookieFile.read().strip()

            _LOGGER.debug(f"Token file {self._tokenFileName} found")

            try:
                self._getAppliancesList()

            except ResponseError as ErrorArg:
                if(ErrorArg.status_code in ("ECP0105", "ECP0201")):
                    _LOGGER.warning("Token probably expired, trying to get new one.")
                    self._sessionToken = None
                    os.remove(self._tokenFileName)
                else:
                    _LOGGER.error(f"Error while get Appliances list: {ErrorArg.text}")
                    raise Exception(ErrorArg.text) from None
        else:
            _LOGGER.debug(f"Token file {self._tokenFileName} not found")

        if(self._sessionToken is None):
            self._createToken()
            with open(self._tokenFileName, "w") as tokenFile:
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
            _json = json.loads(self._requestHttp(
                urls.getApplianceConnectionState(appliance)).text)

            if(_json["status"] == "OK"):
                return {
                    "id": applianceId,
                    "status": _json["data"][0]["stringValue"],
                    "timestamp": _json["data"][0]["spkTimestamp"]
                }
            else:
                _LOGGER.error(f"Error while get appliance {applianceId} state: {_json['message']}")
                raise Exception(_json["message"])

        return None

    def getApplianceState(self,
                          applianceId,
                          paramName=None,
                          rawOutput=False):
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
                    _json["data"], applianceId, rawOutput=rawOutput)
            else:
                _LOGGER.error(f"Error while get appliance {applianceId} state: {_json['message']}")
                raise Exception(_json["message"])
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
                destination
                ):
        """
        send hacl value to appliance 
        hacl - parameter (hex format hacl - 0x0000)
        haclValue - value to set (for Container type, list of {Id: value} is required)
        destination - destination module name, from profile path (NIU, WD1, etc...)
        """
        if(f'{destination}:{hacl}' not in self._applianceProfiles[applianceId]):
            _LOGGER.error(f'Unable to set HACL {hacl}: Unknown destination:hacl combination ({destination}:{hacl})')
            raise Exception(
                f'Unknown destination:hacl combination ({destination}:{hacl})')
        if(self._applianceProfiles[applianceId][f'{destination}:{hacl}']["access"] == "read"):
            _LOGGER.error(f"Unable to set HACL {hacl}: Parameter is read-only (based on profile file)")
            raise Exception("Read-Only parameter")
        if("container" in self._applianceProfiles[applianceId][f'{destination}:{hacl}']):
            if(not isinstance(haclValue, list)):
                _LOGGER.error(f"Unable to set HACL {hacl}: Container type must be list of dicts")
                raise Exception(
                    "Container type hacl, value must be list of dicts")
            else:
                _paramsList = [{hacl: "Container"}]
                _paramsList.extend(haclValue)
        else:
            _paramsList = [{hacl: haclValue}]
        self._sendApplianceCommand(
            applianceId,
            _paramsList,
            destination
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
        _json = json.loads(self._requestHttp(urls.registerMQTT(), None).text)

        if(_json["status"] == "ERROR"):
            if(_json["code"] == "ECP0206"):
                """ Device registered already, unregister first to get new token """
                _LOGGER.info(f"Device registered already in Electrolux MQTT broker, unregistering to get new token")
                self.unregisterMQTT()
                _json = json.loads(self._requestHttp(
                    urls.registerMQTT(), None).text)
            else:
                _LOGGER.error(f"Error while register to Electrolux MQTT broker: {_json['message']}")
                raise Exception(_json["message"])

        if(_json["status"] == "OK"):
            return {
                "Url": _json["data"]["MQTTURL"],
                "OrgId": _json["data"]["ECP_org_id"],
                "DeviceToken": _json["data"]["DeviceToken"],
                "ClientID": _json["data"]["ClientID"],
            }
        else:
            _LOGGER.error(f"Error while register to Electrolux MQTT broker: {_json['message']}")
            raise Exception(_json["message"])

    def unregisterMQTT(self):
        """
        Unregister device from Electrolux MQTT broker
        """
        self._requestHttp(urls.unregisterMQTT(), None)
