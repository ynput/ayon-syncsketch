# -*- coding: utf-8 -*-
"""Integrate SyncSketch reviewables."""
import pyblish.api
from openpype_modules.ayon_syncsketch.api.server_handler import ServerCommunication
import requests


class IntegrateReviewables(pyblish.api.InstancePlugin):
    """Integrate SyncSketch reviewables.

    Uploads representations as reviewables to SyncSketch.
    Representations need to be tagged with "syncsketchreview" tag.
    """

    order = pyblish.api.IntegratorOrder
    label = "Integrate SyncSketch reviewables"

    review_list = "Uploads from Ayon"
    review_item_name_template = "{hierarchy}/{asset_name}/{task_name}/{version}"
    representation_tag = "syncsketchreview"

    def process(self, instance):
        self.log.info("Integrating SyncSketch reviewables...")

        user_name = instance.context.data["user"]
        anatomy_data = instance.data["anatomyData"]
        syncsketch_id = instance.context.data["syncsketchProjectId"]
        server_config = instance.context.data["syncsketchServerConfig"]

        # cache the server handler into context.data
        server_handler = ServerCommunication(
            user_auth=server_config["auth_user"],
            api_key=server_config["auth_token"],
            host=server_config["url"]
        )

        # check if server is available
        response = server_handler.is_connected()

        if not response:
            raise requests.exceptions.ConnectionError("SyncSketch connection failed.")

        # check if review list is available on the project
        #    - server_handler.get_reviews_by_project_id(self, project_id, limit=100, offset=0)
        # create the review list if it doesn't exist
        #    - server_handler.create_review(self, project_id, name, description="", data=None)

        # get all representations with tag "syncsketchreview"
        # upload them to SyncSketch
        #   - 'file_name' - self.review_item_name_template formatted by anatomy_data
        #   - server_handler.add_media(self, review_id, filepath, artist_name="", file_name="",
        #      no_convert_flag=False, item_parent_id=False)
        # get ID of the uploaded media: response["id"]
