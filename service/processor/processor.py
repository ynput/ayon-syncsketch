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
import requests
from copy import deepcopy

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
                    logging.info(
                        "Review session ended "
                        f"event: {pformat(payload)}."
                    )
                    self._process_review_session_end(payload)
                elif event_topic == "syncsketch.item_approval_status_changed":
                    self._process_item_approval_status_changed(payload)
                    logging.info(
                        "Item approval status changed "
                        f"event: {pformat(payload)}."
                    )

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

    def _process_item_approval_status_changed(self, payload):
        """ Update an Ftrack asset version or task with SyncSketch notes.

        This is processing particular SyncSketch review item with
        status synchronization thanks to settings mapping.

        Payload example:
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

        Args:
            payload (dict): Dict with the `action`, `review` and `project_name`
        """
        review_id = payload["review"]["id"]
        status_name = payload["new_status"]
        review_item_id = payload["item_id"]
        project_name = payload["project"]["name"]

        logging.info(f"Processing review item with ID: {review_item_id}")

        review_entity = self.syncsketch_session.get_review_by_id(
            review_id)

        # duplication of notes were caused by inconsistency of
        # www. in the url
        review_link = review_entity["reviewURL"].replace("www.", "")

        review_item = self.syncsketch_session.get_review_item(
            review_item_id)

        review_link = f"{review_link}#/{review_item_id}"

        review_media_item = self._get_media_dict(
            review_item, project_name, review_id, review_link)

        if not review_media_item:
            logging.error(
                f"Unable to find media for review item `{review_item_id}`")
            return

        ftrack_id = review_media_item["ftrack_id"]
        ftrack_version_entities = \
            self._get_ftrack_asset_versions_entities_by_version_ids([ftrack_id])

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
            ft_asset_version, review_media_item, ftrack_status_id)

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

    def _process_review_session_end(self, payload):
        """ Update an Ftrack task with SyncSketch notes.

        The payload contains a SyncSketch review, which we use to find the
        associated Ayon entity, and through that the Ftrack AssetVersion and
        Task, if all is found, we try to update the Task's notes with the ones
        from SyncSketch that are not already there.

        Notes are published as the same user as in SyncSketch if the user has the
        username in Ftrack otherwise it defaults to the API username.

        Payload example:
            {
                'action': 'review_session_end',
                'review': {
                    'id': 2853840,
                    'link': 'https://syncsketch.com/sketch/YmU2YTUyZDY4/',
                    'name': 'Uploads from Ayon'
                },
                'account': {
                    'id': 553271268
                },
                'project': {
                    'id': 310312,
                    'name': 'SyncSketchTesting'
                }
            }

        Args:
            payload (dict): Dict with the `action`, `review` and `project_name`

        Returns:
            None
        """
        review_id = payload["review"]["id"]
        # duplication of notes were caused by inconsistency of
        # www. in the url
        review_link = payload["review"]["link"].replace("www.", "")
        project_name = payload["project"]["name"]

        # get ftrack project entity
        project_entity = self._ftrack_project_entity(project_name)

        logging.info(f"Processing review {review_id}")
        review_items = self.syncsketch_session.get_media_by_review_id(
            review_id)

        review_media_with_notes = []
        for review_item in review_items.get("objects", []):
            review_link_ = f"{review_link}#/{review_item['id']}"

            review_media_item = self._get_media_dict(
                review_item, project_name, review_id, review_link_)

            if review_media_item:
                review_media_with_notes.append(review_media_item)

        all_version_ids = {
            review_media_item["ftrack_id"]
            for review_media_item in review_media_with_notes
        }
        all_version_ids.discard(None)

        ftrack_version_entities = \
            self._get_ftrack_asset_versions_entities_by_version_ids(
                all_version_ids)

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
                ft_asset_version, review_media_item, ftrack_status_id)

    def _notes_to_ftrack(
            self,
            ft_entity,
            review_media_item,
            ftrack_status_id=None,
        ):
        """ Update an Ftrack asset version or task with SyncSketch notes.

        Args:
            ft_entity (dict): The Ftrack AssetVersion entity.
            review_media_item (dict): The SyncSketch review media item.
            ftrack_status_id (Optional[str]): The Ftrack status id.

        Returns:
            None
        """

        if ftrack_status_id:
            ft_entity["status_id"] = ftrack_status_id

        existing_ftrack_notes = [
            # duplication of notes were caused by inconsistency of
            # www. in the url
            note["content"].replace("www.", "")
            for note in ft_entity["notes"]
        ]

        upload_location = self.ft_session.query(
            "Location where name is \"ftrack.server\""
        ).one()

        for review_media_item_note in review_media_item["notes"]:
            if review_media_item_note["text"] in existing_ftrack_notes:
                # Note already exists in Ftrack
                logging.info(
                    f"Note \"{review_media_item_note['text']}\" already exists "
                    f"in Ftrack notes, skipping. {existing_ftrack_notes}"
                )
                continue

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

            note_data = {
                "content": review_media_item_note["text"],
                "author": ft_user
            }

            frame = review_media_item_note.get("frame")
            if frame:
                note_data["frame_number"] = int(frame)

            new_note_entity = self.ft_session.create("Note", note_data)
            ft_entity["notes"].append(new_note_entity)

            sketch_data = review_media_item_note.get("sketch")
            if not sketch_data:
                continue


            img_data = requests.get(sketch_data["url"])

            image_name = "sketch.jpg"
            if frame:
                image_name = f"sketch_{frame:>04}.jpg"

            with open(image_name, 'wb') as file:
                file.write(img_data.content)

            # get name and extension of image
            name, ext = os.path.splitext(image_name)

            # upload sketch as thumbnail
            component_data = {
                "version_id ": ft_entity["id"],
                "name": name,
                "file_type": ext,
            }

            component_entity = self.ft_session.create_component(
                path=image_name,
                data=component_data,
                location=upload_location
            )

            os.remove(image_name)

            # create NoteComponent and use component_entity id
            note_component_data = {
                "component_id": component_entity["id"],
                "note_id": new_note_entity["id"],
            }
            self.ft_session.create("NoteComponent", note_component_data)
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

        # convert sketches list into dictionary where key is frame number
        sketches = {
            sketch["frame"]: sketch
            for sketch in sketches["data"]
        }

        for annotation in annotations.get("objects", []):
            if annotation["type"] == "sketch":
                continue

            frame_number = annotation.get("frame")

            notes_data = {
                "username": annotation["creator"]["username"],
                "frame": frame_number
            }

            # check if frame key is in annotation
            if annotation.get("frame") and annotation["frame"] in sketches:
                frame_number = sketches[annotation["frame"]]["adjustedFrame"]
                notes_data.update({
                    # add frame to formatting data for note text
                    "frame": frame_number,
                    # add sketch data for later thumbnail upload
                    "sketch": sketches[annotation["frame"]],
                })

            comment_text = self.get_comment_text(
                annotation, url=review_link)

            notes_data["text"] = comment_text

            # TODO: need to check existing notes in ftrack here
            media_dict["notes"].append(notes_data)

        if media_dict["notes"] != []:
            # return media_dict only if it has notes
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

        resulted_output = self.ft_session.query(query).all()
        if not resulted_output:
            logging.error(f"Unable to find any {ft_type} with ids {ids}.")
            return {}

        return {
            entity["id"]: entity
            for entity in resulted_output
        }

    def _get_ftrack_asset_versions_entities_by_version_ids(self, version_ids):
        """ Get the Ftrack AssetVersion entities by the Ayon Version ids.

        Args:
            version_ids (list[str]): The Ayon Version ids.

        Returns:
            dict[str, dict]: The Ftrack AssetVersion
                entities by the Ayon Version ids.
        """
        if not version_ids:
            return []

        version_entities = self._ftrack_query_all_by_ids(
            "AssetVersion",
            version_ids,
            selection=["notes"]
        )

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
