from __future__ import annotations

import io
import logging
from typing import Any

import ayon_api

from .lib import SyncsketchConfig
from .syncsketch_api import SyncSketchAPI


class SyncError(Exception):
    pass


def push_review_to_syncsketch(
    event: dict[str, Any],
    credentials: SyncsketchConfig,
) -> None:
    """Push review to SyncSketch server."""
    project_name = event["project"]
    list_id = event["summary"]["listId"]

    logging.info(
        f"Pushing review session '{list_id}' for project {project_name}"
    )
    ayon_list_entity = ayon_api.get_entity_list_rest(project_name, list_id)
    if ayon_list_entity is None:
        msg = f"Failed to find list '{list_id}' in project '{project_name}'."
        logging.error(msg)
        raise SyncError(msg)

    if ayon_list_entity["entityType"] != "version":
        msg = (
            f"List '{list_id}' in project '{project_name}'"
            f" is not a version list."
        )
        logging.error(msg)
        raise SyncError(msg)

    if not ayon_list_entity["items"]:
        msg = (
            f"List '{list_id}' in project '{project_name}' is empty. "
            "Nothing to push to SyncSketch."
        )
        logging.error(msg)
        raise SyncError(msg)

    syncsketch_api = SyncSketchAPI(
        username=credentials.username,
        api_key=credentials.api_key,
        server_url=credentials.server_url,
    )
    project_id: int | None = None
    for project in syncsketch_api.get_projects(fields={"id", "name"}):
        if project["name"] == project_name:
            project_id = project["id"]
            break

    if project_id is None:
        msg = f"Failed to find SyncSketch project with name '{project_name}'"
        logging.error(msg)
        raise SyncError(msg)

    label = ayon_list_entity["label"]
    sketch_review: dict[str, Any] = {}
    for review in syncsketch_api.get_reviews(project_id):
        if review["name"] == label:
            sketch_review = review
            sketch_review["items"] = syncsketch_api.get_review_items(
                sketch_review["id"]
            )
            break

    if not sketch_review:
        sketch_review = syncsketch_api.create_review(project_id, label)
        logging.info(
            f"Created review session '{label}'"
            f" in SyncSketch project '{project_name}'"
        )

    # TODO this logic requires
    #   https://github.com/ynput/ayon-backend/issues/985
    syncsketch_ids = {item["id"] for item in sketch_review["items"]}
    new_items = []
    for ayon_item in ayon_list_entity["items"]:
        syncsketch_id = ayon_item["data"].get("syncsketch_id")
        if syncsketch_id not in syncsketch_ids:
            new_items.append(ayon_item)

    if not new_items:
        logging.info(
            f"Review session '{label}' in SyncSketch project '{project_name}'"
            " is up to date. Nothing to push."
        )
        return

    for ayon_item in new_items:
        version_id = ayon_item in["entityId"]
        reviewable_id: str | None = ayon_item["data"].get("reviewable")
        if reviewable_id is None:
            response = ayon_api.get(
                f"projects/{project_name}/versions/{version_id}/reviewables")
            response.raise_for_status()
            reviewable_id = next(
                (r["fileId"] for r in response.data["reviewables"]),
                None
            )

        if reviewable_id is None:
            logging.info(
                f"Skipped item with version id '{version_id}'"
                f" because it has no reviewable"
            )
            continue

        file_info_response = ayon_api.get(
            f"projects/{project_name}/files/{reviewable_id}/info"
        )
        file_info_response.raise_for_status()
        filename = file_info_response.data["filename"]
        file_response = ayon_api.raw_get(
            f"projects/{project_name}/files/{reviewable_id}",
            allow_redirects=False
        )
        location = file_response.headers["location"]
        if location.lower().startswith("/api/"):
            stream = io.BytesIO()
            ayon_api.download_project_file_to_stream(
                project_name, reviewable_id, stream
            )
            stream.seek(0)

            item = syncsketch_api.create_review_item_from_stream(
                review_id=sketch_review["id"],
                stream=stream,
                name=filename,
            )
            logging.info(
                "Added item by downloading it from AYON and uploading to"
                f" review session '{label}' in SyncSketch project"
                f" '{project_name}'"
            )

        else:
            media_url = location
            item = syncsketch_api.create_review_item_from_url(
                review_id=sketch_review["id"],
                media_url=media_url,
                name=filename,
            )
            logging.info(
                f"Added item with url '{media_url}' to review session"
                f" '{label}' in SyncSketch project '{project_name}'"
            )

        ayon_api.update_entity_list_item(
            project_name,
            list_id,
            ayon_item["id"],
            data={"syncsketch_id": item["id"]},
            # TODO remove when ayon_api has this filled with default value
            new_list_id=None,
        )


def pull_comment_from_syncsketch(
    event: dict[str, Any],
    credentials: SyncsketchConfig,
) -> None:
    project_name = event["project"]
    list_id = event["summary"]["listId"]

    logging.info(
        f"Pulling notes and drawings from review session"
        f" for list '{list_id}' in project {project_name}"
    )
    ayon_list_entity = ayon_api.get_entity_list_rest(project_name, list_id)
    if ayon_list_entity is None:
        msg = f"Failed to find list '{list_id}' in project '{project_name}'."
        logging.error(msg)
        raise SyncError(msg)

    if ayon_list_entity["entityType"] != "version":
        msg = (
            f"List '{list_id}' in project '{project_name}'"
            f" is not a version list."
        )
        logging.error(msg)
        raise SyncError(msg)

    if not ayon_list_entity["items"]:
        msg = (
            f"List '{list_id}' in project '{project_name}' is empty. "
            "Nothing to pull from SyncSketch."
        )
        logging.error(msg)
        raise SyncError(msg)

    syncsketch_api = SyncSketchAPI(
        username=credentials.username,
        api_key=credentials.api_key,
        server_url=credentials.server_url,
    )
    project_id: int | None = None
    for project in syncsketch_api.get_projects(fields={"id", "name"}):
        if project["name"] == project_name:
            project_id = project["id"]
            break

    if project_id is None:
        msg = f"Failed to find SyncSketch project with name '{project_name}'"
        logging.error(msg)
        raise SyncError(msg)

    label = ayon_list_entity["label"]
    sketch_review: dict[str, Any] = {}
    for review in syncsketch_api.get_reviews(project_id):
        if review["name"] == label:
            sketch_review = review
            sketch_review["items"] = syncsketch_api.get_review_items(
                sketch_review["id"]
            )
            break

    if not sketch_review:
        msg = (
            f"Failed to find SyncSketch review session with name '{label}'"
            f" in project '{project_name}'"
        )
        logging.error(msg)
        raise SyncError(msg)

    # TODO implement
    raise SyncError("Push is not yet implemented")
