import factory.django
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _


class UserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular User with the given email and password."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """This represents a User object within our system"""
    username = None
    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    email = models.EmailField(_('email address'), unique=True)
    is_active = models.BooleanField(_("active"), default=False, help_text=_(
        'Designates whether this user should be treated as active. '
        'Unselect this instead of deleting accounts.'
    ), )

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()


class Company(models.Model):
    """This represents a Company within our system"""

    name = models.CharField(max_length=50, help_text='Name of Company')

    class Meta:
        verbose_name_plural = 'Companies'

    def __str__(self):
        return self.name


class Location(models.Model):
    """This represents a location of a company branch in our system"""
    name = models.CharField(
        max_length=20, help_text='Name to identify branch location of Company')
    address = models.TextField(help_text='Address of Office', null=True)
    city = models.CharField(max_length=20, help_text='City', null=True)
    country = models.CharField(max_length=20, help_text='Country', null=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    def __str__(self):
        return self.name + " - " + self.company.name


def user_directory_path(instance, filename):
    ext = filename.split('.')[-1]
    return 'avatars/user_{0}.{1}'.format(instance.user.id, ext)


class Employee(models.Model):
    """This represents an employee within our company"""
    user = models.OneToOneField(User, models.CASCADE)
    username = models.CharField(max_length=20)
    image = models.ImageField(upload_to=user_directory_path)
    location = models.ForeignKey(Location, on_delete=models.CASCADE, default=1)

    def __str__(self):
        return self.user.email


class Category(models.Model):
    """This represents an equipment category in our system."""
    name = models.CharField(max_length=20, help_text='New category')
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    class Meta:
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name + " - " + self.company.name


class Supplier(models.Model):
    name = models.CharField(max_length=100)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    description = models.TextField()
    email = models.EmailField()

    def __str__(self):
        return "{0} ({1})".format(self.name, self.company)


class Item(models.Model):
    """This represents an equipment in our system."""
    SKU = models.CharField(max_length=20, primary_key=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    description = models.TextField(help_text="Enter details on equipment")
    price = models.IntegerField()
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    quantity_purchased = models.IntegerField(default=1)
    quantity_available = models.IntegerField(default=0)
    maximum_daily_usage = models.IntegerField(default=0)
    maximum_lead_time = models.TextField(default=1)
    average_daily_usage = models.IntegerField(default=0)
    average_lead_time = models.TextField(default=1)
    reorder_point = models.IntegerField(default=1)
    is_returnable = models.BooleanField(default=False)

    def __str__(self):
        return self.description


class PurchaseOrder(models.Model):
    ORDER_STATUS = [
        ('Q', 'Queued'),
        ('S', 'Sent'),
        ('C', 'Cancelled'),
        ('F', 'Fulfilled')
    ]
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING)
    created_at = models.DateTimeField(auto_now_add=True)
    quantity = models.IntegerField(default=1)
    status = models.CharField(max_length=20, choices=ORDER_STATUS)

    def __str__(self):
        return "{0} ({1})".format(self.status, self.item)


class ItemRequest(models.Model):
    """This represents an item allocation to a user in our system."""
    REQUEST_STATUS = [
        ('P', 'Pending'),
        ('F', 'Fulfilled'),
        ('C', 'Cancelled'),
        ('SO', 'Stock Out')
    ]
    item = models.ForeignKey(Item, on_delete=models.DO_NOTHING)
    user = models.ForeignKey(User,
                             on_delete=models.DO_NOTHING,
                             related_name='item_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=REQUEST_STATUS,
                              default='P')

    def __str__(self):
        return self.status + " - " + self.item.SKU + " - " + self.user.email


class ItemReturn(models.Model):
    request = models.ForeignKey(ItemRequest, on_delete=models.DO_NOTHING,
                                related_name="returns_to_inventory")
    is_returned = models.BooleanField(default=False)
    return_date = models.DateTimeField(auto_now=True)
    fulfil_date = models.DateTimeField(auto_now_add=True)


class ItemLog(models.Model):
    """This represents the total assets value for a month in our system."""
    MONTHS = [
        ('Jan', 'January'),
        ('Feb', 'February'),
        ('Mar', 'March'),
        ('Apr', 'April'),
        ('May', 'May'),
        ('Jun', 'June'),
        ('Jul', 'July'),
        ('Aug', 'August'),
        ('Sep', 'September'),
        ('Oct', 'October'),
        ('Nov', 'November'),
        ('Dec', 'December')
    ]
    company = models.ForeignKey(Company, models.CASCADE)
    month = models.CharField(max_length=20, choices=MONTHS)
    year = models.IntegerField()
    inventory_value = models.FloatField(default=0)

    def __str__(self):
        return self.company.name + " " + self.month + " " + str(self.year)


class Message(models.Model):
    from_user = models.ForeignKey(User, models.DO_NOTHING,
                                  related_name="sent_messages")
    to_user = models.ForeignKey(User, models.DO_NOTHING,
                                related_name="inbox_messages")
    text = models.TextField()
    date_sent = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    def __str__(self):
        return str(
            self.date_sent) + " " + self.from_user.get_full_name() + ">" + self.to_user.get_full_name()


@receiver(post_save, sender=User)
def create_employee(sender, instance, created, **kwargs):
    if created:
        Employee.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_employee(sender, instance, **kwargs):
    instance.employee.save()


@receiver(post_save, sender=Item)
def log_item(sender, instance, **kwargs):
    months = ['Jan', 'Feb', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep',
              'Oct', 'Nov', 'Dec']
    year = timezone.now().year
    month = months[timezone.now().month - 2]
    month_asset = \
        ItemLog.objects.get_or_create(company=instance.company,
                                      year=year, month=month)[0]
    month_asset.inventory_value = F('inventory_value') + (
            float(instance.price) * float(instance.quantity_purchased))
    month_asset.save()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    email = factory.Faker('email')


class CompanyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Company

    name = factory.Faker('company')


class LocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Location

    name = factory.Faker('city')
    address = factory.Faker('address')
    city = factory.Faker('city')
    country = factory.Faker('country')
    company = factory.SubFactory(CompanyFactory)


class SupplierFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Supplier

    company = factory.SubFactory(CompanyFactory)


class EmployeeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Employee

    location = factory.SubFactory(LocationFactory)


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Faker('word')
    company = factory.SubFactory(CompanyFactory)


class ItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Item

    SKU = factory.Faker('ean')
    description = factory.Faker('sentence')
    condition = factory.Faker('word', ext_word_list=['E', 'VP', 'G', 'F'])
    price = factory.Faker('pyint', min_value=10000, max_value=10000000,
                          step=100)
    location = factory.SubFactory(LocationFactory)
    category = factory.SubFactory(CategoryFactory)


class ItemRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ItemRequest

    item = factory.SubFactory(ItemFactory)
    user = factory.SubFactory(UserFactory)
    approver = factory.SubFactory(UserFactory)
    start_date = factory.Faker('date')
    end_date = factory.Faker('date')
    checked_in = factory.Faker('boolean', chance_of_getting_true=500)
    approved = factory.Faker('boolean', chance_of_getting_true=70)

# class AssetLogFactory(factory.django.DjangoModelFactory):
#     class Meta:
#         model = AssetLog
