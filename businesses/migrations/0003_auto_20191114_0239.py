# Generated by Django 2.2.5 on 2019-11-13 17:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('businesses', '0002_auto_20191114_0101'),
    ]

    operations = [
        migrations.RenameField(
            model_name='photo',
            old_name='Business',
            new_name='business',
        ),
        migrations.AlterField(
            model_name='business',
            name='close_time',
            field=models.TimeField(blank=True),
        ),
        migrations.AlterField(
            model_name='business',
            name='open_time',
            field=models.TimeField(blank=True),
        ),
    ]
