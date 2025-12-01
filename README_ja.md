# Amazon Bedrock AgentCore オンボーディング

[English](README.md) / [日本語](README_ja.md)

**実践的でシンプル、そして実行可能なサンプル** で、すべての開発者にAmazon Bedrock AgentCoreを効果的に習得していただきます。このプロジェクトでは、AgentCoreの中核機能の実践的な実装を通じて、段階的な学習パスを提供します。

## 概要

Amazon Bedrock AgentCoreは、AIエージェントを大規模に構築、デプロイ、管理するための包括的なプラットフォームです。このオンボーディングプロジェクトでは、各AgentCore機能を **実際に動作する実装** を通じて実演し、実行、変更、学習することができます。

### 学習内容

- **Code Interpreter**: 動的な計算とデータ処理のための安全なサンドボックス実行環境
- **Runtime**: AWSクラウドインフラストラクチャにおけるスケーラブルなエージェントのデプロイと管理
- **Gateway**: 認証とMCPプロトコルサポートを備えたAPIゲートウェイ統合
- **Identity**: エージェント操作のためのOAuth 2.0認証と安全なトークン管理
- **Observability**: CloudWatch統合による包括的なモニタリング、トレーシング、デバッグ
- **Memory**: コンテキストを認識するエージェントのインタラクションのための短期・長期メモリ機能

### 学習理念

私たちの **Amazon Bedrock AgentCore実装原則** に従い、このプロジェクトのすべての例は以下の特徴を持っています：

- ✅ **実行可能なコードファースト** - ライブAWSサービスに対してテストされた、完全で実行可能な例
- ✅ **実践的な実装** - 包括的なロギングとエラーハンドリングを備えた実世界のユースケース
- ✅ **シンプルで洗練された** - 機能性を維持しながら学習コストを最小限に抑える、明確で説明的なコード
- ✅ **段階的な学習** - 基本から高度な概念まで複雑さを徐々に増す番号付きシーケンス

## ディレクトリ構成

```
sample-amazon-bedrock-agentcore-onboarding/
├── 01_code_interpreter/          # 安全なサンドボックス実行環境
│   ├── README.md                 # 📖 Code Interpreterハンズオンガイド
│   ├── cost_estimator_agent/     # AWSコスト見積もりエージェント実装
│   └── test_code_interpreter.py  # 完全なテストスイートとサンプル
│
├── 02_runtime/                   # エージェントのデプロイと管理
│   ├── README.md                 # 📖 Runtimeデプロイハンズオンガイド
│   ├── prepare_agent.py          # エージェント準備自動化ツール
│   ├── agent_package/            # デプロイ用パッケージ化エージェント
│   └── deployment_configs/       # Runtime設定テンプレート
│
├── 03_identity/                  # OAuth 2.0認証
│   ├── README.md                 # 📖 Identity統合ハンズオンガイド
│   ├── setup_inbound_authorizer.py  # OAuth2プロバイダーセットアップ
│   └── test_identity_agent.py    # Identity保護されたエージェント
│
├── 04_gateway/                   # 認証付きAPIゲートウェイ
│   ├── README.md                 # 📖 Gateway統合ハンズオンガイド
│   ├── setup_outbound_gateway.py # Gatewayデプロイ自動化
│   ├── src/app.py                # Lambda関数実装
│   ├── deploy.sh                 # Lambdaデプロイスクリプト
│   └── test_gateway.py           # Gatewayテストエージェント
│
├── 05_observability/             # モニタリングとデバッグ
│   └── README.md                 # 📖 Observabilityセットアップハンズオンガイド
│
├── 06_memory/                    # コンテキスト認識インタラクション
│   ├── README.md                 # 📖 Memory統合ハンズオンガイド
│   ├── test_memory.py            # メモリ拡張エージェント実装
│   └── _implementation.md        # 技術的実装詳細
│
├── a1_custom/                    # 📚 付録: カスタムエージェントの開発
│   ├── README.md                 # 📖 カスタムエージェント開発ガイド
│   ├── weather_agent/            # 例: 天気エージェント実装
│   ├── prepare_agent.py          # デプロイ準備用
│   └── test_agentcore_endpoint.py # テスト用
│
├── pyproject.toml                # プロジェクト依存関係と設定
├── uv.lock                       # 依存関係ロックファイル
└── README.md                     # この概要ドキュメント
```

## ハンズオン学習パス

### 🚀 クイックスタート（推奨順序）

1. **[Code Interpreter](01_code_interpreter/README_ja.md)** - 基本的なエージェント開発はここから
   - 安全なPython実行環境でAWSコスト見積もりツールを構築
   - 即座に実践的な結果を得ながらAgentCoreの基本を学習
   - **所要時間**: ~30分 | **難易度**: 初級

2. **[Runtime](02_runtime/README_ja.md)** - エージェントをAWSクラウドインフラストラクチャにデプロイ
   - コスト見積もりツールをAgentCore Runtimeにパッケージ化してデプロイ
   - スケーラブルなエージェントデプロイパターンを理解
   - **所要時間**: ~45分 | **難易度**: 中級

3. **[Identity](03_identity/README_ja.md)** - セキュアな操作のためのOAuth 2.0認証を追加
   - Cognito OAuthプロバイダーとセキュアランタイムをセットアップ
   - `@requires_access_token`で透過的な認証を実装
   - **所要時間**: ~15分 | **難易度**: 中級

4. **[Gateway](04_gateway/README_ja.md)** - MCP互換APIを通じてエージェントを公開
   - Lambda統合でアウトバウンドゲートウェイを作成
   - ローカルツールとリモートゲートウェイ機能を組み合わせ
   - **所要時間**: ~15分 | **難易度**: 中級

5. **[Observability](05_observability/README_ja.md)** - 本番エージェントのモニタリングとデバッグ
   - 包括的なモニタリングのためのCloudWatch統合を有効化
   - トレーシング、メトリクス、デバッグ機能をセットアップ
   - **所要時間**: ~20分 | **難易度**: 初級

6. **[Memory](06_memory/README_ja.md)** - コンテキスト認識型の学習エージェントを構築
   - 短期および長期メモリ機能を実装
   - パーソナライズされた適応型エージェント体験を作成
   - **所要時間**: ~45分 | **難易度**: 上級

### 📚 付録

**[A1. カスタムエージェント](a1_custom/README.md)** - 独自のカスタムエージェントを構築
   - 特定のユースケースに合わせたエージェントの作成方法を学習
   - サンプル実装を提供（天気エージェント）
   - **所要時間**: ~20分 | **難易度**: 中級

### 🎯 フォーカス学習（ユースケース別）

**初めてのエージェント構築**
→ [01_code_interpreter](01_code_interpreter/README_ja.md)から開始

**本番環境へのデプロイ**
→ [02_runtime](02_runtime/README_ja.md) → [03_identity](03_identity/README_ja.md) → [04_gateway](04_gateway/README_ja.md) → [05_observability](05_observability/README_ja.md)の順序で

**エンタープライズセキュリティ**
→ [03_identity](03_identity/README_ja.md) → [04_gateway](04_gateway/README_ja.md)に焦点を当てる

**高度なAI機能**
→ [06_memory](06_memory/README_ja.md) → [01_code_interpreter](01_code_interpreter/README_ja.md)を探求

## 前提条件

### システム要件
- **Python 3.11+** と `uv` パッケージマネージャー
- 適切な権限で設定された **AWS CLI**
- Bedrock AgentCore（プレビュー版）へのアクセス権を持つ **AWSアカウント**

### クイックセットアップ
```bash
# リポジトリをクローン
git clone <repository-url>
cd sample-amazon-bedrock-agentcore-onboarding

# 依存関係をインストール
uv sync

# AWS設定を確認
aws sts get-caller-identity
```

## 主な特徴

### 🔧 **実装重視**
- ダミーデータやプレースホルダーレスポンスなし
- すべての例がライブAWSサービスに接続
- 本物の複雑さとエラーハンドリングパターン

### 📚 **段階的学習設計**
- 各ディレクトリが前の概念に基づいて構築
- 明確な前提条件と依存関係
- ステップバイステップの実行手順

### 🛠️ **本番環境対応パターン**
- 包括的なエラーハンドリングとロギング
- リソースのクリーンアップとライフサイクル管理
- セキュリティのベストプラクティスと認証

### 🔍 **デバッグしやすい設計**
- 動作をモニタリングするための広範なロギング
- 明確なエラーメッセージとトラブルシューティングガイダンス
- 部分的な障害復旧のための増分状態管理

## リソースのクリーンアップ

### 🧹 **重要：AWSリソースのクリーンアップ**

ハンズオン演習完了後は、継続的な課金を避けるためにリソースをクリーンアップしてください。**依存関係のため、逆順（06→01）でクリーンアップしてください**：

```bash
# 1. 最初にMemoryリソースをクリーンアップ
cd 06_memory
uv run python clean_resources.py

# 2. Gatewayリソースをクリーンアップ（SAM CLIを使用）
cd 04_gateway
sam delete  # Lambda関数と関連リソースを削除
uv run python clean_resources.py  # 必要に応じて追加のクリーンアップ

# 3. Identityリソースをクリーンアップ
cd 03_identity
uv run python clean_resources.py

# 4. Runtimeリソースをクリーンアップ
cd 02_runtime
uv run python clean_resources.py

# 5. 最後にCode Interpreterリソースをクリーンアップ
cd 01_code_interpreter
uv run python clean_resources.py
```

### 🔍 **クリーンアップされるもの**

- **Memory (06)**: メモリストア、会話履歴、永続データ
- **Gateway (04)**: Lambda関数（`sam delete`経由）、API Gatewayリソース、デプロイアーティファクト
- **Identity (03)**: Cognitoユーザープール、OAuthクライアント、認証設定
- **Runtime (02)**: デプロイされたエージェント、ランタイム設定、関連S3オブジェクト
- **Code Interpreter (01)**: アクティブなセッションと一時リソース
- **Observability (05)**: クリーンアップスクリプト不要 - CloudWatchログは自動的に期限切れ

### ⚠️ **依存関係の順序が重要**

**逆順（06→01）**でクリーンアップする理由：
- MemoryエージェントがGatewayエンドポイントに依存している可能性
- Gateway関数がIdentity認証を使用している可能性
- Identity設定がRuntimeエージェントによって参照されている可能性
- RuntimeエージェントがCode Interpreterセッションを使用している可能性

### 💡 **ベストプラクティス**

- 依存関係エラーを避けるため、必ず指定された順序でクリーンアップしてください
- 各ハンズオン演習完了後にクリーンアップスクリプトを実行してください
- AWSコンソールまたはCLIコマンドを使用してリソースの削除を確認してください
- 予期しない課金がないかAWS請求ダッシュボードを監視してください
- 独自のプロジェクトを構築する際の参考として、クリーンアップスクリプトを保持してください

## サポート

### ドキュメント
- 各ディレクトリには、ハンズオンの指示を含む詳細な`README.md`が含まれています
- 該当する場合は`_implementation.md`ファイルに実装の詳細
- インラインコードコメントで複雑なロジックを説明

### よくある問題
- **AWS権限**: 上記の必要な権限が認証情報にあることを確認してください
- **サービスの可用性**: AgentCoreはプレビュー版です - リージョンの可用性を確認してください
- **依存関係**: 一貫した依存関係バージョンを確保するため`uv sync`を使用してください
- **リソースのクリーンアップ**: 予期しない課金を避けるため、必ずクリーンアップスクリプトを逆順で実行してください

### サポートリソース
- [Amazon Bedrock AgentCore開発者ガイド](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- アカウント固有の問題については[AWSサポート](https://aws.amazon.com/support/)
- プロジェクト固有の質問については[GitHub Issues](../../issues)

## コントリビューション

私たちの **実装原則** に沿ったコントリビューションを歓迎します：

1. **実行可能なコードファースト** - すべての例は現在のAWS SDKバージョンで動作する必要があります
2. **実践的な実装** - 包括的なコメントと実世界のユースケースを含む
3. **シンプルで洗練された** - 機能性を維持しながら明確さを保つ
4. **意味のある構造** - 説明的な名前と論理的な構成を使用

詳細なガイドラインについては、[実装原則](.amazonq/rules/principle.md)をご覧ください。

## ライセンス

このプロジェクトはMITライセンスの下でライセンスされています - 詳細は[LICENSE](LICENSE)ファイルをご覧ください。

---

**準備はできましたか？** [01_code_interpreter](01_code_interpreter/README_ja.md)から始めて、最初のAgentCoreエージェントを構築しましょう！ 🚀