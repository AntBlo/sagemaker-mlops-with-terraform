from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, as_completed, wait
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

from bs4 import BeautifulSoup
from bs4.element import Tag
import lancedb
from lancedb.pydantic import pydantic_to_schema
import pyarrow as pa
from pydantic import BaseModel, Field
from tqdm import tqdm

from src.lib.config.config import ENV


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


BASE_URL = "https://www.2carpros.com"
DATASET_RAW_DIR = ENV.dataset_two_car_pros / "raw/data"
DATASET_STANDARDIZED_DIR = ENV.dataset_two_car_pros / "standardized/two_car_pros"
DATASET_LANCEDB_DIR = ENV.dataset_two_car_pros / "lancedb"
LANCEDB_STANDARDIZED_RECORDS = "standardized-two-car-pros"
WHITESPACE_RE = re.compile(r"\s+")
ORDINAL_DAY_RE = re.compile(r"(\d{1,2})(st|nd|rd|th)")
ENGINE_LITERS_RE = re.compile(r"^(\d+(?:\.\d+)?)L$", re.IGNORECASE)
CYLINDERS_RE = re.compile(r"^(\d+)\s*CYL$", re.IGNORECASE)
POST_COUNT_RE = re.compile(r"^([\d,]+)\s+POSTS?$", re.IGNORECASE)
MILES_RE = re.compile(r"^([\d,]+)\s+MILES$", re.IGNORECASE)
VEHICLE_RE = re.compile(r"^(\d{4})\s+(.+)$")
SIZE_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*([KMG]?B)$", re.IGNORECASE)


class PageTaxonomy(BaseModel):
    make: str | None = None
    model: str | None = None
    categories: list[str] = Field(default_factory=list)
    leaf_category: str | None = None


class VehicleInfo(BaseModel):
    year: int | None = None
    make: str | None = None
    model: str | None = None
    engine_displacement_liters: float | None = None
    cylinders: int | None = None
    drive_type: str | None = None
    transmission: str | None = None
    aspiration: str | None = None
    mileage: int | None = None
    extra: list[str] = Field(default_factory=list)


class AuthorInfo(BaseModel):
    username: str | None = None
    profile_url: str | None = None
    member_type: str | None = None
    is_staff: bool = False
    post_count: int | None = None


class ImageAsset(BaseModel):
    full_url: str | None = None
    thumbnail_url: str | None = None
    media_type: str | None = None
    size_raw: str | None = None
    size_bytes: int | None = None


class PostRecord(BaseModel):
    author: AuthorInfo
    vehicle: VehicleInfo | None = None
    posted_at_iso: str | None = None
    text: str
    images: list[ImageAsset] = Field(default_factory=list)


class AnswerPostRecord(BaseModel):
    author: AuthorInfo
    posted_at_iso: str | None = None
    text: str
    images: list[ImageAsset] = Field(default_factory=list)


class ForumPageRecord(BaseModel):
    source_file: str
    page_title: str | None = None
    canonical_url: str | None = None
    question: PostRecord
    answers: list[AnswerPostRecord]


PageTaxonomy.model_rebuild()
VehicleInfo.model_rebuild()
AuthorInfo.model_rebuild()
ImageAsset.model_rebuild()
PostRecord.model_rebuild()
AnswerPostRecord.model_rebuild()
ForumPageRecord.model_rebuild()


def normalize_text(value: str) -> str:
    cleaned = value.replace("\xa0", " ")
    lines = [WHITESPACE_RE.sub(" ", line).strip() for line in cleaned.splitlines()]
    return "\n".join(line for line in lines if line)


def absolute_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"{BASE_URL}{url}"


def attribute_as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def parse_int(value: str) -> int | None:
    try:
        return int(value.replace(",", ""))
    except ValueError:
        return None


def parse_size_bytes(size_raw: str | None) -> int | None:
    if not size_raw:
        return None
    match = SIZE_RE.match(size_raw.strip())
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2).upper()
    multipliers = {
        "B": 1,
        "KB": 1024,
        "MB": 1024 * 1024,
        "GB": 1024 * 1024 * 1024,
    }
    return int(amount * multipliers[unit])


def parse_posted_at(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    cleaned = ORDINAL_DAY_RE.sub(r"\1", raw_value)
    for pattern in ("%A, %B %d, %Y AT %I:%M %p", "%A, %B %d, %Y %I:%M %p"):
        try:
            return datetime.strptime(cleaned, pattern).isoformat()
        except ValueError:
            continue
    return None


def parse_vehicle(raw_value: str | None) -> VehicleInfo:
    if not raw_value:
        return VehicleInfo()
    match = VEHICLE_RE.match(raw_value)
    if not match:
        return VehicleInfo()
    model_tokens = match.group(2).split()
    return VehicleInfo(
        year=int(match.group(1)),
        make=model_tokens[0] if model_tokens else None,
        model=" ".join(model_tokens[1:]) if len(model_tokens) > 1 else None,
    )


def parse_vehicle_specs(stats: list[str]) -> VehicleInfo:
    engine_displacement_liters: float | None = None
    cylinders: int | None = None
    drive_type: str | None = None
    transmission: str | None = None
    aspiration: str | None = None
    mileage: int | None = None
    extra: list[str] = []

    for stat in stats:
        upper = stat.upper()
        if VEHICLE_RE.match(stat) or POST_COUNT_RE.match(stat):
            continue
        if upper in {
            "MEMBER",
            "MECHANIC",
            "MASTER CERTIFIED MECHANIC",
            "ADMIN",
            "MODERATOR",
        }:
            continue
        engine_match = ENGINE_LITERS_RE.match(stat)
        cylinder_match = CYLINDERS_RE.match(stat)
        miles_match = MILES_RE.match(stat)

        if miles_match:
            mileage = parse_int(miles_match.group(1))
        elif engine_match:
            engine_displacement_liters = float(engine_match.group(1))
        elif cylinder_match:
            cylinders = int(cylinder_match.group(1))
        elif upper in {"2WD", "4WD", "AWD", "FWD", "RWD"} or "WHEEL DRIVE" in upper:
            drive_type = stat
        elif upper in {"AUTOMATIC", "MANUAL", "CVT"}:
            transmission = stat
        elif upper in {"TURBO", "SUPERCHARGED", "HYBRID", "DIESEL"}:
            aspiration = stat
        else:
            extra.append(stat)

    return VehicleInfo(
        engine_displacement_liters=engine_displacement_liters,
        cylinders=cylinders,
        drive_type=drive_type,
        transmission=transmission,
        aspiration=aspiration,
        mileage=mileage,
        extra=extra,
    )


def apply_taxonomy_to_vehicle(vehicle: VehicleInfo, taxonomy: PageTaxonomy | None) -> VehicleInfo | None:
    if taxonomy is None:
        return vehicle

    if taxonomy.make is not None:
        vehicle.make = taxonomy.make
    if taxonomy.model is not None:
        vehicle.model = taxonomy.model

    if vehicle.make == "All Other Makes" and vehicle.model == "model":
        return None

    return vehicle


def extract_images(container: Tag) -> list[ImageAsset]:
    images: list[ImageAsset] = []
    for anchor in container.select(".gallery .thumbnail a"):
        img = anchor.find("img")
        size_raw = attribute_as_str(anchor.get("data-size"))
        images.append(
            ImageAsset(
                full_url=absolute_url(attribute_as_str(anchor.get("href"))),
                thumbnail_url=absolute_url(attribute_as_str(img.get("src")) if img else None),
                media_type=attribute_as_str(anchor.get("data-type")),
                size_raw=size_raw,
                size_bytes=parse_size_bytes(size_raw),
            )
        )
    return images


def extract_author(stats: list[str], username: str | None, profile_url: str | None, container: Tag) -> AuthorInfo:
    member_type = stats[0] if stats else None
    post_count_raw = next((stat for stat in stats if POST_COUNT_RE.match(stat)), None)
    post_count_match = POST_COUNT_RE.match(post_count_raw) if post_count_raw else None
    return AuthorInfo(
        username=username,
        profile_url=profile_url,
        member_type=member_type,
        is_staff="staff" in (container.get("class") or []),
        post_count=parse_int(post_count_match.group(1)) if post_count_match else None,
    )


def extract_post(container: Tag, taxonomy: PageTaxonomy | None = None) -> PostRecord:
    stats = [normalize_text(item.get_text(" ", strip=True)) for item in container.select(".stats li")]
    stats = [item for item in stats if item]

    username_node = container.select_one(".username")
    profile_link = container.select_one(".avatar a")
    text_node = container.select_one(".text")
    date_node = container.select_one(".date")
    images = extract_images(container)

    username = normalize_text(username_node.get_text(" ", strip=True)) if username_node else None
    profile_url = absolute_url(attribute_as_str(profile_link.get("href")) if profile_link else None)
    posted_at_raw = normalize_text(date_node.get_text(" ", strip=True)) if date_node else None

    text = ""
    if text_node is not None:
        text_soup = BeautifulSoup(str(text_node), "html.parser")
        for selector in [
            ".slink",
            ".magicbox",
            ".same-vote-container",
            ".vote-container",
            ".gallery",
            ".date",
            "script",
            "style",
        ]:
            for node in text_soup.select(selector):
                node.decompose()
        text = normalize_text(text_soup.get_text("\n", strip=True))

    vehicle_raw = next((stat for stat in stats if VEHICLE_RE.match(stat)), None)
    vehicle = parse_vehicle(vehicle_raw)
    vehicle_specs = parse_vehicle_specs(stats)
    merged_vehicle = VehicleInfo(
        year=vehicle.year,
        make=vehicle.make,
        model=vehicle.model,
        engine_displacement_liters=vehicle_specs.engine_displacement_liters,
        cylinders=vehicle_specs.cylinders,
        drive_type=vehicle_specs.drive_type,
        transmission=vehicle_specs.transmission,
        aspiration=vehicle_specs.aspiration,
        mileage=vehicle_specs.mileage,
        extra=vehicle_specs.extra,
    )
    final_vehicle = apply_taxonomy_to_vehicle(merged_vehicle, taxonomy)

    return PostRecord(
        author=extract_author(stats, username, profile_url, container),
        vehicle=final_vehicle,
        posted_at_iso=parse_posted_at(posted_at_raw),
        text=text,
        images=images,
    )


def extract_answer_post(container: Tag) -> AnswerPostRecord:
    stats = [normalize_text(item.get_text(" ", strip=True)) for item in container.select(".stats li")]
    stats = [item for item in stats if item]

    username_node = container.select_one(".username")
    profile_link = container.select_one(".avatar a")
    text_node = container.select_one(".text")
    date_node = container.select_one(".date")
    images = extract_images(container)

    username = normalize_text(username_node.get_text(" ", strip=True)) if username_node else None
    profile_url = absolute_url(attribute_as_str(profile_link.get("href")) if profile_link else None)
    posted_at_raw = normalize_text(date_node.get_text(" ", strip=True)) if date_node else None

    text = ""
    if text_node is not None:
        text_soup = BeautifulSoup(str(text_node), "html.parser")
        for selector in [
            ".slink",
            ".magicbox",
            ".same-vote-container",
            ".vote-container",
            ".gallery",
            ".date",
            "script",
            "style",
        ]:
            for node in text_soup.select(selector):
                node.decompose()
        text = normalize_text(text_soup.get_text("\n", strip=True))

    return AnswerPostRecord(
        author=extract_author(stats, username, profile_url, container),
        posted_at_iso=parse_posted_at(posted_at_raw),
        text=text,
        images=images,
    )


def extract_breadcrumbs(soup: BeautifulSoup) -> list[str]:
    items: list[str] = []
    for _, node in enumerate(soup.select("#breadcrumb li"), start=1):
        label = normalize_text(node.get_text(" ", strip=True))
        if not label:
            continue
        items.append(label)
    return items


def build_taxonomy(breadcrumbs: list[str]) -> PageTaxonomy:
    labels = breadcrumbs
    make = labels[1] if len(labels) > 1 else None
    model = labels[2] if len(labels) > 2 else None
    categories = labels[3:] if len(labels) > 3 else []
    return PageTaxonomy(
        make=make,
        model=model,
        categories=categories,
        leaf_category=categories[-1] if categories else None,
    )


def iter_dataset_raw_paths() -> list[Path]:
    return list(DATASET_RAW_DIR.glob("*.html"))


def iter_extracted_pages(paths: Iterable[Path], total: int | None = None) -> Iterator[ForumPageRecord]:
    path_iterator = iter(paths)
    max_workers = 32
    max_in_flight = max_workers * 4

    with tqdm(total=total, desc="Extracting pages", unit="page") as progress:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            in_flight = {
                executor.submit(extract_page, path)
                for _, path in zip(range(max_in_flight), path_iterator)
            }

            while in_flight:
                done, _ = wait(in_flight, return_when=FIRST_COMPLETED)
                for future in done:
                    in_flight.remove(future)
                    progress.update(1)
                    yield future.result()

                    next_path = next(path_iterator, None)
                    if next_path is not None:
                        in_flight.add(executor.submit(extract_page, next_path))


def extract_pages(paths: Iterable[Path]) -> list[ForumPageRecord]:
    path_list = list(paths)
    if not path_list:
        return []

    if len(path_list) == 1:
        return [extract_page(path_list[0])]

    results: list[ForumPageRecord | None] = [None] * len(path_list)
    max_workers = min(32, len(path_list))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(extract_page, path): index for index, path in enumerate(path_list)
        }
        for future in as_completed(future_to_index):
            index = future_to_index[future]
            results[index] = future.result()

    return [record for record in results if record is not None]


def serialize_pages(pages: Iterable[ForumPageRecord]) -> list[dict[str, object]]:
    return [page.model_dump(mode="json") for page in pages]


def iter_serialized_page_chunks(
    pages: Iterable[ForumPageRecord], chunk_size: int = 500
) -> Iterator[list[dict[str, object]]]:
    chunk: list[dict[str, object]] = []
    for page in pages:
        chunk.append(page.model_dump(mode="json"))
        if len(chunk) >= chunk_size:
            yield chunk
            chunk = []

    if chunk:
        yield chunk


def save_pages_to_lancedb(
    pages_list: list[Path],
    db_dir: Path = DATASET_LANCEDB_DIR,
    table_name: str = LANCEDB_STANDARDIZED_RECORDS,
) -> int:
    pages = iter_extracted_pages(iter(pages_list), total=len(pages_list))
    chunk_iterator = iter_serialized_page_chunks(pages)
    first_chunk = next(chunk_iterator, None)
    if first_chunk is None:
        raise ValueError("No pages to save to LanceDB")

    schema = pydantic_to_schema(ForumPageRecord)
    total_saved = len(first_chunk)

    def iter_record_batches() -> Iterator[pa.RecordBatch]:
        nonlocal total_saved
        first_table = pa.Table.from_pylist(first_chunk, schema=schema)
        yield from first_table.to_batches()
        for chunk in chunk_iterator:
            total_saved += len(chunk)
            table = pa.Table.from_pylist(chunk, schema=schema)
            yield from table.to_batches()

    db_dir.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(db_dir))
    db.create_table(table_name, data=iter_record_batches(), schema=schema, mode="overwrite")

    return total_saved


def extract_page(html_path: Path) -> ForumPageRecord:
    with html_path.open("r", encoding="utf-8") as file:
        soup = BeautifulSoup(file.read(), "html.parser")

    breadcrumbs = extract_breadcrumbs(soup)
    page_title = soup.select_one("h1")
    canonical = soup.select_one('link[rel="canonical"]')
    question_block = soup.select_one("#question .content")
    answer_nodes = [
        node
        for node in soup.select("#replies .reply")
        if node.select_one(".username") and node.select_one(".text")
    ]

    if question_block is None:
        raise ValueError(f"Could not find question block in {html_path}")

    taxonomy = build_taxonomy(breadcrumbs)
    question = extract_post(question_block, taxonomy=taxonomy)
    answers = [extract_answer_post(node) for node in answer_nodes]

    return ForumPageRecord(
        source_file=html_path.name,
        page_title=normalize_text(page_title.get_text(" ", strip=True)) if page_title else None,
        canonical_url=attribute_as_str(canonical.get("href")) if canonical else None,
        question=question,
        answers=answers,
    )


def save_dataset_to_lancedb() -> int:
    paths = iter_dataset_raw_paths()
    return save_pages_to_lancedb(paths)


if __name__ == "__main__":
    total_saved = save_dataset_to_lancedb()
    print(
        f"Saved {total_saved} ForumPageRecord rows to LanceDB table "
        f"'{LANCEDB_STANDARDIZED_RECORDS}' in {DATASET_LANCEDB_DIR}"
    )


