from __future__ import annotations

from datetime import datetime
import io
import logging
from typing import Any
import urllib.request

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
    event_summary = event["summary"]
    list_id: str = event_summary["listId"]
    summary_sketch_project: str | None = event_summary.get(
        "syncsketchProject"
    )

    logging.info(
        f"Pushing review session '{list_id}' from AYON project {project_name}"
    )
    ayon_list_entity = ayon_api.get_entity_list_rest(project_name, list_id)
    if ayon_list_entity is None:
        msg = (
            f"Failed to find list '{list_id}'"
            f" in AYON project '{project_name}'."
        )
        logging.error(msg)
        raise SyncError(msg)

    if ayon_list_entity["entityType"] != "version":
        msg = (
            f"List '{list_id}' in AYON project '{project_name}'"
            f" is not a version list."
        )
        logging.error(msg)
        raise SyncError(msg)

    if not ayon_list_entity["items"]:
        msg = (
            f"List '{list_id}' in AYON project '{project_name}' is empty. "
            "Nothing to push to SyncSketch."
        )
        logging.error(msg)
        raise SyncError(msg)

    syncketch_meta = ayon_list_entity["data"].get("syncsketch") or {}
    sketch_review_id: int | None = syncketch_meta.get("id")
    sketch_meta_project: str | None = syncketch_meta.get("project")
    sketch_project: str
    if sketch_meta_project:
        sketch_project = sketch_meta_project
    elif summary_sketch_project:
        sketch_project = summary_sketch_project
    else:
        sketch_project = project_name

    syncsketch_api = SyncSketchAPI(
        username=credentials.username,
        api_key=credentials.api_key,
        server_url=credentials.server_url,
    )
    project_id: int | None = None
    for project in syncsketch_api.get_projects(fields={"id", "name"}):
        if project["name"].lower() == sketch_project.lower():
            project_id = project["id"]
            sketch_project = project["name"]
            break

    if project_id is None:
        msg = f"Failed to find SyncSketch project '{sketch_project}'"
        # Auto-fix data in AYON if the project stored on the entity does
        #   not exist in syncsketch.
        # NOTE Right now there is no way how to fix this using UI.
        if sketch_meta_project:
            syncketch_meta.pop("project", None)
            ayon_api.update_entity_list(
                project_name,
                list_id,
                data={"syncsketch": syncketch_meta},
            )

        logging.error(msg)
        raise SyncError(msg)

    label = ayon_list_entity["label"]
    sketch_review: dict[str, Any] = {}
    sketch_review_by_name: dict[str, Any] | None = None
    for review in syncsketch_api.get_reviews(project_id):
        if review["id"] == sketch_review_id:
            sketch_review = review
            break

        if review["name"] == label:
            sketch_review_by_name = review

    if not sketch_review and sketch_review_by_name:
        sketch_review = sketch_review_by_name

    if sketch_review:
        # Fetch items of the review item
        sketch_review["items"] = syncsketch_api.get_review_items(
            sketch_review["id"]
        )

    else:
        sketch_review = syncsketch_api.create_review(project_id, label)
        logging.info(
            f"Created review session '{label}'"
            f" in SyncSketch project '{sketch_project}'"
        )

    sketch_review_id = sketch_review["id"]

    meta_changed = False
    for key, old_value, new_value in (
        ("project", syncketch_meta.get("project"), sketch_project),
        ("id", syncketch_meta.get("id"), sketch_review_id),
    ):
        if old_value != new_value:
            syncketch_meta[key] = new_value
            meta_changed = True

    if meta_changed:
        ayon_api.update_entity_list(
            project_name,
            list_id,
            data={"syncsketch": syncketch_meta},
        )

    # TODO this logic requires
    #   https://github.com/ynput/ayon-backend/issues/985
    # - update of the 'syncsketch_id' field
    syncsketch_ids = {item["id"] for item in sketch_review["items"]}
    new_items = []
    for ayon_item in ayon_list_entity["items"]:
        syncsketch_id = ayon_item["data"].get("syncsketch_id")
        if syncsketch_id not in syncsketch_ids:
            new_items.append(ayon_item)

    if not new_items:
        logging.info(
            f"Review session '{label}' in SyncSketch project"
            f" '{sketch_project}' is up to date. Nothing to push."
        )
        return

    for ayon_item in new_items:
        version_id = ayon_item["entityId"]
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
                review_id=sketch_review_id,
                stream=stream,
                name=filename,
            )
            logging.info(
                "Added item by downloading it from AYON and uploading to"
                f" review session '{label}' in SyncSketch project"
                f" '{sketch_project}'"
            )

        else:
            media_url = location
            item = syncsketch_api.create_review_item_from_url(
                review_id=sketch_review_id,
                media_url=media_url,
                name=filename,
            )
            logging.info(
                f"Added item with url '{media_url}' to review session"
                f" '{label}' in SyncSketch project '{sketch_project}'"
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
    # --- Validate AYON list data ---
    ayon_list_entity: dict[str, Any] = ayon_api.get_entity_list_rest(
        project_name, list_id
    )
    if ayon_list_entity is None:
        raise SyncError(
            f"Failed to find list '{list_id}' in project '{project_name}'."
        )

    if ayon_list_entity["entityType"] != "version":
        raise SyncError(
            f"List '{list_id}' in project '{project_name}'"
            f" is not a version list."
        )

    if not ayon_list_entity["items"]:
        raise SyncError(
            f"List '{list_id}' in project '{project_name}' is empty. "
            "Nothing to pull from SyncSketch."
        )

    syncketch_meta = ayon_list_entity["data"].get("syncsketch") or {}
    sketch_review_id: int | None = syncketch_meta.get("id")
    sketch_meta_project: str | None = syncketch_meta.get("project")

    sketch_project: str
    if sketch_meta_project:
        sketch_project = sketch_meta_project
    else:
        sketch_project = project_name

    ayon_items_by_syncsketch_id: dict[int, dict[str, Any]] = {}
    for item in ayon_list_entity["items"]:
        syncsketch_id = item["data"].get("syncsketch_id")
        if syncsketch_id:
            ayon_items_by_syncsketch_id[syncsketch_id] = item

    if not ayon_items_by_syncsketch_id:
        raise SyncError(
            f"List '{list_id}' items in project '{project_name}'"
            " were not synchronized to SyncSketch."
            " Nothing to pull from SyncSketch."
        )

    # --- Prepare and validate SyncSketch data ---
    syncsketch_api = SyncSketchAPI(
        username=credentials.username,
        api_key=credentials.api_key,
        server_url=credentials.server_url,
    )
    project_id: int | None = None
    for project in syncsketch_api.get_projects(fields={"id", "name"}):
        if project["name"].lower() == sketch_project.lower():
            project_id = project["id"]
            break

    if project_id is None:
        raise SyncError(
            f"Failed to find SyncSketch project '{sketch_project}'"
        )

    label: str = ayon_list_entity["label"]
    sketch_review: dict[str, Any] = {}
    sketch_review_by_name: dict[str, Any] | None = None
    for review in syncsketch_api.get_reviews(project_id):
        if review["id"] == sketch_review_id:
            sketch_review = review
            break
        if review["name"] == label:
            sketch_review_by_name = review

    if not sketch_review and sketch_review_by_name:
        sketch_review = sketch_review_by_name

    if sketch_review:
        # Items are not included when 'get_reviews' is called
        # - it can be included in the review, but the payload would
        #   be huge and we don't need it for the all reviews
        sketch_review["items"] = syncsketch_api.get_review_items(
            sketch_review["id"]
        )

    if not sketch_review:
        raise SyncError(
            f"Failed to find SyncSketch review session with name '{label}'"
            f" in project '{sketch_project}'"
        )

    # Prepare mapping of AYON items to SyncSketch items
    sketch_review_id: int = sketch_review["id"]
    ayon_item_entity_ids: set[str] = set()
    mapped_items: list[tuple[dict, dict]] = []
    for item in sketch_review["items"]:
        syncsketch_id: int = item["id"]
        ayon_item = ayon_items_by_syncsketch_id.get(syncsketch_id)
        if ayon_item:
            ayon_item_entity_ids.add(ayon_item["entityId"])
            mapped_items.append((item, ayon_item))

    if not mapped_items:
        raise SyncError(
            f"Failed to find any items in SyncSketch review session '{label}'"
            f" that are mapped to list '{list_id}' in AYON project"
            f" '{project_name}'. Nothing to pull from SyncSketch."
        )

    # Prepare existing AYON activities to avoid duplicated comments
    activities_by_entity_id = {
        entity_id: []
        for entity_id in ayon_item_entity_ids
    }
    for activity in ayon_api.get_activities(
        project_name,
        entity_ids=ayon_item_entity_ids,
    ):
        entity_id = activity["entityId"]
        activities_by_entity_id[entity_id].append(activity)

    # Prepare mapping of AYON and SyncSketch users
    # - the mapping is based on email, in that case mentions in SyncSketch
    #   comments can be replaced with AYON mentions
    # - also the comments creation can be done inbehalve of the user
    sketch_users_by_email: dict[str, str] = {}
    users = syncsketch_api.get_project_users(project_id)
    for user in users:
        first_name = user["first_name"]
        last_name = user["last_name"]
        full_name = f"{first_name} {last_name}"
        email = user["email"].lower()
        sketch_users_by_email[email] = full_name

    ayon_users_by_email: dict[str, dict[str, Any]] = {}
    for user in ayon_api.get_users():
        email = user["attrib"]["email"]
        if not email:
            continue
        email = email.lower()
        ayon_users_by_email[email] = user

    con = ayon_api.get_server_api_connection()

    ayon_entity_type = "version"
    # Process each mapped item
    for sketch_item, ayon_item in mapped_items:
        sketch_item_id: int = sketch_item["id"]
        ayon_entity_id: str = ayon_item["entityId"]
        ayon_activities_by_sketch_id: dict[int, dict[str, Any]] = {}
        ayon_sketch_activities: list[dict[str, Any]] = []
        for activity in activities_by_entity_id[ayon_entity_id]:
            syncsketch_meta = activity["activityData"].get("syncsketch")
            if not syncsketch_meta:
                continue

            if syncsketch_meta["type"] == "comment":
                syncsketch_id = syncsketch_meta["id"]
                ayon_activities_by_sketch_id[syncsketch_id] = activity

            elif syncsketch_meta["type"] == "sketch":
                ayon_sketch_activities.append(activity)

        frames_info = syncsketch_api.get_review_item_frames(sketch_item_id)
        # Sort frame items by load time (epoch time used for sorting)
        frames_info.sort(key=lambda f: f["loadTime"])

        sketches: list[dict[str, Any]] = []
        # Go through frame items and create/update AYON comment activities
        # - also prepare sketche information
        for frame_info in frames_info:
            frame_type: str = frame_info["type"]
            if frame_type == "sketch":
                sketches.append(frame_info)
                continue

            if frame_type != "comment":
                continue

            frame_info_id: int = frame_info["id"]
            sketch_user_id: int = frame_info["creator"]["id"]
            sketch_email: str = frame_info["creator"]["email"].lower()
            frame: int | None = frame_info["frame"]
            text: str = frame_info["text"]

            ayon_text = text
            # Replace mentions with AYON mentions
            if "@" in ayon_text:
                for email, full_name in sketch_users_by_email.items():
                    mention = f"@{full_name}"
                    if mention not in ayon_text:
                        continue

                    ayon_user = ayon_users_by_email.get(email)
                    if not ayon_user:
                        continue
                    username = ayon_user["name"]
                    ayon_text = ayon_text.replace(
                        mention, f"[artist](user:{username})"
                    )

            if frame is not None:
                ayon_text = f"`Frame {frame + 1:0>4}`\n{ayon_text}"

            ayon_user: dict | None = ayon_users_by_email.get(sketch_email)
            ayon_username: str | None = None
            if ayon_user:
                ayon_username = ayon_user["name"]

            ayon_activity: dict[str, Any] | None = (
                ayon_activities_by_sketch_id.get(frame_info_id)
            )
            if ayon_activity:
                syncsketch_meta: dict[str, Any] = (
                    ayon_activity["activityData"]["syncsketch"]
                )
                if syncsketch_meta["text"] == text:
                    continue

                syncsketch_meta["text"] = text
                syncsketch_meta["frame"] = frame

                with con.as_username(
                    ayon_username, ignore_service_error=True
                ):
                    ayon_api.update_activity(
                        project_name,
                        ayon_activity["id"],
                        body=ayon_text,
                        data={"syncsketch": syncsketch_meta},
                    )
                continue

            syncsketch_meta = {
                "text": text,
                "id": frame_info_id,
                "frame": frame,
                "user_id": sketch_user_id,
                "type": frame_type,
            }
            dt_object = datetime.fromtimestamp(frame_info["loadTime"])
            with con.as_username(
                ayon_username, ignore_service_error=True
            ):
                ayon_api.create_activity(
                    project_name,
                    ayon_entity_id,
                    ayon_entity_type,
                    "comment",
                    body=ayon_text,
                    data={"syncsketch": syncsketch_meta},
                    timestamp=dt_object.isoformat(),
                )

        # No sketches just continue
        if not sketches:
            logging.info(
                "No sketches found."
                f" Sync of item '{sketch_item_id}' finished."
            )
            continue

        last_load_time: int = 0
        sketches_items: list[dict[str, int | None]] = []
        sketches_mapping: dict[int, int] = {}
        for rev_frames in sketches:
            load_time: int = rev_frames["loadTime"]
            if load_time > last_load_time:
                last_load_time = load_time
            frame_id: int = rev_frames["id"]
            sketches_mapping[frame_id] = load_time
            sketches_items.append({
                "frame": rev_frames["frame"],
                "loadTime": load_time,
                "id": frame_id,
            })

        matching_activity: dict[str, Any] | None = None
        for activity in ayon_sketch_activities:
            syncsketch_meta = activity["activityData"]["syncsketch"]
            load_time_by_frame_id = {
                mf["id"]: mf["loadTime"]
                for mf in syncsketch_meta["frames"]
            }
            matching = True
            for frame_id, load_time in sketches_mapping.items():
                value = load_time_by_frame_id.get(frame_id)
                if value != load_time:
                    matching = False
                    break

            if matching:
                matching_activity = activity
                break

        if matching_activity:
            logging.info(
                "Sketches already synchronized."
                f" Sync of item '{sketch_item_id}' finished."
            )
            continue

        sketches_data = syncsketch_api.prepare_review_item_sketches(
            sketch_review_id, sketch_item["id"]
        )
        if sketches_data is None:
            logging.error(
                f"Failed to sync sketch frames for SyncSketch review"
                f" '{sketch_review_id}' in project '{sketch_project}'"
            )
            continue

        file_ids: set[str] = set()
        for image in sketches_data:
            url = image["url"]
            with urllib.request.urlopen(url) as response:
                content = response.read()

            stream = io.BytesIO(content)
            adjusted_frame = image["adjustedFrame"]

            filename = f"Frame {adjusted_frame:0>4}.jpg"

            response = ayon_api.upload_project_file_from_stream(
                project_name,
                stream,
                filename,
            )
            file_id: str = response.json()["id"]
            file_ids.add(file_id)

        sketch_count = len(sketches_mapping) + 1
        syncsketch_meta = {
            "type": "sketch",
            "id": f"sketch{sketch_count}",
            "frames": sketches_items,
        }
        dt_object = datetime.fromtimestamp(last_load_time)
        ayon_api.create_activity(
            project_name,
            ayon_entity_id,
            ayon_entity_type,
            "comment",
            body="",
            file_ids=list(file_ids),
            timestamp=dt_object.isoformat(),
            data={
                "syncsketch": syncsketch_meta,
            },
        )

        logging.info(f"Sync of item '{sketch_item_id}' finished.")

    logging.info(f"Pull of review '{sketch_review_id}' is finished.")
