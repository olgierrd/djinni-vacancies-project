import csv
import logging
import sys
import time
from urllib.parse import urljoin

import requests
from dataclasses import dataclass, fields, astuple
from bs4 import BeautifulSoup
import asyncio
from aiohttp import ClientSession

from config import BASE_URL, CSV_FILE, TECHS, PYTHON_VACANCIES


@dataclass
class Vacancy:
    title: str
    company: str
    technologies: list[str]


VACANCY_FIELDS = [field.name for field in fields(Vacancy)]

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)8s] - %(message)s",
    handlers=[
        logging.FileHandler("parser.log"),
        logging.StreamHandler(sys.stdout)
    ]
)


def get_technologies(text: str) -> list[str]:
    return list(set([tech for tech in TECHS if tech.lower() in text.lower()]))


def get_number_of_pages(soup: BeautifulSoup) -> int:
    pagination = soup.select_one(".pagination")
    if not pagination:
        return 1
    return int(pagination.select("li")[-2].text)


async def get_full_description(vacancy_soup: BeautifulSoup) -> str:
    detailed_url = urljoin(BASE_URL, vacancy_soup.select_one("a.job-list-item__link").get("href"))
    async with ClientSession() as session:
        async with session.get(detailed_url, ssl=False) as response:
            page = await response.text()
    soup = BeautifulSoup(page, "html.parser")
    full_description = soup.select_one(".col-sm-8").text
    return full_description


async def parse_single_vacancy(vacancy_soup: BeautifulSoup) -> Vacancy:
    return Vacancy(
        title=vacancy_soup.select_one(".job-list-item__title").text.strip(),
        company=vacancy_soup.select_one("a.mr-2").text.strip(),
        technologies=get_technologies(await get_full_description(vacancy_soup))
    )


async def parse_single_page(page_soup: BeautifulSoup) -> [Vacancy]:
    vacancies = page_soup.select(".job-list-item")
    return await asyncio.gather(*[
        parse_single_vacancy(vacancy_soup)
        for vacancy_soup in vacancies
    ])


async def get_vacancies() -> [Vacancy]:
    logging.info("Parsing vacancies")
    home_page = requests.get(PYTHON_VACANCIES).content
    soup = BeautifulSoup(home_page, "html.parser")
    number_of_pages = get_number_of_pages(soup)
    logging.info(f"Found {number_of_pages} pages")
    logging.info(f"Parsing page 1")
    vacancies = await parse_single_page(soup)
    for page_number in range(2, number_of_pages + 1):
        logging.info(f"Parsing page {page_number}")
        page = requests.get(f"{PYTHON_VACANCIES}?page={page_number}").content
        soup = BeautifulSoup(page, "html.parser")
        vacancies.extend(await parse_single_page(soup))
        time.sleep(1)
    return vacancies


def save_to_csv(vacancies: [Vacancy]):
    with open(CSV_FILE, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(VACANCY_FIELDS)
        for vacancy in vacancies:
            writer.writerow(astuple(vacancy))


def parsing_for_data() -> None:
    vacancies = asyncio.run(get_vacancies())
    save_to_csv(vacancies)


if __name__ == '__main__':
    parsing_for_data()

