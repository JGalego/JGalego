# pylint: disable=too-many-locals,too-many-statements
"""
GitHub Metrics Generator

A self-contained Python script that generates beautiful GitHub contribution metrics
using the GitHub GraphQL API.
"""

# Standard imports
import os
import datetime

from collections import Counter

# Library imports
import requests

GITHUB_API_URL = "https://api.github.com/graphql"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
USERNAME = os.getenv("USERNAME", "JGalego")  # Use env var if available, fallback to JGalego
HEADER_FILE = os.getenv("HEADER_FILE", "header.md")  # Default to header.md, can be overridden
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "README.md")  # Default to README.md, can be overridden

# Languages to exclude from the pie chart
EXCLUDED_LANGUAGES = ["Jupyter Notebook"]  # Add languages you want to exclude

HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

def get_repo_avatar(owner):
    """Get the avatar URL for a repository owner"""
    return f"https://github.com/{owner}.png?size=20"

def format_number(num):
    """Format numbers in a human-readable way"""
    if num >= 1000000:
        return f"{num//1000000}M"
    if num >= 1000:
        return f"{num//1000}k"
    return str(num)

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
    """Get notable repos (by stars/forks)"""
    # Sort by stars, forks, and your contribution count
    notable = sorted(repos, key=lambda r: (r["repository"]["stargazerCount"],
                                          r["repository"]["forkCount"],
                                          r["contributions"]["totalCount"]), reverse=True)
    return notable[:10]

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


def create_language_visualization(data):
    """Create language visualization as a clean list with logos"""
    # Language color mapping (GitHub language colors)
    language_colors = {
        'Python': '#3572A5',
        'JavaScript': '#f1e05a',
        'TypeScript': '#2b7489',
        'Java': '#b07219',
        'C++': '#f34b7d',
        'C#': '#239120',
        'C': '#555555',
        'HTML': '#e34c26',
        'CSS': '#1572B4',
        'SCSS': '#c6538c',
        'Shell': '#89e051',
        'Rust': '#dea584',
        'Go': '#00ADD8',
        'PHP': '#4F5D95',
        'Ruby': '#701516',
        'Swift': '#ffac45',
        'Kotlin': '#F18E33',
        'Scala': '#c22d40',
        'Prolog': '#74283c',
        'Common Lisp': '#3fb68b',
        'Just': '#384d54'
    }

    lines = []
    for lang, percent in data:
        color = language_colors.get(lang, '#586069')  # Default gray color
        logo = f"<span style='color:{color}'>●</span>"
        lines.append(f"{logo} {lang} {percent}%")

    return "\n".join(lines)


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

        if not repos:
            print("No repositories found with contributions.")
            return

        notable = get_notable_repos(repos)

        # Markdown output
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            # Add header content
            header_content = read_header()
            f.write(f"{header_content}\n\n")

            # Notable Contributions section
            f.write("## 🚀 Notable Contributions\n\n")

            for repo in notable:
                r = repo["repository"]
                avatar_url = get_repo_avatar(r['owner']['login'])
                stars = format_number(r['stargazerCount'])
                forks = format_number(r['forkCount'])
                description = r.get('description', 'No description available')
                if description is None:
                    description = 'No description available'

                # Get primary language from languages array (largest by size)
                primary_lang = "Unknown"
                if r.get('languages') and r['languages'].get('edges'):
                    languages = r['languages']['edges']
                    if languages:
                        # Sort by size and get the largest one
                        largest_lang = max(languages, key=lambda x: x['size'])
                        primary_lang = largest_lang['node']['name']

                f.write(f"### <img src='{avatar_url}' width='20' height='20' "
                        f"style='vertical-align:middle;'/> "
                        f"[@{r['owner']['login']}/{r['name']}]({r['url']})\n")
                f.write(f"⭐ {stars} • 🍴 {forks} • {primary_lang}\n\n")
                f.write(f"{description}\n\n")

            # Personal Projects section
            f.write("## 🏗️ Personal Projects\n\n")

            for repo in own_repos[:10]:  # Show top 10 own repos
                avatar_url = get_repo_avatar(USERNAME)
                stars = format_number(repo['stargazerCount'])
                forks = format_number(repo['forkCount'])
                description = repo.get('description', 'No description available')
                if description is None:
                    description = 'No description available'

                # Get primary language with color
                primary_lang = ""
                if repo.get('primaryLanguage'):
                    lang_name = repo['primaryLanguage']['name']
                    primary_lang = f" • {lang_name}"

                f.write(f"#### <img src='{avatar_url}' width='20' height='20' "
                        f"style='vertical-align:middle;'/> "
                        f"[@{USERNAME}/{repo['name']}]({repo['url']})\n")
                f.write(f"⭐ {stars} • 🍴 {forks}{primary_lang}\n\n")
                f.write(f"{description}\n\n")

        print(f"✅ Generated {OUTPUT_FILE} successfully!")

    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"❌ Error: {e}")
        print("Check your token permissions and network connection.")


if __name__ == "__main__":
    main()
