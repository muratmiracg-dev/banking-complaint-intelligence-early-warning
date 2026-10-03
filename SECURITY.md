# Security

This is a local research application. The Python server binds to `127.0.0.1` and has no user accounts or production access controls. Do not expose it directly to the internet.

- Raw CSV/ZIP files, full narratives and SQLite databases are ignored by Git.
- Model parameters are JSON, not executable pickle files.
- The browser classifies text locally. There are no third-party analytics or CDN scripts.
- The local API checks Host and Origin, bounds POST sizes and does not log search queries or text.
- Public previews contain brief excerpts of already published CFPB narratives. Extra regex redaction removes obvious emails, URLs and long numbers; it is not a complete anonymization system.
- Exports escape spreadsheet formula prefixes. The UI escapes source text before rendering it.

Report a security concern through GitHub's private vulnerability reporting feature if enabled for this repository. Otherwise, open an issue with a general description and request a private channel before sharing sensitive details. Never attach private consumer records.

The CI and CodeQL workflow files are included. Repository-level security settings and branch protection are managed separately on GitHub.
