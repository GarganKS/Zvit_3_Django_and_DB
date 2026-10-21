from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from app_BusFlow.models import (
    Client,
    Order,
    Route,
    Stop,
    StopOnRoute,
    Ticket,
    Trip,
    Vehicle,
)
from app_BusFlow.services import refresh_trip_statuses


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user("man", password="pw12345!x")
        cls.manager.groups.add(Group.objects.get(name="Менеджери"))
        cls.client_user = User.objects.create_user("cli", password="pw12345!x")
        cls.client_user.groups.add(Group.objects.get(name="Клієнти"))
        Client.objects.create(user=cls.client_user, name="ТОВ Тест", phone="0501234567")
        cls.admin = User.objects.create_superuser("adm", password="pw12345!x")
        cls.s1 = Stop.objects.create(name="Київ", address="a", latitude=1, longitude=1)
        cls.s2 = Stop.objects.create(name="Львів", address="b", latitude=2, longitude=2)
        cls.route = Route.objects.create(name="Київ - Львів")
        StopOnRoute.objects.create(route=cls.route, stop=cls.s1, stop_sequence=1)
        StopOnRoute.objects.create(route=cls.route, stop=cls.s2, stop_sequence=2)
        cls.bus = Vehicle.objects.create(name="Bogdan", plate_number="AA1111AA", capacity=20)

    def make_trip(self, **kw):
        defaults = dict(route=self.route, vehicle=self.bus, price=Decimal("100"))
        defaults.update(kw)
        return Trip.objects.create(**defaults)

    def bus_status(self):
        return Vehicle.objects.get(pk=self.bus.pk).status


class ErdTests(Base):
    def test_table_and_pk_names_match_erd(self):
        self.assertEqual(Trip._meta.db_table, "trip")
        self.assertEqual(Order._meta.db_table, "order")
        self.assertEqual(Trip._meta.pk.column, "trip_id")
        self.assertEqual(Client._meta.pk.column, "client_id")
        self.assertEqual(Trip._meta.get_field("price").max_digits, 10)
        self.assertEqual(Vehicle._meta.get_field("plate_number").max_length, 8)


class VehicleAutomationTests(Base):
    def test_deleting_in_progress_trip_frees_vehicle(self):
        trip = self.make_trip(status=Trip.Status.IN_PROGRESS)
        self.assertEqual(self.bus_status(), Vehicle.Status.ON_ROUTE)
        self.client.force_login(self.manager)
        self.client.post(reverse("trip_delete", args=[trip.pk]))
        self.assertEqual(self.bus_status(), Vehicle.Status.WAITING)

    def test_other_active_trip_keeps_vehicle_on_route(self):
        a = self.make_trip(status=Trip.Status.IN_PROGRESS)
        self.make_trip(status=Trip.Status.IN_PROGRESS)
        a.delete()
        self.assertEqual(self.bus_status(), Vehicle.Status.ON_ROUTE)

    def test_repair_status_is_not_overwritten(self):
        Vehicle.objects.filter(pk=self.bus.pk).update(status=Vehicle.Status.REPAIR)
        trip = self.make_trip()
        trip.delete()
        self.assertEqual(self.bus_status(), Vehicle.Status.REPAIR)

    def test_changing_trip_vehicle_frees_old_one(self):
        other = Vehicle.objects.create(name="B", plate_number="BB2222BB", capacity=10)
        trip = self.make_trip(status=Trip.Status.IN_PROGRESS)
        trip.vehicle = other
        trip.save()
        self.assertEqual(self.bus_status(), Vehicle.Status.WAITING)
        self.assertEqual(Vehicle.objects.get(pk=other.pk).status, Vehicle.Status.ON_ROUTE)

    def test_completing_trip_frees_vehicle(self):
        trip = self.make_trip(status=Trip.Status.IN_PROGRESS)
        trip.status = Trip.Status.COMPLETED
        trip.save()
        self.assertEqual(self.bus_status(), Vehicle.Status.WAITING)

    def test_trips_advance_by_time(self):
        now = timezone.now()
        trip = self.make_trip(
            departure_time=now - timedelta(hours=1), arrival_time=now + timedelta(hours=1)
        )
        refresh_trip_statuses()
        trip.refresh_from_db()
        self.assertEqual(trip.status, Trip.Status.IN_PROGRESS)
        self.assertEqual(self.bus_status(), Vehicle.Status.ON_ROUTE)
        Trip.objects.filter(pk=trip.pk).update(arrival_time=now - timedelta(minutes=1))
        refresh_trip_statuses()
        trip.refresh_from_db()
        self.assertEqual(trip.status, Trip.Status.COMPLETED)
        self.assertEqual(self.bus_status(), Vehicle.Status.WAITING)


class TicketTests(Base):
    def test_tickets_generated_and_cancelled(self):
        trip = self.make_trip()
        self.assertEqual(trip.tickets.count(), 20)
        self.assertEqual(trip.tickets.first().price, Decimal("100"))
        trip.status = Trip.Status.CANCELLED
        trip.save()
        self.assertEqual(trip.tickets.filter(status=Ticket.Status.CANCELLED).count(), 20)


class ProtectTests(Base):
    def test_cannot_delete_used_vehicle_route_stop(self):
        self.make_trip()
        for obj in (self.bus, self.route):
            with self.assertRaises(ProtectedError):
                obj.delete()
        with self.assertRaises(ProtectedError):
            self.s1.delete()

    def test_delete_view_shows_message_instead_of_500(self):
        self.make_trip()
        self.client.force_login(self.manager)
        response = self.client.post(reverse("vehicle_delete", args=[self.bus.pk]), follow=True)
        self.assertContains(response, "не можна видалити")
        self.assertTrue(Vehicle.objects.filter(pk=self.bus.pk).exists())


class OrderFlowTests(Base):
    def new_order(self):
        return Order.objects.create(
            client=self.client_user,
            destination="Одеса",
            passengers=10,
            departure_time=timezone.now() + timedelta(days=2),
        )

    def test_full_flow_with_client_confirmation(self):
        order = self.new_order()
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("order_plan", args=[order.pk]),
            {"vehicle": self.bus.pk, "total_price": "5000"},
        )
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.AWAITING)
        self.assertEqual(self.bus_status(), Vehicle.Status.RENTED)

        # Менеджер не може підтвердити замість клієнта.
        self.assertEqual(self.client.post(reverse("order_confirm", args=[order.pk])).status_code, 403)

        self.client.force_login(self.client_user)
        self.assertContains(self.client.get(reverse("home")), "Підтвердити")
        self.client.post(reverse("order_confirm", args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PLANNED)
        self.assertEqual(self.bus_status(), Vehicle.Status.RENTED)

        self.client.force_login(self.manager)
        self.client.post(reverse("order_complete", args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.assertEqual(self.bus_status(), Vehicle.Status.WAITING)

    def test_client_decline_releases_vehicle(self):
        order = self.new_order()
        order.plan(self.bus, Decimal("100"))
        self.client.force_login(self.client_user)
        self.client.post(reverse("order_decline", args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.bus_status(), Vehicle.Status.WAITING)

    def test_other_client_cannot_confirm(self):
        order = self.new_order()
        order.plan(self.bus, Decimal("100"))
        stranger = User.objects.create_user("x", password="pw12345!x")
        stranger.groups.add(Group.objects.get(name="Клієнти"))
        Client.objects.create(user=stranger, name="Інший", phone="1")
        self.client.force_login(stranger)
        self.assertEqual(self.client.post(reverse("order_confirm", args=[order.pk])).status_code, 404)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.AWAITING)

    def test_cannot_confirm_new_order(self):
        order = self.new_order()
        self.client.force_login(self.client_user)
        self.client.post(reverse("order_confirm", args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.NEW)


class AuthAndAdminTests(Base):
    def test_admin_login_redirects_to_admin(self):
        response = self.client.post(reverse("login"), {"username": "adm", "password": "pw12345!x"})
        self.assertRedirects(response, reverse("admin:index"), fetch_redirect_response=False)

    def test_manager_login_goes_to_dashboard(self):
        response = self.client.post(reverse("login"), {"username": "man", "password": "pw12345!x"})
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_admin_has_no_home_page(self):
        self.client.force_login(self.admin)
        self.assertRedirects(
            self.client.get(reverse("home")), reverse("admin:index"), fetch_redirect_response=False
        )

    def test_manager_created_in_admin_in_one_step(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("admin:app_BusFlow_manager_add"),
            {
                "username": "newman",
                "usable_password": "true",
                "password1": "Str0ng-pass-77",
                "password2": "Str0ng-pass-77",
                "first_name": "Іван",
                "last_name": "Петренко",
            },
        )
        self.assertEqual(response.status_code, 302, getattr(response, "context", None) and response.context["adminform"].form.errors)
        user = User.objects.get(username="newman")
        self.assertTrue(user.groups.filter(name="Менеджери").exists())
        self.assertEqual(user.first_name, "Іван")
        # Новий менеджер одразу може працювати.
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("vehicles")).status_code, 200)

    def test_registration_creates_client(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "fresh",
                "password1": "Str0ng-pass-77",
                "password2": "Str0ng-pass-77",
                "name": "Нова фірма",
                "phone": "0991112233",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.get(username="fresh").client.name, "Нова фірма")


class PagesTests(Base):
    def test_manager_pages_render(self):
        trip = self.make_trip()
        order = Order.objects.create(
            client=self.client_user, destination="Одеса", passengers=5,
            departure_time=timezone.now() + timedelta(days=1),
        )
        self.client.force_login(self.manager)
        urls = [
            reverse("home"), reverse("routes"), reverse("route_detail", args=[self.route.pk]),
            reverse("route_new"), reverse("route_edit", args=[self.route.pk]),
            reverse("trips"), reverse("trip_detail", args=[trip.pk]),
            reverse("trips") + f"?route={self.route.pk}&vehicle={self.bus.pk}",
            reverse("stops"), reverse("stop_detail", args=[self.s1.pk]),
            reverse("vehicles"), reverse("vehicle_detail", args=[self.bus.pk]),
            reverse("orders"), reverse("order_detail", args=[order.pk]),
            reverse("orders") + f"?client={self.client_user.pk}&vehicle={self.bus.pk}",
            reverse("routes") + f"?stop={self.s1.pk}",
            reverse("order_plan", args=[order.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_route_page_links_to_vehicle(self):
        self.make_trip()
        self.client.force_login(self.manager)
        response = self.client.get(reverse("routes"))
        self.assertContains(response, reverse("vehicle_detail", args=[self.bus.pk]))

    def test_client_pages_hide_vehicle_links(self):
        trip = self.make_trip()
        self.client.force_login(self.client_user)
        for url in (reverse("home"), reverse("trips"), reverse("trip_detail", args=[trip.pk]), reverse("orders")):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "/vehicles/")
        self.assertEqual(self.client.get(reverse("vehicles")).status_code, 403)

    def test_dashboard_is_cards(self):
        Order.objects.create(
            client=self.client_user, destination="Одеса", passengers=5,
            departure_time=timezone.now() + timedelta(days=1),
        )
        self.client.force_login(self.manager)
        self.assertContains(self.client.get(reverse("home")), 'class="tile')

    def test_route_create_autoname_and_custom_name(self):
        self.client.force_login(self.manager)
        data = {
            "name": "",
            "stoponroute_set-TOTAL_FORMS": "2", "stoponroute_set-INITIAL_FORMS": "0",
            "stoponroute_set-MIN_NUM_FORMS": "0", "stoponroute_set-MAX_NUM_FORMS": "1000",
            "stoponroute_set-0-stop": self.s2.pk, "stoponroute_set-0-stop_sequence": "1",
            "stoponroute_set-1-stop": self.s1.pk, "stoponroute_set-1-stop_sequence": "2",
        }
        self.client.post(reverse("route_new"), data)
        self.assertTrue(Route.objects.filter(name="Львів - Київ").exists())
        data["name"] = "Експрес"
        self.client.post(reverse("route_new"), data)
        self.assertTrue(Route.objects.filter(name="Експрес").exists())


class TicketSaleTests(Base):
    def setUp(self):
        self.trip = self.make_trip()
        self.client.force_login(self.manager)

    def sell(self, name="Іван", phone="050111"):
        return self.client.post(
            reverse("ticket_sell", args=[self.trip.pk]),
            {"passenger_name": name, "passenger_phone": phone},
        )

    def test_sell_stores_passenger_data(self):
        self.assertEqual(self.sell().status_code, 302)
        ticket = self.trip.tickets.get(status=Ticket.Status.SOLD)
        self.assertEqual((ticket.passenger_name, ticket.passenger_phone), ("Іван", "050111"))
        self.assertEqual(self.trip.tickets.filter(status=Ticket.Status.FREE).count(), 19)

    def test_name_and_phone_required(self):
        response = self.sell(name="", phone="")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.trip.tickets.filter(status=Ticket.Status.SOLD).exists())

    def test_cannot_oversell(self):
        self.trip.tickets.exclude(pk=self.trip.tickets.first().pk).update(
            status=Ticket.Status.CANCELLED
        )
        self.sell()
        self.sell("Петро", "2")
        self.assertEqual(self.trip.tickets.filter(status=Ticket.Status.SOLD).count(), 1)

    def test_cannot_sell_for_non_scheduled_trip(self):
        Trip.objects.filter(pk=self.trip.pk).update(status=Trip.Status.COMPLETED)
        self.sell()
        self.assertFalse(self.trip.tickets.filter(status=Ticket.Status.SOLD).exists())

    def test_return_clears_passenger(self):
        self.sell()
        ticket = self.trip.tickets.get(status=Ticket.Status.SOLD)
        self.client.post(reverse("ticket_return", args=[ticket.pk]))
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.FREE)
        self.assertEqual((ticket.passenger_name, ticket.passenger_phone), ("", ""))

    def test_trip_with_sold_tickets_cannot_be_deleted(self):
        self.sell()
        response = self.client.post(reverse("trip_delete", args=[self.trip.pk]), follow=True)
        self.assertContains(response, "продані квитки")
        self.assertTrue(Trip.objects.filter(pk=self.trip.pk).exists())

    def test_trip_without_sold_tickets_can_be_deleted(self):
        self.client.post(reverse("trip_delete", args=[self.trip.pk]))
        self.assertFalse(Trip.objects.filter(pk=self.trip.pk).exists())

    def test_list_and_detail_show_counts_and_passenger_hidden_from_clients(self):
        self.sell("Секретний", "0509999")
        self.assertContains(self.client.get(reverse("trips")), "1/20")
        self.assertContains(self.client.get(reverse("trip_detail", args=[self.trip.pk])), "Секретний")
        self.client.force_login(self.client_user)
        self.assertNotContains(self.client.get(reverse("trip_detail", args=[self.trip.pk])), "Секретний")
        self.assertEqual(self.client.get(reverse("ticket_sell", args=[self.trip.pk])).status_code, 403)


class TripListUiTests(Base):
    """Список рейсів: кнопка продажу квитка і клікабельні рядки."""

    def setUp(self):
        self.trip = self.make_trip()
        self.client.force_login(self.manager)

    def test_sell_button_shown_for_scheduled_trip_with_free_tickets(self):
        response = self.client.get(reverse("trips"))
        self.assertContains(response, reverse("ticket_sell", args=[self.trip.pk]))
        self.assertContains(response, "Продати квиток")

    def test_sell_button_hidden_when_no_free_tickets(self):
        self.trip.tickets.update(status=Ticket.Status.SOLD)
        self.assertNotContains(self.client.get(reverse("trips")), "Продати квиток")

    def test_sell_button_hidden_for_non_scheduled_trip(self):
        Trip.objects.filter(pk=self.trip.pk).update(status=Trip.Status.COMPLETED)
        self.assertNotContains(self.client.get(reverse("trips")), "Продати квиток")

    def test_sell_button_hidden_from_clients(self):
        self.client.force_login(self.client_user)
        response = self.client.get(reverse("trips"))
        self.assertNotContains(response, "Продати квиток")
        self.assertNotContains(response, reverse("ticket_sell", args=[self.trip.pk]))

    def test_row_points_to_trip_detail(self):
        response = self.client.get(reverse("trips"))
        self.assertContains(response, f'data-trip-url="{reverse("trip_detail", args=[self.trip.pk])}"')

    def test_row_click_script_is_loaded(self):
        self.assertContains(self.client.get(reverse("trips")), "js/trip_list.js")
