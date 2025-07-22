# AI エージェントの開発からデプロイまでまるっと体験する Amazon Bedrock AgentCore

みなさんは AI エージェントを開発されたことはあるでしょうか? Gartner は、2028 年までに日常業務における意思決定のうちの少なくとも 15% が、AI エージェントにより「自律的に」行われるようになると予測しています。開発の現場では Pull Request のマージは人間がレビューして行う、また業務の現場では AI の回答を人間がチェックして送信、といった作業は増えていると思いますが、5 回に 1 回ぐらいはノーチェックで行うようになるとすると大きな進歩です。

[IPA の DX 動向 2025 年版](https://www.ipa.go.jp/digital/chousa/dx-trend/tbl5kb0000001mn2-att/dx-trend-2025.pdf) では従業員 1,000 名超の企業では米国・ドイツをしのぎ日本が一番 AI を導入していると示していて、こちらを信じるなら "15%" の値は日本ではより一層高くなるかもしれません。

AI エージェント自体を迎える日本のエンジニアとして、AI エージェントの開発からデプロイまで一連ができるよう備えておくのは意義あることかもしれません。前置きが長くなりましたが、そんな「PoC から本番まで」をまるっとカバーする AWS の Amazon Bedrock AgentCore を本記事では紹介します。

AgentCore は AI エージェントを安全かつスケーラブルに動作させるためのマネージドサービス群です。本ブログでは AWS の見積りを計算する AI エージェントを Slack から使えるようにするまでの流れを通じ、主要なサービスを扱う方法を紹介します。

1. 🧮 : AWS の見積りを「計算」するエージェントを作成する : [AgentCore Code Interpreter](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-tool.html)
2. 🚀 : クラウド上に AI エージェントをデプロイする : [AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)
3. 🛡️ : AI エージェントの利用に認証をかけて公開する : [AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)
4. 📊 : AI エージェントの動作をモニタリングする : [AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)
5. 🧠 : 見積の内容を「記憶」する : [AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html)
6. 👤 : ユーザーの認可により 3rd Party のサービスにアクセスする : [AgentCore Identity](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html)


では、はじめて行きましょう！

## 🧮 AWS の見積りを「計算」するエージェントを作成する : [AgentCore Code Interpreter](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-tool.html)

今回一例として開発するのは、"AWS のコスト見積もり" エージェントです。このエージェントは、受け取った「作りたいシステム」の概要から必要な AWS のサービスとサイズを推定し、[AWS Pricing MCP Server](https://github.com/awslabs/mcp/tree/main/src/aws-pricing-mcp-server) により料金を取得し、[AgentCore Code Interpreter](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/code-interpreter-tool.html) で計算を行います。このサンプルは、多くの業務で求められる「データを集めて」「計算する」過程を MCP と CodeInterpreter で行うデモであり、応用の幅が広いと考えています。

AI エージェントの実装は [Strands Agents](https://github.com/strands-agents/sdk-python) で行いますが、後述する通り AgentCore は **実装に使用しているフレームワークに関わらず** 使えるマネージドサービスであるため LangChain/LangGraph 、また Python 以外の言語で実装されていても構いません。

Strands Agents による実装は次の通りです。プロンプトは長いので `config.py` に外だししています。

```python
import os
import logging
from strands import Agent, tool
from strands.tools.mcp import MCPClient
from mcp import stdio_client, StdioServerParameters
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
from config import (
    SYSTEM_PROMPT,
    COST_ESTIMATION_PROMPT,
    DEFAULT_MODEL,
    DEFAULT_REGION,
    LOG_FORMAT
)

# Configure comprehensive logging for debugging and monitoring
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler()]
)

# Enable Strands debug logging for detailed agent behavior
logging.getLogger("strands").setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)


class AWSCostEstimatorAgent:
    """
    AWS Cost Estimation Agent using AgentCore Code Interpreter
    
    This agent combines:
    - MCP pricing tools (automatically available) for real-time pricing data
    - AgentCore Code Interpreter for secure calculations
    - Strands Agents framework for clean implementation
    """
    
    def __init__(self, region: str = DEFAULT_REGION):
        """
        Initialize the cost estimation agent
        
        Args:
            region: AWS region for AgentCore Code Interpreter
        """
        self.region = region
        self.code_interpreter = None
        
        logger.info(f"Initializing AWS Cost Estimator Agent in region: {region}")
        
    def _setup_code_interpreter(self) -> None:
        """Setup AgentCore Code Interpreter for secure calculations"""
        try:
            logger.info("Setting up AgentCore Code Interpreter...")
            self.code_interpreter = CodeInterpreter(self.region)
            self.code_interpreter.start()
            logger.info("✅ AgentCore Code Interpreter session started successfully")
        except Exception as e:
            logger.error(f"❌ Failed to setup Code Interpreter: {e}")
            raise
    
    def _setup_aws_pricing_client(self) -> MCPClient:
        """Setup AWS Pricing MCP Client following Strands best practices"""
        try:
            logger.info("Setting up AWS Pricing MCP Client...")
            aws_profile = os.environ.get("AWS_PROFILE", "default")
            logger.info(f"Using AWS profile: {aws_profile}")
            
            aws_pricing_client = MCPClient(
                lambda: stdio_client(StdioServerParameters(
                    command="uvx", 
                    args=["awslabs.aws-pricing-mcp-server@latest"],
                    env={
                        "FASTMCP_LOG_LEVEL": "ERROR",
                        "AWS_PROFILE": aws_profile,
                        "AWS_REGION": self.region
                    }
                ))
            )
            logger.info("✅ AWS Pricing MCP Client setup successfully")
            return aws_pricing_client
        except Exception as e:
            logger.error(f"❌ Failed to setup AWS Pricing MCP Client: {e}")
            raise
    
    
    @tool
    def execute_cost_calculation(self, calculation_code: str, description: str = "") -> str:
        """
        Execute cost calculations using AgentCore Code Interpreter
        
        Args:
            calculation_code: Python code for cost calculations
            description: Description of what the calculation does
            
        Returns:
            Calculation results as string
        """
        if not self.code_interpreter:
            return "❌ Code Interpreter not initialized"
            
        try:
            logger.info(f"🧮 Executing calculation: {description}")
            logger.debug(f"Code to execute:\n{calculation_code}")
            
            # Execute code in secure AgentCore sandbox
            response = self.code_interpreter.invoke("executeCode", {
                "language": "python",
                "code": calculation_code
            })
            
            # Extract results from response stream
            results = []
            for event in response.get("stream", []):
                if "result" in event:
                    result = event["result"]
                    if "content" in result:
                        for content_item in result["content"]:
                            if content_item.get("type") == "text":
                                results.append(content_item["text"])
            
            result_text = "\n".join(results)
            logger.info("✅ Calculation completed successfully")
            logger.debug(f"Calculation result: {result_text}")
            
            return result_text
            
        except Exception as e:
            error_msg = f"❌ Calculation failed: {e}"
            logger.error(error_msg)
            return error_msg

    def estimate_costs(self, architecture_description: str) -> str:
        """
        Estimate costs for a given architecture description
        
        Args:
            architecture_description: Description of the system to estimate
            
        Returns:
            Cost estimation results
        """
        logger.info("🚀 Initializing AWS Cost Estimation Agent...")
        logger.info("📊 Starting cost estimation...")
        logger.info(f"Architecture: {architecture_description}")
        
        try:
            # Setup components in order
            self._setup_code_interpreter()
            aws_pricing_client = self._setup_aws_pricing_client()

            # Create agent with persistent MCP context for this request
            with aws_pricing_client:
                pricing_tools = aws_pricing_client.list_tools_sync()
                logger.info(f"Found {len(pricing_tools)} AWS pricing tools")
                
                # Create agent with both execute_cost_calculation and MCP pricing tools
                all_tools = [self.execute_cost_calculation] + pricing_tools
                agent = Agent(
                    model=DEFAULT_MODEL,
                    tools=all_tools,
                    system_prompt=SYSTEM_PROMPT
                )
                
                # Use the agent to process the cost estimation request
                prompt = COST_ESTIMATION_PROMPT.format(
                    architecture_description=architecture_description
                )
                result = agent(prompt)
                
                logger.info("✅ Cost estimation completed")
                return result.message["content"] if result.message else "No estimation result."

        except Exception as e:
            error_msg = f"❌ Cost estimation failed: {e}"
            logger.error(error_msg)
            return error_msg
        finally:
            # Clean up resources
            self.cleanup()
    
    def cleanup(self) -> None:
        """Clean up resources"""
        logger.info("🧹 Cleaning up resources...")
        
        if self.code_interpreter:
            try:
                self.code_interpreter.stop()
                logger.info("✅ Code Interpreter session stopped")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping Code Interpreter: {e}")
            finally:
                self.code_interpreter = None

```

AgentCore Code Interpreter は `from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter` から利用します。利用の方法は次の通りです。

1. 環境の作成 : `self.code_interpreter = CodeInterpreter(self.region)`
2. 起動 : `self.code_interpreter.start()`
3. コード実行 : `self.code_interpreter.invok("executeCode", {"language": "python", "code": calculation_code})`
4. 停止 : `self.code_interpreter.stop()`

注目すべき点として、ローカルで開発しているエージェントであっても AgentCore Code Interpreter は普通に使うことができ**安全にコードを実行できるセキュアなサンドボックス**を提供します。この性質は、逆にクラウドで動かさない場合、ローカルでのコード実行により端末の安全性が脅かされないようにするための強力なサービスです。Code Interpreter 以外に [AgentCore Browser](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html) が提供されており、こちらもクラウドベース隔離されたブラウザ環境を提供することでローカルのブラウザが不正に操作されるリスクを回避できます。

**本セクションのまとめ**

* **AgentCore はデプロイしなくても使える！** : セキュアなコード実行環境を提供する Code Interpreter、ブラウザ実行環境を提供する Browser はローカル/クラウド関わらずセキュアな AI エージェントの実行を可能にする


## 🚀 : クラウド上に AI エージェントをデプロイする : [AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)

開発したエージェントをデプロイすることで、アプリケーションの中から呼び出したり、開発者同士で共用することが出来ます。今回のエージェントなら、例えばクラウド構築の相談サービスを行っていれば呼び出しを行うことで概算見積りを顧客に提示できるかもしれません。

[AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)は、AI エージェントをホスティングするためのサービスです。このサービスは、専用の microVM により AI エージェントごとにセッションを分離しセッション間のデータ汚染を防ぐことが出来ます。[こちらのドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/getting-started-custom.html) を見るとわかりますが、中身は FastAPI 等で作成した API サーバーをコンテナに固めて ECR に登録し、AgentCore Runtime に登録します。セッションは同一 id を指定することで継続することもでき、15 分の idle 状態または 8 時間の稼働上限にかからない限り処理を継続することが出来ます (詳細 : [Use isolated sessions for agents](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html))。


先ほどの AI エージェントを AgentCore Runtime にデプロイしてみましょう。必要な作業は 3 つです。

1. `bedrock_agentcore` を使用し Agent を起動する関数に対し entrypoint のアノテーションを付与する
2. AgentCore Runtime の実行に必要な IAM ロールを  [Permissions for AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-permissions.html) に従い準備する
3. `bedrock_agentcore_starter_toolkit` で AI エージェントのコードをコンテナに固めて登録、起動する

では、手順通り実装していきましょう。今回用意した `register_agent.py` は、`prepare` 関数により任意の AI エージェントを実装したスクリプトファイルをベースにデプロイ用のディレクトリを作り、アノテーションを追加したファイルと `requirements.txt` を配置、さらにロールを作成します。`deploy` でエージェントをデプロイし `invoke` で起動します。`deploy` の実装は次の通りです。

```python
[[Code of `deploy`]]
```

`invoke` の実装は次の通りです。

```python
[[Code of `invokeB`]]
```

結果、次のような出力が得られます。

**本セクションのまとめ**

* **AgentCore Runtime により継続的かつ安全なコンテキストが維持できる！** : いままで AI エージェントをデプロイする先は Fargate や AWS Lambda がありましたが、AI エージェントとのインタラクティブなやり取りで必要になるひつようになるセキュアなコード実行環境を提供する Code Interpreter、ブラウザ実行環境を提供する Browser はローカル/クラウド関わらずセキュアな AI エージェントの実行を可能にする

## 🛡️ : AI エージェントの利用に認証をかけて公開する : [AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)

[AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)は、エージェントとユーザーのアイデンティティを検証するためのイングレス認証と、外部ツールやサービスに安全に接続するためのエグレス認証の両方を提供する、セキュアなエージェントデプロイメントのための包括的な機能を提供します。

実装では、外部リクエストとAgentCore Runtimeでホストされるエージェント間のブリッジとして機能する[AWS Lambda関数](https://docs.aws.amazon.com/lambda/latest/dg/welcome.html)を作成します。[Amazon Cognito User Pool認証](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-integrate-with-cognito.html)を備えた[Amazon API Gateway](https://docs.aws.amazon.com/apigateway/latest/developerguide/welcome.html)がユーザー認証を処理し、承認されたユーザーのみがコスト見積もりエージェントにアクセスできることを保証します。

```python
import json
import boto3
from typing import Dict, Any

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """AgentCore Gateway統合のためのLambda関数"""
    
    # Cognito JWTトークンからユーザーコンテキストを抽出
    user_context = extract_user_context(event['requestContext']['authorizer'])
    
    # リクエストペイロードを検証
    if not validate_request(event['body']):
        return {
            'statusCode': 400,
            'body': json.dumps({'error': '無効なリクエスト形式'})
        }
    
    # AgentCore Runtimeにリクエストを転送
    agentcore_client = boto3.client('bedrock-agentcore')
    
    try:
        response = agentcore_client.invoke_agent(
            agentId=os.environ['AGENT_ID'],
            sessionId=generate_session_id(user_context),
            inputText=json.loads(event['body'])['message']
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response)
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': '内部サーバーエラー'})
        }
```

ゲートウェイ設定は、[RFC 6749](https://tools.ietf.org/html/rfc6749)仕様に従って、サードパーティ統合のための[OAuth 2.0フロー](https://oauth.net/2/)を実装します。レート制限は[AWS API Gatewayスロットリング](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html)を通じて悪用を防ぎ、包括的なログ記録は[AWS CloudTrail](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-user-guide.html)を通じてセキュリティ監査を可能にします。

セキュリティ実装は、適切なCORS設定、リクエストサイズ制限、入力検証、基盤インフラストラクチャに関する情報開示を防ぐためのエラーメッセージのサニタイゼーションを含む[OWASP API Security Top 10](https://owasp.org/www-project-api-security/)ガイドラインに従います。

## 📊 : AI エージェントの動作をモニタリングする : [AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)

[AgentCore Observability](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)は、AIエージェントワークロード専用に設計された特殊な監視機能を提供し、統一された運用ダッシュボードと既存の監視インフラストラクチャとの統合のための[OpenTelemetry](https://opentelemetry.io/)互換のテレメトリを提供します。

実装では、ユーザー入力の解析から価格データの取得、最終的なレスポンス生成まで、コスト見積もりプロセスの各ステップをキャプチャする詳細なテレメトリ収集を設定します。[AWS X-Ray](https://docs.aws.amazon.com/xray/latest/devguide/aws-xray.html)統合は分散トレース機能を提供し、[Amazon CloudWatch](https://docs.aws.amazon.com/cloudwatch/latest/monitoring/WhatIsCloudWatch.html)はメトリクス収集とアラートを処理します。

```python
import opentelemetry
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# AgentCore ObservabilityのためのOpenTelemetryを設定
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

otlp_exporter = OTLPSpanExporter(
    endpoint="https://agentcore-observability.amazonaws.com/v1/traces",
    headers={"Authorization": f"Bearer {os.environ['AGENTCORE_API_KEY']}"}
)

span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)

@tracer.start_as_current_span("cost_estimation_request")
def process_cost_estimation(architecture_description: str) -> Dict[str, Any]:
    """包括的なトレースを使用したコスト見積もりの処理"""
    
    with tracer.start_as_current_span("parse_architecture") as span:
        span.set_attribute("input.length", len(architecture_description))
        parsed_architecture = parse_architecture_description(architecture_description)
        span.set_attribute("services.count", len(parsed_architecture.get('services', [])))
    
    with tracer.start_as_current_span("retrieve_pricing_data") as span:
        pricing_data = retrieve_pricing_data(parsed_architecture)
        span.set_attribute("pricing.api_calls", pricing_data.get('api_calls', 0))
    
    with tracer.start_as_current_span("calculate_costs") as span:
        cost_estimate = calculate_total_costs(parsed_architecture, pricing_data)
        span.set_attribute("estimate.total_monthly", cost_estimate.get('monthly_total', 0))
    
    return cost_estimate
```

可観測性設定には、異なるタイプのコスト見積もりリクエストの平均応答時間、価格データ取得の成功率、ユーザーインタラクションフローのパターンを含む、エージェントパフォーマンスを追跡するためのカスタムメトリクスが含まれます。[Amazon CloudWatchダッシュボード](https://docs.aws.amazon.com/cloudwatch/latest/monitoring/CloudWatch_Dashboards.html)は、エージェントのパフォーマンスと健全性へのリアルタイムの可視性を提供します。

アラートメカニズムは、[Amazon SNS](https://docs.aws.amazon.com/sns/latest/dg/welcome.html)通知と[AWS Systems Manager Incident Manager](https://docs.aws.amazon.com/incident-manager/latest/userguide/what-is-incident-manager.html)統合を通じて、エージェントがエラー、パフォーマンス低下、またはセキュリティ問題やシステム問題を示す可能性のある異常な使用パターンを経験した際に運用チームに通知します。

## 🧠 : 見積の内容を「記憶」する : [AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html)

[AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html)は、情報保持と利用に対する開発者の完全な制御を提供しながら、コンテキスト管理において業界をリードする精度を提供します。このサービスは、マルチターン会話内でコンテキストを維持するための短期メモリと、エージェントとセッション間で共有できる長期メモリの両方をサポートします。

実装では、以前のコスト見積もり、特定のAWSサービスに対するユーザー設定、組織の予算制約、ユーザーリクエストに頻繁に現れるアーキテクチャパターンを含む、コスト見積もりエージェントの情報保持を定義するメモリポリシーを設定します。

```python
from amazon_bedrock_agentcore.memory import MemoryManager, MemoryPolicy

memory_policy = MemoryPolicy(
    short_term_retention_hours=24,
    long_term_retention_days=90,
    privacy_level="organization",
    sharing_scope="team",
    encryption_key_id="arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
)

memory_manager = MemoryManager(
    agent_id="cost-estimation-agent",
    policy=memory_policy
)

class CostEstimationAgent:
    def __init__(self):
        self.memory = memory_manager
    
    async def process_request(self, user_id: str, request: str) -> str:
        """メモリ統合を使用したコスト見積もりリクエストの処理"""
        
        # 関連する履歴コンテキストを取得
        historical_context = await self.memory.retrieve_context(
            user_id=user_id,
            query=request,
            max_results=5
        )
        
        # 履歴コンテキストを使用して現在のリクエストを処理
        response = await self.generate_cost_estimate(request, historical_context)
        
        # 将来の参照のためにインタラクションを保存
        await self.memory.store_interaction(
            user_id=user_id,
            request=request,
            response=response,
            metadata={
                "timestamp": datetime.utcnow().isoformat(),
                "services_analyzed": self.extract_services(request),
                "estimated_monthly_cost": self.extract_cost(response)
            }
        )
        
        return response
```

メモリ実装には、特にコスト情報が非常に機密性が高い可能性がある企業環境において、データ保持ポリシーとプライバシーへの影響の慎重な考慮が必要です。実装は、[AWSデータ保護ベストプラクティス](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/data-protection-in-transit.html)に従い、自動データライフサイクル管理と安全な削除機能を通じて[GDPR準拠](https://gdpr.eu/)をサポートします。

メモリシステムは、保存時および転送時の暗号化のために[AWS Key Management Service (KMS)](https://docs.aws.amazon.com/kms/latest/developerguide/overview.html)と統合し、機密コスト情報がそのライフサイクル全体を通じて保護されることを保証します。

## 👤 : ユーザーの認可により 3rd Party のサービスにアクセスする : [AgentCore Identity](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html)


[AgentCore Identity](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity.html)は、既存の企業アイデンティティプロバイダーとシームレスに統合するセキュアでスケーラブルなエージェントアイデンティティおよびアクセス管理機能を提供し、ユーザー移行や認証フローの再構築の必要性を排除します。

実装では、[Okta](https://developer.okta.com/docs/)、[Microsoft Entra ID](https://docs.microsoft.com/en-us/azure/active-directory/)、または[Amazon Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/what-is-amazon-cognito.html)などの企業アイデンティティプロバイダーと統合するようにAgentCore Identityを設定し、Slack統合が別個の認証情報管理を必要とするのではなく、既存のユーザー認証を活用することを保証します。

```python
import slack_sdk
from slack_sdk.oauth import OAuthFlow
from amazon_bedrock_agentcore.identity import IdentityManager

class SlackIntegration:
    def __init__(self):
        self.identity_manager = IdentityManager()
        self.slack_client = slack_sdk.WebClient()
        
        # AgentCore IdentityでOAuthフローを設定
        self.oauth_flow = OAuthFlow(
            client_id=os.environ['SLACK_CLIENT_ID'],
            client_secret=os.environ['SLACK_CLIENT_SECRET'],
            scopes=["chat:write", "channels:read", "users:read"],
            redirect_uri="https://api.example.com/slack/oauth/callback"
        )
    
    async def handle_slack_event(self, event_data: Dict[str, Any]) -> None:
        """アイデンティティ検証を使用した受信Slackイベントの処理"""
        
        # Slackリクエスト署名を検証
        if not self.verify_slack_signature(event_data):
            raise ValueError("無効なSlack署名")
        
        # Slackイベントからユーザーアイデンティティを抽出
        slack_user_id = event_data['event']['user']
        
        # Slackユーザーをエンタープライズアイデンティティにマッピング
        enterprise_identity = await self.identity_manager.resolve_identity(
            provider="slack",
            external_id=slack_user_id
        )
        
        if not enterprise_identity:
            await self.send_slack_message(
                channel=event_data['event']['channel'],
                text="まず企業の認証情報で認証してください。"
            )
            return
        
        # 検証されたアイデンティティでエージェントリクエストを処理
        user_message = event_data['event']['text']
        agent_response = await self.process_agent_request(
            user_id=enterprise_identity['user_id'],
            message=user_message
        )
        
        # Slackにレスポンスを送信
        await self.send_slack_message(
            channel=event_data['event']['channel'],
            text=agent_response
        )
```

Slack統合は、適切なトークン保存、更新メカニズム、スコープ管理を含む[Slackのセキュリティベストプラクティス](https://api.slack.com/authentication/best-practices)に従って[OAuth 2.0フロー](https://api.slack.com/authentication/oauth-v2)を実装します。実装は、指数バックオフとリクエストキューイングを通じて[Slackのレート制限](https://api.slack.com/docs/rate-limits)を処理します。

企業セキュリティ要件には、不正アクセスを防ぐための[Slackのリクエスト検証](https://api.slack.com/authentication/verifying-requests-from-slack)の実装、アクセススコープを最小化するための適切な[Slackアプリ権限](https://api.slack.com/scopes)の設定、[AWS CloudTrail](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-user-guide.html)統合を通じた監査ログの確立が含まれます。

統合は、リッチメッセージフォーマットのための[SlackのBlock Kit](https://api.slack.com/block-kit)をサポートし、コスト見積もりエージェントがSlackインターフェース内で複雑な価格情報を消化しやすい形式で提示できるようにします。

## 結論と次のステップ

この包括的な実装は、Amazon Bedrock AgentCoreが組織が既存の企業インフラストラクチャとシームレスに統合する本格的なAIエージェントを構築することをどのように可能にするかを実証しています。コスト見積もりエージェントは、セキュアなコード実行から企業アイデンティティ統合まで、完全なAgentCoreエコシステムを紹介します。

同様のソリューションを実装する組織は、プロアクティブなコスト監視のための[AWS Cost Anomaly Detection](https://docs.aws.amazon.com/cost-management/latest/userguide/getting-started-ad.html)との統合、自動予算追跡のための[AWS Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)統合の実装、包括的なアーキテクチャ最適化のための[AWS Well-Architected Tool](https://docs.aws.amazon.com/wellarchitected/latest/userguide/intro.html)推奨事項のサポートへの拡張などの追加の拡張を検討すべきです。

完全な実装コード、デプロイメントテンプレート、追加ドキュメントは、[Amazon Bedrock AgentCoreサンプルリポジトリ](https://github.com/awslabs/amazon-bedrock-agentcore-samples/)で利用できます。詳細なAPIリファレンスと高度な設定オプションについては、[Amazon Bedrock AgentCore開発者ガイド](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html)を参照してください。
