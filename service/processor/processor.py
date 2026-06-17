from __future__ import annotations

import atexit
import logging
import signal
import sys
import threading
import time
import traceback

import ayon_api

from .lib import (
    SyncsketchConfig,
    get_syncsketch_config,
    get_syncksketch_settings,
    validate_syncsketch_credentials,
)
from .logic import (
    push_review_to_syncsketch,
    pull_comment_from_syncsketch,
    SyncError,
)


class SyncSketchContext:
    credentials: SyncsketchConfig | None = None
    last_credentials: SyncsketchConfig | None = None
    credentials_valid: bool = False
    last_validation_time: float = 0.0


class _GlobalContext:
    stop_event: threading.Event = threading.Event()
    process_cleaned_up: bool = False
    syncsketch: SyncSketchContext = SyncSketchContext()


def _context_has_valid_credentials() -> bool:
    """Make sure SyncSketch credentials are valid."""
    syncsketch = _GlobalContext.syncsketch
    if syncsketch.credentials_valid:
        return True

    settings = get_syncksketch_settings()
    config = get_syncsketch_config(settings)
    if validate_syncsketch_credentials(config):
        syncsketch.credentials = config
        syncsketch.credentials_valid = True
        return True

    addon_version = ayon_api.get_service_addon_version()
    sleep_time = 5
    if syncsketch.last_validation_time == 0.0:
        logging.warning(
            "SyncSketch credentials are not set or invalid."
            " Please check settings"
            f" of syncksketh {addon_version}."
        )
    elif time.time() - syncsketch.last_validation_time > 60:
        logging.warning(
            "SyncSketch credentials are still not valid."
            " Please check settings"
            f" of syncksketh {addon_version}."
        )
        sleep_time = 30

    syncsketch.last_validation_time = time.time()
    while True:
        if _GlobalContext.stop_event.is_set():
            break
        diff = time.time() - syncsketch.last_validation_time
        if diff > sleep_time:
            break
        time.sleep(1)
    return False


def listen_for_events():
    while not _GlobalContext.stop_event.is_set():
        if not _context_has_valid_credentials():
            continue

        job_events = list(ayon_api.get_events(
            [
                "syncsketch.push.review",
                "syncsketch.pull.review",
            ],
            statuses={"pending"},
        ))
        if not job_events:
            time.sleep(10)
            continue

        job_event = job_events[0]
        ayon_api.update_event(
            job_event["id"],
            status="in_progress",
        )

        description = "Action process finished."
        new_status = "finished"
        payload = None
        try:
            if job_event["topic"] == "syncsketch.push.review":
                push_review_to_syncsketch(
                    job_event, _GlobalContext.syncsketch.credentials
                )

            elif job_event["topic"] == "syncsketch.pull.review":
                pull_comment_from_syncsketch(
                    job_event, _GlobalContext.syncsketch.credentials
                )

            else:
                description = f"Unknown job event topic: {job_event['topic']}"
                logging.warning(description)
                new_status = "failed"

        except SyncError as exc:
            description = str(exc)
            logging.error(description)
            new_status = "failed"

        except Exception:
            logging.exception(
                f"Failed to process job event {job_event['id']}"
            )
            new_status = "failed"
            description = (
                "Unexpected error occurred during action process."
                " Check logs for details."
            )
            payload = job_event["payload"]
            payload["traceback"] = traceback.format_exc()

        finally:
            ayon_api.update_event(
                job_event["id"],
                status=new_status,
                description=description,
                payload=payload,
            )


def main_loop():
    while not _GlobalContext.stop_event.is_set():
        logging.info("Starting listen server")
        try:
            listen_for_events()
        finally:
            logging.info("Server stopped.")
    logging.info("Main loop stopped.")


def _cleanup_process():
    """Cleanup timer threads on exit."""
    if _GlobalContext.process_cleaned_up:
        return
    _GlobalContext.process_cleaned_up = True
    logging.info("Process stop requested. Terminating process.")
    logging.info("Canceling threading timers.")
    counter = 0
    for thread in threading.enumerate():
        if isinstance(thread, threading.Timer):
            thread.cancel()
            counter += 1

    if counter:
        logging.info(f"Canceled {counter} timers.")

    logging.info("Stopping main loop.")
    if not _GlobalContext.stop_event.is_set():
        _GlobalContext.stop_event.set()


def main():
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    try:
        ayon_api.init_service()
        connected = True
    except Exception:
        connected = False

    if not connected:
        logging.warning("Failed to connect to AYON server.")
        # Sleep for 10 seconds, so it is possible to see the message in
        #   docker
        # NOTE: Becuase AYON connection failed, there's no way how to log it
        #   to AYON server (obviously)... So stdout is all we have.
        time.sleep(10)
        sys.exit(1)

    logging.info("Connected to AYON server.")

    # Register interrupt signal
    def signal_handler(sig, frame):
        _cleanup_process()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(_cleanup_process)

    ayon_api.set_sender_type("syncsketch")
    try:
        main_loop()
    finally:
        _cleanup_process()
