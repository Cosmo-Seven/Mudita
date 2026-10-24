from django.db import models

from models.base_models import BaseModel


class GroupModel(BaseModel):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        app_label = "core"
        db_table = "groups"
        verbose_name = "Group"
        verbose_name_plural = "Groups"


class TeamModel(BaseModel):
    group = models.ForeignKey(
        GroupModel, on_delete=models.CASCADE, related_name="teams"
    )
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name

    class Meta:
        app_label = "core"
        db_table = "teams"
        verbose_name = "Team"
        verbose_name_plural = "Teams"
