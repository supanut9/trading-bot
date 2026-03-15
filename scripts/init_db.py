from app.infrastructure.database.init_db import init_database


def main() -> None:
    tables = init_database()
    print("initialized tables:", ", ".join(tables))


if __name__ == "__main__":
    main()
