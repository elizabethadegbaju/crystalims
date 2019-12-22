from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
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

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()


class Company(models.Model):
    """This represents a Company within our system"""

    name = models.CharField(max_length=50, help_text='Name of Company')
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
    email_verified = models.BooleanField(default=False)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, default=1)
    location = models.ForeignKey(Location, on_delete=models.PROTECT, default=1)

    def __str__(self):
        return self.user.email


@receiver(post_save, sender=User)
def create_employee(sender, instance, created, **kwargs):
    if created:
        Employee.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_employee(sender, instance, **kwargs):
    instance.employee.save()


class Category(models.Model):
    """This represents an equipment category in our system."""
    name = models.CharField(max_length=20, help_text='New category')
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name + " - " + self.company.name


class Equipment(models.Model):
    """This represents an equipment in our system."""
    POSSIBLE_EQUIPMENT_CONDITIONS = [
        ('VP', 'Very Poor'),
        ('F', 'Fair'),
        ('G', 'Good'),
        ('E', 'Excellent'),
    ]
    serial = models.CharField(max_length=20, primary_key=True)
    description = models.TextField(help_text="Enter details on equipment")
    price = models.IntegerField()
    vendor = models.EmailField(name="Vendor's Email Address",
                               help_text="Enter Vendor's email address")
    condition = models.CharField(max_length=20,
                                 choices=POSSIBLE_EQUIPMENT_CONDITIONS)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)

    def __str__(self):
        return self.description


class Allocation(models.Model):
    """This represents an equipment allocation to a user in our system."""
    equipment = models.ForeignKey(Equipment, on_delete=models.DO_NOTHING)
    user = models.ForeignKey(User,
                             on_delete=models.DO_NOTHING,
                             related_name='equipment_allocations')
    start_date = models.DateField()
    end_date = models.DateField()
    approved = models.BooleanField(default=False)
    approver = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        limit_choices_to={'groups__pk': 1},
        related_name='allocations_overseen',
        blank=True,
        null=True)

    def __str__(self):
        if self.approved:
            status = "Approved"
        elif self.approver:
            status = "Not approved"
        else:
            status = "Pending"
        return status + " - " + self.equipment.serial + " - " + self.user.email


class AssetLog(models.Model):
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
    company = models.ForeignKey(Company,models.CASCADE)
    month = models.CharField(max_length=20, choices=MONTHS)
    year = models.IntegerField()
    assets = models.FloatField()

