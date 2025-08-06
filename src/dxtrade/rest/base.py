"""Base class for REST API endpoints."""

from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Type
from typing import TypeVar
from typing import Union

import httpx
from pydantic import ValidationError

from dxtrade.errors import DXtradeDataError
from dxtrade.errors import DXtradeHTTPError
from dxtrade.http import DXtradeHTTPClient
from dxtrade.models import DataResponse
from dxtrade.models import DXtradeBaseModel
from dxtrade.models import PaginatedResponse

T = TypeVar("T", bound=DXtradeBaseModel)


class BaseAPI:
    """Base class for REST API endpoints."""
    
    def __init__(self, http_client: DXtradeHTTPClient) -> None:
        """Initialize base API.
        
        Args:
            http_client: HTTP client instance
        """
        self.http_client = http_client
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], bytes, str]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> httpx.Response:
        """Make authenticated HTTP request.
        
        Args:
            method: HTTP method
            endpoint: API endpoint
            params: Query parameters
            data: Request data
            json: JSON data
            headers: Additional headers
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            HTTP response
            
        Raises:
            DXtradeHTTPError: HTTP error
        """
        return await self.http_client.request(
            method=method,
            url=endpoint,
            params=params,
            data=data,
            json=json,
            headers=headers,
            timeout=timeout,
            idempotency_key=idempotency_key,
        )
    
    async def _get_data(
        self,
        endpoint: str,
        model_class: Type[T],
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> T:
        """Get single data object from API.
        
        Args:
            endpoint: API endpoint
            model_class: Pydantic model class
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout
            
        Returns:
            Parsed data object
            
        Raises:
            DXtradeDataError: Data validation error
        """
        response = await self._request("GET", endpoint, params=params, headers=headers, timeout=timeout)
        return await self._parse_response(response, model_class)
    
    async def _get_list(
        self,
        endpoint: str,
        model_class: Type[T],
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> List[T]:
        """Get list of data objects from API.
        
        Args:
            endpoint: API endpoint
            model_class: Pydantic model class
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout
            
        Returns:
            List of parsed data objects
            
        Raises:
            DXtradeDataError: Data validation error
        """
        response = await self._request("GET", endpoint, params=params, headers=headers, timeout=timeout)
        return await self._parse_list_response(response, model_class)
    
    async def _get_paginated(
        self,
        endpoint: str,
        model_class: Type[T],
        *,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
    ) -> PaginatedResponse:
        """Get paginated data from API.
        
        Args:
            endpoint: API endpoint
            model_class: Pydantic model class
            params: Query parameters
            headers: Additional headers
            timeout: Request timeout
            
        Returns:
            Paginated response with parsed data
            
        Raises:
            DXtradeDataError: Data validation error
        """
        response = await self._request("GET", endpoint, params=params, headers=headers, timeout=timeout)
        return await self._parse_paginated_response(response, model_class)
    
    async def _post_data(
        self,
        endpoint: str,
        model_class: Type[T],
        *,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], bytes, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> T:
        """Post data and get response object.
        
        Args:
            endpoint: API endpoint
            model_class: Pydantic model class
            json: JSON data
            data: Request data
            headers: Additional headers
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            Parsed response object
            
        Raises:
            DXtradeDataError: Data validation error
        """
        response = await self._request(
            "POST", endpoint, json=json, data=data, headers=headers,
            timeout=timeout, idempotency_key=idempotency_key
        )
        return await self._parse_response(response, model_class)
    
    async def _put_data(
        self,
        endpoint: str,
        model_class: Type[T],
        *,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], bytes, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> T:
        """Put data and get response object.
        
        Args:
            endpoint: API endpoint
            model_class: Pydantic model class
            json: JSON data
            data: Request data
            headers: Additional headers
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            Parsed response object
            
        Raises:
            DXtradeDataError: Data validation error
        """
        response = await self._request(
            "PUT", endpoint, json=json, data=data, headers=headers,
            timeout=timeout, idempotency_key=idempotency_key
        )
        return await self._parse_response(response, model_class)
    
    async def _patch_data(
        self,
        endpoint: str,
        model_class: Type[T],
        *,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Union[Dict[str, Any], bytes, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> T:
        """Patch data and get response object.
        
        Args:
            endpoint: API endpoint
            model_class: Pydantic model class
            json: JSON data
            data: Request data
            headers: Additional headers
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            Parsed response object
            
        Raises:
            DXtradeDataError: Data validation error
        """
        response = await self._request(
            "PATCH", endpoint, json=json, data=data, headers=headers,
            timeout=timeout, idempotency_key=idempotency_key
        )
        return await self._parse_response(response, model_class)
    
    async def _delete_data(
        self,
        endpoint: str,
        model_class: Optional[Type[T]] = None,
        *,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        idempotency_key: Optional[str] = None,
    ) -> Optional[T]:
        """Delete resource and optionally get response object.
        
        Args:
            endpoint: API endpoint
            model_class: Optional pydantic model class
            headers: Additional headers
            timeout: Request timeout
            idempotency_key: Idempotency key
            
        Returns:
            Parsed response object or None
            
        Raises:
            DXtradeDataError: Data validation error
        """
        response = await self._request(
            "DELETE", endpoint, headers=headers, timeout=timeout,
            idempotency_key=idempotency_key
        )
        
        if model_class and response.content:
            return await self._parse_response(response, model_class)
        
        return None
    
    async def _parse_response(self, response: httpx.Response, model_class: Type[T]) -> T:
        """Parse API response into model object.
        
        Args:
            response: HTTP response
            model_class: Pydantic model class
            
        Returns:
            Parsed model object
            
        Raises:
            DXtradeDataError: Data validation error
        """
        try:
            response_data = response.json()
        except Exception as e:
            raise DXtradeDataError(f"Failed to parse JSON response: {e}") from e
        
        # Handle wrapped responses
        if isinstance(response_data, dict) and "data" in response_data:
            data = response_data["data"]
        else:
            data = response_data
        
        try:
            return model_class.model_validate(data)
        except ValidationError as e:
            raise DXtradeDataError(
                f"Failed to validate {model_class.__name__}: {e}",
                data=data
            ) from e
    
    async def _parse_list_response(self, response: httpx.Response, model_class: Type[T]) -> List[T]:
        """Parse API response into list of model objects.
        
        Args:
            response: HTTP response
            model_class: Pydantic model class
            
        Returns:
            List of parsed model objects
            
        Raises:
            DXtradeDataError: Data validation error
        """
        try:
            response_data = response.json()
        except Exception as e:
            raise DXtradeDataError(f"Failed to parse JSON response: {e}") from e
        
        # Handle wrapped responses
        if isinstance(response_data, dict) and "data" in response_data:
            data = response_data["data"]
        else:
            data = response_data
        
        if not isinstance(data, list):
            raise DXtradeDataError(f"Expected list response, got {type(data)}", data=data)
        
        try:
            return [model_class.model_validate(item) for item in data]
        except ValidationError as e:
            raise DXtradeDataError(
                f"Failed to validate {model_class.__name__} list: {e}",
                data=data
            ) from e
    
    async def _parse_paginated_response(
        self, response: httpx.Response, model_class: Type[T]
    ) -> PaginatedResponse:
        """Parse paginated API response.
        
        Args:
            response: HTTP response
            model_class: Pydantic model class
            
        Returns:
            Paginated response
            
        Raises:
            DXtradeDataError: Data validation error
        """
        try:
            response_data = response.json()
        except Exception as e:
            raise DXtradeDataError(f"Failed to parse JSON response: {e}") from e
        
        if not isinstance(response_data, dict):
            raise DXtradeDataError(
                f"Expected dict response for paginated data, got {type(response_data)}",
                data=response_data
            )
        
        # Extract data and pagination info
        data = response_data.get("data", [])
        pagination = response_data.get("pagination", {})
        
        if not isinstance(data, list):
            raise DXtradeDataError(f"Expected list in data field, got {type(data)}", data=data)
        
        try:
            parsed_data = [model_class.model_validate(item) for item in data]
        except ValidationError as e:
            raise DXtradeDataError(
                f"Failed to validate {model_class.__name__} list: {e}",
                data=data
            ) from e
        
        return PaginatedResponse(
            success=response_data.get("success", True),
            data=parsed_data,
            pagination=pagination,
            timestamp=response_data.get("timestamp"),
        )