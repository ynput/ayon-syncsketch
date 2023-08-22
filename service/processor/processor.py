"""
A SyncSketch Events listener processor for Ayon.

This service will continually run and query the Ayon Events Server in order to
enroll the events of topic `syncsketch.leech` to perform processing of Shotgrid
related events.
"""
import os
import time
import socket
import json

from pprint import pformat
import ayon_api
import ftrack_api
from nxtools import logging, log_traceback

from .common.server_handler import ServerCommunication
from .common.config import get_resolved_secrets


class SyncSketchProcessor:
    def __init__(self):
        """ Ensure both Ayon, Syncsketch and Ftrack connections are available.
        """
        logging.info("Initializing the SyncSketch Processor.")
        logging.debug(f"AYON_SERVER_URL: {os.environ['AYON_SERVER_URL']}")
        try:

            settings = ayon_api.get_addon_settings(
                "syncsketch",
                os.environ["AYON_ADDON_VERSION"]
            )
            self.syncsk_server_config = settings["syncsketch_server_config"]
            self.all_resolved_secrets = get_resolved_secrets(
                self.syncsk_server_config)

        except Exception as e:
            logging.error("Unable to get Addon settings from the server.")
            log_traceback(e)
            raise e

        try:
            self.syncsketch_session = ServerCommunication(
                self.all_resolved_secrets["auth_user"],
                self.all_resolved_secrets["auth_token"],
                host=self.syncsk_server_config["url"],
            )
            self.syncsketch_session.is_connected()

        except Exception as e:
            logging.error("Unable to connect to SyncSketch API:")
            log_traceback(e)
            raise e

        # Need to think if we require the Ftrack Addon?
        # Or allow people to specify ftrack info though this addon too?

        try:
            self.ft_session = ftrack_api.Session(
                server_url=self.syncsk_server_config["ftrack_url"],
                api_key=self.all_resolved_secrets["ftrack_api_key"],
                api_user=self.all_resolved_secrets["ftrack_username"],
                # QUESTION: should we cash it or not?
                schema_cache_path=False
            )

        except Exception as e:
            logging.error("Unable to connect to Ftrack API:")
            log_traceback(e)

    def start_processing(self):
        """ Main loop enrolling on AYON events.

        We look for events of the topic `syncsketch.event` and process them by
        issuing events of topic `syncsketch.proc` which run the `_upload_review_
        notes_to_ftrack` method against the event payload.
        """
        logging.info("Start enrolling for Ayon `syncsketch.event` Events...")

        while True:

            logging.info("Querying for 1 new `syncsketch.event` events...")
            try:
                event = ayon_api.enroll_event_job(
                    "syncsketch.event",
                    "syncsketch.proc",
                    socket.gethostname(),
                    description="SyncSketch Event processing",
                )
            except Exception as err:
                logging.error(f"Unable to enroll for Ayon events: {err}")
                time.sleep(1.5)
                continue

            if not event:
                logging.info(
                    "No event of origin `syncsketch.event` is pending.")
                time.sleep(1.5)
                continue

            event_status = "failed"
            try:
                source_event = ayon_api.get_event(event["dependsOn"])
                payload = source_event["payload"]

                if not payload:
                    time.sleep(1.5)
                    ayon_api.update_event(event["id"], status="finished")
                    continue

                logging.info(f"Processing event: {payload}")
                self._upload_review_notes_to_ftrack(payload)

                logging.info(
                    "Event has been processed... setting to finished!")
                event_status = "finished"

            except ftrack_api.exception.Error:
                logging.error(f"Unable to process handler {payload}")

            except Exception as err:
                logging.error(f"Unable to process handler {payload}")
                log_traceback(err)

            finally:
                ayon_api.update_event(event["id"], status=event_status)

    def _upload_review_notes_to_ftrack(self, payload):
        """ Update an FTrack task with SyncSketch notes.

        The payload contains a SyncSketch review, which we use to find the
        associated Ayon entity, and through that the FTrack AssetVersion and
        Task, if all is found, we try to update the Task's notes with the ones
        from SyncSketch that are not already there.

        Notes are published as the same user as in SyncSketch if the user has the
        username in FTrack otherwise it defaults to the API username.

        Args:
            payload (dict): Dict with the `action`, `review` and `project_name`, i.e:
            {
                "action": "review_session_end",
                "review": {
                    "id": 2783585,
                    "link": "https://syncsketch.com/sketch/NmZmNTg5N2I5/",
                    "name": "My fancy review"
                },
                "project_name": "testApiProjectKey"
            }
        """
        review_id = payload["review"]["id"]
        project_name = payload["project_name"]

        logging.info(f"Processing review {review_id}")
        review_items = self.syncsketch_session.get_media_by_review_id(
            review_id)

        logging.info(f"Review items: {pformat(review_items)}")

        review_media_with_notes = []
        for review_item in review_items.get("objects", []):
            logging.info(
                f"Processing review item `{review_id}` media {review_item}")

            if review_item.get("metadata") is None:
                logging.warning(
                    f"Media {review_item['name']} is missing metadata.")
                continue

            # json string to dict and get the ayonVersionID
            metadata_data = json.loads(review_item["metadata"])
            ayon_version_id = metadata_data.get("ayonVersionID")

            if not ayon_version_id:
                logging.error(
                    f"Media {review_item['name']} is missing the AYON id.")
                continue

            ayon_version_entity = ayon_api.get_version_by_id(
                project_name, ayon_version_id)

            logging.info(
                f"AYON version entity: {pformat(ayon_version_entity)}")

            if not ayon_version_entity["attrib"].get("ftrackId"):
                logging.error(
                    f"Media {ayon_version_entity} is missing the Ftrack ID.")
                continue

            media_dict = {
                "ftrack_id": ayon_version_entity["attrib"]["ftrackId"],
                "notes": [],
            }
            annotations = self.syncsketch_session.get_annotations(
                review_item["id"],
                review_id=review_id
            )
            sketches = self.syncsketch_session.get_flattened_annotations(
                review_item["id"],
                review_id,
                with_tracing_paper=True,
                return_as_base64=True
            )
            logging.info(f"Annotations: {pformat(annotations)}")
            logging.info(f"Sketches: {pformat(sketches)}")

            """
            TODO: we need to group annotations by frame if any
            TODO: we need to reference frame number in the note
            TODO: get image sketch sources via `get_flattened_annotations`
            """
            for annotation in annotations.get("objects", []):
                if annotation["type"] == "sketch":
                    continue

                comment_text = self.get_comment_text(
                    annotation, payload)
                logging.debug(f"Comment text: {comment_text}")

                media_dict["notes"].append({
                    "username": annotation["creator"]["username"],
                    "text": comment_text
                })

            if media_dict["notes"]:
                review_media_with_notes.append(media_dict)

        logging.info(
            f">> review_media_with_notes: {pformat(review_media_with_notes)}")

        all_version_ids = {
            review_media_item["ftrack_id"]
            for review_media_item in review_media_with_notes
        }
        all_version_ids.discard(None)

        ftrack_version_entities = \
            self._get_ftrack_task_entities_by_version_ids(all_version_ids)

        logging.info(
            f">> ftrack_version_entities: {pformat(ftrack_version_entities)}")

        for review_media_item in review_media_with_notes:
            # Ftrack AssetVersion
            ftrack_id = review_media_item["ftrack_id"]
            ft_asset_version = ftrack_version_entities.get(ftrack_id)

            if not ft_asset_version:
                logging.error(
                    f"Unable to find Ftrack asset version `{ftrack_id}`")
                continue

            ft_task_entity = ft_asset_version["task"]

            existing_ftrack_notes = [
                {
                    "username": note["author"]["username"],
                    "text": note["content"]
                }
                for note in ft_task_entity["notes"]
            ]

            for review_media_item_note in review_media_item["notes"]:
                if review_media_item_note not in existing_ftrack_notes:
                    # Create a new note
                    try:
                        # Try to get the FTrack user by username
                        ft_user = self._get_ftrack_user_by_username(
                            review_media_item_note["username"])
                    except Exception:
                        # user does not exist in FTrack so we default
                        # to the API user
                        api_username = self.all_resolved_secrets[
                            "ftrack_username"]
                        ft_user = self._get_ftrack_user_by_username(
                            api_username)

                    logging.debug(f">> ft_user: {ft_user}")

                    new_note = self.ft_session.create('Note', {
                        'content': review_media_item_note["text"],
                        'author': ft_user
                    })
                    ft_task_entity["notes"].append(new_note)

            self.ft_session.commit()

    def _get_ftrack_user_by_username(self, username):
        """ Get the FTrack user by username.

        Args:
            username (str): The FTrack username.

        Returns:
            dict: The FTrack user.
        """
        return self.ft_session.query(
            f"User where username is '{username}'"
        ).one()

    def _ftrack_query_one_by_id(self, ft_type, id, selection=None):
        """ Helper method to do single output FTrack queries.

        Args:
            ft_type (str): The FTrack entity type.
            id (str): The Ftrack entity id.
            selection (Optional|list): List of attributes to select.

        Returns:
            dict: Ftrack Entity
            | ftrack_api.exception.NoResultFoundError
            | ftrack_api.exception.ServerError.
        """
        query = f"{ft_type} where id is {id}"

        if selection:
            if isinstance(selection, list):
                query = f"select {', '.join(selection)} from {query}"
            else:
                logging.error("Selection has to be a list, ignoring.")

        return self.ft_session.query(query).one()

    def _ftrack_query_all_by_ids(self, ft_type, ids, selection=None):
        """ Helper method to do multiple output FTrack queries.

        Args:
            ft_type (str): The FTrack entity type.
            ids (list[str]): The Ftrack entity ids in list.
            selection (Optional|list): List of attributes to select.

        Returns:
            dict[str, dict]: Ftrack Entities by id
            | ftrack_api.exception.NoResultFoundError
            | ftrack_api.exception.ServerError.
        """
        if not ids:
            return {}

        joined_ids = ",".join({
            f'"{entity_id}"' for entity_id in ids
        })
        query = f"{ft_type} where id in ({joined_ids})"

        if selection:
            if isinstance(selection, list):
                query = f"select {', '.join(selection)} from {query}"
            else:
                logging.error("Selection has to be a list, ignoring.")

        logging.info(f"Querying ftrack: {query}")

        resulted_output = self.ft_session.query(query).all()
        if not resulted_output:
            logging.error(f"Unable to find any {ft_type} with ids {ids}.")
            return {}

        return {
            entity["id"]: entity
            for entity in resulted_output
        }

    def _get_ftrack_task_entities_by_version_ids(self, version_ids):
        """ Get the FTrack Task entities by the Ayon Version ids.

        Args:
            version_ids (list[str]): The Ayon Version ids.

        Returns:
            dict[str, dict]: The FTrack Task entities by the Ayon Version ids.
        """
        if not version_ids:
            return []

        version_entities = self._ftrack_query_all_by_ids(
            "AssetVersion",
            version_ids,
            selection=["task_id"]
        )
        logging.info(f"version_entities: {pformat(version_entities)}")

        task_ids = {
            version_entity["task_id"]
            for version_entity in version_entities.values()
        }
        task_ids.discard(None)
        logging.info(f"task_ids: {pformat(task_ids)}")

        # TODO: need to query notes as parents separately for
        # "notes.author.username"
        # "notes.content"
        task_entities = self._ftrack_query_all_by_ids(
            "Task",
            task_ids,
            selection=[
                "notes"
            ]
        )
        logging.info(f"task_entities: {pformat(task_entities)}")

        # merge task entities into version entities
        for version_entity in version_entities.values():
            version_entity["task"] = task_entities.get(
                version_entity["task_id"])

        return version_entities

    def get_comment_text(self, annotation, payload):
        """ Get the comment text to be uploaded to ftrack.

        Args:
            annotation (dict): The SyncSketch annotation.
            payload (dict): The SyncSketch payload.

        Returns:
            str: The comment text.
        """
        return f"""
{annotation['creator']['username']}: {annotation['text']}

SyncSketch link: {payload['review']['link']}
"""
