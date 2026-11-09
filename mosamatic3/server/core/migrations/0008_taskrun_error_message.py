from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('core', '0007_dicomimportsession_dicomimportfile_and_more')]
    operations = [
        migrations.AddField(
            model_name='taskrun',
            name='error_message',
            field=models.TextField(blank=True, default=''),
        ),
    ]
