import pytest
import os
from tests.lib import BaseTest
from server_handler import ServerCommunication

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
class TestServerHandler(BaseTest):
    def test_upload_image_file(self):
        server_handle = ServerCommunication(
            user_auth=os.environ["SYNCSKETCH_USER_AUTH"],
            api_key=os.environ["SYNCSKETCH_API_KEY"],
        )
        response = server_handle.upload_review_item(
            review_id=os.environ["SYNCSKETCH_REVIEW_ID"],
            filepath=os.path.join(THIS_DIR, "test_image.jpg"),
            artist_name="John.Smith",
            file_name="shot | episode | sequence | shot01 | compositing | v11 .mp4",
            no_convert_flag=True,
            item_parent_id=False
        )
        print(response)

    def test_upload_video_file(self):
        server_handle = ServerCommunication(
            user_auth=os.environ["SYNCSKETCH_USER_AUTH"],
            api_key=os.environ["SYNCSKETCH_API_KEY"],
        )
        response = server_handle.upload_review_item(
            review_id=os.environ["SYNCSKETCH_REVIEW_ID"],
            filepath=os.path.join(THIS_DIR, "test_video.mp4"),
            artist_name="John.Smith",
            file_name="shot | episode | sequence | shot01 | compositing | v11 .mp4",
            no_convert_flag=True,
            item_parent_id=False
        )
        print(response)