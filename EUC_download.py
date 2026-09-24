from pathlib import Path
from urllib.parse import urljoin
import requests
# ========================================== #
# download_attachments                       #
# ========================================== #
def download_attachments(soup, page_url):
    """
    Находит файлы на странице 'Вложения' и скачивает их
    в отдельную папку рядом с проектом.

    Содержимое файлов пока НЕ читается.
    """

    # Ищем реестровый номер в URL
    if "reestrNumber=" in page_url:
        registry_number = page_url.split("reestrNumber=")[1].split("&")[0]
    else:
        registry_number = "unknown_contract"

    # Папка рядом с файлом Python
    project_dir = Path(__file__).resolve().parent

    # Папка для файлов конкретного контракта
    attachments_dir = project_dir / "contract_files" / registry_number

    attachments_dir.mkdir(parents=True, exist_ok=True)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        )
    }

    downloaded_files = []

    # Ищем все ссылки на файлы
    links = soup.find_all("a", href=True)

    for link in links:

        href = link["href"]

        # Нас интересуют именно файлы из filestore
        if "/44fz/filestore/public/" not in href:
            continue

        file_url = urljoin(page_url, href)

        # Пытаемся получить имя файла из title
        file_name = link.get("title")

        # Если title отсутствует — берём текст ссылки
        if not file_name:
            file_name = link.get_text(" ", strip=True)

        # Если и текста нет — временное имя
        if not file_name:
            file_name = "attachment"

        # Убираем потенциально проблемные символы
        invalid_chars = '<>:"/\\|?*'

        for char in invalid_chars:
            file_name = file_name.replace(char, "_")

        file_name = file_name.strip()

        # Иногда название содержит лишнюю информацию.
        # Расширение определяем по URL/Content-Type ниже.
        file_path = attachments_dir / file_name

        # Если файл уже существует — повторно не скачиваем
        if file_path.exists():
            print(f"Файл уже существует: {file_path.name}")

            downloaded_files.append(str(file_path))
            continue

        print(f"Скачивание: {file_name}")

        try:

            response = requests.get(
                file_url,
                headers=headers,
                timeout=60,
                verify=False
            )

            response.raise_for_status()

            # Если сервер отдал имя файла в Content-Disposition
            content_disposition = response.headers.get(
                "Content-Disposition",
                ""
            )

            if "filename=" in content_disposition:

                server_filename = content_disposition.split(
                    "filename=",
                    1
                )[1].strip().strip('"')

                if server_filename:
                    file_name = server_filename

                    for char in invalid_chars:
                        file_name = file_name.replace(char, "_")

                    file_path = attachments_dir / file_name

            with open(file_path, "wb") as file:
                file.write(response.content)

            print(f"Скачан: {file_path}")

            downloaded_files.append(str(file_path))

        except requests.RequestException as e:

            print(f"Ошибка скачивания {file_url}: {e}")

    return downloaded_files