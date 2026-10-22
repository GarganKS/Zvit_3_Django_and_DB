try:
    import pymysql
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Для роботи з MySQL потрібен PyMySQL: uv pip install --python .venv/bin/python pymysql"
    ) from exc

pymysql.install_as_MySQLdb()
