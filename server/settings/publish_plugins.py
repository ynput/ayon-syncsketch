from pydantic import Field
from ayon_server.settings import BaseSettingsModel


class IntegrateReviewablesModel(BaseSettingsModel):
    """Settings for Integrate SyncSketch reviewable plugin."""

    review_list: str = Field(title="Review List")
    review_item_name_template: str = Field(title="Review Item Name Template")
    representation_tag: str = Field(
        title="Representations' Activation Tag",
        disabled=True,
        description=(
            "This is just for information and cannot be changed. "
            "This meant to be copy pasted to the tag field of "
            "the representation you want to upload to SyncSketch."
        )
    )


class PublishPluginsModel(BaseSettingsModel):
    IntegrateReviewables: IntegrateReviewablesModel = \
        Field(
            default_factory=IntegrateReviewablesModel,
            title="Integrate Reviewables"
        )


DEFAULT_SYNCSKETCH_PLUGINS_SETTINGS = {
    "IntegrateReviewables":  {
        "review_list": "Uploads from Ayon",
        "review_item_name_template": "{asset} | {task[name]} | v{version} .{ext}",
        "representation_tag": "syncsketchreview"
    }
}
