# How to publish the site with GitHub Pages

This guide takes the pack from this folder to a GitHub Pages site that rebuilds itself every
Monday. The workflow collects the data in the job and ships it inside the Pages artifact, so
no commit data is ever committed.

GitHub settings and action versions below were read from GitHub's documentation and release
pages on 5 November 2026.

## Before you start

- A GitHub organisation whose repositories you can read, and the right to create a repository
  in it and to create a GitHub App or a fine-grained personal access token for it.
- The pack checked locally once with the [quick start](../../README.md#quick-start-see-your-organisation-locally),
  so that you know which `--highlight` rule you want.

## 1. Create the publishing repository

1. Create a new repository in the organisation, for example `commit-history`. Make it
   **private** unless you want the author names and emails in the data to be public.
2. Copy everything in `github-commit-history/` into it except `.venv/` and `site/data/`, and
   commit. The workflow file must end up at `.github/workflows/commit-history.yml` in the
   repository root.
3. Make the community files yours. `CODE_OF_CONDUCT.md` and `SECURITY.md` say to write to a
   maintainer or an organisation owner; replace that with your own channel if you have one.
   Under **Settings → Code security**, enable **Private vulnerability reporting** so that the
   **Report a vulnerability** button the security policy refers to exists. Leave the
   attribution of the visual to Nadieh Bremer, the third-party notices and the `references`
   entry in `CITATION.cff` as they are: they are the original author's credit, and the MPL-2.0
   requires the notices.
4. Give the repository a description, and after the first deploy its website (the Pages URL)
   and a few topics. **Insights → Community Standards** then shows every item of GitHub's
   checklist as added; `gh api repos/OWNER/REPO/community/profile` reports the same as
   `health_percentage`. The pilot repository reached 100 on 5 November 2026 once `LICENSE`
   held the plain MIT text (GitHub detects a licence only from an unmodified text).

## 2. Choose how the workflow authenticates

Pick the first option that fits. The workflow tries them in this order.

**A GitHub App** (private repositories, membership rules):

1. In the organisation settings, create a GitHub App with no webhook and these permissions:
   repository **Contents: Read-only**, which GitHub's permissions reference lists for the
   commits endpoints, and, if you want `--highlight outside` or `members`, organisation
   **Members: Read-only**, which it lists for the members endpoint (both read on
   5 November 2026 at
   <https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps>).
2. Install the App on the organisation for **All repositories**. A selection of repositories
   would leave the others out of the site.
3. Generate a private key. In the publishing repository add the variable
   `COMMIT_HISTORY_APP_ID` (the App ID) and the secret `COMMIT_HISTORY_APP_PRIVATE_KEY`
   (the whole `.pem` file).

**A fine-grained personal access token** (quick, tied to one person): create one with the same
read permissions on the organisation's repositories and store it in the secret
`COMMIT_HISTORY_TOKEN`.

**Nothing**: the workflow's own `GITHUB_TOKEN` reads the organisation's public repositories
only and cannot list members, so keep `highlight` at `bots` or `none`.

## 3. Turn on Pages for workflow deployments

In the publishing repository open **Settings → Pages**. Under **Build and deployment**, under
**Source**, select **GitHub Actions**. Nothing else is needed; the workflow creates the
`github-pages` environment on its first run.

Decide who may see the site before that run, because the data holds author names and emails.
GitHub's documentation, read on 5 November 2026, says: "To publish a GitHub Pages site
privately, your organization must use GitHub Enterprise Cloud", and "A privately published
site can only be accessed by people with read access to the repository the site is published
from." On Enterprise Cloud without Enterprise Managed Users, set this on the same page:
"Under "GitHub Pages", select the **GitHub Pages visibility** dropdown menu, then select a
visibility." On any other plan, treat the site as readable by anyone who has its address.

## 4. Run the workflow once by hand

1. Open **Actions → Commit history site → Run workflow**.
2. Leave `organisation` empty to read the repository's owner (an organisation or a personal
   account), or enter another login the token can read. Choose `highlight` and, if you want,
   a `since` date. Leave `redact_emails` ticked unless the site is private to people who may
   see author emails; scheduled runs always redact.
3. Start it. The `build` job prints one line per repository; the `deploy` job prints the page
   URL in its summary.

## 5. Check that it worked

- Open the page URL. The heading reads "Commit history of *your organisation*" and the
  **REPOSITORIES IN** table lists every repository the token could read with status `ok`.
- A yellow annotation "Some repositories could not be read" on the run means the collector
  exited with status 1: open the table, the failing rows show the GraphQL error. Usually the
  token lacks access to those repositories.
- A red "The collector could not run" means status 2: the token was missing or rejected, or the
  organisation name is wrong.

## If the organisation is not on github.com

The workflow passes the server URL of the runner's own GitHub instance as `--host`, so on
GitHub Enterprise Server or GHE.com the same workflow works when the publishing repository
lives on that instance. For an organisation on another instance run the collector from a
machine with network access to both and publish by another route.

## Keeping it running

- The schedule is `17 6 * * 1` (Mondays, 06:17 UTC); edit the cron line to change it.
- In a public repository, GitHub disables scheduled workflows after 60 days without repository
  activity; running the workflow by hand re-enables it.
- Every action is pinned to the full commit SHA of a release, with the version in a comment
  beside it, because organisation policies that require SHA pinning otherwise refuse the run
  (the pilot organisation's did). `.github/dependabot.yml` asks Dependabot to update the pins
  weekly; merge those pull requests to pick up new releases.
- Large organisations: the collector spends about one GraphQL point and 3 to 4 seconds per
  100 commits, plus one point per repository (mozilla/pdf.js, 24,401 commits, took 14 minutes
  and 273 points on 5 November 2026). It pauses when fewer than 50 points remain in the hourly
  budget of 5,000 points (10,000 for an App installed on a GitHub Enterprise Cloud
  organisation). An organisation with a few hundred thousand commits therefore needs an hour or
  more and more than one budget window; split the run with `--since` or raise the job's
  `timeout-minutes`.
