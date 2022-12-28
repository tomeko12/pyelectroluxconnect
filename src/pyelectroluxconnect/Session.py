""" Implements API wrapper to Electolux Connectivity Platform """

import hashlib
import json
import os
import requests
import time
import urllib3
import zipfile
import logging
import traceback

from pyelectroluxconnect import urls
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

def _validate_response(response):
    """ Verify that response is OK """
    if response.status_code == 200:
        return
    raise HttpResponseError(response.status_code, response.text)


class Error(Exception):
    """ Session error """
    pass


class RequestError(Error):
    """ Wrapped requests.exceptions.RequestException """
    pass

class LoginError(Error):
    """ Login failed """
    pass

class AuthError(Error):
    """ Authfailed """
    pass


class HttpResponseError(Error):
    """ Unexcpected response """

    def __init__(self, status_code, text):
        super(HttpResponseError, self).__init__(
            "Invalid http response"
            ", status code: {0} - Data: {1}".format(
                status_code,
                text))
        self.status_code = status_code
        self.text = text

class ResponseError(Error):
    """ Unexcpected response """

    def __init__(self, status_code, message):
        super(ResponseError, self).__init__(
            "Invalid API response: {1} ({0})".format(
                status_code,
                message))
        self.status_code = status_code
        self.message = message


class Session(object):
    """
    Session object
    """

    def __init__(
            self,
            username,
            password,
            tokenFileName="~/.pyelectroluxconnect/electrolux-token.txt",
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

        try:
            _payload = {
                "brand": urls.getEcpClientBrand(self._region),
                "country": self._country,
                "deviceId": self._deviceId,
                "password": self._password,
                "username": self._username
            }
    
            _LOGGER.warn("Getting new auth token")
    
            loginResp = self._requestApi(urls.login(), _payload)
            self._sessionToken = loginResp["sessionKey"]
            try:
                if(not os.path.exists(os.path.expanduser("~/.pyelectroluxconnect/"))):
                    os.mkdir(os.path.expanduser("~/.pyelectroluxconnect/"))
                with open(self._tokenFileName, "w") as tokenFile:
                    tokenFile.write(self._sessionToken)
            except OSError as err:
                _LOGGER.error(f'Unable to write session token to file {self._tokenFileName}. {err.text}')
        except ResponseError as err:
            if(err.status_code == 401 or err.status_code in ("AER0802", "ECP0108")): 
                raise LoginError(f'{err.message} ({err.status_code})') from None
            else:
                raise ResponseError(err.status_code, err.message) from None
        except Exception as err:
            _LOGGER.error(err)
            raise

    def _getAppliancesList(self):
        """ 
        Get user registered appliances list
        """
        try:
            _json = self._requestApi(urls.getAppliances(self._username))
    
            for device in _json:
                if device:
                    self._applianceIndex[device["appliance_id"]] = {
    					key: device[key] for
                          key in device if key in ["pnc", "elc", "sn", "mac", "cpv"]
                    }
    
                    if "nickname" in device:
                        self._applianceIndex[device["appliance_id"]]["alias"] = device["nickname"]
                    else:
                        self._applianceIndex[device["appliance_id"]]["alias"] = ""
    
                    applianceProfile = self._getApplianceConfiguration(self._applianceIndex[device["appliance_id"]]["pnc"], 
                                                                       self._applianceIndex[device["appliance_id"]]["elc"], 
                                                                       self._applianceIndex[device["appliance_id"]]["sn"])
                    self._applianceIndex[device["appliance_id"]].update(applianceProfile["Attributes"])
                    self._applianceTranslations[device["appliance_id"]] = applianceProfile["Translations"]
                    self._applianceProfiles[device["appliance_id"]] = applianceProfile["Profiles"]
        except LoginError as err:
            raise LoginError(err) from None
        except AuthError as err:
            raise AuthError(err) from None
        except Exception as err:
            _LOGGER.exception(f'Exception in _getAppliancesList: {err}')
            raise Error(err) from None
        except Error as err:
            _LOGGER.error(err)
            raise

    def _getApplianceConfiguration(self, pnc, elc, sn):
        """
        Get appliance configuration file 
        """
        try:
            result = {}
            
            if(pnc and elc and sn):
                _json = self._requestApi(urls.getApplianceConfigurationVersion(pnc, elc, sn))
    
                applianceConfigFileName = list(
                    _json[0]["configuration_file"])[0]
                deviceConfigId = _json[0]["configuration_id"]
                applianceConfigFilePath = os.path.join(
                    str(Path.home()), f'.pyelectroluxconnect/{applianceConfigFileName}')

                """ Checking proper appliance configuration file exists"""
                if not((os.path.exists(applianceConfigFilePath)
                        and f'md5-{hashlib.md5(open(applianceConfigFilePath,"rb").read()).hexdigest()}' ==
                        _json[0]["configuration_file"][applianceConfigFileName]["digest"])):
                    try:
                        _zipFile = self._requestHttp(
                            urls.getApplianceConfigurationFile(deviceConfigId))
                        open(applianceConfigFilePath, "wb").write(
                            _zipFile.content)
                    except requests.exceptions.RequestException as ex:
                        raise RequestError(ex)

                if(os.path.exists(applianceConfigFilePath)
                   and f'md5-{hashlib.md5(open(applianceConfigFilePath,"rb").read()).hexdigest()}' ==
                        _json[0]["configuration_file"][applianceConfigFileName]["digest"]):

                    with zipfile.ZipFile(applianceConfigFilePath, "r") as archive:
                        result["Translations"] = {}

                        _json = json.loads(
                            archive.read(
                                f'{archive.namelist()[0]}profile.json'))
                        _profile = self._parseProfileFile(_json)

                        result["Attributes"] = self._getApplianceAttributes(_json, pnc, elc)
                        result["Attributes"]["pnc"] = pnc
                        result["Attributes"]["elc"] = elc
                        result["Attributes"]["sn"] = sn
                        

                        _json = json.loads(
                            archive.read(
                                f'{archive.namelist()[0]}{next(item for item in _json["bundles"] if item["type"] == "Localization")["path"]}'))

                        result["Translations"] = self._parseLocale_bundleFile(
                            _json)
                        result["Profiles"] = self._createApplianceProfile(
                            result["Translations"],
                            _profile
                        )
                        return result
                else:
                    raise Exception("Unable to get device configuration file.")
        except Exception as err:
            _LOGGER.exception(f'Exception in _getApplianceConfiguration({pnc},{elc},{sn}): {err}')
            raise Error(err) from None
        except Error as err:
            _LOGGER.error(err)
            raise

    def _parseProfileFile(self, _json):
        """
        Parse device profile.json file
        """
        try:
            result = {}
            result["id"] = []
            for modules in _json["modules"]:
                self._parseProfileModule(result, modules)
    
            return result
        except Exception as err:
            _LOGGER.exception(f'Exception in _parseProfileFile({_json}): {err}')
            raise Error(err)
        except Error as err:
            _LOGGER.error(err)
            raise

    def _getApplianceAttributes(self, _json, pnc, elc):
        """
        Get appliance attributes from json
        """
        try:
            result = {}
            for attr in ["group", "brand", "model_name"]:
                if attr in _json and _json[attr] != "":
                    result["model" if attr == "model_name" else attr] = _json[attr]
                else:
                    match attr:
                        case "group":
                            result["group"] = ""
                        case "brand":
                            result["brand"] = "Electrolux"
                        case "model_name":
                            result["model"] = self._findModel(pnc, elc)[0]
            return result
        except Exception as err:
            _LOGGER.exception(f'Exception in _getApplianceAttributes({_json},{pnc},{elc}): {err}')
            raise Error(err)
        except Error as err:
            _LOGGER.error(err)
            raise

    def _parseProfileModule(self, result, modules):
        try:
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
        except Exception as err:
            _LOGGER.exception(f'Exception in _parseProfileModule({result, modules}): {err}')
            raise Error(err)
        except Error as err:
            _LOGGER.error(err)
            raise
        
    def _parseProfileFileEntry(self, path, component):
        try:
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
        except Exception as err:
            _LOGGER.exception(f'Exception in _parseProfileFileEntry({path}, {component}): {err}')
            raise Error(err)
        except Error as err:
            _LOGGER.error(err)
            raise

    def _parseLocale_bundleFile(self, _json):
        """
        Parse device locale_bundle.json file
        """
        try:
            result = {}
            for item in _json["locale_bundles"]:
                result[item["locale_key"]] = {}
                for transitem in item["localizations"]:
                    result[item["locale_key"]][transitem["locale"]
                                               ] = transitem["translation"]
            return result
        except Exception as err:
            _LOGGER.exception(f'Exception in _parseLocale_bundleFile({_json}): {err}')
            raise Error(err)
        except Error as err:
            _LOGGER.error(err)
            raise

    def _parseApplianceProfileContainer(self, 
                                        applianceTranslations, 
                                        profileContainer, 
                                        applianceParsedProfile):
        try:
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
                        applianceTranslations, _idlist, applianceParsedProfile)
                    result[_idlist["id"]].update(_subcontainer)
                elif(_idlist["data_format"] == "array(struct)"):
                    _subcontainer = {}
                    _subcontainer["list"] = self._parseApplianceProfileContainer(
                        applianceTranslations, _idlist, applianceParsedProfile)
                    result[_idlist["id"]].update(_subcontainer)
                else:
                    result[_idlist["id"]]["data_format"] = _idlist["data_format"]
    
                if("steps" in _idlist):
                    result[_idlist["id"]]["steps"] = {}
                    for _containerstepkey, _containerstepvalue in _idlist["steps"].items():
                        result[_idlist["id"]]["steps"][_containerstepkey] = {}
                        if("locale_key" in _containerstepvalue):
                            result[_idlist["id"]]["steps"][_containerstepkey]["transl"] = self._getTranslation(
                                applianceTranslations, _containerstepvalue["locale_key"])
                        if("key" in _containerstepvalue):
                            result[_idlist["id"]
                                   ]["steps"][_containerstepkey]["key"] = _containerstepvalue["key"]
                if _idlist["locale_key"] in applianceTranslations:
                    result[_idlist["id"]]["nameTransl"] = self._getTranslation(
                        applianceTranslations, _idlist["locale_key"])
            return result
        except Exception as err:
            _LOGGER.exception(f'Exception in _parseApplianceProfileContainer({applianceTranslations},{profileContainer},{applianceParsedProfile}): {err}')
            raise Error(err) from None
        except Error as err:
            _LOGGER.error(err)
            raise

    def _createApplianceProfile(self,
                                applianceTranslations,
                                applianceParsedProfile):
        try:
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
                    if _profval["locale_key"] in applianceTranslations:
                        result[_profkey]["nameTransl"] = self._getTranslation(
                            applianceTranslations, _profval["locale_key"])
                    if("steps" in _profval):
                        result[_profkey]["steps"] = []
                        for _stepval, _steplangkey in _profval["steps"].items():
                            if("locale_key" in _steplangkey and _steplangkey["locale_key"] in applianceTranslations):
                                result[_profkey]["steps"].append(
                                    {_stepval: self._getTranslation(applianceTranslations, _steplangkey["locale_key"])})
                    if("type" in _profval and (_profval["type"] == "Container" or _profval["data_format"] == "array(struct)")):
                        result[_profkey]["container"] = []
                        _container = self._parseApplianceProfileContainer(
                            applianceTranslations, _profval, applianceParsedProfile)
                        result[_profkey]["container"].append(_container)
            return result
        except Exception as err:
            _LOGGER.exception(f'Exception in _createApplianceProfile({applianceTranslations},{applianceParsedProfile}): {err}')
            raise Error(err) from None
        except Error as err:
            _LOGGER.error(err)
            raise

    def _parseApplianceState(self,
                             status,
                             profile,
                             rawOutput=False):
        try:
            result = {}
            if(not rawOutput and len(status) > 0):
                for _item in status:
                    _hexHacl = f'{_item["source"]}:0x{_item["haclCode"]}'
                    result[_hexHacl] = {key: _item[key] for
                                        key in _item if key not in
                                        [
                                            "haclCode",
                                            "containers",
                                            "description"
                    ]}
                    if(_hexHacl in profile):
                        result[_hexHacl].update(
                            {key: profile[_hexHacl][key] for
                             key in profile[_hexHacl] if key in
                             [
                                "name",
                                "visibility",
                                "access",
                                "unit",
                                "nameTransl"
                            ]
                            })
    
                        if("steps" in profile[_hexHacl]):
                            for _step in profile[_hexHacl]["steps"]:
                                if "numberValue" in _item and str(_item["numberValue"]) in _step:
                                    result[_hexHacl]["valueTransl"] = _step[str(
                                        _item["numberValue"])]
                                elif "stringValue" in _item and _item["stringValue"] in _step:
                                    result[_hexHacl]["valueTransl"] = _step[_item["stringValue"]]
                    if("containers" in _item and len(_item["containers"]) > 0 and
                        _hexHacl in profile and
                        "container" in profile[_hexHacl]
                       ):
                        result[_hexHacl]["container"] = self._parseApplianceStateContainer(
                            _item["containers"],
                            profile[_hexHacl]["container"],
                        )
            else:
                result = status
            return result
        except Exception as err:
            _LOGGER.exception(f'Exception in _parseApplianceState({status},{profile},{rawOutput}): {err}')
            raise Error(err)
        except Error as err:
            _LOGGER.error(err)
            raise

    def _parseApplianceStateItem(self,
                                 profileItem,
                                 stateItem):
        try:
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
        except Exception as err:
            _LOGGER.exception(f'Exception in _parseApplianceStateItem({profileItem},{stateItem}): {err}')
            raise Error(err)
        except Error as err:
            _LOGGER.error(err)
            raise

    def _parseApplianceStateContainer(self,
                                      stateContainer,
                                      profileContainer):
        try:
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
        except Exception as err:
            _LOGGER.exception(f'Exception in _parseApplianceStateContainer({stateContainer},{profileContainer}): {err}')
            raise Error(err)
        except Error as err:
            _LOGGER.error(err)
            raise

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
        try:
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
                _json = self._requestApi(urls.setApplianceCommand(appliance), _payload)
        except Error:
            raise
        except Exception as err:
            _LOGGER.exception(f'Exception in _sendApplianceCommand({applianceId},{params},{destination},{source},{operationMode},{version}): {err}')
            raise Error(err)
        except Error as err:
            _LOGGER.error(err)
            raise

    def _getTranslation(self, applianceTranslations, langKey):
        """
        Getting translation based on selected languages
        """
        try:
            if(langKey is None or langKey == ""):
                return ""
            _translation = None
            if(langKey in applianceTranslations):
                if(self._language == "All"):
                    _translation = applianceTranslations[langKey]
                elif(self._language in applianceTranslations[langKey]
                     and applianceTranslations[langKey][self._language] != ""):
                    _translation = applianceTranslations[langKey][self._language]
                elif("eng" in applianceTranslations[langKey]):
                    _translation = applianceTranslations[langKey]["eng"]
            return _translation
        except Exception as err:
            _LOGGER.exception(f'Exception in _getTranslation({applianceTranslations}, {langKey}): {err}')
            raise Error(err)
        except Error as err:
            _LOGGER.error(err)
            raise

    def _requestHttp(self, operation, payload=None, verifySSL=None):
        """
        Request to Electrolux cloud
        """

        if (verifySSL is None):
            verifySSL = self._verifySsl

        _LOGGER.debug(f'HTTP Request {operation[1]!s}: {operation[0]!s}')
        _LOGGER.debug(f"HTTP Request headers: {self._headers()}")
        if(payload):
            _LOGGER.debug(f"HTTP Request body: {str(payload).replace(self._password,'MaskedPassword').replace(self._username,'MaskedUsername')}")
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

            _LOGGER.debug(f"HTTP Respose body: {response.text}")

            if 2 != response.status_code // 100:
                raise HttpResponseError(response.status_code, response.text) from None

        except requests.exceptions.RequestException as ex:
            raise RequestError(ex) from None

        return response
    
    
    def _requestApi(self, operation, payload=None):
        """
        Request to API
        returns JSON response
        """
        try:
            jsonresponse =  json.loads(self._requestHttp(
                        operation, payload).text)
            if(jsonresponse["status"] != "OK"):
                raise ResponseError(jsonresponse["code"], jsonresponse["message"]) from None
            return jsonresponse["data"]
        
        except RequestError as err:
            _LOGGER.error(f'API request error: {err}')
            raise Exception(err) from None
        except ResponseError as err:
            if(err.status_code in ("ECP0105", "ECP2004")):
                _LOGGER.warn(f'API token error {err.status_code}: {err.message}')
                try:
                    self._createToken()
                    return json.loads(self._requestHttp(
                            operation, payload).text)["data"]
                except LoginError as err:
                    raise LoginError(err) from None
                except AuthError(err):
                    raise AuthError(err) from None
            else:
                _LOGGER.error(f'API response error {err.status_code}: {err.message}')
                raise ResponseError(err.status_code, err.message) from None
        except HttpResponseError as err:
            message = err.text
            errcode = err.status_code
            
            try:
                message = json.loads(err.text)
                if("code" in message):
                    errcode = message["code"]
                if("message" in message):
                    message = message["message"]
                raise ResponseError(errcode, message) from None
            except ValueError:
                _LOGGER.error(f'HTTP response error {err.status_code}: {err.text}')
                raise HttpResponseError(err.status_code, err.text) from None
            raise ResponseError(err.status_code, err.text) from None
        except Exception as err:
            _LOGGER.error(f'API request error: {err}')
            raise
        
            
        

    def _findModel(self, pnc, elc):
        """
        Find model on https://www.electrolux-ui.com/ website
        """
        appliancesModelFilePath = os.path.join(
                        str(Path.home()), f'.pyelectroluxconnect/models.json')
        appliancesModels = {}
        model = ""
        brand = ""
        
        try:
            _LOGGER.debug(f"Trying to get model {pnc}_{elc} info from cache")
            if(os.path.exists(appliancesModelFilePath)):
                with open(appliancesModelFilePath, "r") as modelsFile:
                    appliancesModels = json.load(modelsFile)
                    if(f'{pnc}{elc}' in appliancesModels):
                        model = appliancesModels[f'{pnc}{elc}']["model"]
                        brand = appliancesModels[f'{pnc}{elc}']["brand"]
                        return (model, brand)
        except:
            pass
             
        try:
            from bs4 import BeautifulSoup

            _LOGGER.debug(f"Trying to get model {pnc}_{elc} info from https://www.electrolux-ui.com/ website")

            if(pnc and elc):
#                _html = self._requestHttp(
#                    urls.getDocsTable(pnc, elc), verifySSL=True).text
                _html = requests.get(urls.getDocsTable(pnc, elc)[0], verify=True, timeout=10).text

                soup = BeautifulSoup(_html, "html.parser")
                cols = soup.find("table", {"class": "SearchGridView"}).find(
                    "tr", {"class": "bottomBorder"}).find_all("td")
                if(cols[0].get_text().strip().startswith(f'{pnc}{elc}')):
                    model = cols[1].get_text().strip()
                    brand = cols[4].get_text().strip()
                    if(os.path.exists(appliancesModelFilePath)):
                        with open(appliancesModelFilePath, "r") as modelsFile:
                            appliancesModels = json.load(modelsFile)
                    appliancesModels[f'{pnc}{elc}'] = {}
                    appliancesModels[f'{pnc}{elc}']["model"] = model
                    appliancesModels[f'{pnc}{elc}']["brand"] = brand    
                    with open(appliancesModelFilePath, "w") as modelsFile:
                        json.dump(appliancesModels, modelsFile)
        except Exception:
            pass

        return (model, brand)

    def login(self):
        """ 
        Login to API
        """
        try:
            try:
                if(os.path.exists(self._tokenFileName)):
                    with open(self._tokenFileName, "r") as tokenFile:
                        self._sessionToken = tokenFile.read().strip()
                else:
                    _LOGGER.debug(f"Token file {self._tokenFileName} not found, trying to get new one.")
                    self._createToken()
            except OSError as err:
                _LOGGER.error(f'Unable to open token file {self._tokenFileName}: {err.text}')
            else:
                try:
                    self._getAppliancesList()
                except LoginError as err:
                    raise LoginError(err) from None
                except AuthError as err:
                    raise AuthError(err) from None
                except Exception as ErrorArg:
                    _LOGGER.error(f"Error while get Appliances list: {ErrorArg}")
                    raise Exception(ErrorArg) from None
        except Exception as err:
            _LOGGER.error(err)
            raise

    def getAppliances(self):
        """
        Get user registered appliances
        """
        if(self._sessionToken is None or
           self._applianceIndex is {}):
            self.login()

        return self._applianceIndex

    def getApplianceConnectionState(self,
                                    applianceId):
        """
        Get appliance connection state
        """
        appliance = self._applianceIndex.get(applianceId)

        if(appliance):
            _json = self._requestApi(
                urls.getApplianceConnectionState(appliance))

            if(_json["status"] == "OK"):
                return {
                    "id": applianceId,
                    "status": _json[0]["stringValue"],
                    "timestamp": _json[0]["spkTimestamp"]
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
        try:
            appliance = self._applianceIndex.get(applianceId)
    
            if(appliance):
                _json = None
                if(paramName):
                    _json = self._requestApi(
                        urls.getApplianceParameterState(appliance, paramName))
                else:
                    _json = self._requestApi(
                        urls.getApplianceAllStates(appliance))
    
                return self._parseApplianceState(
                     _json, self._applianceProfiles[applianceId], rawOutput=rawOutput)
            return None
        except Exception as err:
            _LOGGER.error(err)
            raise

    def getApplianceProfile(self,
                            applianceId):
        """
        Get appliance profile (params used by appliance, supported hacl's, and Id's, with translations)
        """
        if(self._applianceProfiles is None or
           self._applianceIndex is None):
            self.login()

        return self._applianceProfiles[applianceId]

    def getCustomPncApplianceProfile(self,
                            pnc, elc, sn):
        """
        Get custom defined appliance profile (params used by appliance, supported hacl's, and Id's, with translations)
        pnc - 9 digits PNC number
        elc - 2 digits ELC number
        sn - serial number
        """

        return self._getApplianceConfiguration(pnc, elc, sn)
    
    def parseCustomApplianceState(self, json):
        """
        Parse custom json appliance state response
        json - raw json response from i.e. getApplianceState(...., rawOutput=True)
        """
        if("data" in json):
            json = json["data"]
        
        pnc = next((item for item in json if item["haclCode"] == "0007"), None)
        elc = next((item for item in json if item["haclCode"] == "000A"), None)
        sn = next((item for item in json if item["haclCode"] == "0002"), None)
        
                
        if(pnc and elc and  sn):
            return self._parseApplianceState(
                                            json,
                                            self.getCustomPncApplianceProfile(pnc["stringValue"],
                                                                            elc["stringValue"],
                                                                            sn["stringValue"])["Profiles"]
                                            )
        else:
            return None


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
        try:
            if(f'{destination}:{hacl}' not in self._applianceProfiles[applianceId]):
                raise Exception(
                    f'Unable to set HACL {hacl}: Unknown destination:hacl combination ({destination}:{hacl})')
            if(self._applianceProfiles[applianceId][f'{destination}:{hacl}']["access"] == "read"):
                raise Exception(f"Unable to set HACL {hacl}: Parameter is read-only (based on profile file)")
            if("container" in self._applianceProfiles[applianceId][f'{destination}:{hacl}']):
                if(not isinstance(haclValue, list)):
                    raise Exception(f"Unable to set HACL {hacl}: Container type must be list of dicts")
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
        except Exception as err:
            _LOGGER.error(err)
            raise

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
        try:
            _json = self._requestApi(urls.registerMQTT(), None)
        except ResponseError as err:
            if(err.status_code == "ECP0206"):
                """ Device registered already, unregister first to get new token """
                _LOGGER.warn(f"Device registered already in Electrolux MQTT broker, unregistering to get new token")
                self.unregisterMQTT()
                _json = self._requestApi(
                    urls.registerMQTT(), None)
            else:
                raise
        finally:
            return {
                "Url": _json["MQTTURL"],
                "OrgId": _json["ECP_org_id"],
                "DeviceToken": _json["DeviceToken"],
                "ClientID": _json["ClientID"],
            }



    def unregisterMQTT(self):
        """
        Unregister device from Electrolux MQTT broker
        """
        self._requestApi(urls.unregisterMQTT(), None)
