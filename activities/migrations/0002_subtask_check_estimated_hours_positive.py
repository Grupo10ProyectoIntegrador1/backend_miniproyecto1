# Migration emptied: CheckConstraint removed from model, constraint validation
# is now handled at the serializer level.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('activities', '0001_initial'),
    ]

    operations = [
        # CheckConstraint was removed; validation is done in SubtaskSerializer.
    ]
