def roles(request):
    """Додає в шаблони прапорці ролей: is_manager / is_client."""
    user = request.user
    return {
        "is_manager": user.is_authenticated and user.groups.filter(name="Менеджери").exists(),
        "is_client": user.is_authenticated and hasattr(user, "client_profile"),
    }
