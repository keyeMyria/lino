from django.db import models
from django.contrib.contenttypes.models import ContentType
from lino.api import dd


class Member(dd.Model):
    name = models.CharField(max_length=200)
    email = models.EmailField(max_length=200, blank=True)

    def __unicode__(self):
        return self.name


class Note(dd.Model):
    owner_type = dd.ForeignKey(ContentType)
    owner_id = models.PositiveIntegerField(blank=True, null=True)
    owner = dd.GenericForeignKey(
        'owner_type', 'owner_id',
        verbose_name="Owner")
    
    subject = models.CharField(max_length=200)
    body = models.TextField()


class Memo(dd.Model):
    owner_type = dd.ForeignKey(ContentType)
    owner_id = models.PositiveIntegerField()
    owner = dd.GenericForeignKey(
        'owner_type', 'owner_id',
        verbose_name="Owner")
    
    subject = models.CharField(max_length=200)
    body = models.TextField()

