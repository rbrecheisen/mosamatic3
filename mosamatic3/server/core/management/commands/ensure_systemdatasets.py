from django.core.management.base import BaseCommand

from core.datasets.system import sync_builtin_model_files_dataset_for_all_users


class Command(BaseCommand):
    help = "Create/update built-in system datasets, such as the AI model files dataset."

    def handle(self, *args, **options):
        count = sync_builtin_model_files_dataset_for_all_users()
        self.stdout.write(
            self.style.SUCCESS(f"Synced built-in datasets for {count} user(s).")
        )