from builtins import ValueError, TypeError, OverflowError

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from .models import *
from .tokens import account_activation_token


def home(request):
    return render(request, 'index.html')


@login_required
def dashboard(request):
    user = request.user
    if user.groups.filter(name__in=["Company Admins", "Company Superusers"]):
        most_requested = Equipment.objects.annotate(num_allocations=Count('allocation')).order_by('-num_allocations')[
                         :5]
        assets_value = Equipment.objects.aggregate(Sum('price'))
        return render(request, 'dashboard.html', {'most_requested': most_requested, 'assets_value': assets_value})
    else:
        return redirect('profile')


def signup(request):
    if request.method == "GET":
        companies = Company.objects.all()
        return render(request, 'registration/register.html', {'companies': companies})
    elif request.method == "POST":
        email = request.POST['email']
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        password = request.POST['password']
        company_id = request.POST['company']
        company = Company.objects.get(id=company_id)
        image = request.FILES['profile_pic']

        user = User.objects.create_user(email, password)
        user.first_name = first_name
        user.last_name = last_name
        user.is_active = False
        user.save()
        current_site = get_current_site(request)
        mail_subject = 'Activate your {0} employee account on Crystal.'.format(company.name)
        message = render_to_string('acc_activate_email.html', {
            'user': user,
            'domain': current_site.domain,
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': account_activation_token.make_token(user),
        })
        to_email = email
        send_mail(mail_subject, message, from_email="admin@crystalims.com", recipient_list=[to_email])
        user.employee.company = company
        user.employee.username = first_name[:3] + "_" + last_name[:3]
        user.employee.image = image
        user.employee.save()
        return HttpResponse('Account created successfully and activation link sent to email address.')


def equipments(request):
    if request.method == "GET":
        company = request.user.employee.company
        equipments = Equipment.objects.filter(company=company)
        return render(request, 'equipments.html', {'equipments': equipments})


def equipment(request, pk):
    if request.method == "GET":
        equipment = Equipment.objects.get(id=pk)
        return render(request, 'equipment.html', {'equipment': equipment})


def profile(request):
    if request.method == "GET":
        allocations = Allocation.objects.filter(user=request.user)
        return render(request, 'profile.html', {'allocations': allocations})


def create(request):
    if request.method == "GET":
        return render(request, 'registration/register_company.html')
    elif request.method == "POST":
        email = request.POST['email']
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        password = request.POST['password']
        company_name = request.POST['company_name']
        company_address = request.POST['company_address']
        company_city = request.POST['company_city']
        company_country = request.POST['company_country']
        image = request.FILES['profile_pic']

        company = Company.objects.create(name=company_name)
        company.save()
        location = Location.objects.create(company=company, address=company_address, city=company_city,
                                           country=company_country, name=company_city)
        location.save()
        user = User.objects.create_user(email, password)
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        user.employee.company = Company.objects.get(id=company.id)
        user.employee.location = Location.objects.get(id=location.id)
        user.employee.username = first_name[:3] + "_" + last_name[:3]
        user.employee.image = image
        user.employee.save()
        superuser_group = Group.objects.get(name="Company Superusers")
        admin_group = Group.objects.get(name="Company Admins")
        user.groups.add([superuser_group, admin_group])

        return redirect('login')


def team(request):
    team = Employee.objects.filter(company=request.user.employee.company)
    return render(request, 'team.html', {'team': team})


def activate(request, uidb64, token):
    try:
        uid = force_text(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        return HttpResponse('Thank you for your email confirmation. Now you can login your account.')
    else:
        return HttpResponse('Activation link is invalid!')


def team_member(request):
    return None


def image_upload(request):
    image = request.FILES['profile_pic']
    user = request.user
    user.employee.image.delete()
    user.employee.image = image
    user.employee.save()
    return redirect('profile')


def edit_user(request):
    username = request.POST['username']
    email = request.POST['email']
    first_name = request.POST['first_name']
    last_name = request.POST['last_name']
    user = request.user

    user.employee.username = username
    user.employee.save()
    user.email = email
    user.first_name = first_name
    user.last_name = last_name
    user.save()
    return redirect('profile')


def add_employee(request):
    user = request.user
    if user.groups.filter(name__in=["Company Admins", "Company Superusers"]):
        if request.method == "GET":
            locations = Location.objects.filter(company=user.employee.company)
            return render(request, 'add_employee.html', {'locations': locations})
        elif request.method == "POST":
            email = request.POST['email']
            location = request.POST['location']

            return redirect('team')
    else:
        return redirect('team')


def add_equipment(request):
    user = request.user
    if user.groups.filter(name__in=["Company Admins", "Company Superusers"]):
        if request.method == "GET":
            return render(request, 'add_equipment.html')
        elif request.method == "POST":
            serial = request.POST['serial']
            description = request.POST['description']
            price = request.POST['price']
            vendor = request.POST['vendor']
            condition = request.POST['condition']
            category = request.POST['category']
            return redirect('equipments')
    else:
        return redirect('equipments')


def allocations(request):
    user = request.user
    if user.groups.filter(name__in=["Company Admins", "Company Superusers"]):
        return render(request, 'allocations.html', {'allocations': allocations})
    else:
        return redirect('dashboard')
