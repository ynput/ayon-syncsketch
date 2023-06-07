from pydantic import Field

from ayon_server.settings import BaseSettingsModel


class IntegrateReviewablesModel(BaseSettingsModel):
    """Settings for Integrate SyncSketch reviewable plugin."""

    review_list: str = Field(title="Review List")
    review_item_name_template: str = Field(title="Review Item Name Template")


class PublishPluginsModel(BaseSettingsModel):
    IntegrateReviewables: IntegrateReviewablesModel = \
        Field(
            default_factory=IntegrateReviewablesModel,
            title="Integrate Reviewables"
        )


DEFAULT_SYNCSKETCH_PLUGINS_SETTINGS = {
    "IntegrateReviewables":  {
        "review_list": "Uploads from Ayon",
        "review_item_name_template": "{hierarchy}/{asset_name}/{task_name}/{version}"
    }
}
