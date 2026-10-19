from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class ClientRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Лише клієнти (група "Клієнти"). Аноніми - на логін, інші ролі - 403."""

    def test_func(self):
        return self.request.user.groups.filter(name="Клієнти").exists()


class ManagerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Лише менеджери (група "Менеджери")."""

    def test_func(self):
        return self.request.user.groups.filter(name="Менеджери").exists()
