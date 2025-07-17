from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('attendance', '0006_editrequest_unique_user_timestamp_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='editrequest',
            name='status',
            field=models.CharField(
                max_length=10,
                choices=[('pending','در انتظار'),('approved','تأیید شده'),('rejected','رد شده'),('cancelled','لغو شده')],
                default='pending'
            ),
        ),
        migrations.AlterField(
            model_name='leaverequest',
            name='status',
            field=models.CharField(
                max_length=10,
                choices=[('pending','در انتظار'),('approved','تأیید شده'),('rejected','رد شده'),('cancelled','لغو شده')],
                default='pending'
            ),
        ),
    ]
