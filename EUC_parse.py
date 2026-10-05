from pathlib import Path
from xml.etree import ElementTree as ET
import re

from docx import Document
from bs4 import BeautifulSoup

from EUC_download import *


# ========================================== #
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ЛОКАЛЬНЫХ ФАЙЛОВ
# ========================================== #

def _xml_tag(element):
    """Возвращает имя XML-тега без namespace."""
    return element.tag.split("}")[-1]


def _find_xml_value(root, tag_name):
    """Ищет первое значение XML-тега по его локальному имени."""
    for element in root.iter():
        if _xml_tag(element) == tag_name:
            if element.text and element.text.strip():
                return element.text.strip()

    return None


def _find_all_xml_values(root, tag_name):
    """Возвращает все непустые значения указанного XML-тега."""
    values = []

    for element in root.iter():
        if _xml_tag(element) == tag_name:
            if element.text and element.text.strip():
                values.append(element.text.strip())

    return values


def _find_local_contract_folder(contract_number):
    """
    Ищет папку contract_files по введенному номеру.

    Сначала проверяется:
        contract_files/<номер>

    Если такой папки нет, дополнительно просматриваются
    XML-файлы в подпапках: если <contractNumber> совпадает
    с введенным номером, используется эта папка.
    """

    project_dir = Path(__file__).resolve().parent
    contracts_dir = project_dir / "contract_files"

    if not contracts_dir.exists():
        raise FileNotFoundError(
            f"Папка с контрактами не существует: {contracts_dir}"
        )

    if not contracts_dir.is_dir():
        raise FileNotFoundError(
            f"Путь {contracts_dir} существует, но это не папка."
        )

    direct_folder = contracts_dir / str(contract_number)

    if direct_folder.exists() and direct_folder.is_dir():
        return direct_folder

    for folder in contracts_dir.iterdir():
        if not folder.is_dir():
            continue

        for xml_file in folder.glob("*.xml"):
            try:
                root = ET.parse(xml_file).getroot()
                xml_contract_number = _find_xml_value(
                    root,
                    "contractNumber"
                )

                if xml_contract_number == str(contract_number):
                    return folder

            except (ET.ParseError, OSError):
                continue

    raise FileNotFoundError(
        f"Папка или файлы контракта №{contract_number} не найдены "
        f"в {contracts_dir}"
    )


def _find_contract_files(folder):
    """Проверяет наличие XML и DOCX файлов в папке контракта."""

    all_files = [
        file for file in folder.iterdir()
        if file.is_file()
    ]

    if not all_files:
        raise FileNotFoundError(
            f"Папка контракта пуста: {folder}"
        )

    xml_files = [
        file for file in all_files
        if file.suffix.lower() == ".xml"
    ]

    docx_files = [
        file for file in all_files
        if file.suffix.lower() == ".docx"
    ]

    if not xml_files and not docx_files:
        raise FileNotFoundError(
            f"В папке {folder} нет поддерживаемых файлов "
            f"(XML или DOCX)."
        )

    return xml_files, docx_files


def parse_local_xml(xml_file):
    """
    Извлекает основные данные электронного контракта из XML.
    """

    try:
        root = ET.parse(xml_file).getroot()
    except ET.ParseError as e:
        raise ValueError(
            f"Не удалось прочитать XML-файл {xml_file.name}: {e}"
        )

    data = {}

    fields = {
        "Номер контракта": "contractNumber",
        "Заказчик": "fullName",
        "ИНН заказчика": "INN",
        "КПП заказчика": "KPP",
        "Поставщик / исполнитель": "counterparty160Name",
        "ИНН поставщика": "INN",
        "Способ определения поставщика": "name",
        "Идентификационный код закупки": "purchaseCode",
        "Номер извещения": "purchaseNumber",
        "Предмет контракта": "contractSubject",
        "Цена контракта": "price",
        "Дата начала исполнения": "startDate",
        "Дата окончания исполнения": "endDate",
        "Место исполнения": "deliveryPlace",
        "Количество": "quantity",
        "Единица измерения": "nationalCode",
        "Бюджет": "name",
    }

    # Значения, которые однозначно можно получить из XML.
    # Для неоднозначных тегов ниже используются отдельные блоки.

    data["Номер контракта"] = _find_xml_value(root, "contractNumber")
    data["Заказчик"] = _find_xml_value(root, "fullName")

    customer_inn = None
    customer_kpp = None

    for element in root.iter():
        tag = _xml_tag(element)

        if tag == "customerInfo":
            for child in element.iter():
                child_tag = _xml_tag(child)

                if child_tag == "INN" and child.text:
                    customer_inn = child.text.strip()
                elif child_tag == "KPP" and child.text:
                    customer_kpp = child.text.strip()

            break

    data["ИНН заказчика"] = customer_inn
    data["КПП заказчика"] = customer_kpp

    supplier_name = None
    supplier_inn = None

    for element in root.iter():
        if _xml_tag(element) == "participantInfo":
            for child in element.iter():
                tag = _xml_tag(child)

                if tag == "counterparty160Name" and child.text:
                    supplier_name = child.text.strip()

                elif tag == "INN" and child.text:
                    supplier_inn = child.text.strip()

            break

    data["Поставщик / исполнитель"] = supplier_name
    data["ИНН поставщика"] = supplier_inn

    # Способ определения поставщика.
    placing_names = _find_all_xml_values(root, "name")

    for value in placing_names:
        if value in (
            "Запрос котировок в электронной форме",
            "Открытый конкурс в электронной форме",
            "Электронный аукцион",
        ):
            data["Способ определения поставщика"] = value
            break

    data["Идентификационный код закупки"] = _find_xml_value(
        root,
        "purchaseCode"
    )

    data["Номер извещения"] = _find_xml_value(
        root,
        "purchaseNumber"
    )

    data["Предмет контракта"] = _find_xml_value(
        root,
        "contractSubject"
    )

    # Цена именно из contractPriceInfo.
    contract_price = None
    currency = None

    for element in root.iter():
        if _xml_tag(element) == "contractPriceInfo":
            for child in element.iter():
                tag = _xml_tag(child)

                if tag == "price" and child.text:
                    contract_price = child.text.strip()

                elif tag == "name" and child.text:
                    if child.text.strip() in (
                        "РОССИЙСКИЙ РУБЛЬ",
                        "Доллар США",
                        "Евро",
                    ):
                        currency = child.text.strip()

            break

    data["Цена контракта"] = contract_price
    data["Валюта"] = currency

    # Сроки исполнения.
    data["Дата начала исполнения"] = _find_xml_value(
        root,
        "startDate"
    )

    data["Дата окончания исполнения"] = _find_xml_value(
        root,
        "endDate"
    )

    data["Место исполнения"] = _find_xml_value(
        root,
        "deliveryPlace"
    )

    # Первый объект закупки.
    quantity = _find_xml_value(root, "quantity")
    unit = _find_xml_value(root, "nationalCode")

    data["Количество"] = quantity
    data["Единица измерения"] = unit

    # Бюджетный источник.
    budget = None

    for element in root.iter():
        if _xml_tag(element) == "budgetInfo":
            for child in element:
                if _xml_tag(child) == "name" and child.text:
                    budget = child.text.strip()
                    break

            if budget:
                break

    data["Источник финансирования"] = budget

    # Банковское сопровождение.
    bank_support = _find_xml_value(
        root,
        "bankSupportContractRequired"
    )

    data["Банковское сопровождение"] = bank_support

    # Аванс.
    advance = _find_xml_value(root, "sum")

    # В XML есть несколько sum, поэтому ищем именно advancePaymentSumInfo.
    for element in root.iter():
        if _xml_tag(element) == "advancePaymentSumInfo":
            for child in element:
                if _xml_tag(child) == "sum" and child.text:
                    advance = child.text.strip()
                    break

            if advance is not None:
                break

    data["Аванс"] = advance

    # Удаляем пустые значения.
    return {
        key: value
        for key, value in data.items()
        if value not in (None, "")
    }


def parse_local_docx(docx_file):
    """
    Читает DOCX и извлекает основные данные из текста контракта.
    """

    try:
        document = Document(docx_file)
    except Exception as e:
        raise ValueError(
            f"Не удалось открыть DOCX-файл {docx_file.name}: {e}"
        )

    paragraphs = [
        paragraph.text.strip()
        for paragraph in document.paragraphs
        if paragraph.text.strip()
    ]

    text = "\n".join(paragraphs)

    data = {}

    # Номер контракта.
    match = re.search(
        r"КОНТРАКТ\s*№\s*([^\s]+)",
        text,
        re.IGNORECASE
    )

    if match:
        data["Номер контракта"] = match.group(1)

    # Цена контракта.
    match = re.search(
        r"Цена\s+(?:настоящего\s+)?Контракта\s+составляет\s+"
        r"([0-9\s]+(?:[.,][0-9]+)?)",
        text,
        re.IGNORECASE
    )

    if match:
        data["Цена контракта по тексту"] = match.group(1).strip()

    # Идентификационный код закупки.
    match = re.search(
        r"Идентификационный код закупки:\s*(\d+)",
        text
    )

    if match:
        data["ИКЗ"] = match.group(1)

    # Период оказания услуг.
    match = re.search(
        r"Период оказания услуг:\s*(.+?)(?:\n|$)",
        text,
        re.IGNORECASE
    )

    if match:
        data["Период оказания услуг"] = match.group(1).strip()

    # Источник финансирования.
    match = re.search(
        r"Источник финансирования:\s*(.+?)(?:\n|$)",
        text,
        re.IGNORECASE
    )

    if match:
        data["Источник финансирования"] = match.group(1).strip()

    # Обеспечение исполнения контракта.
    match = re.search(
        r"8\.1\.\s*Обеспечение исполнения Контракта\s*(.+?)(?:\n|$)",
        text,
        re.IGNORECASE
    )

    if match:
        data["Обеспечение исполнения"] = match.group(1).strip()

    return data


def parse_local_contract(contract_number):
    """
    Основная функция локального режима.

    1. Проверяет папку contract_files.
    2. Находит папку нужного контракта.
    3. Проверяет наличие XML/DOCX.
    4. Парсит найденные файлы.
    5. Возвращает объединенный результат.
    """

    folder = _find_local_contract_folder(contract_number)

    xml_files, docx_files = _find_contract_files(folder)

    result = {
        "source": "local_files",
        "folder": str(folder),
        "files": [
            file.name
            for file in xml_files + docx_files
        ],
        "xml_data": {},
        "docx_data": {}
    }

    # Читаем ВСЕ XML-файлы и объединяем данные
    if xml_files:
        merged_xml_data = {}

        for xml_file in xml_files:
            try:
                xml_data = parse_local_xml(xml_file)
            except ValueError as e:
                print(f"Предупреждение: {e}")
                continue

            for key, value in xml_data.items():
                # Если ключ уже есть и значение непустое —
                # оставляем первое непустое значение,
                # но если в новом файле значение тоже непустое
                # и отличается, добавляем его с пометкой файла.
                if key not in merged_xml_data:
                    merged_xml_data[key] = value
                elif merged_xml_data[key] != value:
                    # Конфликт: сохраняем оба значения
                    existing = merged_xml_data[key]

                    if isinstance(existing, list):
                        if value not in existing:
                            existing.append(value)
                    else:
                        merged_xml_data[key] = [existing, value]

        result["xml_data"] = merged_xml_data

    if docx_files:
        # Обычно DOCX один. Если их несколько — читаем первый.
        result["docx_data"] = parse_local_docx(docx_files[0])

    return result


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
