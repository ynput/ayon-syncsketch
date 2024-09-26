from pydantic import validator

from ayon_server.settings import (
    BaseSettingsModel,
    task_types_enum,
    SettingsField,
    ensure_unique_names
)


class ReviewItemProfile(BaseSettingsModel):
    _layout = "collapsed"
    name: str = SettingsField("", title="Name")
    product_types: list[str] = SettingsField(
        default_factory=list, title="Product types"
    )
    hosts: list[str] = SettingsField(default_factory=list, title="Hosts")
    task_types: list[str] = SettingsField(
        default_factory=list,
        title="Task types",
        enum_resolver=task_types_enum
    )
    tasks: list[str] = SettingsField(default_factory=list, title="Task names")
    list_name_template: str = SettingsField(
        "", title="Review list name template")
    review_item_name_template: str = SettingsField(
        "", title="Review item name template")


class IntegrateReviewablesModel(BaseSettingsModel):
    """Settings for Integrate SyncSketch reviewable plugin."""

    representation_tag: str = SettingsField(
        title="Representations' activation tag",
        disabled=True,
        description=(
            "This is just for information and cannot be changed. "
            "This meant to be copy pasted to the tag field of "
            "the representation you want to upload to SyncSketch."
        )
    )
    review_item_profiles: list[ReviewItemProfile] = SettingsField(
        default_factory=list,
        title="Review item profiles"
    )

    @validator("review_item_profiles")
    def ensure_unique_names(cls, value):
        """Ensure name fields within the lists have unique names."""
        ensure_unique_names(value)
        return value


class PublishPluginsModel(BaseSettingsModel):
    IntegrateReviewables: IntegrateReviewablesModel = \
        SettingsField(
            default_factory=IntegrateReviewablesModel,
            title="Integrate reviewables"
        )


DEFAULT_SYNCSKETCH_PLUGINS_SETTINGS = {
    "IntegrateReviewables":  {
        "representation_tag": "syncsketchreview",
        "review_item_profiles": [
            {
                "name": "Default",
                "product_types": [],
                "hosts": [],
                "task_types": [],
                "tasks": [],
                "list_name_template": "Uploads from Ayon",
                "review_item_name_template": "{folder[name]} | {subset} | v{version}",  # noqa: E501
            },
        ]
    }
}
