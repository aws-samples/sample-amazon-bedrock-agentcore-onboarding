# Amazon Bedrock AgentCore オンボーディング

[English](README.md) / [日本語](README_ja.md)

**実践的でシンプル、そして実行可能なサンプル** で、すべての開発者にAmazon Bedrock AgentCoreを効果的に習得していただきます。このプロジェクトでは、AgentCoreの中核機能の実践的な実装を通じて、段階的な学習パスを提供します。

## 概要

Amazon Bedrock AgentCoreは、AIエージェントを大規模に構築、デプロイ、管理するための包括的なプラットフォームです。このオンボーディングプロジェクトでは、各AgentCore機能を **実際に動作する実装** を通じて実演し、実行、変更、学習することができます。

### 学習内容

**Foundation** - エージェントの構築・評価・監視
- **Code Interpreter**: 動的な計算とデータ処理のための安全なサンドボックス実行環境
- **Runtime**: AWSクラウドインフラストラクチャにおけるスケーラブルなエージェントのデプロイと管理
- **Memory**: コンテキストを認識するエージェントのインタラクションのための短期・長期メモリ機能
- **Evaluation**: ビルトインおよびカスタム評価器による品質保証 * (近日公開)*
- **Observability**: CloudWatch統合による包括的なモニタリング、トレーシング、デバッグ

**Extension** - 外部ツールとの連携
- **Identity**: エージェント操作のためのOAuth 2.0認証と安全なトークン管理
- **Gateway**: 認証とMCPプロトコルサポートを備えたAPIゲートウェイ統合
- **Policy**: エージェントからツールへのアクセスをきめ細かく制御 * (近日公開)*
- **Browser Use**: 永続的なブラウザプロファイルによるWeb自動化 * (近日公開)*

### 学習理念

私たちの **Amazon Bedrock AgentCore実装原則** に従い、このプロジェクトのすべての例は以下の特徴を持っています：

- ✅ **実行可能なコードファースト** - ライブAWSサービスに対してテストされた、完全で実行可能な例
- ✅ **実践的な実装** - 包括的なロギングとエラーハンドリングを備えた実世界のユースケース
- ✅ **シンプルで洗練された** - 機能性を維持しながら学習コストを最小限に抑える、明確で説明的なコード
- ✅ **段階的な学習** - 基本から高度な概念まで複雑さを徐々に増す番号付きシーケンス

## ディレクトリ構成

```
sample-amazon-bedrock-agentcore-onboarding/
│
│  # ベースのエージェント (全 Lab から利用)
├── agents/
│   ├── CostEstimatorAgent/       # AWSコスト見積もりエージェント (唯一の常設エージェント)
│   │   └── app/CostEstimatorAgent/
│   │       ├── main.py           # Runtime エントリポイント
│   │       ├── cost_estimator_agent.py  # AWSCostEstimatorAgent (Facade)
│   │       ├── config.py         # SYSTEM_PROMPT / DEFAULT_MODEL
│   │       ├── pyproject.toml    # Python 依存関係
│   │       └── iam_policies/     # additionalPolicies に配線される IAM ポリシー
│   ├── setup.py                  # ベース (+ overlay) を agentcore create の雛形へコピー
│   │                             #   --target=プロジェクト / --agent=その中のエージェント
│   └── .gitignore                # My*Agent/ (受講者が作る雛形) を除外
│
│  # Foundation - エージェントの構築・評価・監視
├── 02_runtime/                   # エージェントのデプロイと管理
│   ├── README.md                 # 📖 Runtimeデプロイハンズオンガイド
│   └── invoke_agent.py           # boto3 (InvokeAgentRuntime) から呼び出すクライアント
│
├── 03_memory/                    # コンテキスト認識インタラクション
│   ├── README.md                 # 📖 Memory統合ハンズオンガイド
│   ├── agent/                    # ベースへ被せる Lab 3 固有のコード (overlay)
│   └── test_memory.py            # 短期記憶 / 長期記憶 / actor分離の検証
│
├── 04_observability/             # モニタリングとデバッグ
│   ├── README.md                 # 📖 Observabilityセットアップハンズオンガイド
│   └── test_observability.py     # 同一セッションで複数回呼び出してトレースを生成
│
├── 05_evaluation/                # 品質保証
│   ├── README.md                 # 📖 Evaluationハンズオンガイド
│   ├── test_evaluation.py        # ローカル評価 (strands-agents-evals)
│   └── evaluators/               # ローカル評価器 + AgentCore 評価器の設定
│
│  # Extension - 外部ツールとの連携
├── 06_identity/                  # OAuth 2.0 認証 (inbound / outbound)
│   ├── agent/                    # ベースへ被せる Lab 6 固有のコード (overlay)
│   ├── setup_cognito.py          # 認可サーバー (Cognito) の作成と削除
│   └── clean_resources.py        # 06 が追加した分だけを削除
│   ├── README.md                 # 📖 Identity統合ハンズオンガイド
│   ├── setup_cognito.py          # 認可サーバー (Cognito) の作成と削除
│   ├── test_identity_agent.py    # Identity保護されたエージェントのテスト
│   └── clean_resources.py        # Runtime + Cognito の削除 (--force で Cognito も)
│
├── 07_gateway/                   # 認証付きAPIゲートウェイ
│   ├── README.md                 # 📖 Gateway統合ハンズオンガイド
│   ├── src/app.py                # Lambda関数実装 (Markdown → HTML メール)
│   ├── template.yaml             # AWS SAM テンプレート
│   ├── deploy.sh                 # Lambdaデプロイスクリプト
│   ├── tool_schema.json          # Gateway に公開するツールのスキーマ
│   ├── test_gateway.py           # Gatewayテストエージェント
│   └── clean_resources.py        # Gateway + Lambda の削除 (--force が必要)
│
├── 08_policy/                    # ツール呼び出しのアクセス制御
│   ├── README.md                 # 📖 Policyハンズオンガイド
│   ├── setup_policy_demo.py      # Cedarポリシーの生成とデモ用スコープの追加
│   ├── policies/                 # Cedar ポリシー (テンプレート)
│   ├── test_policy.py            # スコープ別アクセスのテスト
│   └── clean_resources.py        # Policy Engine / Cedar ポリシー / デモ用スコープの削除
│
├── 09_browser_use/               # Web自動化
│   ├── README.md                 # 📖 Browser Useハンズオンガイド
│   ├── test_browser_use.py       # ブラウザ操作デモ
│   └── clean_resources.py        # アクティブなブラウザセッションの停止
│
│  # 付録
├── a1_custom/                    # 📚 付録: カスタムエージェントの開発
│   └── README.md                 # 📖 カスタムエージェント開発ガイド
│
├── pyproject.toml                # プロジェクト依存関係と設定
├── uv.lock                       # 依存関係ロックファイル
└── README.md                     # この概要ドキュメント
```

各 Lab は **`agentcore create` で雛形を作り、`agents/setup.py` でベースのコードを配置する** 運用です。
Lab 固有の差分があるものは `0N_xxx/agent/` に置き、`--overlay` でベースへ被せます。

## ハンズオン学習パス

### 🚀 Foundation - エージェントの構築・評価・監視

1. **[Code Interpreter](agents/CostEstimatorAgent/app/CostEstimatorAgent/README_ja.md)** - 基本的なエージェント開発はここから
   - 安全なPython実行環境でAWSコスト見積もりツールを構築
   - 即座に実践的な結果を得ながらAgentCoreの基本を学習
   - **所要時間**: ~30分 | **難易度**: 初級

2. **[Runtime](02_runtime/README_ja.md)** - エージェントをAWSクラウドインフラストラクチャにデプロイ
   - コスト見積もりツールをAgentCore Runtimeにパッケージ化してデプロイ
   - スケーラブルなエージェントデプロイパターンを理解
   - **所要時間**: ~45分 | **難易度**: 中級

3. **[Memory](03_memory/README_ja.md)** - コンテキスト認識型の学習エージェントを構築
   - 短期および長期メモリ機能を実装
   - パーソナライズされた適応型エージェント体験を作成
   - **所要時間**: ~45分 | **難易度**: 上級

4. **[Observability](04_observability/README_ja.md)** - 本番エージェントのモニタリングとデバッグ
   - 包括的なモニタリングのためのCloudWatch統合を有効化
   - トレーシング、メトリクス、デバッグ機能をセットアップ
   - **所要時間**: ~20分 | **難易度**: 初級

5. **Evaluation** * (近日公開)* - エージェントの品質を保証
   - 13のビルトイン評価器でエージェントのパフォーマンスをテスト
   - カスタムモデルベースのスコアリングシステムを作成

### 🔗 Extension - 外部ツールとの連携

6. **[Identity](06_identity/README_ja.md)** - セキュアな操作のためのOAuth 2.0認証を追加
   - Cognito OAuthプロバイダーとセキュアランタイムをセットアップ
   - `@requires_access_token`で透過的な認証を実装
   - **所要時間**: ~15分 | **難易度**: 中級

7. **[Gateway](07_gateway/README_ja.md)** - MCP互換APIを通じてエージェントを公開
   - Lambda統合でアウトバウンドゲートウェイを作成
   - ローカルツールとリモートゲートウェイ機能を組み合わせ
   - **所要時間**: ~15分 | **難易度**: 中級

8. **Policy** * (近日公開)* - エージェントからツールへのアクセス制御
   - Cedar言語できめ細かなアクセスポリシーを定義
   - Gateway統合によるリアルタイムのツール呼び出しインターセプト

9. **Browser Use** * (近日公開)* - Webベースのワークフロー自動化
   - ブラウザプロファイルで複雑なWebタスクを実行
   - セッション間での永続的な認証状態

### 📚 付録

**[A1. カスタムエージェント](a1_custom/README.md)** - 独自のカスタムエージェントを構築
   - 特定のユースケースに合わせたエージェントの作成方法を学習
   - サンプル実装を提供（天気エージェント）
   - **所要時間**: ~20分 | **難易度**: 中級

### 🎯 フォーカス学習（ユースケース別）

**初めてのエージェント構築**
→ [agents/CostEstimatorAgent](agents/CostEstimatorAgent/app/CostEstimatorAgent/README_ja.md)から開始

**本番環境へのデプロイ**
→ [02_runtime](02_runtime/README_ja.md) → [03_memory](03_memory/README_ja.md) → [04_observability](04_observability/README_ja.md)の順序で

**エンタープライズセキュリティ**
→ [06_identity](06_identity/README_ja.md) → [07_gateway](07_gateway/README_ja.md)に焦点を当てる

**高度なAI機能**
→ [agents/CostEstimatorAgent](agents/CostEstimatorAgent/app/CostEstimatorAgent/README_ja.md) → [03_memory](03_memory/README_ja.md) → [04_observability](04_observability/README_ja.md)を探求

## 前提条件

### システム要件
- **Python 3.12+** と `uv` パッケージマネージャー
- 適切な権限で設定された **AWS CLI**
- Bedrock AgentCore（プレビュー版）へのアクセス権を持つ **AWSアカウント**
- **Node.js 20+** と **AgentCore CLI** (`npm install -g @aws/agentcore`)
- **AWS CDK** — `agentcore deploy` が内部で使用します。デプロイ先リージョンで `cdk bootstrap` を一度実行してください
- **AWS SAM CLI** — 07_gateway の Lambda デプロイに必要

### クイックセットアップ
```bash
# リポジトリをクローン
git clone <repository-url>
cd sample-amazon-bedrock-agentcore-onboarding

# 依存関係をインストール
uv sync

# AgentCore CLI をインストール
npm install -g @aws/agentcore
agentcore --version

# CDK をブートストラップ (リージョンごとに一度)
cdk bootstrap

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

ハンズオン演習完了後は、継続的な課金を避けるためにリソースをクリーンアップしてください。

AgentCore CLI で作成したリソースは `agentcore remove all` で宣言から外し、
`agentcore deploy` で削除を AWS に適用します。**`remove` だけでは AWS のリソースは
残ったままです。** Cognito、Lambda、ブラウザセッションのように CLI の管理対象外のリソースを
持つ演習 (06 / 07 / 08 / 09) には、両方をまとめた `clean_resources.py` があります。
**依存関係のため、逆順（09→02）でクリーンアップしてください**：

```bash
# 1. Browser Use — アクティブなブラウザセッションを停止
cd 09_browser_use && uv run python clean_resources.py && cd ..

# 2. Policy — Cedar ポリシー、ポリシーエンジン、デモ用スコープ
cd 08_policy && uv run python clean_resources.py && cd ..

# 3. Gateway — Gateway / target / credential と Lambda スタック
cd 07_gateway && uv run python clean_resources.py --force && cd ..

# 4. Identity — 06 が追加した 2 つの Runtime と Credential Provider、Cognito
#    (Lab 2 のエージェントは残ります)
cd 06_identity && uv run python clean_resources.py --force && cd ..

# 5. Evaluation — 評価器とオンライン評価設定 (Runtime は残す)
cd agents/MyCostEstimatorAgent
agentcore remove online-eval --name cost_estimator_online_eval -y
agentcore remove evaluator --name cost_estimator_tool_usage -y
agentcore deploy
cd ../..

# 6. Memory — Lab 2 のプロジェクトに追加した Memory のみ削除
cd agents/MyCostEstimatorAgent
agentcore remove memory --name MyCostEstimatorAgentMemory -y && agentcore deploy
cd ../..

# 7. Runtime — ベースのエージェント (最後に実行)
cd agents/MyCostEstimatorAgent
agentcore remove all -y && agentcore deploy
cd .. && rm -r MyCostEstimatorAgent && cd ..
```

`agentcore remove all` はプロジェクト内のすべての宣言を空にします。`agents/MyCostEstimatorAgent`
は 02 / 03 / 05 / 06 が共有しているため、**すべての演習を終えたあとの最後の手順としてのみ**
使ってください。途中で使うと他の演習のリソースまで消えます。個別に消す場合は
`agentcore remove <種別> --name <名前>` を使います。

後続の演習が使うリソースを守るため、07 と 06 のスクリプトは `--force` を要求します。
スクリプトは削除後に `list-*` API を呼んで実際に消えたことを確認し、`✅` または `⚠️` で
結果を報告します。

01 と 04 は独自のクラウドリソースを作りません (01 はローカル実行、04 は 02 の Runtime を
観測するだけ)。02 / 03 / 05 のリソースはすべて AgentCore CLI の管理下にあるため、
スクリプトは不要です。

削除できたことを確認します。

```bash
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE REVIEW_IN_PROGRESS \
  --query 'StackSummaries[?starts_with(StackName,`AgentCore-My`)].[StackName,StackStatus]'
aws bedrock-agentcore-control list-agent-runtimes \
  --query 'agentRuntimes[?starts_with(agentRuntimeName,`My`)].agentRuntimeName'
aws bedrock-agentcore-control list-memories --query 'memories[?starts_with(id,`My`)].id'
aws cognito-idp list-user-pools --max-results 20 \
  --query 'UserPools[?starts_with(Name,`agentcore-cost-estimator`)].Name'
```

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
- プロジェクト固有の質問については[GitHub Issues](https://github.com/aws-samples/sample-amazon-bedrock-agentcore-onboarding/issues)

## コントリビューション

私たちの **実装原則** に沿ったコントリビューションを歓迎します：

1. **実行可能なコードファースト** - すべての例は現在のAWS SDKバージョンで動作する必要があります
2. **実践的な実装** - 包括的なコメントと実世界のユースケースを含む
3. **シンプルで洗練された** - 機能性を維持しながら明確さを保つ
4. **意味のある構造** - 説明的な名前と論理的な構成を使用

詳細なガイドラインについては、[CONTRIBUTING](CONTRIBUTING.md)をご覧ください。

## ライセンス

このプロジェクトはMITライセンスの下でライセンスされています - 詳細は[LICENSE](LICENSE)ファイルをご覧ください。

---

**準備はできましたか？** [agents/CostEstimatorAgent](agents/CostEstimatorAgent/app/CostEstimatorAgent/README_ja.md)から始めて、最初のAgentCoreエージェントを構築しましょう！