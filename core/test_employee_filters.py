from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from models.employee_models import EmployeeModel, NationalityModel
from models.employer_models import EmployerModel
from models.role_models import RoleModel


class EmployeeListFilterTests(TestCase):
    def setUp(self):
        role = RoleModel.objects.create(name="Employee Filter Manager")
        role.permissions.add(Permission.objects.get(codename="view_employeemodel"))
        self.user = get_user_model().objects.create_user(
            username="employee-filter-manager",
            email="employee-filter-manager@example.com",
            password="StrongPass123!",
            role=role,
            is_staff=True,
        )
        self.client.force_login(self.user)

    def test_employer_passport_country_and_expiry_ranges_combine(self):
        employer = EmployerModel.objects.create(name_en="Selected Employer", name_th="Selected")
        other_employer = EmployerModel.objects.create(name_en="Other Employer", name_th="Other")
        myanmar = NationalityModel.objects.create(name="Myanmar", country_code="MM")
        cambodia = NationalityModel.objects.create(name="Cambodia", country_code="KH")
        matching_employee = EmployeeModel.objects.create(
            employer=employer,
            created_by=self.user,
            nationality=myanmar,
            full_name_en="Matching Employee",
            work_permit_expiry_date=date(2026, 12, 1),
            visa_expiry_date=date(2026, 11, 15),
        )
        EmployeeModel.objects.create(
            employer=employer,
            created_by=self.user,
            nationality=myanmar,
            full_name_en="Outside Expiry Range",
            work_permit_expiry_date=date(2027, 1, 1),
            visa_expiry_date=date(2026, 11, 15),
        )
        EmployeeModel.objects.create(
            employer=other_employer,
            created_by=self.user,
            nationality=cambodia,
            full_name_en="Other Employee",
            work_permit_expiry_date=date(2026, 12, 1),
            visa_expiry_date=date(2026, 11, 15),
        )

        response = self.client.get(
            reverse("employee_list"),
            {
                "employer": str(employer.pk),
                "passport_country": "myanmar",
                "work_permit_expiry_range": "2026-11-01 to 2026-12-31",
                "visa_expiry_range": "2026-11-01 to 2026-12-01",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["employees"].object_list),
            [matching_employee],
        )

    def test_employee_list_does_not_show_mou_type_filter(self):
        response = self.client.get(reverse("employee_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="work_permit_type"')
        self.assertNotContains(response, "all_mou_types")

    def test_employee_expiry_dates_use_single_range_inputs(self):
        response = self.client.get(reverse("employee_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="work_permit_expiry_range"')
        self.assertContains(response, 'name="visa_expiry_range"')
        self.assertNotContains(response, 'name="work_permit_expiry_from"')
        self.assertNotContains(response, 'name="work_permit_expiry_to"')
        self.assertNotContains(response, 'name="visa_expiry_from"')
        self.assertNotContains(response, 'name="visa_expiry_to"')
