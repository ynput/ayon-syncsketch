"""
A SyncSketch Events listener processor for Ayon.

This service will continually run and query the Ayon Events Server in order to
enroll the events of topic `syncsketch.leech` to perform processing of Shotgrid
related events.
"""
import os
import time
import socket

import ayon_api
import ftrack_api
from nxtools import logging, log_traceback
from syncsketch import SyncSketchAPI


class SyncSketchProcessor:
    def __init__(self):
        """ Ensure both Ayon, Syncsketch and Ftrack connections are available.
        """
        logging.info("Initializing the SyncSketch Processor.")

        try:
            self.settings = ayon_api.get_addon_settings(
                os.environ["AYON_ADDON_NAME"],
                os.environ["AYON_ADDON_VERSION"]
            )["syncsketch_server_configs"][0]

            self.sk_url = self.settings["url"]
            self.sk_auth_token = self.settings["auth_token"]
            self.sk_auth_username = self.settings["auth_user"]

        except Exception as e:
            logging.error("Unable to get Addon settings from the server.")
            log_traceback(e)
            raise e

        try:
            self.sk_session = SyncSketchAPI(self.sk_auth_username, self.sk_auth_token)
            self.sk_session.is_connected()

        except Exception as e:
            logging.error("Unable to connect to SyncSketch API:")
            log_traceback(e)
            raise e

        # Need to think if we require the Ftrack Addon?
        # Or allow peopel to specify ftrack info though this addon too?
        # THIS WILL FAIL
        try:
            self.ft_session = ftrack_api.Session(
                server_url=self.settings["ftrack_url"],
                api_key=self.settings["ftrack_api_key"],
                api_user=self.settings["ftrack_api_username"]
            )

        except Exception as e:
            logging.error("Unable to connect to Ftrack API:")
            log_traceback(e)
            #raise e

    def start_processing(self):
        """ Main loop enrolling on AYON events.

        We look for events of the topic `syncsketch.event` and process them by issuing
        events of topic `syncsketch.proc` which run the `_upload_sk_notes_to_ftrack`
        method against the event payload.
        """
        logging.info("Start enrolling for Ayon `syncsketch.event` Events...")

        while True:
            logging.info("Querying for new `syncsketch.event` events...")
            try:
                event = ayon_api.enroll_event_job(
                    "syncsketch.event",
                    "syncsketch.proc",
                    socket.gethostname(),
                    description="SyncSketch Event processing",
                )

                if not event:
                    logging.info("No event of origin `syncsketch.event` is pending.")
                    time.sleep(1.5)
                    continue

                source_event = ayon_api.get_event(event["dependsOn"])
                payload = source_event["payload"]

                if not payload:
                    time.sleep(1.5)
                    ayon_api.update_event(event["id"], status="finished")
                    ayon_api.update_event(source_event["id"], status="finished")
                    continue

                try:
                    logging.info(f"Procesing event: {payload}")
                    self._upload_sk_notes_to_ftrack(payload)

                except Exception as e:
                    logging.error(f"Unable to process handler {payload}")
                    log_traceback(e)
                    ayon_api.update_event(event["id"], status="failed")
                    ayon_api.update_event(source_event["id"], status="failed")

                logging.info("Event has been processed... setting to finished!")
                ayon_api.update_event(event["id"], status="finished")
                ayon_api.update_event(source_event["id"], status="finished")

            except Exception as err:
                log_traceback(err)

    def _upload_sk_notes_to_ftrack(self, payload):
        """ Update an FTrack task with SyncSketch notes.

        The payload contains a SyncSketch reveiw, which we use to find the
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
        review_media_with_notes = []
        review_id = payload["review"]["id"]

        for media in self.sk_session.get_media_by_review_id(review_id)["objects"]:
            media_dict = {}

            ayon_id = media.get("metadata", {}).get("ayonVersionID")

            if not ayon_id:
                logging.error(f"Media {media['name']} is missing the AYON id.")
                continue

            # Not sure what data type are we uploading to Ayon...
            ayon_entity = ayon_api.get_subset_by_id(ayon_id)

            if not ayon_entity.attribs.get("ftrackId"):
                logging.error(f"Media {ayon_entity} is missing the Ftrack ID.")
                continue

            media_dict["ftrack_id"] = ayon_entity.attribs.get("ftrackId")
            media_dict["notes"] = []

            for note in self.sk_session.get_annotations(media["id"], review_id=review_id)["objects"]:
                if not note["text"]:
                    logging.info("Note has no text, most likely it's a sketch.")
                    continue

                note_text = f"{note['text']}\nFilepath: {ayon_entity.path}\n{payload['review']['link']}"
                media_dict["notes"].append({
                    "username": note["creator"]["username"],
                    "text": note_text
                })

            if media_dict["notes"]:
                review_media_with_notes.append(media_dict)


        for sk_media in review_media_with_notes:
            ayon_entity = ayon_api.get_subset_by_id(sk_media["ayon_id"])

            #Ftrack AssetVersion
            ft_av = self._ft_query_one_by_id(
                "AssetVersion",
                sk_media['ftrack_id'],
                selection=["task_id"]
            )

            if not ft_av:
                logging.error("Unable to find Task <{ftrack_id}>")
                continue

            ft_task = self._ft_query_one_by_id(
                "Task",
                ft_av['task_id'],
                selection=["notes", "notes.author.username", "notes.content"]
            )

            existing_ftrack_notes = [
                {"username": note["author"]["username"], "text": note["content"]}
                for note in ft_task["notes"]
            ]

            for sk_note in sk_media["notes"]:
                if sk_note not in existing_ftrack_notes:
                    try:
                        ft_user = self.ft_session.session.query(
                            f"User where username is {sk_note['username']}"
                        ).one()
                    except Exception:
                        # Default to the API user
                        api_username = self.settings["ftrack_api_username"]
                        ft_user = self.ft_session.session.query(
                            f"User where username is '{api_username}'"
                        )

                    new_note = self.ft_session.create('Note', {
                        'content': sk_note["text"],
                        'author': ft_user
                    })
                    ft_task["notes"].append(new_note)

            self.ft_session.commit()

        def _ft_query_one_by_id(self, ft_type, id, selection=None):
            """ Helper method to do long FTrack queries.

            Args:
                ft_type (str): The FTrack entity type.
                id (str): The Ftrack entity id.
                selection (Optional|list): List of attributes to select.

            Returns:
                Ftrack Entity | ftrack_api.exception.NoResultFoundError | ftrack_api.exception.ServerError.
            """
            query = f"{ft_type} where id is {id}"

            if selection:
                if isinstance(selection, list):
                    query = f"select {', '.join(selection)} from {query}"
                else:
                    logging.error("Selection has to be a list, ignoring.")

            return self.ft_session.query(query).one()


