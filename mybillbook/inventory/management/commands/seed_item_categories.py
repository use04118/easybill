from django.core.management.base import BaseCommand
from inventory.models import ItemCategory
from users.models import User  # Adjust this import based on your actual User model location
from users.utils import get_current_business  # Assuming you have this function available

class Command(BaseCommand):
    help = "Seed ItemCategory data into the database for a specific user/business"

    def add_arguments(self, parser):
        # Add user argument to specify which user's business to seed
        parser.add_argument(
            '--user-id',
            type=int,
            help='Specify the user ID to seed data for their business.',
        )

    def handle(self, *args, **options):
        user_id = options['user_id']
        if not user_id:
            self.stdout.write(self.style.ERROR("Please provide a user ID using --user-id."))
            return

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"User with ID {user_id} does not exist."))
            return

        # Dynamically get the business for the user
        business = get_current_business(user)

        data = [
            {"name": "Food"},
            {"name": "Beverages"},
            {"name": "Clothing"},
            {"name": "Electronics"},
            {"name": "Furniture"},
            {"name": "Books"},
            {"name": "Toys"},
            {"name": "Sports"},
            {"name": "Health"},
            {"name": "Beauty"},
            {"name": "Automotive"},
            {"name": "Jewelry"},
            {"name": "Music"},
            {"name": "Games"},
            {"name": "Movies"},
            {"name": "Travel"},
            {"name": "Home Decor"},
            {"name": "Pets"},
            {"name": "Gifts"},
            {"name": "Stationery"},
        ]

        created_count = 0
        for entry in data:
            # Create the ItemCategory if it doesn't already exist
            obj, created = ItemCategory.objects.get_or_create(
                name=entry["name"],
                business=business
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Seeded {created_count} new item categories for business '{business.name}'."))
