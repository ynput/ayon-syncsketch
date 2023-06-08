import pytest
import os
from tests.lib import BaseTest
from server_handler import ServerCommunication


class TestServerHandler(BaseTest):
    def test_upload_file(self):
        server_handle = ServerCommunication(
            user_auth=os.environ["SYNCSKETCH_USER_AUTH"],
            api_key=os.environ["SYNCSKETCH_API_KEY"],
        )
        response = server_handle.upload_review_item(
            review_id=os.environ["SYNCSKETCH_REVIEW_ID"],
            filepath="renderCompositingMain_baking.jpg",
            artist_name="John.Smith",
            file_name="shot | episode | sequence | shot01 | compositing | v11 .mp4",
            no_convert_flag=True,
            item_parent_id=False
        )
        print(response)