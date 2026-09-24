import urllib3
from EUC_parse import *

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

url = input("Закинь мне URL сынок (0 - стоп): ")

while url != "0":

    try:

        result = parse_contract(url)

        print("\n========== РЕЗУЛЬТАТ ==========\n")

        # ==========================================
        # ОБЩАЯ ИНФОРМАЦИЯ
        # ==========================================

        if isinstance(result, dict) and "objects" not in result:

            for key, value in result.items():
                print(f"{key}: {value}")

        # ==========================================
        # ИСПОЛНЕНИЕ КОНТРАКТА
        # ==========================================

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

        # ==========================================
        # ПЛАТЕЖИ И ОБЪЕКТЫ
        # ==========================================

        elif isinstance(result, dict) and "objects" in result:

            print("График финансирования:")

            for stage in result["finance_schedule"]:
                print(f"  {stage['stage']}")

            print("\nОбъекты закупки:")

            for number, obj in enumerate(result["objects"], start=1):

                print(f"\n--- Позиция {number} ---")

                for value in obj:
                    print(value)

        # ==========================================
        # ОБЩАЯ ИНФОРМАЦИЯ
        # ==========================================

        elif isinstance(result, dict):

            for key, value in result.items():
                print(f"{key}: {value}")

        # ==========================================
        # ОСТАЛЬНЫЕ СТРАНИЦЫ
        # ==========================================

        else:

            print(result)

        print("\n===============================\n")

        url = input("Закинь мне URL сынок: ")

    except requests.RequestException as e:

        print("Ошибка при загрузке страницы:", e)

        url = input("Закинь мне URL сынок: ")