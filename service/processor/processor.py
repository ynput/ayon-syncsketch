"""
A SyncSketch Events listener processor for Ayon.

This service will continually run and query the Ayon Events Server in order to
enroll the events of topic `syncsketch.leech` to perform processing of Shotgrid
related events.
"""
import os
from importlib.machinery import SourceFileLoader
import time
import inspect
import socket
import itertools
from nxtools import logging, log_traceback

import ayon_api
import ftrack_api

from .lib.event_abstraction import EventProcessor


class SyncSketchProcessor:
    ftrack_statuses = None
    event_sleep_time = 0.5
    event_handlers_folder_name = "event_handlers"

    def __init__(self):
        """ Ensure both Ayon, Syncsketch and Ftrack connections are available.
        """
        logging.info("Initializing the SyncSketch Processor.")
        logging.debug(f"AYON_SERVER_URL: {os.environ['AYON_SERVER_URL']}")
        try:
            # self.settings = ayon_api.get_service_addon_settings()
            self.settings = ayon_api.get_addon_settings(
                "syncsketch",
                os.environ["AYON_ADDON_VERSION"]
            )

        except Exception as e:
            logging.error("Unable to get Addon settings from the server.")
            log_traceback(e)
            raise e


    def start_processing(self):
        """ Main loop enrolling on AYON events.

        We look for events of the topic `syncsketch.event` and process them by
        issuing events of topic `syncsketch.proc` which run the
        `_upload_review_ notes_to_ftrack` method against the event payload.
        """
        logging.info("Starting the SyncSketch Processor.")
        root_dir = os.path.dirname(__file__)
        self.event_handlers_folder = os.path.join(
            root_dir, self.event_handlers_folder_name)

        # Get a list of all the Python files in the folder
        handler_files = [
            f[:-3]
            for f in os.listdir(self.event_handlers_folder)
            if f.endswith(".py")
        ]

        # Import each module and get the class
        event_handlers = {}
        for handler_file in handler_files:

            module = SourceFileLoader(
                f"{self.event_handlers_folder_name}.{handler_file}",
                os.path.join(self.event_handlers_folder, f"{handler_file}.py")
            ).load_module()

            for attr in dir(module):

                handler_class = getattr(module, attr)

                if (
                    not inspect.isclass(handler_class)
                    or handler_class is EventProcessor
                    or not issubclass(handler_class, EventProcessor)
                ):
                    continue

                event_handler = handler_class(self.settings)
                event_handlers[handler_file] = event_handler

        event_cycle = itertools.cycle(event_handlers.items())
        while True:
            event_topic = None
            try:
                event_topic, event_handler = next(event_cycle)
                event_topic = f"syncsketch.{event_topic}"
                logging.info(
                    f"Querying event `{event_topic}` from events...")
                event = ayon_api.enroll_event_job(
                    event_topic,
                    "syncsketch.proc",
                    socket.gethostname(),
                    description=f"\'{event_topic}\' processing",
                )
                if not event:
                    time.sleep(self.event_sleep_time)
                    continue

                event_status = "failed"
                try:
                    source_event = ayon_api.get_event(event["dependsOn"])
                    payload = source_event["payload"]

                    if not payload:
                        time.sleep(self.event_sleep_time)
                        ayon_api.update_event(event["id"], status="finished")
                        continue

                    event_handler.process(payload)

                    logging.info(
                        "Event has been processed... setting to finished!")
                    event_status = "finished"

                except (
                    ftrack_api.exception.Error,
                    Exception
                ) as err:
                    logging.error(f"Unable to process handler {payload}")
                    log_traceback(err)

                finally:
                    ayon_api.update_event(event["id"], status=event_status)

                time.sleep(self.event_sleep_time)

            except Exception as err:
                logging.error(f"Unable to enroll for Ayon events: {err}")
                time.sleep(self.event_sleep_time)
                continue
