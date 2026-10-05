import urllib3
from EUC_parse import *

from EUC_parse import (
    parse_contract,
    parse_local_contract
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def print_result(result):
    """Красиво выводит результат парсинга."""
    print("\n========== РЕЗУЛЬТАТ ==========\n")

    if isinstance(result, dict) and result.get("source") == "local_files":
        print(f"Папка контракта: {result['folder']}")
        print(f"Найденные файлы: {', '.join(result['files'])}")

        print("\n--- Информация из XML ---")
        for key, value in result["xml_data"].items():
            if isinstance(value, list):
                print(f"{key}:")
                for item in value:
                    print(f"    - {item}")
            else:
                print(f"{key}: {value}")

        if result.get("docx_data"):
            print("\n--- Информация из DOCX ---")
            for key, value in result["docx_data"].items():
                if isinstance(value, list):
                    print(f"{key}:")
                    for item in value:
                        print(f"    - {item}")
                else:
                    print(f"{key}: {value}")

        return

    # Исполнение контракта
    if isinstance(result, dict) and "stages" in result:
        print(f"Цена контракта: {result['contract_price']}")
        print(
            f"Стоимость исполненных обязательств: "
            f"{result['fulfilled_obligations']}"
        )
        print(f"Фактически оплачено: {result['actually_paid']}")

        print("\nЭтапы исполнения:")

        for number, stage in enumerate(result["stages"], start=1):
            print(f"\n--- Этап {number} ---")
            print(f"Этап: {stage['stage']}")
            print(
                f"Исполнено обязательств: "
                f"{stage['fulfilled_obligations']}"
            )
            print(f"Фактически оплачено: {stage['actually_paid']}")
            print(f"Документы: {stage['documents']}")
            print(f"Неустойки: {stage['penalties']}")
            print(
                f"Исполнение завершено: "
                f"{stage['execution_completed']}"
            )

    # Платежи и объекты
    elif isinstance(result, dict) and "objects" in result:
        print("График финансирования:")

        for stage in result["finance_schedule"]:
            print(f"  {stage['stage']}")

        print("\nОбъекты закупки:")

        for number, obj in enumerate(result["objects"], start=1):
            print(f"\n--- Позиция {number} ---")

            for value in obj:
                print(value)

    elif isinstance(result, dict):
        for key, value in result.items():
            print(f"{key}: {value}")

    else:
        print(result)

    print("\n===============================\n")


def url_mode():
    """Старый режим: парсинг страниц по URL."""
    url = input("Закинь мне URL сынок (0 - стоп): ")

    while url != "0":
        try:
            result = parse_contract(url)
            print_result(result)

        except requests.RequestException as e:
            print("Ошибка при загрузке страницы:", e)

        except Exception as e:
            print("Ошибка:", e)

        url = input("Закинь мне URL сынок (0 - стоп): ")


def local_files_mode():
    """Новый режим: чтение файлов конкретного контракта."""
    contract_number = input(
        "\nВведи номер контракта "
        "(0 - вернуться в главное меню): "
    )

    while contract_number != "0":
        try:
            result = parse_local_contract(contract_number)
            print_result(result)

        except FileNotFoundError as e:
            print(f"\nОшибка: {e}")

        except ValueError as e:
            print(f"\nОшибка в файлах контракта: {e}")

        except Exception as e:
            print(f"\nОшибка при чтении файлов: {e}")

        contract_number = input(
            "\nВведи номер контракта "
            "(0 - вернуться в главное меню): "
        )


def main():
    while True:
        print("\n========== ВЫБОР РЕЖИМА ==========")
        print("1 - Прочитать файлы по номеру контракта")
        print("2 - Закинуть URL")
        print("0 - Выход")
        print("===================================")

        choice = input("Выбери режим: ").strip()

        if choice == "1":
            local_files_mode()

        elif choice == "2":
            url_mode()

        elif choice == "0":
            print("Программа завершена.")
            break

        else:
            print("Неизвестный пункт. Выбери 0, 1 или 2.")


if __name__ == "__main__":
    main()
