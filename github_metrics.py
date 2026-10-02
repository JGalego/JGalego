# pylint: disable=too-many-locals,too-many-statements
"""
GitHub Metrics Generator

A self-contained Python script that generates beautiful GitHub contribution metrics
using the GitHub GraphQL API.
"""

# Standard imports
import os
import datetime
import re
import textwrap

from collections import Counter

# Library imports
import requests

GITHUB_API_URL = "https://api.github.com/graphql"
HUGGING_FACE_API_URL = "https://huggingface.co/api"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
USERNAME = os.getenv("USERNAME", "JGalego")  # Use env var if available, fallback to JGalego
HF_USERNAME = os.getenv("HF_USERNAME", USERNAME.lower())
HEADER_FILE = os.getenv("HEADER_FILE", "header.md")  # Default to header.md, can be overridden
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "README.md")  # Default to README.md, can be overridden
GITHUB_ITEM_LIMIT = 6

# Languages to exclude from the pie chart
EXCLUDED_LANGUAGES = ["Jupyter Notebook"]  # Add languages you want to exclude

HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

def read_header():
    """Read header file content to use as header"""
    # Priority order: custom HEADER_FILE -> header.md -> README.md -> default
    files_to_try = ([HEADER_FILE, "header.md", "README.md"]
                    if HEADER_FILE != "header.md"
                    else ["header.md", "README.md"])

    for filename in files_to_try:
        try:
            with open(filename, "r", encoding="utf-8") as f:
                content = f.read().strip()
            print(f"Using header from {filename}")
            return content
        except FileNotFoundError:
            continue
        except (IOError, OSError) as e:
            print(f"Warning: Could not read {filename}: {e}")
            continue

    # Default fallback
    print("No header file found, using default header")
    return "# GitHub Profile\n\nWelcome to my GitHub profile!"

# Languages to exclude from the pie chart
EXCLUDED_LANGUAGES = ["Jupyter Notebook"]  # Add languages you want to exclude

HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

def fetch_repos_and_contributions():
    """Fetch repositories and contributions data from GitHub API"""
    # First get user creation date
    user_query = '''
    query($login: String!) {
      user(login: $login) {
        createdAt
      }
    }
    '''
    variables = {"login": USERNAME}
    user_resp = requests.post(GITHUB_API_URL,
                              json={"query": user_query, "variables": variables},
                              headers=HEADERS, timeout=30)
    user_resp.raise_for_status()
    user_data = user_resp.json()

    if "errors" in user_data:
        raise ValueError(f"GraphQL errors: {user_data['errors']}")

    created_at = datetime.datetime.fromisoformat(
        user_data["data"]["user"]["createdAt"].replace('Z', '+00:00'))
    now = datetime.datetime.now(datetime.timezone.utc)

    # Split into yearly chunks to respect GitHub's 1-year limit
    all_repos = {}
    total_stats = {
        'totalCommitContributions': 0,
        'totalPullRequestContributions': 0,
        'totalIssueContributions': 0,
        'totalRepositoriesWithContributedCommits': 0
    }

    current_date = created_at
    while current_date < now:
        end_date = min(current_date + datetime.timedelta(days=365), now)

        # Query for this year chunk
        query = '''
        query($login: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $login) {
            contributionsCollection(from: $from, to: $to) {
              totalCommitContributions
              totalPullRequestContributions
              totalIssueContributions
              totalRepositoriesWithContributedCommits
              commitContributionsByRepository(maxRepositories: 100) {
                repository {
                  name
                  url
                  description
                  stargazerCount
                  forkCount
                  owner { login }
                  languages(first: 10) {
                    edges {
                      size
                      node {
                        name
                        color
                      }
                    }
                  }
                }
                contributions {
                  totalCount
                }
              }
            }
          }
        }
        '''

        from_date = current_date.isoformat()
        to_date = end_date.isoformat()
        variables = {"login": USERNAME, "from": from_date, "to": to_date}

        print(f"Fetching contributions from {from_date[:10]} to {to_date[:10]}...")

        response = requests.post(GITHUB_API_URL,
                                 json={"query": query, "variables": variables},
                                 headers=HEADERS, timeout=30)
        response.raise_for_status()
        result = response.json()

        if "errors" in result:
            raise ValueError(f"GraphQL errors: {result['errors']}")

        contribs = result["data"]["user"]["contributionsCollection"]

        # Aggregate stats
        total_stats['totalCommitContributions'] += contribs['totalCommitContributions']
        total_stats['totalPullRequestContributions'] += contribs['totalPullRequestContributions']
        total_stats['totalIssueContributions'] += contribs['totalIssueContributions']
        # Note: totalRepositoriesWithContributedCommits is not additive,
        # we'll calculate unique repos later

        # Aggregate repos
        for repo_contrib in contribs['commitContributionsByRepository']:
            repo_key = repo_contrib['repository']['url']
            if repo_key in all_repos:
                all_repos[repo_key]['contributions']['totalCount'] += \
                    repo_contrib['contributions']['totalCount']
            else:
                all_repos[repo_key] = repo_contrib

        current_date = end_date

    # Count unique repositories
    total_stats['totalRepositoriesWithContributedCommits'] = len(all_repos)

    # Convert back to list format
    repos_list = list(all_repos.values())

    return {
        'contributionsCollection': {
            **total_stats,
            'commitContributionsByRepository': repos_list
        }
    }

def get_notable_repos(repos):
    """Get every contributed repository with more than 1,000 stars."""
    notable = [repo for repo in repos
               if repo["repository"]["stargazerCount"] > 1000]
    return sorted(notable, key=lambda r: (r["repository"]["stargazerCount"],
                                          r["repository"]["forkCount"],
                                          r["contributions"]["totalCount"]), reverse=True)


def fetch_hugging_face_items(resource):
    """Fetch public models or Spaces owned by the configured Hugging Face user."""
    response = requests.get(
        f"{HUGGING_FACE_API_URL}/{resource}",
        params={"author": HF_USERNAME, "limit": 100, "full": "true"},
        timeout=30,
    )
    response.raise_for_status()
    items = response.json()
    if not isinstance(items, list):
        raise ValueError(f"Unexpected Hugging Face {resource} response")
    return items


def fetch_hugging_face_portfolio():
    """Fetch the user's public Hugging Face resources and collections."""
    models = fetch_hugging_face_items("models")
    spaces = fetch_hugging_face_items("spaces")
    collections = fetch_hugging_face_collections()
    for model in models:
        model["description"] = fetch_model_description(model["id"])
    models.sort(key=lambda item: item.get("lastModified", ""), reverse=True)
    spaces.sort(key=lambda item: item.get("lastModified", ""), reverse=True)
    return models, spaces, collections


def fetch_hugging_face_collections():
    """Fetch public collections and hydrate their current memberships."""
    response = requests.get(
        f"{HUGGING_FACE_API_URL}/collections",
        params={"owner": HF_USERNAME, "limit": 100},
        timeout=30,
    )
    response.raise_for_status()
    collections = response.json()
    if not isinstance(collections, list):
        raise ValueError("Unexpected Hugging Face collections response")

    hydrated_collections = []
    for collection in collections:
        slug = collection.get("slug")
        if not slug:
            continue
        detail_response = requests.get(
            f"{HUGGING_FACE_API_URL}/collections/{slug}",
            timeout=30,
        )
        detail_response.raise_for_status()
        detail = detail_response.json()
        if not isinstance(detail, dict):
            raise ValueError(f"Unexpected Hugging Face collection response: {slug}")
        hydrated_collections.append(detail)

    return hydrated_collections


def fetch_model_description(model_id):
    """Extract the first prose paragraph from a model card."""
    try:
        response = requests.get(
            f"https://huggingface.co/{model_id}/raw/main/README.md",
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException:
        return "No description available."

    markdown = response.text
    if markdown.startswith("---"):
        parts = markdown.split("---", 2)
        if len(parts) == 3:
            markdown = parts[2]

    paragraph = []
    in_code_block = False
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        if not line:
            if paragraph:
                break
            continue
        if line.startswith(("#", "![", "[![", "<", "|", "-", "* ", ">")):
            continue
        paragraph.append(line)

    return " ".join(paragraph) or "No description available."


def format_hugging_face_tags(item):
    """Format a small set of meaningful Hugging Face tags."""
    excluded_tags = {
        "endpoints_compatible",
        "model-index",
        "text-generation-inference",
    }
    excluded_prefixes = ("base_model:", "dataset:", "license:", "region:")
    tags = []
    for tag in item.get("tags", []):
        if tag in excluded_tags or tag.startswith(excluded_prefixes):
            continue
        tags.append(f"`{tag}`")
        if len(tags) == 5:
            break
    return " ".join(tags) or "-"


def format_hugging_face_description(value):
    """Normalize a Hugging Face description for a Markdown table cell."""
    text = " ".join(str(value or "No description available.").split())
    text = re.sub(r"\[([^]]+)]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("`", "").replace("*", "")
    text = textwrap.shorten(text, width=180, placeholder="...")
    return text.replace("|", "\\|")


def write_hugging_face_item(output, item, item_type):
    """Write one model or Space row in a collection table."""
    item_id = item["id"]
    name = item_id.rsplit("/", maxsplit=1)[-1]
    tags = format_hugging_face_tags(item)
    if item_type == "model":
        url = f"https://huggingface.co/{item_id}"
        description = item.get("description")
        label = "Model"
    else:
        url = f"https://huggingface.co/spaces/{item_id}"
        card_data = item.get("cardData") or {}
        description = card_data.get("short_description")
        label = "Space"

    output.write(
        f"| [{name}]({url}) | {label} | {tags} | "
        f"{format_hugging_face_description(description)} |\n"
    )


def write_hugging_face_collection(output, collection, resources):
    """Write one collection description and its resource table."""
    slug = collection.get("slug")
    title = collection.get("title") or "Untitled collection"
    description = format_hugging_face_description(collection.get("description"))
    if slug:
        output.write(f"### [{title}](https://huggingface.co/collections/{slug})\n\n")
    else:
        output.write(f"### {title}\n\n")
    output.write(f"{description}\n\n")
    output.write("| Item | Type | Tags | Description |\n")
    output.write("|---|---|---|---|\n")
    for item, item_type in resources:
        write_hugging_face_item(output, item, item_type)
    output.write("\n")


def write_hugging_face_section(output, models, spaces, collections):
    """Write models and Spaces grouped by their Hugging Face collections."""
    output.write("## 🤗 Models & Spaces\n\n")
    resources_by_id = {
        **{model["id"]: (model, "model") for model in models},
        **{space["id"]: (space, "space") for space in spaces},
    }
    collected_ids = set()
    collection_groups = []

    for collection in collections:
        resources = []
        for collection_item in collection.get("items", []):
            item_id = collection_item.get("id")
            resource = resources_by_id.get(item_id)
            if resource is None:
                continue
            resources.append(resource)
            collected_ids.add(item_id)
        if resources:
            collection_groups.append((collection, resources))

    legacy_groups = []
    for collection, resources in collection_groups:
        if (collection.get("title") or "").casefold() == "legacy":
            legacy_groups.append((collection, resources))
        else:
            write_hugging_face_collection(output, collection, resources)

    uncollected = [resource for item_id, resource in resources_by_id.items()
                   if item_id not in collected_ids]
    if uncollected:
        write_hugging_face_collection(
            output,
            {
                "title": "Uncollected",
                "description": (
                    "Models and Spaces that have not been added to a collection yet."
                ),
            },
            uncollected,
        )

    for collection, resources in legacy_groups:
        write_hugging_face_collection(output, collection, resources)

    output.write(
        f"> 🧪 More experiments live on Hugging Face: browse all my "
        f"[models](https://huggingface.co/{HF_USERNAME}/models) and try the "
        f"full collection of [Spaces]"
        f"(https://huggingface.co/{HF_USERNAME}/spaces).\n\n"
    )

# Fetch user's own repositories
def fetch_own_repositories():
    """Fetch repositories owned by the user"""
    query = '''
    query($login: String!) {
      user(login: $login) {
        repositories(first: 20, ownerAffiliations: OWNER, isFork: false,
                     orderBy: {field: STARGAZERS, direction: DESC}) {
          nodes {
            name
            url
            description
            stargazerCount
            forkCount
            primaryLanguage {
              name
              color
            }
            languages(first: 5) {
              edges {
                size
                node {
                  name
                  color
                }
              }
            }
          }
        }
      }
    }
    '''
    variables = {"login": USERNAME}
    response = requests.post(GITHUB_API_URL,
                             json={"query": query, "variables": variables},
                             headers=HEADERS, timeout=30)
    response.raise_for_status()
    result = response.json()

    if "errors" in result:
        raise ValueError(f"GraphQL errors: {result['errors']}")

    return result["data"]["user"]["repositories"]["nodes"]

def get_language_stats(repos):
    """Aggregate language usage statistics"""
    lang_counter = Counter()
    for repo in repos:
        for lang in repo["repository"]["languages"]["edges"]:
            name = lang["node"]["name"]
            # Skip excluded languages
            if name in EXCLUDED_LANGUAGES:
                continue
            size = lang["size"]
            lang_counter[name] += size
    top_langs = lang_counter.most_common(10)
    total = sum(lang_counter.values())
    if total == 0:
        return [], {}
    # Convert to percentages
    top_langs_percent = [(name, round(value / total * 100, 2))
                         for name, value in top_langs]
    return top_langs_percent


# GitHub language colors, used for both the language pie chart and repo badges
LANGUAGE_COLORS = {
    'Python': '3572A5',
    'JavaScript': 'f1e05a',
    'TypeScript': '2b7489',
    'Java': 'b07219',
    'C++': 'f34b7d',
    'C#': '239120',
    'C': '555555',
    'HTML': 'e34c26',
    'CSS': '1572B4',
    'SCSS': 'c6538c',
    'Shell': '89e051',
    'Rust': 'dea584',
    'Go': '00ADD8',
    'PHP': '4F5D95',
    'Ruby': '701516',
    'Swift': 'ffac45',
    'Kotlin': 'F18E33',
    'Scala': 'c22d40',
    'Prolog': '74283c',
    'Common Lisp': '3fb68b',
    'Just': '384d54',
    'Jupyter Notebook': 'DA5B0B',
}


def create_language_visualization(data):
    """Create language visualization as a clean list with logos"""
    lines = []
    for lang, percent in data:
        color = f"#{LANGUAGE_COLORS.get(lang, '586069')}"  # Default gray color
        logo = f"<span style='color:{color}'>●</span>"
        lines.append(f"{logo} {lang} {percent}%")

    return "\n".join(lines)


def language_badge(lang):
    """Build a shields.io static badge for a language"""
    color = LANGUAGE_COLORS.get(lang, '586069')  # Default gray color
    label = lang.replace(' ', '%20').replace('-', '--')
    return f"![{lang}](https://img.shields.io/badge/-{label}-{color}?style=flat-square)"


def write_repo_entry(f, owner, name, url, description, lang):
    """Write a single repository as a compact badge-based list entry."""
    if description is None:
        description = 'No description available'
    description = description.replace("\n", " ")

    f.write(f"**[@{owner}/{name}]({url})** — {description}<br>\n")
    f.write(f"![Stars](https://img.shields.io/github/stars/{owner}/{name}"
            f"?style=flat-square&label=%E2%AD%90) "
            f"![Forks](https://img.shields.io/github/forks/{owner}/{name}"
            f"?style=flat-square&label=%F0%9F%8D%B4)")
    if lang:
        f.write(f" {language_badge(lang)}")
    f.write("\n\n")


def main():
    """Main function to generate GitHub metrics"""
    try:
        if not GITHUB_TOKEN:
            print("❌ Error: GITHUB_TOKEN environment variable is required")
            print("Get a token from: https://github.com/settings/tokens")
            print("For CI environments, ensure GITHUB_TOKEN is set in secrets")
            return

        if not USERNAME:
            print("❌ Error: USERNAME not set")
            print("Set USERNAME environment variable or update the script directly")
            return

        print(f"🔍 Generating metrics for user: {USERNAME}")
        user = fetch_repos_and_contributions()
        contribs = user["contributionsCollection"]
        repos = contribs["commitContributionsByRepository"]

        # Fetch own repositories
        print("Fetching your own repositories...")
        own_repos = fetch_own_repositories()

        print("Fetching your Hugging Face models and Spaces...")
        models, spaces, collections = fetch_hugging_face_portfolio()

        if not repos:
            print("No repositories found with contributions.")
            return

        notable = get_notable_repos(repos)

        # Markdown output
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            # Add header content
            header_content = read_header()
            f.write(f"{header_content}\n\n")

            write_hugging_face_section(f, models, spaces, collections)

            # Notable Contributions section (badge-based list)
            f.write("## 🚀 Notable Contributions\n\n")

            for repo in notable:
                r = repo["repository"]
                description = r.get('description')

                # Get primary language from languages array (largest by size)
                primary_lang = None
                if r.get('languages') and r['languages'].get('edges'):
                    languages = r['languages']['edges']
                    if languages:
                        # Sort by size and get the largest one
                        largest_lang = max(languages, key=lambda x: x['size'])
                        primary_lang = largest_lang['node']['name']

                write_repo_entry(f, r['owner']['login'], r['name'], r['url'],
                                  description, primary_lang)

            # Personal Projects section (badge-based list)
            f.write("## 🏗️ Personal Projects\n\n")

            for repo in own_repos[:GITHUB_ITEM_LIMIT]:
                description = repo.get('description')
                primary_lang = None
                if repo.get('primaryLanguage'):
                    primary_lang = repo['primaryLanguage']['name']

                write_repo_entry(f, USERNAME, repo['name'], repo['url'],
                                  description, primary_lang)

        print(f"✅ Generated {OUTPUT_FILE} successfully!")

    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"❌ Error: {e}")
        print("Check your token permissions and network connection.")


if __name__ == "__main__":
    main()
