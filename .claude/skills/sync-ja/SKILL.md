---
name: sync-ja
description: Sync Japanese README translations with English source. Use when English READMEs change and Japanese versions need updating, or when improving Japanese translation fluency.
allowed-tools: Read, Write, Edit, Glob, Grep, Task, AskUserQuestion
---

# Sync Japanese README

Synchronize README_ja.md files with their English README.md counterparts, producing natural, native-speaker-quality Japanese — not literal translation.

## Usage

- `/sync-ja` — Auto-detect all out-of-sync README_ja.md files and update them
- `/sync-ja 09_browser_use` — Sync a specific module's README_ja.md
- `/sync-ja 06_identity 07_gateway` — Sync multiple specific modules
- `/sync-ja --check` — Report which files are out of sync without modifying them

## Arguments

`$ARGUMENTS` contains optional module directory names and flags.

Parse `$ARGUMENTS` for:
- **Positional**: directory name(s) (optional, e.g. `09_browser_use`)
- **--check**: Dry-run mode — only report drift, don't edit

If no directories specified, scan all numbered directories (`[0-9]*_*/`) for README.md + README_ja.md pairs.

## Translation Quality Rules

### The Two-Pass Method

**Pass 1 — Translate for meaning**: Convert the English content into Japanese, focusing on accurately conveying the meaning of each section.

**Pass 2 — Rewrite for fluency**: Read the Pass 1 output as a native Japanese reader would. Rewrite sentences that sound like translated text (翻訳調) into natural Japanese that reads as if originally written by a native speaker.

### Fluency Guidelines

- **Avoid translationese (翻訳調)**:
  - BAD: `このステップでは、エージェントのランタイムへのデプロイを行います` (stiff, literal)
  - GOOD: `このステップでは、エージェントをランタイムにデプロイします` (natural)
- **Use appropriate sentence endings**: Mix `です/ます` for explanations with concise `する/できる` for instructions
- **Keep sentences short**: Japanese readers prefer shorter sentences. Split long compound sentences
- **Natural word order**: Japanese has different information flow — restructure sentences rather than mirroring English order
- **Appropriate particles**: Use natural particle choices (は/が/を/に/で) — don't force English preposition mappings
- **Omit unnecessary subjects**: Japanese often omits obvious subjects — don't add 「あなたは」or「これは」where context is clear

### What to Keep in English

- AWS service names (Amazon Bedrock, AgentCore, CloudWatch, etc.)
- API names, SDK method names, CLI commands
- Code blocks (entire content)
- Mermaid diagrams (entire content)
- File paths and filenames
- Technical terms that are commonly used in English in Japanese tech writing (e.g., runtime, deploy, endpoint)

### Established Term Mappings

| English | Japanese |
|---------|----------|
| Process Overview | プロセス概要 |
| Prerequisites | 前提条件 |
| How to use | 使用方法 |
| File Structure | ファイル構成 |
| Step N: | ステップN: |
| Key Implementation Pattern | 主要な実装パターン |
| Usage Example | 使用例 |
| References | 参考資料 |
| Next Steps | 次のステップ |
| Troubleshooting | トラブルシューティング |
| Architecture | アーキテクチャ |
| Clean up | クリーンアップ |
| Overview | 概要 |

## Steps

### 1. Identify target files

If specific directories given in `$ARGUMENTS`, use those. Otherwise, find all pairs:

```
Glob: [0-9]*_*/README.md
Glob: [0-9]*_*/README_ja.md
```

For `--check` mode, compare heading structure between EN and JA and report differences, then stop.

### 2. Analyze drift for each pair

For each README.md + README_ja.md pair:
1. Read both files
2. Compare heading structure (count and names of `#`, `##`, `###` headings)
3. Identify:
   - Sections in EN missing from JA (need translation)
   - Sections in JA not in EN (stale, need removal)
   - Sections where EN content has substantially changed (need update)

### 3. Apply two-pass translation

For each file that needs updating:

**Pass 1**: Edit README_ja.md to match the English structure and content. Focus on meaning accuracy.

**Pass 2**: Re-read the edited README_ja.md and rewrite any sentences that sound unnatural. Ask yourself: "Would a native Japanese technical writer write it this way?" If not, rephrase.

Key rules during editing:
- **Preserve heading levels exactly** — same `#` depth as English
- **Preserve mermaid diagrams and code blocks verbatim**
- **Preserve all links** — update link text to Japanese but keep URLs
- **Match section order** with English README

### 4. Self-review checklist

Before finishing each file, verify:
- [ ] All EN headings have corresponding JA headings at the same level
- [ ] No stale JA sections that don't exist in EN
- [ ] Code blocks and mermaid diagrams are identical to EN
- [ ] No translationese — reads naturally in Japanese
- [ ] Technical terms kept in English where appropriate
- [ ] Links work (relative paths unchanged)

### 5. Summary

Print a summary:
- Files updated (with brief description of what changed)
- Files already in sync (skipped)
- Any sections that need manual review (e.g., heavily rewritten content)

## Examples of Good vs Bad Translation

### Example 1: Instruction text
- EN: `In this step, you will deploy the agent to the AgentCore runtime.`
- BAD: `このステップでは、あなたはエージェントをAgentCoreランタイムにデプロイすることになります。`
- GOOD: `このステップでは、エージェントをAgentCoreランタイムにデプロイします。`

### Example 2: Feature description
- EN: `AgentCore Browser provides persistent browser sessions that your agent can use to interact with web applications.`
- BAD: `AgentCore Browserは、あなたのエージェントがWebアプリケーションと対話するために使用できる永続的なブラウザセッションを提供します。`
- GOOD: `AgentCore Browserは、Webアプリケーションを操作するための永続的なブラウザセッションを提供します。エージェントはこのセッションを使ってWebページの閲覧や入力を行えます。`

### Example 3: Benefit list
- EN: `- Eliminates the need for hardcoded credentials`
- BAD: `- ハードコードされた認証情報の必要性を排除します`
- GOOD: `- 認証情報のハードコードが不要になります`

## Important Notes

- Never overwrite README_ja.md without reading it first — it may have manual refinements
- If a README_ja.md doesn't exist yet, create it from scratch using the two-pass method
- When in doubt about a translation choice, prefer clarity over literal accuracy
- The top-level project README_ja.md follows the same rules
