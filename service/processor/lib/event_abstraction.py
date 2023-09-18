
import os
import json
import requests
from pprint import pformat
from nxtools import logging, log_traceback
from abc import ABC, abstractmethod

import ayon_api
import ftrack_api

from processor.common.server_handler import ServerCommunication
from processor.common.config import get_resolved_secrets


# create abstract class for event
class EventProcessor(ABC):

    def __init__(self, settings):
        self.settings = settings

    @abstractmethod
    def process(self, payload):
        pass


class FtrackNoteSyncing(EventProcessor):
    # Ayon and Syncsketch connections
    syncsk_server_config = None
    statuses_mapping = None
    all_resolved_secrets = None
    syncsketch_session = None

    def __init__(self, addon_settings):
        """ Ensure both Ayon, Syncsketch and Ftrack connections are available.
        """

        try:
            self.statuses_mapping = addon_settings["statuses_mapping"]
            self.syncsk_server_config = addon_settings["syncsketch_server_config"]
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


    def process(self, payload):
        pass

    def _process_all_versions(
            self,
            ayon_version_ids,
            review_id,
            project_name,
            review_link,
            status_name=None
        ):
        """ Update an Ftrack task with SyncSketch notes.

        The payload contains a SyncSketch review, which we use to find the


        Args:
            ayon_version_ids (dict[str, dict]): The Ayon Version ids.
            review_id (str): The SyncSketch review id.
            project_name (str): The project name.
            review_link (str): The SyncSketch review link.
            status_name (Optional[str]): The SyncSketch review status name.

        Returns:
            None
        """
        version_data_all = self._get_version_data(
            project_name, ayon_version_ids)

        for _, version_data in version_data_all.items():
            review_item = version_data["syncsketch_review_item"]
            review_item_id = review_item["id"]
            logging.info(f"Processing review item \'{review_item_id}\'...")

            review_link_ = f"{review_link}#/{review_item_id}"
            ftrack_entity = version_data["ftrack_entity"]

            if not ftrack_entity:
                ftrack_id = version_data["ftrack_id"]
                logging.error(
                    f"Unable to find Ftrack asset version `{ftrack_id}`")
                continue

            notes = self._generate_notes(
                version_data, review_id, review_link_)

            if not notes:
                logging.info(
                    f"Unable to find notes for review item `{review_item_id}`")
                continue

            logging.info(
                f"Ftrack status and notes: \'{review_item_id}\'...")

            # get ftrack project entity
            project_entity = self._ftrack_project_entity(project_name)

            # get ftrack status id from mapped status name
            ftrack_status_id = self._get_ftrack_status_id_from_name(
                status_name or review_item["approval_status"],
                project_entity
            )

            self._notes_to_ftrack(
                ftrack_entity, notes, ftrack_status_id)

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

    def _get_metadata_version_ids(self, review_items):
        """ Get the Ayon Version ids from the SyncSketch review items.

        Args:
            review_items (list[dict]): The SyncSketch review items.

        Returns:
            list[str]: The Ayon Version ids.
        """

        ayon_version_ids = {}
        for review_item in review_items:

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

            ayon_version_ids[ayon_version_id] = {
                "syncsketch_review_item": review_item
            }

        return ayon_version_ids

    def _ftrack_project_entity(self, project_name):
        project_query = 'Project where full_name is "{0}"'.format(project_name)

        project_entity = self.ft_session.query(project_query).one()
        if not project_entity:
            raise AssertionError(
                f"Project \"{project_name}\" not found in Ftrack."
            )

        return project_entity

    def _notes_to_ftrack(
            self,
            ft_entity,
            notes,
            ftrack_status_id=None,
        ):
        """ Update an Ftrack asset version or task with SyncSketch notes.

        Args:
            ft_entity (dict): The Ftrack AssetVersion entity.
            notes (list[dict]): notes to be synced to ftrack
            ftrack_status_id (Optional[str]): The Ftrack status id.

        Returns:
            None
        """

        if ftrack_status_id:
            ft_entity["status_id"] = ftrack_status_id


        upload_location = self.ft_session.query(
            "Location where name is \"ftrack.server\""
        ).one()

        for note_data in notes:
            frame_number = note_data.get("frame")
            logging.info(f"< Note {frame_number}" + "-" * 50 + " >")
            logging.info(pformat(note_data))

            # Create a new note
            try:
                # Try to get the Ftrack user by username
                ft_user = self._get_ftrack_user_by_username(
                    note_data["username"])
            except Exception:
                # user does not exist in Ftrack so we default
                # to the API user
                api_username = self.all_resolved_secrets[
                    "ftrack_username"]
                ft_user = self._get_ftrack_user_by_username(
                    api_username)

            ftrack_note_data = {
                "content": note_data["text"],
                "author": ft_user
            }

            frame = note_data.get("frame")
            if frame:
                ftrack_note_data["frame_number"] = int(frame)

            new_note_entity = self.ft_session.create("Note", ftrack_note_data)
            ft_entity["notes"].append(new_note_entity)

            sketch_data = note_data.get("sketch")
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

    def _get_version_data(self, project_name, ayon_version_ids):
        """ Get Ayon and Ftrack entities by the Ayon Version ids.

        Args:
            project_name (str): The project name.
            ayon_version_ids (dict[str, dict]): The Ayon Version ids.

        Returns:
            dict[str, dict]: The Ftrack entities by the Ayon Version ids.
        """
        if not ayon_version_ids:
            return {}

        ayon_version_entities = {
            version["id"]: {
                "ayon_version_entity": version
            }
            for version in ayon_api.get_versions(
                project_name, ayon_version_ids.keys()
            )
        }

        for version_id, version_data in ayon_version_entities.items():
            # update ayon_version_entities with ayon version entities
            version_data.update(ayon_version_ids[version_id])
            ayon_version_entity = version_data["ayon_version_entity"]

            if not ayon_version_entity.get("attrib", {}).get("ftrackId"):
                logging.error(
                    f"Media {ayon_version_entity} is missing the Ftrack ID.")
                continue

            ftrack_id = ayon_version_entity["attrib"]["ftrackId"]
            version_data.update({
                "ftrack_id": ftrack_id
            })

        ftrack_version_entities = \
            self._get_ftrack_asset_versions_entities_by_version_ids(
                [
                    ayon_version_entity["ftrack_id"]
                    for ayon_version_entity in ayon_version_entities.values()
                ]
            )

        for ayon_version_entity in ayon_version_entities.values():
            ayon_version_entity["ftrack_entity"] = ftrack_version_entities.get(
                ayon_version_entity["ftrack_id"]
            )

        return ayon_version_entities

    def _generate_notes(self, version_data, review_id, review_link):

        review_item = version_data["syncsketch_review_item"]
        ftrack_entity = version_data["ftrack_entity"]

        existing_ftrack_notes = [
            # duplication of notes were caused by inconsistency of
            # www. in the url
            note["content"].replace("www.", "")
            for note in ftrack_entity["notes"]
        ]

        annotations = self.syncsketch_session.get_annotations(
            review_item["id"],
            review_id=review_id
        )

        notes = []
        for annotation in annotations.get("objects", []):
            if annotation["type"] == "sketch":
                continue

            frame_number = annotation.get("frame")

            note_data = {
                "username": annotation["creator"]["username"],
                "frame": frame_number
            }
            comment_text = self.get_comment_text(
                annotation, url=review_link)

            note_data["text"] = comment_text

            # skip if comment already exists in ftrack notes
            if comment_text in existing_ftrack_notes:
                logging.info(
                    f"Existing note from: \'{review_item['id']}\', "
                    f"with frame: \'{frame_number}\', "
                    f"in review list: \'{review_id}\'"
                )
                continue

            notes.append(note_data)

        if not notes:
            return

        # get flattened annotations with tracing paper
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

        # add sketches to note_data
        for note_data in notes:
            sync_frame = note_data["frame"]

            # check if frame key is in annotation
            if sync_frame not in sketches:
                continue

            frame_number = sketches[sync_frame]["adjustedFrame"]
            note_data.update({
                # add frame to formatting data for note text
                "frame": frame_number,
                # add sketch data for later thumbnail upload
                "sketch": sketches[sync_frame],
            })

        return notes

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
