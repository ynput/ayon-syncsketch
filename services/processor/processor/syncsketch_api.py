from __future__ import annotations

import io
from typing import Any, Iterable

import requests


class SessionClosed(Exception):
    pass


class SyncSketchAPI:
    def __init__(
        self,
        username: str,
        api_key: str,
        *,
        server_url: str | None = None,
    ) -> None:
        if server_url is None:
            server_url = "https://syncsketch.com"

        self.api_key = api_key
        self.username = username
        self.server_url = server_url

        self._session = requests.Session(base_url=server_url)

    def validate_credentials(self) -> None:
        response = self._session.get(
            "api/v1/person/connected/",
            params=self._get_params(),
        )
        response.raise_for_status()

    def get_account_info(self) -> list[dict[str, Any]]:
        if self._session is None or self._session.closed:
            raise SessionClosed("Syncsketch session is closed")

        params = self._get_params(
            active=1,
            offset=0,
        )
        output = []
        while True:
            response = self._session.get(
                self._get_api_endpoint("account"),
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            output.extend(data["objects"])
            meta = data["meta"]
            if not meta["next"]:
                break
        return output

    def get_projects(
        self,
        *,
        fields: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        params = self._get_params(
            active=1,
            is_archived=0,
            account__active=1,
            limit=100,
            offset=0,
        )
        if fields is not None:
            fields = set(fields)
            if "connections" in fields:
                params["withFullConnections"] = 1

            if fields:
                params["fields"] = ",".join(fields)

        output = []
        while True:
            data = self._do_get(
                "project",
                params=params,
            )
            output.extend(data["objects"])
            meta = data["meta"]
            if not meta["next"]:
                break
            params["offset"] = meta["offset"] + meta["limit"]

        return output

    def get_project_by_id(
        self,
        project_id: str,
        *,
        fields: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        params = self._get_params()
        if fields is not None:
            fields = set(fields)
            if fields:
                params["fields"] = ",".join(fields)

        return self._do_get(
            f"project/{project_id}",
            params=params,
        )

    def get_reviews(
        self,
        project_id: int | None = None,
        *,
        fields: Iterable[str] | None = None,
    ) -> list[dict[str, Any]]:
        limit = 100
        params = self._get_params(
            limit=limit,
            offset=0,
        )

        if fields is not None:
            fields = set(fields)
            if fields:
                params["fields"] = ",".join(fields)

        if project_id:
            params["project_id"] = project_id

        reviews = []
        while True:
            data = self._do_get(
                "review",
                api_version="v2",
                params=params,
            )
            reviews.extend(data)
            if len(data) < limit:
                break
            params["offset"] += limit

        return reviews

    def create_review(
        self,
        project_id: int,
        review_name: str,
        description: str = "",
        group: str = "",
    ) -> dict[str, Any]:
        body = {
            "project": f"/api/v1/project/{project_id}/",
            "name": review_name,
            "description": description,
            "group": group,
        }

        return self._do_post("review", body)

    def delete_review(self, review_id: str) -> None:
        self._do_delete(f"review/{review_id}/")

    def get_review_items(
        self,
        review_id: int | None = None,
        *,
        fields: Iterable[str] | None = None,
    ):
        params = self._get_params(
            offset=0,
            limit=100,
        )
        if review_id:
            params["reviews__id"] = review_id

        fields = self._convert_fields(fields)
        if fields:
            params["fields"] = fields

        output = []
        while True:
            data = self._do_get(
                "item",
                params=params,
            )
            output.extend(data["objects"])
            meta = data["meta"]
            if not meta["next"]:
                break
            params["offset"] = meta["offset"] + meta["limit"]

        return output

    def create_review_item_from_url(
        self,
        review_id: int,
        media_url: str,
        artist: str = "",
        description: str | None = None,
        name: str | None = None,
    ) -> dict[str, Any]:
        body = {
            "media_url": media_url,
            "artist": artist,
        }
        if description:
            body["description"] = description

        if name:
            body["name"] = name

        params = self._get_params()

        response = self._session.post(
            f"/items/uploadToReview/{review_id}/",
            params=params,
            data=body,
            headers={},
        )
        response.raise_for_status()
        return response.json()

    def create_review_item_from_stream(
        self,
        review_id: int,
        stream: io.BytesIO,
        name: str,
        artist: str = "",
        description: str | None = None,
    ):
        body = {
            "artist": artist,
            "name": name,
        }
        if description:
            body["description"] = description

        params = self._get_params()

        response = requests.post(
            f"/items/uploadToReview/{review_id}/",
            params=params,
            files={"reviewFile": stream},
            data=body,
            headers={},
        )
        response.raise_for_status()
        return response.json()

    def close(self):
        self._session.close()
        self._session = None

    def _do_get(
        self,
        endpoint: str,
        params: dict[str, Any],
        api_version: str | None = None,
    ) -> Any:
        self._validate_session()
        response = self._session.get(
            self._get_api_endpoint(endpoint, api_version=api_version),
            params=params,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()

    def _do_post(
        self,
        endpoint: str,
        body: dict[str, Any],
        api_version: str | None = None,
    ) -> Any:
        self._validate_session()
        params = self._get_params()
        response = self._session.post(
            self._get_api_endpoint(endpoint, api_version=api_version),
            params=params,
            json=body,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()

    def _do_delete(
        self,
        endpoint: str,
        api_version: str | None = None,
    ) -> Any:
        self._validate_session()
        params = self._get_params()
        response = self._session.delete(
            self._get_api_endpoint(endpoint, api_version=api_version),
            params=params,
        )
        response.raise_for_status()

    def _validate_session(self) -> None:
        if self._session is None:
            raise SessionClosed("Syncsketch session is closed")

    def _convert_fields(self, fields: Iterable[str] | None) -> str:
        if fields is None:
            return ""
        return ",".join(set(fields))

    def _get_api_endpoint(
        self, path: str, api_version: str | None = None
    ) -> str:
        if api_version is None:
            api_version = "v1"
        return f"/api/{api_version}/{path}/"

    def _get_params(self, **kwargs) -> dict[str, Any]:
        return {
            "api_key": self.api_key,
            "username": self.username,
            **kwargs,
        }
