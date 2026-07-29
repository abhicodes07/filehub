import asyncio
from pathlib import Path

import click

from filehub.downloader import (
    download_files,
    download_gist,
    download_zip,
    get_repository_content,
)
from filehub.fzf import select_files
from filehub.utils import (
    check_user_rate_limit,
    parse_repo_url,
    print_info,
)

# download dir
DOWNLOAD_DIR = Path("Filehub")

# limit download to only 4 cpus
DOWNLOAD_LIMIT = 4

# flags
BRANCH = False
FLATTEN = False
DIR = False
ZIP = False


@click.group()
@click.version_option()
def main():
    """A CLI asynchronous Github files downloader with fzf selection menu."""
    pass


@main.command()
@click.argument("url", type=str)
@click.option(
    "-b",
    "--branch",
    default=None,
    metavar="BRANCH_NAME",
    help="Specific branch of the repository to download files from.",
)
@click.option(
    "-c",
    "--concurrency",
    type=int,
    metavar="VALUE",
    default=DOWNLOAD_LIMIT,
    show_default=DOWNLOAD_LIMIT,
    help="Number of concurrent downloads.",
)
@click.option(
    "-r", "--rate-limit", is_flag=True, help="Check Github API rate limit uses."
)
@click.option("-d", "--dir", is_flag=True, help="Download whole directory.")
@click.option("-i", "--info", is_flag=True, help="Show repository info.")
@click.option("-f", "--flatten", is_flag=True, help="Flatten the directory structure.")
@click.option("-z", "--zip", is_flag=True, help="Download zip archive of a repository.")
def fetch(url, branch, rate_limit, dir, info, flatten, zip, concurrency):
    try:
        asyncio.run(
            initialize_download(
                url, branch, rate_limit, dir, info, flatten, zip, concurrency
            )
        )
    except Exception as e:
        print(str(e))


@main.command()
@click.argument("url", type=str)
@click.option(
    "-b",
    "--branch",
    default=None,
    metavar="BRANCH_NAME",
    help="Download zip of the this branch.",
)
@click.option("-i", "--info", is_flag=True, help="Show repository info.")
def zip(url, branch, info):
    try:
        repo = parse_repo_url(url, branch)

        if info:
            print_info(repo)

        # create folder
        global DOWNLOAD_DIR
        if repo["repository"]:
            DOWNLOAD_DIR = Path(repo["repository"])
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

        # download repo as zip
        download_zip(repo, DOWNLOAD_DIR)
    except Exception as e:
        print(e)


@main.command()
@click.argument("url", type=str)
def gist(url):
    try:
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        download_gist(url, DOWNLOAD_DIR)
    except Exception as e:
        print(e)


async def initialize_download(
    url, branch, rate_limit, dir, info, flatten, zip, concurrency
):
    # fetch url information
    repo = parse_repo_url(url, branch)

    if info:
        print_info(repo)

    # download selected files
    global DOWNLOAD_DIR
    if repo["repository"]:
        DOWNLOAD_DIR = Path(repo["repository"])
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    if zip:
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
        download_zip(repo, DOWNLOAD_DIR)
    else:
        files = await get_repository_content(repo)
        if not dir:
            files = select_files(files)
        await download_files(files, DOWNLOAD_DIR, concurrency, flatten)

    if rate_limit:
        check_user_rate_limit()
