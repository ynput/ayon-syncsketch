"""
A SyncSketch Events listener processor for Ayon.

This service will continually run and query the Ayon Events Server in order to
enroll the events of topic `syncsketch.leech` to perform processing of Shotgrid
related events.
"""
from copy import deepcopy
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
    ftrack_statuses = None

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
            self.statuses_mapping = settings["statuses_mapping"]
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
        events_topics = [
            "syncsketch.review_session_end",
            "syncsketch.item_approval_status_changed",
        ]
        while True:
            event_topic = None
            try:
                for event_topic in events_topics:
                    logging.info(
                        f"Querying for 1 new `{event_topic}` from events...")
                    event = ayon_api.enroll_event_job(
                        event_topic,
                        "syncsketch.proc",
                        socket.gethostname(),
                        description=f"\'{event_topic}\' processing",
                    )
                    if event:
                        break
            except Exception as err:
                logging.error(f"Unable to enroll for Ayon events: {err}")
                time.sleep(1.5)
                continue

            if not event:
                logging.info(
                    f"No event of origin `{event_topic}` is pending.")
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

                # dividing by event_topic so relevant process is called
                if event_topic == "syncsketch.review_session_end":
                    logging.info(f"Review session ended event: {payload}.")
                    self._process_review_session_end(payload)
                elif event_topic == "syncsketch.item_approval_status_changed":
                    self._process_item_approval_status_changed(payload)
                    logging.info(f"Item approval status changed event: {payload}.")

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

    def _process_item_approval_status_changed(self, payload, to_task=False):
        """ Update an Ftrack asset version or task with SyncSketch notes.

        This is processing particular SyncSketch review item with
        status synchronization thanks to settings mapping.

        Args:
            payload (dict): Dict with the `action`, `review` and `project_name`, i.e:
            {
                'action': 'item_approval_status_changed',
                'account': {
                    'id': 553271268,
                    'name': 'testAPI'
                },
                'item_creator': {
                    'email': 'script_user_003f785a435e4759',
                    'id': 564818831,
                    'name': 'Script User'
                },
                'item_id': 20252190,
                'item_name': 'sh020 | compositing | v3 .mp4',
                'new_status': 'approved',
                'old_status': 'on_hold',
                'project': {
                    'id': 310312,
                    'name': 'SyncSketchTesting'
                },
                'review': {
                    'id': 2853840,
                    'name': 'Uploads from Ayon'
                },
                'user': {
                    'email': 'ayonocs@gmail.com',
                    'username': 'ayonocs'
                }
            }
        """
        review_id = payload["review"]["id"]
        status_name = payload["new_status"]
        review_item_id = payload["item_id"]
        project_name = payload["project"]["name"]

        logging.info(f"Processing review item with ID: {review_item_id}")

        review_entity = self.syncsketch_session.get_review_by_id(
            review_id)
        review_link = review_entity["reviewURL"]

        review_item = self.syncsketch_session.get_review_item(
            review_item_id)


        logging.info(
            f"Processing review item `{review_id}` media {review_item}")

        review_media_item = self._get_media_dict(
            review_item, project_name, review_id, review_link)

        if not review_media_item:
            logging.error(
                f"Unable to find media for review item `{review_item_id}`")
            return

        ftrack_id = review_media_item["ftrack_id"]
        ftrack_version_entities = \
            self._get_ftrack_task_entities_by_version_ids([ftrack_id], to_task)

        logging.info(
            f">> ftrack_version_entities: {pformat(ftrack_version_entities)}")

        # Ftrack AssetVersion
        ft_asset_version = ftrack_version_entities.get(ftrack_id)

        if not ft_asset_version:
            logging.error(
                f"Unable to find Ftrack asset version `{ftrack_id}`")
            return

        # get ftrack project entity
        project_entity = self._ftrack_project_entity(project_name)

        # get ftrack status id from mapped status name
        ftrack_status_id = self._get_ftrack_status_id_from_name(
            status_name, project_entity)

        self._notes_to_ftrack(
            ft_asset_version, review_media_item, to_task, ftrack_status_id)

    def _get_ftrack_status_id_from_name(self, status_name, project_entity):
        """ Get the Ftrack status id from the status name.

        Args:
            status_name (str): The status name.
            project_entity (dict): The Ftrack project entity.

        Returns:
            str: The Ftrack status id.
        """
        if not self.ftrack_statuses:
            project_schema = project_entity["project_schema"]
            asset_version_statuses = (
                project_schema.get_statuses("AssetVersion")
            )
            self.ftrack_statuses = {
                status["name"].lower(): status["id"]
                for status in asset_version_statuses
            }

        # convert syncsketch status name to ftrack status name
        ftrack_status_name = None
        for status in self.statuses_mapping:
            if status["name"].replace(" ", "_").lower() == status_name:
                ftrack_status_name = status["ftrack_status"].lower()
                break

        if not ftrack_status_name:
            logging.warning(f"Status \"{status_name}\" not found in Ftrack.")
            return

        return self.ftrack_statuses.get(ftrack_status_name)

    def _ftrack_project_entity(self, project_name):
        project_query = 'Project where full_name is "{0}"'.format(project_name)

        project_entity = self.ft_session.query(project_query).one()
        if not project_entity:
            raise AssertionError(
                f"Project \"{project_name}\" not found in Ftrack."
            )

        return project_entity

    def _process_review_session_end(self, payload, to_task=False):
        """ Update an Ftrack task with SyncSketch notes.

        The payload contains a SyncSketch review, which we use to find the
        associated Ayon entity, and through that the Ftrack AssetVersion and
        Task, if all is found, we try to update the Task's notes with the ones
        from SyncSketch that are not already there.

        Notes are published as the same user as in SyncSketch if the user has the
        username in Ftrack otherwise it defaults to the API username.

        Args:
            payload (dict): Dict with the `action`, `review` and `project_name`, i.e:
            {
                'action': 'review_session_end',
                'account': {
                    'id': 553271268,
                    'name': 'testAPI'
                },
                'item_creator': {
                    'email': 'script_user_003f785a435e4759',
                    'id': 564818831,
                    'name': 'Script User'
                },
                'item_id': 20252190,
                'item_name': 'sh020 | compositing | v3 .mp4',
                'new_status': 'approved',
                'old_status': 'on_hold',
                'project': {
                    'id': 310312,
                    'name': 'SyncSketchTesting'
                },
                'review': {
                    'id': 2853840,
                    'name': 'Uploads from Ayon'
                    "link": "https://syncsketch.com/sketch/NmZmNTg5N2I5/"
                },
                'user': {
                    'email': 'ayonocs@gmail.com',
                    'username': 'ayonocs'
                }
            }
        """
        review_id = payload["review"]["id"]
        review_link = payload["review"]["link"]
        project_name = payload["project"]["name"]

        # get ftrack project entity
        project_entity = self._ftrack_project_entity(project_name)

        logging.info(f"Processing review {review_id}")
        review_items = self.syncsketch_session.get_media_by_review_id(
            review_id)

        logging.info(f"Review items: {pformat(review_items)}")

        review_media_with_notes = []
        for review_item in review_items.get("objects", []):
            review_media_item = self._get_media_dict(
                review_item, project_name, review_id, review_link)

            if review_media_item:
                review_media_with_notes.append(review_media_item)

        logging.info(
            f">> review_media_with_notes: {pformat(review_media_with_notes)}")

        all_version_ids = {
            review_media_item["ftrack_id"]
            for review_media_item in review_media_with_notes
        }
        all_version_ids.discard(None)

        ftrack_version_entities = \
            self._get_ftrack_task_entities_by_version_ids(
                all_version_ids, to_task)

        logging.info(
            f">> ftrack_version_entities: {pformat(ftrack_version_entities)}")

        for review_media_item in review_media_with_notes:
            # Ftrack AssetVersion
            status_name = review_media_item["approval_status"]

            ftrack_id = review_media_item["ftrack_id"]
            ft_asset_version = ftrack_version_entities.get(ftrack_id)

            if not ft_asset_version:
                logging.error(
                    f"Unable to find Ftrack asset version `{ftrack_id}`")
                continue

            # get ftrack status id from mapped status name
            ftrack_status_id = self._get_ftrack_status_id_from_name(
                status_name, project_entity)

            self._notes_to_ftrack(
                ft_asset_version, review_media_item, to_task, ftrack_status_id)

    def _notes_to_ftrack(
            self,
            ft_asset_version,
            review_media_item,
            to_task=False,
            ftrack_status_id=None
        ):
        """ Update an Ftrack asset version or task with SyncSketch notes.

        Args:
            ft_asset_version (dict): The Ftrack AssetVersion entity.
            review_media_item (dict): The SyncSketch review media item.
            to_task (Optional[bool]): If we want to update the Ftrack Task instead.
            ftrack_status_id (Optional[str]): The Ftrack status id.

        Returns:
            None
        """
        if to_task:
            ft_entity = ft_asset_version["task"]
        else:
            ft_entity = ft_asset_version

        if ftrack_status_id:
            ft_entity["status_id"] = ftrack_status_id

        existing_ftrack_notes = [
            {
                "username": note["author"]["username"],
                "text": note["content"]
            }
            for note in ft_entity["notes"]
        ]

        for review_media_item_note in review_media_item["notes"]:
            if review_media_item_note not in existing_ftrack_notes:
                # Create a new note
                try:
                    # Try to get the Ftrack user by username
                    ft_user = self._get_ftrack_user_by_username(
                        review_media_item_note["username"])
                except Exception:
                    # user does not exist in Ftrack so we default
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
                ft_entity["notes"].append(new_note)

        self.ft_session.commit()

    def _get_media_dict(self, review_item, project_name, review_id, review_link):

        if review_item.get("metadata") is None:
            logging.warning(
                f"Media {review_item['name']} is missing metadata.")
            return

        # json string to dict and get the ayonVersionID
        metadata_data = json.loads(review_item["metadata"])
        ayon_version_id = metadata_data.get("ayonVersionID")

        if not ayon_version_id:
            logging.error(
                f"Media {review_item['name']} is missing the AYON id.")
            return

        ayon_version_entity = ayon_api.get_version_by_id(
            project_name, ayon_version_id)

        logging.info(
            f"AYON version entity: {pformat(ayon_version_entity)}")

        if not ayon_version_entity["attrib"].get("ftrackId"):
            logging.error(
                f"Media {ayon_version_entity} is missing the Ftrack ID.")
            return
        media_dict = deepcopy(review_item)
        media_dict.update({
            "ftrack_id": ayon_version_entity["attrib"]["ftrackId"],
            "notes": [],
        })

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
                annotation, url=review_link)

            logging.debug(f"Comment text: {comment_text}")

            media_dict["notes"].append({
                "username": annotation["creator"]["username"],
                "text": comment_text
            })

        if media_dict["notes"]:
            return media_dict

    def _get_ftrack_user_by_username(self, username):
        """ Get the Ftrack user by username.

        Args:
            username (str): The Ftrack username.

        Returns:
            dict: The Ftrack user.
        """
        return self.ft_session.query(
            f"User where username is '{username}'"
        ).one()

    def _ftrack_query_one_by_id(self, ft_type, id, selection=None):
        """ Helper method to do single output Ftrack queries.

        Args:
            ft_type (str): The Ftrack entity type.
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
        """ Helper method to do multiple output Ftrack queries.

        Args:
            ft_type (str): The Ftrack entity type.
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

    def _get_ftrack_task_entities_by_version_ids(self, version_ids, to_task=False):
        """ Get the Ftrack Task entities by the Ayon Version ids.

        Args:
            version_ids (list[str]): The Ayon Version ids.
            to_task (bool): If we want to get the Ftrack Task along with the
                AssetVersion.

        Returns:
            dict[str, dict]: The Ftrack Task entities by the Ayon Version ids.
        """
        if not version_ids:
            return []

        version_entities = self._ftrack_query_all_by_ids(
            "AssetVersion",
            version_ids,
            selection=["task_id"]
        )
        logging.info(f"version_entities: {pformat(version_entities)}")

        if not to_task:
            # we only need the version entities
            return version_entities

        task_ids = {
            version_entity["task_id"]
            for version_entity in version_entities.values()
        }
        task_ids.discard(None)
        logging.info(f"task_ids: {pformat(task_ids)}")

        # TODO: need to query notes as parents separately for
        # "notes.author.username" and "notes.content"
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

    def get_comment_text(self, annotation, url):
        """ Get the comment text to be uploaded to ftrack.

        Args:
            annotation (dict): The SyncSketch annotation.
            url (str): SyncSketch url.

        Returns:
            str: The comment text.
        """
        return f"""
{annotation['creator']['username']}: {annotation['text']}

SyncSketch link: {url}
"""
