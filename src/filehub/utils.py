from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

from filehub.colors import BRIGHT_GREEN, BRIGHT_RED, BRIGHT_YELLOW, RESET
from filehub.errors import BranchNotFoundError


def timing(start, fetch, download, finish):
    fetch_time = fetch - start
    select_time = download - fetch
    download_time = finish - download
    total_time = finish - start

    print(
        f"\nFetched files in: {BRIGHT_RED}{fetch_time:.2f}{RESET} seconds. {(fetch_time / total_time) * 100:.2f}% of total time.",
    )
    print(
        f"Selected files in: {BRIGHT_RED}{select_time:.2f}{RESET} seconds. {(select_time / total_time) * 100:.2f}% of total time.",
    )
    print(
        f"Downloaded files in: {BRIGHT_RED}{download_time:.2f}{RESET} seconds. {(download_time / total_time) * 100:.2f}% of total time.",
    )
    print(
        f"Total execution time: {BRIGHT_RED}{total_time:.2f}{RESET} seconds. {(total_time / total_time) * 100:.2f}% of total time.",
    )


def print_info(repo: dict[str, Any]):
    print(f"{BRIGHT_GREEN}[*]{RESET} Owner: ", end="")
    print(BRIGHT_YELLOW + repo["owner"] + RESET)

    print(f"{BRIGHT_GREEN}[*]{RESET} Repository name: ", end="")
    print(BRIGHT_YELLOW + repo["repository"] + RESET)

    if repo["branch"]:
        print(f"{BRIGHT_GREEN}[*]{RESET} Branch: ", end="")
        print(BRIGHT_YELLOW + repo["branch"] + RESET)

    if repo["path"]:
        print(f"{BRIGHT_GREEN}[*]{RESET} Path: ", end="")
        print(BRIGHT_YELLOW + repo["path"] + RESET)
    print()


def check_user_rate_limit() -> None:
    response = httpx.get("https://api.github.com/rate_limit").json()
    rate_remaining = response["rate"]["remaining"]
    rate_used = response["rate"]["used"]
    reset_time = datetime.fromtimestamp(response["rate"]["reset"])

    print(
        f"\n{BRIGHT_YELLOW}[!]{RESET} Github API Remaining Rates: {BRIGHT_YELLOW}{rate_remaining}{RESET}"
    )
    print(
        f"{BRIGHT_YELLOW}[!]{RESET} Github API Used Rates: {BRIGHT_YELLOW}{rate_used}{RESET}"
    )
    print(f"{BRIGHT_YELLOW}[!]{RESET} Reset: {BRIGHT_YELLOW}{str(reset_time)}{RESET}")


def validate_url(url: str):
    """check if the provided url is Github url"""
    segments = urlsplit(url)

    if segments.netloc not in ("github.com"):
        raise ValueError(f"{url} is not a valid Github URL!")

    if segments.scheme not in ("https", "http"):
        raise ValueError("URL must start with http:// or https://")


def validate_branch(owner: str, repo: str, branch: str) -> bool:
    """verify the existence of the branch if provided as an argument."""

    branch_url = f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}"

    res = httpx.get(branch_url)
    if res.status_code != 200:
        return False

    return True


def parse_repo_url(repo_url: str, branch: str | None = None) -> dict[str, Any]:
    """retrieve provided URL information"""
    info = {}

    validate_url(repo_url)

    url = urlsplit(repo_url)
    path = url.path.strip("/").split("/")

    # if extra / slash is present in the url then
    # it might create a empty string in path so strip them
    # and create a new list
    path_segments = [item for item in path if item.strip()]

    # check the validity of url
    if len(path_segments) < 2:
        match url.netloc:
            case "github.com":
                raise ValueError(
                    "Invalid URL: https://github.com/owner/repository is expected."
                )
            case "gist.github.com":
                raise ValueError(
                    "Invalid URL: https://gist.github.com/owner/gistid is expected."
                )

    info["owner"] = path_segments[0]
    info["repository"] = path_segments[1]
    info["branch"] = None
    info["path"] = None

    if len(path_segments) > 2:
        # find branch in url
        if ("blob" not in path_segments) ^ ("tree" not in path_segments):
            # NOTE: IN SOME CASES BRANCH NAME MAY LOOK LIKE PATH SUCH AS feat/something
            # SO TO IDENTIFY RIGHT BRANCH, CONSTRUCT AND VALIDATE BRANCH BY ITERATING
            # OVER PATH
            for i in range(1, len(path_segments)):
                branch_name = "/".join(path_segments[3:][:i])
                if validate_branch(info["owner"], info["repository"], branch_name):
                    info["branch"] = branch_name
                    # rest of the path after branch
                    info["path"] = "/".join(path_segments[3:][i:])
                    break
        else:
            raise ValueError(f"Invalid URL: {repo_url} is not a valid URL.")

    # replace the found branch with explicitly provided branch after path is sorted
    if branch:
        if not validate_branch(info["owner"], info["repository"], branch):
            raise BranchNotFoundError(branch, info["repository"])
        info["branch"] = branch

    return info


def parse_gist_url(url: str) -> str:
    validate_url(url)
    gist_segments = urlsplit(url)
    gist_id = gist_segments.path.strip().split("/")[-1]

    return gist_id
