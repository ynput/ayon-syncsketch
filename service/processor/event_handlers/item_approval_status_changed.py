from nxtools import logging

from processor.lib.event_abstraction import FtrackNoteSyncing


class SyncsketchItemApprovalStatusChanged(FtrackNoteSyncing):
    """ SyncSketch Item Approval Status Changed Event Handler.

    This class is responsible for processing SyncSketch Item Approval Status
    Changed events.
    """

    def __init__(self, addon_settings):
        """ Ensure both Ayon, Syncsketch and Ftrack connections are available.
        """
        logging.info("Initializing `SyncsketchItemApprovalStatusChanged`...")
        super().__init__(addon_settings)


    def process(self, payload):
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

        ayon_version_ids = self._get_metadata_version_ids(
            [review_item]
        )

        self._process_all_versions(
            ayon_version_ids, review_id, project_name, review_link,
            status_name=status_name
        )
