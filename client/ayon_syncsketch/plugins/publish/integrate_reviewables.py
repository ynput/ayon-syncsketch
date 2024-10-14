# -*- coding: utf-8 -*-
"""Integrate SyncSketch reviewables."""
import os
import json
from copy import deepcopy
from pprint import pformat

import pyblish.api
import requests

from ayon_core.pipeline import KnownPublishError, AYONPyblishPluginMixin
from ayon_core.lib import (
    StringTemplate,
    BoolDef,
    filter_profiles,
    prepare_template_data
)
from ayon_syncsketch.common.server_handler import ServerCommunication


class IntegrateReviewables(pyblish.api.InstancePlugin,
                           AYONPyblishPluginMixin):
    """Integrate SyncSketch reviewables.

    Uploads representations as reviewables to SyncSketch.
    Representations need to be tagged with "syncsketchreview" tag.
    """
    settings_category = "syncsketch"

    order = pyblish.api.IntegratorOrder
    label = "Integrate SyncSketch reviewables"

    representation_tag = "syncsketchreview"
    review_item_profiles = []

    def filter_review_item_profiles(
        self, family, host_name, task_name, task_type
    ):
        if not self.review_item_profiles:
            return []

        filtering_criteria = {
            "families": family,
            "hosts": host_name,
            "tasks": task_name,
            "task_types": task_type
        }

        matching_profile = filter_profiles(
            self.review_item_profiles, filtering_criteria)

        self.log.debug("Matching profile: {}".format(matching_profile))
        return matching_profile

    def _format_template(self, instance, template, formatting_data):
        """Format template with data from instance and anatomy data."""

        nested_keys = ["folder", "task"]
        fill_pairs_keys = [
            "variant", "family", "app", "user", "subset",
            "host", "output", "ext", "name", "short", "version",
            "type"
        ]

        def prepare_template_data_pairs(data):
            """Prepare data for template formatting."""
            fill_pairs = {}
            for key, value in data.items():
                if key in nested_keys and isinstance(value, dict):
                    self.log.debug("Nested key: {}:{}".format(key, value))
                    fill_pairs[key] = prepare_template_data_pairs(value)
                elif key in fill_pairs_keys and isinstance(value, str):
                    self.log.debug("Key: {}:{}".format(key, value))
                    fill_pairs.update(prepare_template_data({key: value}))
                elif key in fill_pairs_keys and not isinstance(value, str):
                    fill_pairs[key] = value
            return fill_pairs

        formatting_data = deepcopy(formatting_data)
        host_name = instance.context.data["hostName"]
        variant = instance.data["variant"]
        formatting_data.update({
            "variant": variant,
            "app": host_name,
            "host": host_name
        })

        formatting_data_pairs = prepare_template_data_pairs(formatting_data)
        self.log.debug("Formatting data pairs: {}".format(
            pformat(formatting_data_pairs)
        ))

        formatted_name = StringTemplate(
                template).format(formatting_data_pairs)

        self.log.debug("Formatted name: {}".format(formatted_name))

        return formatted_name

    def process(self, instance):
        self.log.info("Integrating SyncSketch reviewables...")

        # get the attribute values from data
        instance.data["attributeValues"] = self.get_attr_values_from_data(
            instance.data)
        upload_to_syncsketch = instance.data["attributeValues"].get(
            "SyncSketchUpload", True)

        # skip if instance without representation
        representations = [
            repre for repre in instance.data.get("representations", [])
            if repre.get("tags", []) and self.representation_tag in repre["tags"]  # noqa: E501
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

        self.log.debug("Syncsketch Project ID: {}".format(syncsketch_id))
        self.log.debug("Version entity id: {}".format(version_entity["_id"]))

        # making sure the server is available
        response = server_handler.is_connected()
        if not response:
            raise requests.exceptions.ConnectionError(
                "SyncSketch connection failed.")

        # filter review item profiles
        self.matching_profile = self.filter_review_item_profiles(
            instance.data["family"],
            instance.context.data["hostName"],
            anatomy_data["task"]["name"],
            anatomy_data["task"]["type"]
        )

        if not self.matching_profile:
            raise KnownPublishError(
                "No matching profile for SyncSketch review item found.")

        # get review list the project
        review_list_id = self.get_review_list_id(
            instance, server_handler, syncsketch_id)

        self.log.info("Review list ID: {}".format(review_list_id))

        review_item_id, review_item_name = self.upload_reviewable(
            instance,
            representations,
            server_handler,
            review_list_id,
            user_name
        )

        # update version entity with review item ID
        if review_item_id:
            # update review item with avalon version entity ID
            self.update_version_entity(
                server_handler,
                version_entity,
                review_item_id,
                review_item_name
            )

            version_attributes = instance.data.get("versionAttributes", {})
            version_attributes["syncsketchId"] = review_item_id
            instance.data["versionAttributes"] = version_attributes
        else:
            raise KnownPublishError("SyncSketch upload failed.")

    def update_version_entity(
            self, server_handler, version_entity,
            review_item_id, review_item_name
        ):
        """Update version entity with review item ID."""
        data = {
            # updating name without extension (duplicity issue)
            "name": os.path.splitext(review_item_name)[0],
            "metadata": json.dumps({"ayonVersionID": version_entity["_id"]})
        }
        self.log.debug("Version entity id: {}".format(version_entity["_id"]))
        self.log.debug("Review item id: {}".format(review_item_id))

        # update review item with version entity ID
        result = server_handler.update_review_item(review_item_id, data)

        self.log.debug("Review item updated: {}".format(result))

    def upload_reviewable(
        self, instance, representations,
        server_handler, review_list_id, user_name
    ):
        """Upload reviewable to SyncSketch."""
        anatomy_data = instance.data["anatomyData"]

        # loop representations representations with tag "syncsketchreview"
        for representation in representations:
            formatting_data = deepcopy(anatomy_data)
            # update anatomy data with representation data
            formatting_data["ext"] = representation["ext"]
            if representation.get("output"):
                formatting_data["output"] = representation["output"]

            # solving the review item name
            review_item_name_template = self.matching_profile[
                "review_item_name_template"]

            if not review_item_name_template:
                raise KnownPublishError(
                    "Name in matching profile for "
                    "SyncSketch review item not filled. "
                    "\n\nProfile data: {}".format(
                        self.matching_profile)
                )

            self.log.debug("Review item name template: {}".format(
                review_item_name_template))

            # add extension
            review_item_name_template = (
                review_item_name_template + " .{ext}")

            # format the file_name template
            review_item_name = self._format_template(
                instance, review_item_name_template, formatting_data
            )

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
            # get ID of the uploaded media: response["id"] and review item name
            return response.get("id"), review_item_name

    def get_review_list_id(self, instance, server_handler, project_id):
        """Get review list ID by name."""
        context = instance.context
        # get the review list ID from cached context.data if exists
        review_list_id = context.data.get("review_list_id")
        if review_list_id:
            self.log.debug("Cached Review list ID: {}".format(review_list_id))
            return review_list_id

        # solving the review list name
        matching_profile_review_list_name = self.matching_profile[
            "list_name_template"]

        if not matching_profile_review_list_name:
            raise KnownPublishError(
                "Name in matching profile for "
                "SyncSketch review list not filled. "
                "\n\nProfile data: {}".format(
                    self.matching_profile)
            )

        self.log.debug("Review list name template: {}".format(
                matching_profile_review_list_name))

        # format the review list name template
        review_list_name = self._format_template(
            instance,
            matching_profile_review_list_name,
            instance.data["anatomyData"]
        )

        self.log.debug("Review list Name: {}".format(review_list_name))

        # get the review list ID from SyncSketch project
        response = server_handler.get_reviews_by_project_id(project_id)
        for review in response["objects"]:
            if review["name"] == review_list_name:
                review_list_id = review["id"]
                self.log.debug(
                    "Existing Review list ID: {}".format(review_list_id))
                break

        # if review list not found, create it
        if not review_list_id:
            response = server_handler.create_review(
                project_id, review_list_name)
            review_list_id = response["id"]
            self.log.debug("Created Review list ID: {}".format(review_list_id))

        context.data["review_list_id"] = review_list_id

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
