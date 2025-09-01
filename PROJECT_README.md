# GitHub Metrics Generator

A self-contained Python script that generates beautiful GitHub contribution metrics using the GitHub GraphQL API. This tool creates a comprehensive Markdown report showcasing your notable contributions and programming language usage.

## ✨ Features

- 📊 **All-time contributions**: Fetches your complete GitHub history, not just the last year
- 🏆 **Notable repositories**: Lists top repositories you've contributed to, sorted by stars and forks
- 📈 **Language statistics**: Interactive pie chart showing your top 10 programming languages
- 🎨 **Professional presentation**: Repository avatars and human-readable formatting
- 🚫 **Language filtering**: Exclude specific languages (e.g., Jupyter Notebook) from statistics
- 📝 **Dynamic headers**: Use custom header files to personalize your report
- 🔗 **Repository descriptions**: Includes actual GitHub "About" text for each project

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- GitHub Personal Access Token with `repo` and `read:user` scopes

### Setup

1. **Clone or download** the `github_metrics.py` script
2. **Get a GitHub token**:
   - Go to [GitHub Settings > Tokens](https://github.com/settings/tokens)
   - Create a new token with `repo` and `read:user` permissions
3. **Set environment variables**:
   ```bash
   export GITHUB_TOKEN=your_token_here
   export GITHUB_USERNAME=your_username  # Optional, defaults to "JGalego"
   ```

### Usage

```bash
python3 github_metrics.py
```

The script will generate `github-contributions.md` with your metrics.

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_TOKEN` | GitHub Personal Access Token | *Required* |
| `GITHUB_USERNAME` | Your GitHub username | `"JGalego"` |
| `HEADER_FILE` | Custom header file to use | `"header.md"` |

### Language Exclusions

Edit the `EXCLUDED_LANGUAGES` list in the script:

```python
EXCLUDED_LANGUAGES = ["Jupyter Notebook", "HTML", "CSS"]
```

### Header Files

The script looks for header files in this order:
1. Custom file specified by `HEADER_FILE` environment variable
2. `header.md` (default)
3. `README.md` (fallback)
4. Default header (if no files found)

## 📋 Example Usage

### Basic Usage
```bash
python3 github_metrics.py
```

### With Custom Header
```bash
export HEADER_FILE=my_intro.md
python3 github_metrics.py
```

### Different User
```bash
export GITHUB_USERNAME=octocat
python3 github_metrics.py
```

## 📊 Output Format

The generated markdown includes:

1. **Dynamic Header**: Content from your header file
2. **Notable Contributions**: Top repositories with:
   - Repository avatars
   - Owner and project name
   - Star and fork counts (human-readable format)
   - Project descriptions
3. **Language Statistics**: 
   - Interactive pie chart (SVG)
   - Percentage breakdown
   - Color-coded legend
4. **All-time Stats**: Total commits, PRs, issues, and repositories

## 🎨 Customization

### Header File Example (`header.md`)
```markdown
# 👋 Hello, I'm John Doe

I'm a passionate developer working on AI/ML projects and open-source contributions.

![My Avatar](https://github.com/johndoe.png?size=100)
```

### Styling
The script generates clean, GitHub-flavored Markdown with:
- Repository avatars (20x20px)
- Human-readable numbers (e.g., "114K" instead of "114,592")
- Responsive SVG pie charts
- Professional color schemes

## 🔧 Technical Details

### API Limitations
- GitHub GraphQL API limits contribution queries to 1 year
- The script automatically chunks requests by year to get all-time data
- Maximum 100 repositories per query (GitHub limitation)

### Performance
- Fetches ~11 years of data with 12 API calls
- Each call respects GitHub's rate limits
- Progress indicators show fetching status

### Dependencies
- `requests`: HTTP client for API calls
- `collections.Counter`: Language statistics aggregation
- `math`: Pie chart calculations
- `datetime`: Date range handling

## 🐛 Troubleshooting

### Common Issues

**"GITHUB_TOKEN environment variable is required"**
- Set your GitHub token: `export GITHUB_TOKEN=ghp_xxxxxxxxxxxx`

**"GraphQL errors: [...] must not exceed 1 year"**
- This is handled automatically by the script's chunking logic

**Empty language statistics**
- Check if `EXCLUDED_LANGUAGES` is filtering out all languages
- Verify you have repositories with language data

**No repositories found**
- Ensure your token has proper permissions (`repo`, `read:user`)
- Check that your username is correct

### Debug Mode
Add debug prints to see API responses:
```python
print(result)  # Add after API calls
```

## 📜 License

MIT License - feel free to use and modify for your needs.

## 🤝 Contributing

This is a simple, self-contained script. Feel free to:
- Fork and modify for your needs
- Submit issues for bugs
- Suggest improvements

## 📧 Support

## 🤖 CI/CD Integration

### GitHub Actions Workflow

The repository includes a GitHub Actions workflow (`.github/workflows/metrics.yml`) that automatically:

1. **Runs daily at midnight UTC** to keep your metrics fresh
2. **Triggers on manual dispatch** when you want to update immediately  
3. **Runs when the script or header changes** to reflect updates

#### Setup Instructions

1. **Ensure GITHUB_TOKEN is available**: The workflow uses `secrets.GITHUB_TOKEN` automatically
2. **Configure repository permissions**: Go to Settings → Actions → General → Workflow permissions → "Read and write permissions"
3. **Trigger manually**: Actions tab → "Generate GitHub Metrics" → "Run workflow"

#### Workflow Features

- ✅ **Zero configuration required** - works out of the box
- ✅ **Smart commits** - only commits when README actually changes
- ✅ **Skip CI loops** - uses `[skip ci]` to prevent infinite loops
- ✅ **Automatic username detection** - uses `github.repository_owner`
- ✅ **Dependency management** - installs `requests` automatically

#### Workflow Triggers

```yaml
# Daily automatic updates
schedule: 
  - cron: "0 0 * * *"

# Manual trigger
workflow_dispatch:

# On script changes
push:
  paths: 
    - "github_metrics.py"
    - "header.md"
    - ".github/workflows/metrics.yml"
```

### For Other CI Systems

The script works with any CI system that supports:
- Python 3.8+
- Environment variables
- Git operations

Required environment variables:
- `GITHUB_TOKEN`: GitHub personal access token
- `USERNAME`: GitHub username (optional, auto-detected in GitHub Actions)

If you encounter issues:
1. Check the troubleshooting section
2. Verify your GitHub token permissions
3. Ensure Python 3.8+ is installed
4. Check GitHub API status at [status.github.com](https://status.github.com)

---

**Generated with ❤️ for the GitHub community**
