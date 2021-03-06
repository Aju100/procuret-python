"""
Procuret Python
Api Request Module
author: hugh@blinkybeach.com
"""
import json
from procuret.ancillary.command_line import CommandLine
from procuret.http.method import HTTPMethod
from typing import TypeVar, Type, Optional, Dict, Union
from procuret.data.codable import Object, Array
from procuret.http.query_parameters import QueryParameters
from procuret.ancillary.abstract_session import AbstractSession
from procuret.ancillary.session_lifecycle import Lifecycle
from procuret.errors.api_error import ProcuretApiError
from datetime import datetime
import hmac
from hashlib import sha256
from base64 import b64encode
from urllib.request import HTTPError
from urllib.request import Request
from urllib.request import urlopen

T = TypeVar('T', bound='ApiRequest')

with open('VERSION') as versionfile:
    AGENT_VERSION = versionfile.read()

API_ENDPOINT = 'https://procuret.com/api'

CL = CommandLine.load()
OVERRIDE_ENDPOINT = CL.get(key='--procuret-api-endpoint')
if OVERRIDE_ENDPOINT is not None:
    API_ENDPOINT = OVERRIDE_ENDPOINT


class ApiRequest:

    API_KEY_NAME = 'x-procuret-api-key'
    SIGNATURE_KEY_NAME = 'x-procuret-signature'
    SESSION_ID_NAME = 'x-procuret-session-id'
    USER_AGENT = 'Procuret Python ' + AGENT_VERSION

    @classmethod
    def make(
        cls,
        path: str,
        method: HTTPMethod,
        data: Optional[Union[Object, Array]],
        session: Optional[AbstractSession],
        query_parameters: Optional[QueryParameters] = None,
        api_endpoint: str = API_ENDPOINT
    ) -> Optional[Union[Object, Array]]:
        """Return the decoded json body of a response from the Procuret API"""

        url = api_endpoint + path
        if query_parameters is not None:
            url = query_parameters.add_to(url)

        headers = {'User-Agent': cls.USER_AGENT}

        if session is not None:
            headers = cls._add_authorisation_to_headers(
                headers=headers,
                path=path,
                session=session
            )

        if data is not None:
            data = json.dumps(data).encode('utf-8')
            headers['Content-Type'] = 'application/json'

        request = Request(
            url=url,
            method=method.value,
            data=data,
            headers=headers
        )

        try:
            response = urlopen(request).read()
        except HTTPError as error:
            if error.code == 404:
                return None
            raise ProcuretApiError(error.code)

        return json.loads(response)

    @classmethod
    def _add_authorisation_to_headers(
        cls: Type[T],
        headers: Dict[str, str],
        path: str,
        session: AbstractSession
    ) -> Dict[str, str]:

        headers[cls.SESSION_ID_NAME] = str(session.session_id)

        if session.lifecycle == Lifecycle.SHORT_LIVED:
            return cls._headers_with_key(
                headers=headers,
                api_key=session.api_key
            )

        if session.lifecycle == Lifecycle.LONG_LIVED:
            return cls._headers_with_signature(
                headers=headers,
                api_key=session.api_key,
                path=path
            )

        raise NotImplementedError

    @classmethod
    def _headers_with_key(
        cls: Type[T],
        headers: Dict[str, str],
        api_key: str
    ) -> Dict[str, str]:

        headers[cls.API_KEY_NAME] = api_key
        return headers

    @classmethod
    def _headers_with_signature(
        cls: Type[T],
        headers: Dict[str, str],
        api_key: str,
        path: str
    ) -> Dict[str, str]:

        time = int(datetime.utcnow().timestamp())
        payload = (str(time - (time % 900)) + path).encode('utf-8')
        digest = hmac.new(api_key.encode('utf-8'), payload, sha256).digest()

        headers[cls.SIGNATURE_KEY_NAME] = b64encode(digest).decode()

        return headers
