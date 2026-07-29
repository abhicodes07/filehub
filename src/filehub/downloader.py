import asyncio
import sys
import time
from pathlib import Path
from typing import Any

import aiofiles
import httpx
from rich.progress import TaskID

from filehub.colors import BRIGHT_GREEN, BRIGHT_YELLOW, RESET
from filehub.errors import handle_client_error
from filehub.progress import download_progress, fetch_progress
from filehub.utils import parse_gist_url


def process_request_url(
    owner: str, repo: str, branch: str | None, path: str | None, is_zip: bool = False
) -> str:
    """process Github API url using repo details"""

    if is_zip:
        zip_prefix = f"https://api.github.com/repos/{owner}/{repo}/zipball"
        zip_suffix = ""
        if branch:
            zip_suffix = f"/{branch}"
        return zip_prefix + zip_suffix

    repo_url_prefix = f"https://api.github.com/repos/{owner}/{repo}/contents"
    repo_url_suffix = ""

    if branch and path:
        repo_url_suffix = f"/{path}?ref={branch}"
    elif branch:
        repo_url_suffix = f"?ref={branch}"
    elif path:
        repo_url_suffix = f"/{path}"

    return repo_url_prefix + repo_url_suffix


async def get_repository_content(repo_info: dict) -> list[dict]:
    """fetch files from provided repository"""

    request_url = process_request_url(
        repo_info["owner"],
        repo_info["repository"],
        repo_info["branch"],
        repo_info["path"],
    )
    fetched_urls = [request_url]

    response = []
    files = []

    try:
        fetch_start_time = time.perf_counter()
        with fetch_progress:
            fetch_task = fetch_progress.add_task(
                description="Fetching repository content"
            )
            async with httpx.AsyncClient() as client:
                for req in fetched_urls:
                    # fetch_progress.console.log(f"Fetched URL: [bold yellow]{req}")

                    res = await client.get(req)
                    res.raise_for_status()

                    # response is a dict if it's single file
                    # else it is a list of dicts of multiple files
                    if isinstance(res.json(), dict):
                        response.append(res.json())
                    else:
                        response = res.json()

                    if response:
                        # sort files and directories
                        for res in response:
                            if res["type"] == "file":
                                # remove the filename from the path
                                res["path"] = "/".join(res["path"].split("/")[:-1])
                                files.append(res)
                            else:
                                fetched_urls.append(res["url"])
                    response.clear()

            fetch_progress.update(fetch_task, visible=False)

        fetch_finish_time = time.perf_counter()
        print(
            f"\nFetched {BRIGHT_GREEN}{len(files)}{RESET} files in {fetch_finish_time - fetch_start_time:.2f}s.\n"
        )
    except httpx.HTTPError as exc:
        handle_client_error(exc)
        sys.exit(1)

    return files


async def download_single_file(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    taskid: TaskID,
    file: dict,
    root: Path,
    flatten: bool | None = None,
) -> Path:
    path = file["path"]

    if flatten:
        path = ""

    # preserve repository path
    file_path = Path(root / path)
    file_path.mkdir(parents=True, exist_ok=True)
    download_path = file_path / file["name"]

    if download_path.exists():
        print(f"{BRIGHT_YELLOW}{file['name']}{RESET} already exists!")
    else:
        try:
            async with semaphore:
                ts = int(time.time())
                url = f"{file['download_url']}?ts={ts}"

                async with client.stream("GET", url, follow_redirects=True) as response:
                    response.raise_for_status()
                    download_progress.update(taskid, total=int(file["size"]))

                    async with aiofiles.open(download_path, "wb") as f:
                        download_progress.start_task(taskid)

                        async for chunk in response.aiter_bytes(chunk_size=512 * 1024):
                            if chunk:
                                await f.write(chunk)
                                download_progress.update(taskid, advance=len(chunk))
                    download_progress.update(taskid, visible=False)
                    download_progress.console.log(
                        f"Downloaded {file['name']} and saved to [yellow][italic]{download_path}"
                    )
        except Exception as e:
            print(e)

    return download_path


async def download_files(
    files: list[dict[str, Any]],
    path: Path,
    download_limit: int,
    flatten: bool | None = None,
) -> list[Path]:
    """download files asynchronously"""

    # NOTE: LIMIT PROCESSES SPAWN LIMIT IN CPU IN CASE THERE ARE THOUSANDS OF REQUESTS
    dl_semaphore = asyncio.Semaphore(download_limit)

    with download_progress:
        async with httpx.AsyncClient() as client:
            async with asyncio.TaskGroup() as tg:
                tasks = []
                for file in files:
                    task_id = download_progress.add_task(
                        "download", filename=file["name"], start=False
                    )
                    tasks.append(
                        tg.create_task(
                            download_single_file(
                                client, dl_semaphore, task_id, file, path, flatten
                            )
                        )
                    )

            file_paths = [task.result() for task in tasks]

    return file_paths


def download_zip(repo_info: dict, download_path: Path) -> None:
    """download zip file"""
    # process api url
    url = process_request_url(
        repo_info["owner"],
        repo_info["repository"],
        repo_info["branch"],
        repo_info["path"],
    )

    # download file name, add branch if provided
    output = f"{repo_info['repository']}.zip"
    if repo_info["branch"]:
        output = f"{repo_info['repository']}-{repo_info['branch']}.zip"

    path = download_path / output
    if path.exists():
        print(f"{output} already exists at {download_path}/")
        sys.exit(0)

    try:
        with download_progress:
            with httpx.Client(follow_redirects=True) as client:
                with client.stream("GET", url) as response:
                    response.raise_for_status()

                    # NOTE: this might break if response doesn't contain `Content-Length`
                    zip_size = int(response.headers.get("Content-Length", 0))
                    task = download_progress.add_task(
                        description=f"Downloading {repo_info['repository']}",
                        filename=output,
                        total=zip_size,
                    )
                    with open(path, "wb") as f:
                        for chunk in response.iter_bytes(chunk_size=512 * 1024):
                            if chunk:
                                f.write(chunk)
                                download_progress.update(task, advance=len(chunk))

            # print(f"Downloaded {repo_info['repository']} to {path}.")
            download_progress.console.log(
                f"Downloaded {repo_info['repository']} to [bold][yellow]{path}."
            )

    except httpx.HTTPError as e:
        handle_client_error(e)
        sys.exit(1)


def get_gist(url: str) -> dict[str, str]:
    gist_id = parse_gist_url(url)
    req = f"https://api.github.com/gists/{gist_id}"
    try:
        with httpx.Client(follow_redirects=True) as client:
            res = client.get(req)
            res.raise_for_status()
            gist = res.json()
            file_name = list(gist["files"].keys())
            raw_url = gist["files"][file_name[0]]["raw_url"]
            return {"file": file_name[0], "raw_url": raw_url}

    except httpx.HTTPError as e:
        handle_client_error(e)
        sys.exit(1)


def download_gist(url: str, download_path: Path):
    gist = get_gist(url)
    file_name = gist["file"]
    raw_url = gist["raw_url"]
    path = download_path / file_name

    if path.exists():
        print(f"{file_name} already exists at {BRIGHT_YELLOW}{download_path}/{RESET}")
        sys.exit(1)

    try:
        with fetch_progress:
            fetch_task = fetch_progress.add_task(description="Downloading gist")
            response = httpx.get(raw_url).text
            with open(path, "w", encoding="utf-8") as f:
                f.write(response)

            fetch_progress.update(fetch_task, visible=False)
            print(f"Downloaded {BRIGHT_GREEN}{file_name}{RESET}.")

    except httpx.HTTPError as e:
        handle_client_error(e)
        sys.exit(1)
