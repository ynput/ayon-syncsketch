from pydantic import Field

from ayon_server.settings import BaseSettingsModel


class IntegrateSyncSketchReviewableModel(BaseSettingsModel):
    """Settings for Integrate SyncSketch reviewable plugin."""

    review_list: str = Field(title="Review List")


class PublishPluginsModel(BaseSettingsModel):
    IntegrateSyncSketchReviewable: IntegrateSyncSketchReviewableModel = \
        Field(
            default_factory=IntegrateSyncSketchReviewableModel,
            title="Integrate SyncSketch Reviewable"
        )


DEFAULT_SYNCSKETCH_PLUGINS_SETTINGS = {
    "IntegrateSyncSketchReviewable":  {
        "review_list": "Uploads from Ayon"
    }
}
