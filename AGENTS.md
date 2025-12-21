# Repository Guidelines

## Project Structure & Module Organization
- Site configuration lives in `_config.yml`; global data is in `_data/` (YAML/JSON used by layouts).
- Layout and rendering live in `_layouts/` and `_includes/`; styles are in `_sass/`; static assets are under `assets/`.
- Content collections are in `_pages/`, `_posts/`, `_news/`, `_projects/`, and `_bibliography/`.
- Automation and tooling: `bin/` has local Docker helpers; `.github/scripts/` holds automation scripts; `.github/workflows/` contains CI workflows.

## Build, Test, and Development Commands
- `bundle install` installs Ruby dependencies for the Jekyll site.
- `bundle exec jekyll serve` runs the site locally with live reload (default at `http://localhost:4000`).
- `bundle exec jekyll build` builds the static site into `_site/` for deployment.
- `./bin/docker_build_image.sh` builds the Docker image for local use.
- `./bin/docker_run.sh` serves the site in Docker on `http://localhost:8080`.
- `python .github/scripts/arxiv_updater.py` runs the arXiv updater (requires `OPENAI_API_KEY`).

## Coding Style & Naming Conventions
- Use 2-space indentation in YAML and SCSS; keep Markdown front matter tidy and aligned with existing keys.
- Name posts and news with date prefixes: `YYYY-MM-DD-title-slug.md` (see `_posts/` and `_news/`).
- Prefer lowercase, hyphenated slugs for filenames and URLs.
- Keep content edits scoped to the relevant collection folder and avoid touching generated assets.

## Testing Guidelines
- There is no formal unit test suite; validate changes by running `bundle exec jekyll serve` and browsing key pages.
- For build verification, use `bundle exec jekyll build` to ensure `_site/` renders cleanly.
- If modifying the arXiv updater, run the script locally and confirm the workflow logic still matches `.github/workflows/arxiv-updater-test.yml`.

## Commit & Pull Request Guidelines
- Recent history favors short, imperative, sentence-case messages (e.g., “Add news item…”, “Improve arXiv updater…”); include issue numbers when relevant.
- For features or bugs, open or reference a GitHub issue first, and mention it in the PR per `CONTRIBUTING.md`.
- PRs should include a concise summary, how you tested (command or manual check), and screenshots for visual/layout changes.
