from nxtools import logging

from processor.lib.event_abstraction import FtrackNoteSyncing


class SyncsketchReviewSessionEnd(FtrackNoteSyncing):
    """ SyncSketch Review Session End Event Handler.

    This class is responsible for processing SyncSketch Review Session End events.
    """

    def __init__(self, addon_settings):
        """ Ensure both Ayon, Syncsketch and Ftrack connections are available.
        """
        """ Ensure both Ayon, Syncsketch and Ftrack connections are available.
        """
        logging.info("Initializing `SyncsketchReviewSessionEnd`...")
        super().__init__(addon_settings)

    def process(self, payload):
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

        logging.info(f"Processing review {review_id}")
        review_items = self.syncsketch_session.get_media_by_review_id(
            review_id)

        ayon_version_ids = self._get_metadata_version_ids(
            review_items.get("objects", [])
        )
        self._process_all_versions(
            ayon_version_ids, review_id, project_name, review_link)
