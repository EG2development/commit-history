/*
 * Page logic for the organisation commit-history site.
 *
 * Reads data/index.json, lets the visitor choose a repository (or the combined
 * all-repositories dataset), loads that dataset's commits.csv and optional
 * highlights.csv, and hands them to the unmodified ORCA visual
 * (createORCAVisual.js, MPL-2.0, Nadieh Bremer). Everything in this file is
 * part of this project, not of the visual.
 */
(function () {
    "use strict";

    const formatDigit = d3.format(",.0f");
    const parseGitDate = d3.timeParse("%Y-%m-%d %H:%M:%S %Z");
    const formatLongDate = d3.utcFormat("%B %-e, %Y");
    const formatShortDate = d3.utcFormat("%-e %b %Y");

    const byId = (id) => document.getElementById(id);
    const setText = (id, text) => { const el = byId(id); if (el) el.textContent = text; };
    const setAll = (selector, text) => document.querySelectorAll(selector).forEach((el) => { el.textContent = text; });
    const show = (id, visible) => { const el = byId(id); if (el) el.style.display = visible ? "" : "none"; };
    const shortDate = (iso) => (iso ? formatShortDate(new Date(iso)) : "–");

    const COLUMNS = [
        { key: "full_name", label: "Repository", numeric: false },
        { key: "commits", label: "Commits", numeric: true },
        { key: "contributors", label: "Contributors", numeric: true },
        { key: "first_commit", label: "First commit", numeric: false },
        { key: "last_commit", label: "Last commit", numeric: false },
        { key: "insertions", label: "Insertions", numeric: true },
        { key: "deletions", label: "Deletions", numeric: true },
        { key: "highlighted_commits", label: "Highlighted", numeric: true },
        { key: "status", label: "Status", numeric: false },
    ];

    /////////////////////////////////////////////////////////////////
    ////////////////////////// Start-up /////////////////////////////
    /////////////////////////////////////////////////////////////////

    async function main() {
        let index;
        try {
            const response = await fetch("data/index.json", { cache: "no-store" });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            index = await response.json();
        } catch (error) {
            showEmptyState(`data/index.json could not be loaded (${error.message}). Run the collector and publish the site again.`);
            return;
        }

        const datasets = availableDatasets(index);
        renderHeader(index);
        renderDataDetails(index);
        renderRepositoryTable(index);

        const selected = chooseDataset(datasets);
        if (!selected) {
            showEmptyState("The collector ran, but no repository produced any commits.");
            return;
        }
        renderPicker(datasets, selected);
        markCurrentRow(selected.slug);
        try {
            await drawDataset(index, selected);
        } catch (error) {
            showEmptyState(`The dataset for ${selected.full_name} could not be drawn (${error.message}).`);
        }
    }

    function showEmptyState(message) {
        setText("empty-state-message", message);
        byId("empty-state").hidden = false;
        show("loading", false);
        show("chart-container", false);
        show("search-box-outer", false);
        show("chart-extra", false);
        show("highlight-note", false);
    }

    /////////////////////////////////////////////////////////////////
    ///////////////////////// Dataset choice ////////////////////////
    /////////////////////////////////////////////////////////////////

    function availableDatasets(index) {
        const datasets = [];
        const title = index.title || index.organisation;
        if (index.combined && index.combined.slug) {
            datasets.push({
                slug: index.combined.slug,
                name: "all repositories",
                full_name: `${title} (all repositories)`,
                commits: index.combined.commits,
                combined: true,
            });
        }
        (index.repositories || [])
            .filter((repo) => repo.status === "ok" && repo.commits > 0)
            .forEach((repo) => datasets.push({ ...repo, combined: false }));
        return datasets;
    }

    function chooseDataset(datasets) {
        const wanted = new URLSearchParams(window.location.search).get("repo");
        if (wanted) {
            const hit = datasets.find((d) => d.slug === wanted || d.name === wanted || d.full_name === wanted);
            if (hit) return hit;
        }
        const combined = datasets.find((d) => d.combined);
        if (combined) return combined;
        return datasets.slice().sort((a, b) => b.commits - a.commits)[0] || null;
    }

    function navigateTo(slug) {
        const url = new URL(window.location.href);
        url.searchParams.set("repo", slug);
        window.location.href = url.toString();
    }

    function renderPicker(datasets, selected) {
        const select = byId("repo-select");
        datasets.forEach((dataset) => {
            const option = document.createElement("option");
            option.value = dataset.slug;
            option.textContent = dataset.combined
                ? `All repositories (${formatDigit(dataset.commits)} commits)`
                : `${dataset.name} (${formatDigit(dataset.commits)})`;
            option.selected = dataset.slug === selected.slug;
            select.appendChild(option);
        });
        select.addEventListener("change", () => navigateTo(select.value));
    }

    /////////////////////////////////////////////////////////////////
    //////////////////////// Static page text ///////////////////////
    /////////////////////////////////////////////////////////////////

    function renderHeader(index) {
        const title = index.title || index.organisation;
        setText("org-name", title);
        setAll(".org-name-text", title);
        document.title = `Commit history · ${title}`;
        if (index.highlight && index.highlight.label) {
            setText("highlight-label", index.highlight.label);
        } else {
            show("highlight-note", false);
            show("highlight-legend", false);
        }
    }

    function renderDataDetails(index) {
        const generated = index.generated_at ? formatLongDate(new Date(index.generated_at)) : "an unknown date";
        const totals = index.totals || {};
        const sourceText = index.source === "git log"
            ? `The data was read from local clones with git log on ${generated}.`
            : `The data was read from the GitHub GraphQL API on ${generated} for ${formatDigit(totals.repositories_ok || 0)} of ${formatDigit(totals.repositories || 0)} repositories` +
              (index.since ? `, counting commits made on or after ${index.since}.` : ".");
        setText("data-source-text", sourceText);
        setText("data-highlight-text", index.highlight && index.highlight.label
            ? `Hexagons mark commits by ${index.highlight.label}.`
            : "No contributors are highlighted in this dataset, so every commit is a circle.");
        setText("repositories-summary",
            `${formatDigit(totals.repositories_ok || 0)} repositories with ${formatDigit(totals.commits || 0)} commits` +
            (totals.repositories_failed ? `; ${totals.repositories_failed} could not be read.` : "."));
        const credit = byId("credit-repo-link");
        if (credit && index.site_repository) credit.href = index.site_repository;
    }

    /////////////////////////////////////////////////////////////////
    ///////////////////////// Repository table //////////////////////
    /////////////////////////////////////////////////////////////////

    function renderRepositoryTable(index) {
        const rows = index.repositories || [];
        const sort = { key: "commits", descending: true };
        const headRow = document.querySelector("#repo-table thead tr");
        const body = document.querySelector("#repo-table tbody");
        const filter = byId("repo-filter");

        COLUMNS.forEach((column) => {
            const th = document.createElement("th");
            th.textContent = column.label;
            th.dataset.key = column.key;
            th.scope = "col";
            th.addEventListener("click", () => {
                sort.descending = sort.key === column.key ? !sort.descending : column.numeric;
                sort.key = column.key;
                paint();
            });
            headRow.appendChild(th);
        });

        function compare(a, b) {
            const column = COLUMNS.find((c) => c.key === sort.key);
            let left = a[sort.key];
            let right = b[sort.key];
            if (column.numeric) { left = left || 0; right = right || 0; }
            else { left = (left || "").toString().toLowerCase(); right = (right || "").toString().toLowerCase(); }
            const order = left < right ? -1 : left > right ? 1 : 0;
            return sort.descending ? -order : order;
        }

        function paint() {
            headRow.querySelectorAll("th").forEach((th) => {
                th.classList.toggle("sorted-asc", th.dataset.key === sort.key && !sort.descending);
                th.classList.toggle("sorted-desc", th.dataset.key === sort.key && sort.descending);
            });
            const needle = (filter.value || "").trim().toLowerCase();
            body.replaceChildren();
            rows.filter((repo) => !needle || repo.full_name.toLowerCase().includes(needle))
                .sort(compare)
                .forEach((repo) => body.appendChild(rowFor(repo)));
            markCurrentRow(currentSlug);
        }

        filter.addEventListener("input", paint);
        paint();
    }

    function rowFor(repo) {
        const tr = document.createElement("tr");
        tr.dataset.slug = repo.slug;
        const usable = repo.status === "ok" && repo.commits > 0;
        if (!usable) tr.classList.add("unavailable");

        const nameCell = document.createElement("td");
        if (usable) {
            const link = document.createElement("a");
            link.href = `?repo=${encodeURIComponent(repo.slug)}`;
            link.textContent = repo.full_name;
            nameCell.appendChild(link);
        } else {
            nameCell.textContent = repo.full_name;
        }
        if (repo.url) {
            const github = document.createElement("a");
            github.href = repo.url;
            github.target = "_blank";
            github.rel = "noopener";
            github.className = "external";
            github.title = "Open on GitHub";
            github.textContent = "↗";
            nameCell.appendChild(github);
        }
        const flags = [repo.private ? "private" : null, repo.archived ? "archived" : null, repo.fork ? "fork" : null].filter(Boolean);
        if (flags.length) {
            const small = document.createElement("small");
            small.textContent = ` ${flags.join(", ")}`;
            nameCell.appendChild(small);
        }
        tr.appendChild(nameCell);

        const share = repo.commits ? ` (${Math.round(100 * repo.highlighted_commits / repo.commits)}%)` : "";
        [
            [formatDigit(repo.commits || 0), true],
            [formatDigit(repo.contributors || 0), true],
            [shortDate(repo.first_commit), false],
            [shortDate(repo.last_commit), false],
            [formatDigit(repo.insertions || 0), true],
            [formatDigit(repo.deletions || 0), true],
            [`${formatDigit(repo.highlighted_commits || 0)}${share}`, true],
            [repo.status === "error" ? `error: ${repo.error || "unknown"}` : repo.status, false],
        ].forEach(([text, numeric]) => {
            const td = document.createElement("td");
            td.textContent = text;
            if (numeric) td.className = "num";
            tr.appendChild(td);
        });
        return tr;
    }

    let currentSlug = null;
    function markCurrentRow(slug) {
        currentSlug = slug;
        document.querySelectorAll("#repo-table tbody tr").forEach((tr) => {
            tr.classList.toggle("current", tr.dataset.slug === slug);
        });
    }

    /////////////////////////////////////////////////////////////////
    //////////////////////////// The visual /////////////////////////
    /////////////////////////////////////////////////////////////////

    async function drawDataset(index, dataset) {
        const container = byId("chart-container");
        const promises = [
            d3.csv(`data/${dataset.slug}/commits.csv`),
            d3.csv(`data/${dataset.slug}/highlights.csv`).catch(() => null),
        ];

        const ORCAVisual = await createORCAVisual(container);
        ORCAVisual.width(container.offsetWidth);
        ["normal 400", "italic 400", "normal 700", "italic 700"].forEach((style) => {
            document.fonts.load(`${style} 10px "${FONT_FAMILY}"`);
        });
        await document.fonts.ready;

        const values = await Promise.all(promises);
        const commits = values[0];
        if (!commits || commits.length === 0) throw new Error("commits.csv is empty");
        if (!values[1] || values[1].length === 0) {
            values[1] = null;
            show("highlight-note", false);
            show("highlight-legend", false);
        }

        // Copy the rows before the visual decorates them with circular month references.
        const raw = JSON.parse(JSON.stringify(commits));
        fillTitles(index, dataset, commits);
        setupSearchBox(commits, ORCAVisual);
        setupDownload(raw, dataset.slug);
        setupResize(container, ORCAVisual);
        ORCAVisual(values);
    }

    function fillTitles(index, dataset, commits) {
        setAll(".commit-num", `${formatDigit(commits.length)} `);
        setText("title-repo-name", dataset.full_name);
        setAll(".repo-name", dataset.full_name);
        const dates = commits.map((d) => parseGitDate(d.commit_time)).filter(Boolean);
        const [first, last] = d3.extent(dates);
        if (last) setText("last-commit-date", `Up to ${formatLongDate(last)}`);
        if (first) setText("first-commit-date", ` on ${formatLongDate(first)}`);
        if (!dataset.combined) return;

        const lead = byId("intro-lead");
        const count = (index.totals || {}).repositories_ok || 0;
        lead.replaceChildren();
        lead.append("The ");
        const org = document.createElement("span");
        org.className = "repository";
        org.textContent = index.title || index.organisation;
        lead.append(org, ` organisation's ${formatDigit(count)} repositories have been shaped by their contributors`);
        setText("intro-branch", "their default branches");
    }

    /////////////////////////////////////////////////////////////////
    /////////////////////////// Search box //////////////////////////
    /////////////////////////////////////////////////////////////////

    function setupSearchBox(commits, ORCAVisual) {
        const searchBox = byId("search-box");
        const awesomplete = new Awesomplete(searchBox, {
            maxItems: 60,
            item: safeItem,
        });

        // Awesomplete's default item renderer uses innerHTML; author names come from commits, so build the
        // list items from text and mark the matched prefix with DOM nodes instead
        function safeItem(text, input, itemId) {
            const li = document.createElement("li");
            li.setAttribute("role", "option");
            li.setAttribute("aria-selected", "false");
            li.id = `awesomplete_list_${this.count}_item_${itemId}`;
            const label = String(text.label);
            const needle = input.trim();
            if (needle && label.toLowerCase().startsWith(needle.toLowerCase())) {
                const mark = document.createElement("mark");
                mark.textContent = label.slice(0, needle.length);
                li.append(mark, label.slice(needle.length));
            } else {
                li.textContent = label;
            }
            return li;
        }

        const counts = d3.rollup(commits, (v) => v.length, (d) => d.author_name);
        const entries = Array.from(counts, ([name, n]) => ({
            name,
            label: `${name} - ${n} commit${n > 1 ? "s" : ""}`,
        }));
        awesomplete.list = entries.map((d) => d.label);
        awesomplete.sort = (a, b) => a.localeCompare(b);
        awesomplete.filter = (text, input) => {
            const escape = (s) => s.replace(/[-\\^$*+?.()|[\]{}]/g, "\\$&");
            const label = text.label.split(" - ")[0];
            return new RegExp("^" + escape(input.trim()), "i").test(label);
        };

        const byLabel = (label) => entries.find((d) => d.label === label);
        let items = [];
        const reveal = function () {
            const chosen = byLabel(this.textContent);
            if (chosen) ORCAVisual.highlight(chosen.name);
        };

        searchBox.addEventListener("focus", (event) => { event.stopPropagation(); ORCAVisual.reset(); });
        searchBox.addEventListener("input", function () {
            if (this.value.length >= 2) {
                items = Array.from(document.querySelectorAll("#search-box-outer li"));
                items.forEach((item) => item.addEventListener("mouseover", reveal));
            } else {
                ORCAVisual.reset();
            }
        });
        searchBox.addEventListener("awesomplete-close", (event) => {
            event.stopPropagation();
            items.forEach((item) => item.removeEventListener("mouseover", reveal));
        });
        searchBox.addEventListener("awesomplete-selectcomplete", (event) => {
            event.stopPropagation();
            searchBox.blur();
            const chosen = byLabel(event.text.label);
            if (chosen) ORCAVisual.highlight(chosen.name, true);
        });
        searchBox.addEventListener("awesomplete-highlight", (event) => {
            const chosen = byLabel(event.text.label);
            if (chosen) ORCAVisual.highlight(chosen.name);
        });
    }

    /////////////////////////////////////////////////////////////////
    ////////////////////// Download and resizing ////////////////////
    /////////////////////////////////////////////////////////////////

    function setupDownload(raw, slug) {
        byId("dataviz-download-data").addEventListener("click", () => {
            const blob = new Blob([d3.csvFormat(raw)], { type: "text/csv;charset=utf-8" });
            const link = document.createElement("a");
            link.href = window.URL.createObjectURL(blob);
            link.download = `${slug}-commits.csv`;
            link.click();
        });
    }

    function setupResize(container, ORCAVisual) {
        let currentWidth = window.innerWidth;
        let timer = null;
        window.addEventListener("resize", () => {
            clearTimeout(timer);
            timer = setTimeout(() => {
                if (window.innerWidth === currentWidth) return;
                currentWidth = window.innerWidth;
                ORCAVisual.width(container.offsetWidth).resize();
            }, 300);
        });
    }

    main();
})();
