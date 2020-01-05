from builtins import ValueError, TypeError, OverflowError

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Count, Sum
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from .models import *
from .render import Render
from .tokens import account_activation_token


def home(request):
    return render(request, 'index.html')


@login_required
def dashboard(request):
    user = request.user
    company = user.employee.location.company
    if user.groups.filter(name__in=["Company Admins", "Company Superusers"]):
        most_requested = Equipment.objects.filter(location__company=company).annotate(
            num_allocations=Count('allocation')).order_by('-num_allocations')[
                         :10]
        assets_value = Equipment.objects.filter(location__company=company).aggregate(Sum('price'))
        pending_requests = Allocation.objects.filter(equipment__location__company=company,
                                                     approver_id=1).count()
        pending_equipments = Allocation.objects.filter(equipment__location__company=company,
                                                       approver_id=1).order_by(
            'equipment_id').distinct().count()  # there can be multiple requests on one equipment
        allocated_equipments = Allocation.objects.filter(equipment__location__company=company, approved=True,
                                                         returned=False,
                                                         start_date__lte=timezone.now().date()).count()
        equipments_count = Equipment.objects.filter(location__company=company).count()
        free_equipments = equipments_count - (pending_equipments + allocated_equipments)
        categories = Category.objects.filter(company=company).annotate(Count('equipment'))
        categories_count = categories.count()
        unread_messages = Message.objects.filter(to_user=user, from_user_id__gte=2, read=False).order_by('-date_sent')
        alerts = Message.objects.filter(from_user_id=1, to_user=user).order_by('-date_sent')
        assets_monthly_value = AssetLog.objects.filter(company=company, year=timezone.now().year)
        excellent_condition = Equipment.objects.filter(location__company=company, condition='E').count()
        excellent_condition_percentage = round((excellent_condition / equipments_count) * 100, 1)
        good_condition = Equipment.objects.filter(location__company=company, condition='G').count()
        good_condition_percentage = round((good_condition / equipments_count) * 100, 1)
        fair_condition = Equipment.objects.filter(location__company=company, condition='F').count()
        fair_condition_percentage = round((fair_condition / equipments_count) * 100, 1)
        very_poor_condition = Equipment.objects.filter(location__company=company, condition='VP').count()
        very_poor_condition_percentage = round((very_poor_condition / equipments_count) * 100, 1)
        year = timezone.now().year
        assets_mv = {}
        for monthly_value in assets_monthly_value:
            assets_mv[monthly_value.month] = monthly_value.assets
        context = {'company': company,
                   'unread_messages': unread_messages,
                   'alerts': alerts,
                   'most_requested': most_requested,
                   'assets_value': assets_value,
                   'equipments_count': equipments_count,
                   'pending_requests': pending_requests,
                   'pending_equipments': pending_equipments,
                   'allocated_equipments': allocated_equipments,
                   'free_equipments': free_equipments,
                   'categories': categories,
                   'categories_count': categories_count,
                   'assets_mv': assets_mv,
                   'excellent_condition_percentage': excellent_condition_percentage,
                   'good_condition_percentage': good_condition_percentage,
                   'fair_condition_percentage': fair_condition_percentage,
                   'very_poor_condition_percentage': very_poor_condition_percentage,
                   'year': year}
        return render(request, 'dashboard.html', context)
    else:
        return redirect('profile')


def signup(request):
    if request.method == "GET":
        companies = Company.objects.all().order_by('name')
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


@login_required
def equipments(request):
    if request.method == "GET":
        user = request.user
        unread_messages = Message.objects.filter(to_user=user, from_user_id__gte=2, read=False).order_by('-date_sent')
        alerts = Message.objects.filter(from_user_id=1, to_user=user).order_by('-date_sent')
        company = user.employee.location.company
        equipments = Equipment.objects.filter(location__company=company)
        return render(request, 'equipments.html',
                      {'company': company, 'equipments': equipments, 'unread_messages': unread_messages,
                       'alerts': alerts})


def equipment(request, pk):
    user = request.user
    if request.method == "GET":
        equipment = Equipment.objects.get(id=pk)
        allocations = Allocation.objects.filter(equipment=equipment)
        unread_messages = Message.objects.filter(to_user=user, from_user_id__gte=2, read=False).order_by('-date_sent')
        alerts = Message.objects.filter(from_user_id=1, to_user=user).order_by('-date_sent')
        return render(request, 'equipment.html',
                      {'equipment': equipment, 'allocations': allocations, 'unread_messages': unread_messages,
                       'alerts': alerts})


@login_required
def profile(request):
    if request.method == "GET":
        user = request.user
        unread_messages = Message.objects.filter(to_user=user, from_user_id__gte=2, read=False).order_by('-date_sent')
        alerts = Message.objects.filter(from_user_id=1, to_user=user).order_by('-date_sent')
        allocations = Allocation.objects.filter(user=user)
        return render(request, 'profile.html', {'allocations': allocations, 'unread_messages': unread_messages,
                                                'alerts': alerts})


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
        user.groups.set(['superuser_group', 'admin_group'])

        return redirect('login')


@login_required
def team(request):
    user = request.user
    unread_messages = Message.objects.filter(to_user=user, from_user_id__gte=2, read=False).order_by('-date_sent')
    alerts = Message.objects.filter(from_user_id=1, to_user=user).order_by('-date_sent')
    team_list = Employee.objects.filter(location__company=user.employee.location.company)
    if "num" in request.GET.keys():
        number = int(request.GET["num"])
    else:
        number = 10
    paginator = Paginator(team_list, number)
    page = request.GET.get('page')
    team = paginator.get_page(page)
    return render(request, 'team.html', {'team': team, 'unread_messages': unread_messages,
                                         'alerts': alerts})


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


@login_required
def team_member(request, pk):
    if request.method == "GET":
        user = User.objects.get(id=pk)
        logged_in_user = request.user
        unread_messages = Message.objects.filter(to_user=logged_in_user, from_user_id__gte=2, read=False).order_by(
            '-date_sent')
        alerts = Message.objects.filter(from_user_id=1, to_user=logged_in_user).order_by('-date_sent')
        if user.employee.location.company_id == logged_in_user.employee.location.company_id:
            allocations = Allocation.objects.filter(user=user)
            return render(request, 'profile.html', {'allocations': allocations, 'unread_messages': unread_messages,
                                                    'alerts': alerts, 'user': user})
        else:
            return redirect('page_not_found')


def error(request):
    user = request.user
    unread_messages = Message.objects.filter(to_user=user, from_user_id__gte=2, read=False).order_by(
        '-date_sent')
    alerts = Message.objects.filter(from_user_id=1, to_user=user).order_by('-date_sent')
    return render(request, '404.html', {'unread_messages': unread_messages, 'alerts': alerts})


@login_required
def image_upload(request):
    image = request.FILES['profile_pic']
    user = request.user
    user.employee.image.delete()
    user.employee.image = image
    user.employee.save()
    return redirect('profile')


@login_required
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


@login_required
def add_employee(request):
    user = request.user
    if user.groups.filter(name__in=["Company Admins", "Company Superusers"]):
        if request.method == "GET":
            unread_messages = Message.objects.filter(to_user=user, from_user_id__gte=2, read=False).order_by(
                '-date_sent')
            alerts = Message.objects.filter(from_user_id=1, to_user=user).order_by('-date_sent')
            locations = Location.objects.filter(company=user.employee.location.company)
            return render(request, 'add_employee.html', {'locations': locations, 'unread_messages': unread_messages,
                                                         'alerts': alerts})
        elif request.method == "POST":
            email = request.POST['email']
            location = request.POST['location']
            return redirect('team')
    else:
        return redirect('team')


@login_required
def add_equipment(request):
    user = request.user
    company = user.employee.location.company
    if user.groups.filter(name__in=["Company Admins", "Company Superusers"]):
        if request.method == "GET":
            unread_messages = Message.objects.filter(to_user=user, from_user_id__gte=2, read=False).order_by(
                '-date_sent')
            alerts = Message.objects.filter(from_user_id=1, to_user=user).order_by('-date_sent')
            locations = Location.objects.filter(company=user.employee.location.company)
            categories = Category.objects.filter(company=user.employee.location.company)
            return render(request, 'add_equipment.html',
                          {'locations': locations, 'categories': categories, 'unread_messages': unread_messages,
                           'alerts': alerts})
        elif request.method == "POST":
            serial = request.POST['serial']
            description = request.POST['description']
            price = request.POST['price']
            vendor = request.POST['vendor']
            category = request.POST['category']
            location = request.POST['location']
            months = ['Jan', 'Feb', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            year = timezone.now().year
            month = months[timezone.now().month - 1]
            equipment = Equipment.objects.create(serial=serial, description=description, price=price, vendor=vendor,
                                                 condition='E', category_id=category, location_id=location)
            equipment.save()
            month_asset = AssetLog.objects.get_or_create(company=company, year=year, month=month)[0]
            assets = month_asset.assets + float(price)
            month_asset.assets = assets
            month_asset.save()
            return redirect('equipments')
    else:
        return redirect('equipments')


@login_required
def allocations(request):
    user = request.user
    if user.groups.filter(name__in=["Company Admins", "Company Superusers"]):
        unread_messages = Message.objects.filter(to_user=user, from_user_id__gte=2, read=False).order_by('-date_sent')
        alerts = Message.objects.filter(from_user_id=1, to_user=user).order_by('-date_sent')
        allocations = Allocation.objects.filter(equipment__location__company=user.employee.location.company)
        return render(request, 'allocations.html', {'allocations': allocations, 'unread_messages': unread_messages,
                                                    'alerts': alerts})
    else:
        return redirect('dashboard')


@login_required
def add_category(request):
    company = request.user.employee.location.company
    name = request.POST['category']
    category = Category.objects.create(name=name, company=company)
    category.save()
    return redirect('add_equipment')


@login_required
def messages(request):
    user = request.user
    employees = Employee.objects.filter(location__company=user.employee.location.company)
    unread_messages = Message.objects.filter(to_user=user, from_user_id__gte=2, read=False).order_by('-date_sent')
    alerts = Message.objects.filter(from_user_id=1, to_user=user).order_by('-date_sent')
    inbox = Message.objects.filter(to_user=user, from_user_id__gte=2).order_by('-date_sent')
    sent = Message.objects.filter(from_user=user)
    return render(request, 'messages.html',
                  {'inbox': inbox, 'sent': sent, 'unread_messages': unread_messages, 'alerts': alerts,
                   'employees': employees})


def add_location(request):
    company = request.user.employee.location.company
    name = request.POST['name']
    address = request.POST['address']
    city = request.POST['city']
    country = request.POST['country']
    location = Location.objects.create(name=name, address=address, city=city, country=country, company=company)
    location.save()
    return redirect('add_equipment')


def pdf(request):
    user = request.user
    company = user.employee.location.company
    most_requested = Equipment.objects.filter(location__company=company).annotate(
        num_allocations=Count('allocation')).order_by('-num_allocations')[
                     :10]
    assets_value = Equipment.objects.filter(location__company=company).aggregate(Sum('price'))
    pending_requests = Allocation.objects.filter(equipment__location__company=company,
                                                 approver__isnull=True).count()
    pending_equipments = Allocation.objects.filter(equipment__location__company=company,
                                                   approver__isnull=True).order_by(
        'equipment_id').distinct().count()
    allocated_equipments = Allocation.objects.filter(equipment__location__company=company, approved=True,
                                                     returned=False,
                                                     start_date__lte=timezone.now().date()).count()
    equipments_count = Equipment.objects.filter(location__company=company).count()
    free_equipments = equipments_count - (pending_equipments + allocated_equipments)
    categories_count = Category.objects.filter(company=company).count()
    assets_monthly_value = AssetLog.objects.filter(company=company, year=timezone.now().year)
    excellent_condition = Equipment.objects.filter(location__company=company, condition='E').count()
    excellent_condition_percentage = round((excellent_condition / equipments_count) * 100, 1)
    good_condition = Equipment.objects.filter(location__company=company, condition='G').count()
    good_condition_percentage = round((good_condition / equipments_count) * 100, 1)
    fair_condition = Equipment.objects.filter(location__company=company, condition='F').count()
    fair_condition_percentage = round((fair_condition / equipments_count) * 100, 1)
    very_poor_condition = Equipment.objects.filter(location__company=company, condition='VP').count()
    very_poor_condition_percentage = round((very_poor_condition / equipments_count) * 100, 1)
    assets_mv = {}
    for monthly_value in assets_monthly_value:
        assets_mv[monthly_value.month] = monthly_value.assets
    params = {'request': request,
              'company': company,
              'most_requested': most_requested,
              'assets_value': assets_value,
              'equipments_count': equipments_count,
              'pending_requests': pending_requests,
              'pending_equipments': pending_equipments,
              'allocated_equipments': allocated_equipments,
              'free_equipments': free_equipments,
              'categories_count': categories_count,
              'assets_mv': assets_mv,
              'excellent_condition_percentage': excellent_condition_percentage,
              'good_condition_percentage': good_condition_percentage,
              'fair_condition_percentage': fair_condition_percentage,
              'very_poor_condition_percentage': very_poor_condition_percentage}
    return Render.render('dashboard.html', params)


def message(request, pk):
    user = request.user
    unread_messages = Message.objects.filter(to_user=user, from_user_id__gte=2, read=False).order_by('-date_sent')
    alerts = Message.objects.filter(from_user_id=1, to_user=user).order_by('-date_sent')
    message = Message.objects.get(pk=pk)
    return render(request, 'message.html', {'unread_messages': unread_messages, 'alerts': alerts, 'message': message})


def send_message(request):
    to_user = request.POST['to_user']
    message = request.POST['message']
    user = request.user
    Message.objects.create(to_user_id=to_user, text=message, from_user_id=user.id)
    return redirect('messages')
