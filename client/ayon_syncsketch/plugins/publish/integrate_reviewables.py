# -*- coding: utf-8 -*-
"""Integrate SyncSketch reviewables."""
import os
from copy import deepcopy
import pyblish.api
from openpype.pipeline import KnownPublishError
from openpype.pipeline.publish import (
    OpenPypePyblishPluginMixin
)
from openpype.lib import (
    StringTemplate,
    BoolDef
)
from openpype_modules.ayon_syncsketch.api.server_handler import ServerCommunication
import requests


class IntegrateReviewables(pyblish.api.InstancePlugin,
                           OpenPypePyblishPluginMixin):
    """Integrate SyncSketch reviewables.

    Uploads representations as reviewables to SyncSketch.
    Representations need to be tagged with "syncsketchreview" tag.
    """
    settings_category = "syncsketch"

    order = pyblish.api.IntegratorOrder
    label = "Integrate SyncSketch reviewables"


    review_list = "Uploads from Ayon"
    review_item_name_template = "{asset} | {task[name]} | v{version} .{ext}"
    representation_tag = "syncsketchreview"

    def process(self, instance):
        self.log.info("Integrating SyncSketch reviewables...")

        # get the attribute values from data
        instance.data["attributeValues"] = self.get_attr_values_from_data(
            instance.data)
        upload_to_syncsketch = instance.data["attributeValues"].get("SyncSketchUpload", True)

        # skip if instance without representation
        representations = [
            repre for repre in instance.data.get("representations", [])
            if repre.get("tags", []) and self.representation_tag in repre["tags"]
        ]
        if not representations or not upload_to_syncsketch:
            self.log.info("Skipping SyncSketch publishing: `{}`".format(
                instance.data["name"]))
            return

        context = instance.context
        user_name = context.data["user"]
        anatomy_data = instance.data["anatomyData"]
        syncsketch_id = context.data["syncsketchProjectId"]
        server_config = context.data["syncsketchServerConfig"]
        version_entity = instance.data["versionEntity"]
        server_handler = self.get_server_handler(context, server_config)

        self.log.debug("Version entity id: {}".format(version_entity["_id"]))

        # making sure the server is available
        response = server_handler.is_connected()
        if not response:
            raise requests.exceptions.ConnectionError("SyncSketch connection failed.")

        # get review list the project
        review_list_id = self.get_review_list_id(context, server_handler, syncsketch_id)

        self.log.info("Review list ID: {}".format(review_list_id))

        review_item_id = self.upload_reviewable(
            representations, anatomy_data, server_handler, review_list_id, user_name)

        # update review item with avalon version entity ID
        self.update_version_entity(version_entity, review_item_id)

        # update version entity with review item ID
        if review_item_id:
            version_attributes = instance.data.get("versionAttributes", {})
            version_attributes["syncsketchId"] = review_item_id
            instance.data["versionAttributes"] = version_attributes
        else:
            raise KnownPublishError("SyncSketch upload failed.")

    def update_version_entity(self, version_entity, review_item_id):
        self.log.debug("Version entity id: {}".format(version_entity["_id"]))
        self.log.debug("Review item id: {}".format(review_item_id))


    def upload_reviewable(self,
            representations, anatomy_data, server_handler,
            review_list_id, user_name
        ):
        """Upload reviewable to SyncSketch."""
        # loop representations representations with tag "syncsketchreview"
        for representation in representations:
            formatting_data = deepcopy(anatomy_data)
            # update anatomy data with representation data
            formatting_data["ext"] = representation["ext"]
            if representation.get("output"):
                formatting_data["output"] = representation["output"]

            # format the file_name template
            review_item_name = StringTemplate(
                self.review_item_name_template).format(formatting_data)

            # get the file path only for single file representations
            file_path = os.path.join(
                representation["stagingDir"], representation["files"]
            )

            self.log.debug("Uploading reviewable: {}".format(file_path))
            self.log.debug("Review item name: {}".format(review_item_name))

            # upload them to SyncSketch
            response = server_handler.upload_review_item(
                review_list_id, file_path,
                artist_name=user_name,
                file_name=review_item_name,
                no_convert_flag=False,
                item_parent_id=False
            )
            # get ID of the uploaded media: response["id"]
            return response.get("id")

    def get_review_list_id(self, context, server_handler, project_id):
        """Get review list ID by name."""
        # get the review list ID from cached context.data if exists
        review_list_id = context.data.get("review_list_id")
        if review_list_id:
            return review_list_id

        # get the review list ID from SyncSketch project
        response = server_handler.get_reviews_by_project_id(project_id)
        for review in response["objects"]:
            if review["name"] == self.review_list:
                review_list_id = review["id"]

        # if review list not found, create it
        if not review_list_id:
            response = server_handler.create_review(project_id, self.review_list)
            review_list_id = response["id"]

        return review_list_id

    def get_server_handler(self, context, server_config):
        # cache the server handler into context.data
        if "syncsketchServerHandler" not in context.data:
            context.data["syncsketchServerHandler"] = ServerCommunication(
                user_auth=server_config["auth_user"],
                api_key=server_config["auth_token"],
                host=server_config["url"],
                log=self.log
            )
        return context.data["syncsketchServerHandler"]

    @classmethod
    def get_attribute_defs(cls):
        return [
            BoolDef(
                "SyncSketchUpload",
                default=True,
                label="SyncSketch Upload"
            )
        ]