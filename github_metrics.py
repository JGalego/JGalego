# pylint: disable=too-many-locals,too-many-statements
"""
GitHub Metrics Generator

A self-contained Python script that generates beautiful GitHub contribution metrics
using the GitHub GraphQL API.
"""

import os
import datetime
from collections import Counter
from math import pi, cos, sin
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
    lang_colors = {}
    for repo in repos:
        for lang in repo["repository"]["languages"]["edges"]:
            name = lang["node"]["name"]
            # Skip excluded languages
            if name in EXCLUDED_LANGUAGES:
                continue
            size = lang["size"]
            color = lang["node"].get("color", "#cccccc")
            lang_counter[name] += size
            lang_colors[name] = color
    top_langs = lang_counter.most_common(10)
    total = sum(lang_counter.values())
    if total == 0:
        return [], {}
    # Convert to percentages
    top_langs_percent = [(name, round(value / total * 100, 2))
                         for name, value in top_langs]
    return top_langs_percent, lang_colors


def pie_chart_svg(data, colors, size=200):
    """Generate SVG pie chart"""
    svg = [f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
           'xmlns="http://www.w3.org/2000/svg">']
    cx, cy, r = size // 2, size // 2, size // 2 - 10
    start_angle = 0
    angles = [v / 100 * 360 for _, v in data]  # v is already percent

    for i, (lang, percent) in enumerate(data):
        end_angle = start_angle + angles[i]
        x1 = cx + r * cos(pi * start_angle / 180)
        y1 = cy + r * sin(pi * start_angle / 180)
        x2 = cx + r * cos(pi * end_angle / 180)
        y2 = cy + r * sin(pi * end_angle / 180)
        large_arc = 1 if angles[i] > 180 else 0
        color = colors.get(lang, "#cccccc")
        path = f"M{cx},{cy} L{x1},{y1} A{r},{r} 0 {large_arc},1 {x2},{y2} Z"
        svg.append(f'<path d="{path}" fill="{color}" stroke="#fff" stroke-width="1"/>')

        # Add percentage label only if >= 5%
        if percent >= 5:
            mid_angle = start_angle + angles[i] / 2
            label_x = cx + (r - 30) * cos(pi * mid_angle / 180)
            label_y = cy + (r - 30) * sin(pi * mid_angle / 180)
            svg.append(f'<text x="{label_x:.1f}" y="{label_y:.1f}" '
                      f'font-size="12" text-anchor="middle" '
                      f'alignment-baseline="middle">{percent}%</text>')

        start_angle = end_angle

    svg.append('</svg>')
    return "\n".join(svg)


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
        top_langs, lang_colors = get_language_stats(repos)

        if not top_langs:
            print("No language data found.")
            return

        svg = pie_chart_svg(top_langs, lang_colors)

        # Markdown output
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            # Add header content
            header_content = read_header()
            f.write(f"{header_content}\n\n")

            # My Projects section
            f.write("## 🏗️ My Projects\n\n")

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
                    lang_color = repo['primaryLanguage']['color']
                    primary_lang = f" • <span style='color:{lang_color}'>●</span> {lang_name}"

                f.write(f"### <img src='{avatar_url}' width='20' height='20' "
                        f"style='vertical-align:middle;'/> "
                        f"[@{USERNAME}/{repo['name']}]({repo['url']})\n")
                f.write(f"⭐ {stars} • 🍴 {forks}{primary_lang}\n\n")
                f.write(f"{description}\n\n")

            f.write("## 🚀 Notable Contributions\n\n")

            for repo in notable:
                r = repo["repository"]
                avatar_url = get_repo_avatar(r['owner']['login'])
                stars = format_number(r['stargazerCount'])
                forks = format_number(r['forkCount'])
                description = r.get('description', 'No description available')
                if description is None:
                    description = 'No description available'

                f.write(f"### <img src='{avatar_url}' width='20' height='20' "
                        f"style='vertical-align:middle;'/> "
                        f"[@{r['owner']['login']}/{r['name']}]({r['url']})\n")
                f.write(f"⭐ {stars} • 🍴 {forks}\n\n")
                f.write(f"{description}\n\n")

            f.write("\n## 📊 Top 10 Languages\n\n")
            if EXCLUDED_LANGUAGES:
                excluded_str = ", ".join(EXCLUDED_LANGUAGES)
                f.write(f"*Excluding: {excluded_str}*\n\n")
            f.write(f'<div align="center">\n{svg}\n</div>\n')
            # Legend below chart
            f.write("\n<table align='center'>\n")
            f.write("<tr><th>🎨 Color</th><th>💻 Language</th><th>📈 Percent</th></tr>\n")
            for lang, percent in top_langs:
                color = lang_colors.get(lang, "#cccccc")
                f.write(f"<tr><td><span style='display:inline-block;width:16px;"
                        f"height:16px;background:{color};border-radius:3px;'></span></td>"
                        f"<td>{lang}</td><td>{percent}%</td></tr>\n")
            f.write("</table>\n")
            f.write("## 📈 All-Time Stats\n")
            c = contribs
            f.write(f"- **💻 Total Commits:** {c['totalCommitContributions']:,}\n")
            f.write(f"- **🔀 Total PRs:** {c['totalPullRequestContributions']:,}\n")
            f.write(f"- **🐛 Total Issues:** {c['totalIssueContributions']:,}\n")
            f.write(f"- **📚 Repos Contributed To:** "
                    f"{c['totalRepositoriesWithContributedCommits']:,}\n")

        print(f"✅ Generated {OUTPUT_FILE} successfully!")

    except (requests.RequestException, ValueError, KeyError) as e:
        print(f"❌ Error: {e}")
        print("Check your token permissions and network connection.")


if __name__ == "__main__":
    main()
