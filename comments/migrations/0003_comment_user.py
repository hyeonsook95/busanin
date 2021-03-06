# Generated by Django 2.2.8 on 2020-03-13 14:46

from django.conf import settings
from django.db import migrations, models
import users.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('comments', '0002_comment_post'),
    ]

    operations = [
        migrations.AddField(
            model_name='comment',
            name='user',
            field=models.ForeignKey(on_delete=models.SET(users.models.set_FkUser), related_name='comments', to=settings.AUTH_USER_MODEL),
        ),
    ]
