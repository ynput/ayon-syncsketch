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
        # check what is the ayon version id stored at related review item in syncsketch
        # get ayon version entity and get ftrack version id from version attributes
        # pass the comment to related ftrack version entitiy comments
        # {
        # "action": "review_session_end",
        # "review": {
        #     "id": 2783585,
        #     "link": "https://syncsketch.com/sketch/NmZmNTg5N2I5/",
        #     "name": "My fancy review"
        # },
        # "project_name": "testApiProjectKey"
        # }
        return
        review_media_with_notes = []
        review_id = payload["review"]["id"]
        # pseudocode, since i don't have a real payload
        for media in self.sk_session.get_media_by_review_id(review_id)["objects"]:
            media_dict = {}

            ayon_id = media.get("metadata", {}).get("ayonVersionID")
                
            if not ayon_id:
                logging.error(f"Media {media['name']} is missing the AYON id.")
                continue

            media_dict["ayon_id"] = ayon_id
            media_dict["notes"] = []

            for note in self.sk_session.get_annotations(media["id"], review_id=review_id)["objects"]:
                media_dict["notes"].append({
                    "username": note["creator"]["username"],
                    "text": note["text"]
                })

            if media_dict["notes"]:
                review_media_with_notes.append(media_dict)


        for entity in review_media_with_notes:
            ayon_entity = ayon_api.get_subset_by_id(entity["ayon_id"])

            if not ayon_entity:
                logging.error(f"Couldn't find AYON entity with id {ayon_id}")
                continue

            ftrack_id = ayon_entity.attribs.get("ftrackId")

            if not ftrack_id:
                logging.error("AYON entity does not have the ftrackId attribute.")
                continue

            ft_entity = self.ft_session.query(f'Version where id is {ftrack_id}').one()

            if not ft_entity:
                logging.error("Unable to find Version <{ftrack_id}>")
                continue

            # Compare sessions notes with the ft entity notes
            # Add only the new ones


