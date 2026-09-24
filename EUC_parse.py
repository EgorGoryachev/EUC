from EUC_download import *
from bs4 import BeautifulSoup
# ========================================== #
# parse_common_info                          #
# ========================================== #
def parse_common_info(soup):
    """
    Извлекает только важную информацию
    со страницы 'Общая информация'.
    """

    text = soup.get_text("\n", strip=True)

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    data = {}

    important_fields = [
        "Реестровый номер контракта",
        "Статус контракта",
        "Номер извещения об осуществлении закупки",
        "Способ определения поставщика (подрядчика, исполнителя)",
        "Дата подведения результатов определения поставщика (подрядчика, исполнителя)",
        "Дата размещения (по местному времени)",
        "Основание заключения контракта с единственным поставщиком",
        "Информация о банковском и (или) казначейском сопровождении контракта",

        "Полное наименование заказчика",
        "Сокращенное наименование заказчика",
        "ИНН",

        "Дата заключения контракта",
        "Номер контракта",
        "Предмет контракта",
        "Цена контракта",
        "Валюта контракта",
        "Дата начала исполнения контракта",
        "Дата окончания исполнения контракта",

        "Контрактом предусмотрено удержание суммы неисполненных требований об уплате неустоек (штрафов, пеней) из суммы, подлежащей оплате поставщику (подрядчику, исполнителю)",

        "Размер обеспечения исполнения контракта, ₽"
    ]

    for i, line in enumerate(lines):

        for field in important_fields:

            if line == field:

                if i + 1 < len(lines):
                    data[field] = lines[i + 1]

                break

    return data

# ========================================== #
# parse_payment_info                         #
# ========================================== #

def parse_payment_info(soup):
    """
    Извлекает важную информацию со страницы
    'Платежи и объекты закупки'.
    """

    data = {
        "finance_schedule": [],
        "objects": []
    }

    text = soup.get_text("\n", strip=True)

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    for i, line in enumerate(lines):

        if line.startswith("Этап:"):

            data["finance_schedule"].append({
                "stage": line
            })

    tables = soup.find_all("table")

    for table in tables:

        rows = table.find_all("tr")

        for row in rows:

            cells = row.find_all(["td", "th"])

            cell_text = [
                cell.get_text(" ", strip=True)
                for cell in cells
            ]

            if not cell_text:
                continue

            if "Наименование объекта закупки" in " ".join(cell_text):
                continue

            if any("Итого" in cell for cell in cell_text):
                continue

            if len(cell_text) < 5:
                continue

            data["objects"].append(cell_text)

    return data
# ========================================== #
# parse_contract                             #
# ========================================== #

def parse_contract(url):

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        )
    }

    if "common-info.html" in url:
        page_type = "Общая информация"

    elif "payment-info-and-target-of-order.html" in url:
        page_type = "Платежи и объекты закупки"

    elif "process-info.html" in url:
        page_type = "Исполнение (расторжение контракта)"

    elif "document-info.html" in url:
        page_type = "Вложения"

    else:
        page_type = "Неизвестная страница"

    print("\nТип страницы:", page_type)

    response = requests.get(
        url,
        headers=headers,
        timeout=30,
        verify=False
    )

    response.raise_for_status()

    print("Статус:", response.status_code)
    print("Размер ответа:", len(response.text))

    soup = BeautifulSoup(response.text, "html.parser")

    for element in soup(["script", "style", "noscript"]):
        element.decompose()

    if "common-info.html" in url:

        return parse_common_info(soup)

    elif "payment-info-and-target-of-order.html" in url:

        return parse_payment_info(soup)

    elif "process-info.html" in url:

        return parse_process_info(soup)

    elif "document-info.html" in url:

        return download_attachments(soup, url)

    else:

        return soup.get_text("\n", strip=True)

# ========================================== #
# parse_process_info                         #
# ========================================== #

def parse_process_info(soup):
    """
    Извлекает важную информацию со страницы
    'Исполнение (расторжение контракта)'.
    """

    data = {
        "contract_price": None,
        "fulfilled_obligations": None,
        "actually_paid": None,
        "stages": []
    }

    text = soup.get_text("\n", strip=True)

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    for i, line in enumerate(lines):

        if line == "Цена контракта, ₽":
            if i + 1 < len(lines):
                data["contract_price"] = lines[i + 1]

        elif line == "Стоимость исполненных поставщиком (подрядчиком, исполнителем) обязательств, ₽":
            if i + 1 < len(lines):
                data["fulfilled_obligations"] = lines[i + 1]

        elif line == "Фактически оплачено, ₽":
            if i + 1 < len(lines):
                data["actually_paid"] = lines[i + 1]

    tables = soup.find_all("table")

    for table in tables:

        rows = table.find_all("tr")

        for row in rows:

            cells = row.find_all(["td", "th"])

            cell_text = [
                cell.get_text(" ", strip=True)
                for cell in cells
            ]

            if not cell_text:
                continue

            joined = " ".join(cell_text)

            if "Этап контракта" in joined:
                continue

            if any("идентификатор:" in cell for cell in cell_text):

                stage = {
                    "stage": None,
                    "fulfilled_obligations": None,
                    "actually_paid": None,
                    "documents": None,
                    "penalties": None,
                    "execution_completed": None
                }

                for cell in cell_text:

                    if "идентификатор:" in cell:
                        stage["stage"] = cell


                if len(cell_text) >= 2:
                    stage["fulfilled_obligations"] = cell_text[1]

                if len(cell_text) >= 3:
                    stage["actually_paid"] = cell_text[2]

                if len(cell_text) >= 4:
                    stage["documents"] = cell_text[3]

                if len(cell_text) >= 5:
                    stage["penalties"] = cell_text[4]

                if len(cell_text) >= 6:
                    stage["execution_completed"] = cell_text[5]

                data["stages"].append(stage)

    return data