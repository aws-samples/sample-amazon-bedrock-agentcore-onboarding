"""
Amazon Bedrock AgentCore Code Interpreter を使用したAWSコスト見積もりエージェント

このエージェントは以下の方法を実演します：
1. AWS Pricing MCP Server を使用して料金データを取得する
2. AgentCore Code Interpreter を使用して安全な計算を実行する
3. AWSアーキテクチャの包括的なコスト見積もりを提供する

主要機能：
- AgentCoreサンドボックスでの安全なコード実行
- リアルタイムAWS料金データ
- 包括的なログ記録とエラーハンドリング
- 段階的な複雑性の構築
"""

import logging
import traceback
import boto3
from contextlib import contextmanager
from typing import Generator, AsyncGenerator
from strands import Agent, tool
from strands.tools.mcp import MCPClient
from strands.handlers.callback_handler import null_callback_handler
from mcp import stdio_client, StdioServerParameters
from bedrock_agentcore.tools.code_interpreter_client import CodeInterpreter
from cost_estimator_agent.config import (
    SYSTEM_PROMPT,
    COST_ESTIMATION_PROMPT,
    DEFAULT_MODEL,
    LOG_FORMAT
)

# デバッグと監視のための包括的なログ設定を構成
logging.basicConfig(
    level=logging.ERROR,  # デフォルトでERRORに設定、詳細情報が必要な場合はDEBUGに変更可能
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler()]
)

# エージェントの詳細な動作を把握するためのStrandsデバッグログを有効化
logging.getLogger("strands").setLevel(logging.ERROR)

logger = logging.getLogger(__name__)


class AWSCostEstimatorAgent:
    """
    AgentCore Code Interpreter を使用したAWSコスト見積もりエージェント
    
    このエージェントは以下を組み合わせます：
    - リアルタイム料金データのためのMCP料金ツール（自動で利用可能）
    - 安全な計算のためのAgentCore Code Interpreter
    - きれいな実装のためのStrandsエージェントフレームワーク
    """
    
    def __init__(self, region: str = ""):
        """
        Initialize the cost estimation agent
        
        Args:
            region: AWS region for AgentCore Code Interpreter
        """
        self.region = region
        if not self.region:
            # 指定されていない場合はboto3セッションからデフォルトリージョンを使用
            self.region = boto3.Session().region_name
        self.code_interpreter = None
        
        logger.info(f"Initializing AWS Cost Estimator Agent in region: {region}")
        
    def _setup_code_interpreter(self) -> None:
        """安全な計算のためのAgentCore Code Interpreterをセットアップ"""
        try:
            logger.info("Setting up AgentCore Code Interpreter...")
            self.code_interpreter = CodeInterpreter(self.region)
            self.code_interpreter.start()
            logger.info("✅ AgentCore Code Interpreter session started successfully")
        except Exception as e:
            logger.error(f"❌ Failed to setup Code Interpreter: {e}")
            return  # 再発生させる代わりにエラーを処理
    
    def _get_aws_credentials(self) -> dict:
        """
        Get current AWS credentials (including session token if present)
        
        Returns:
            Dict with current AWS credentials including session token
        """
        try:
            logger.info("Getting current AWS credentials...")
            
            # 現在の認証情報を取得するためのセッションを作成
            session = boto3.Session()
            credentials = session.get_credentials()
            
            if credentials is None:
                raise Exception("No AWS credentials found")
            
            # 呼び出し元のアイデンティティを取得して認証情報が機能することを確認
            sts_client = boto3.client('sts', region_name=self.region)
            identity = sts_client.get_caller_identity()
            logger.info(f"Using AWS identity: {identity.get('Arn', 'Unknown')}")
            
            # アクセスするためにフリーズした認証情報を取得
            frozen_creds = credentials.get_frozen_credentials()
            
            credential_dict = {
                "AWS_ACCESS_KEY_ID": frozen_creds.access_key,
                "AWS_SECRET_ACCESS_KEY": frozen_creds.secret_key,
                "AWS_REGION": self.region
            }
            
            # 利用可能な場合はセッショントークンを追加（EC2インスタンスロールがこれを提供）
            if frozen_creds.token:
                credential_dict["AWS_SESSION_TOKEN"] = frozen_creds.token
                logger.info("✅ Using AWS credentials with session token (likely from EC2 instance role)")
            else:
                logger.info("✅ Using AWS credentials without session token")
                
            return credential_dict
            
        except Exception as e:
            logger.error(f"❌ Failed to get AWS credentials: {e}")
            return {}  # フォールバックとして空の辞書を返す

    def _setup_aws_pricing_client(self) -> MCPClient:
        """現在のAWS認証情報でAWS Pricing MCPクライアントをセットアップ"""
        try:
            logger.info("Setting up AWS Pricing MCP Client...")
            
            # 現在の認証情報を取得（セッショントークンが利用可能な場合は含む）
            aws_credentials = self._get_aws_credentials()
            
            # MCPクライアント用の環境変数を準備
            env_vars = {
                "FASTMCP_LOG_LEVEL": "ERROR",
                **aws_credentials  # すべてのAWS認証情報を含む
            }
            
            aws_pricing_client = MCPClient(
                lambda: stdio_client(StdioServerParameters(
                    command="uvx", 
                    args=["awslabs.aws-pricing-mcp-server@latest"],
                    env=env_vars
                ))
            )
            logger.info("✅ AWS Pricing MCP Client setup successfully with AWS credentials")
            return aws_pricing_client
        except Exception as e:
            logger.error(f"❌ Failed to setup AWS Pricing MCP Client: {e}")
            return None  # フォールバックとしてNoneを返す
    
    
    @tool
    def execute_cost_calculation(self, calculation_code: str, description: str = "") -> str:
        """
        AgentCore Code Interpreterを使用してコスト計算を実行
        
        Args:
            calculation_code: コスト計算用のPythonコード
            description: 計算が何をするかの説明
            
        Returns:
            文字列としての計算結果
        """
        if not self.code_interpreter:
            return "❌ Code Interpreter not initialized"
            
        try:
            logger.info(f"🧮 Executing calculation: {description}")
            logger.debug(f"Code to execute:\n{calculation_code}")
            
            # 安全なAgentCoreサンドボックスでコードを実行
            response = self.code_interpreter.invoke("executeCode", {
                "language": "python",
                "code": calculation_code
            })
            
            # レスポンスストリームから結果を抽出
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
            logger.exception(f"❌ Calculation failed: {e}")

    @contextmanager
    def _estimation_agent(self) -> Generator[Agent, None, None]:
        """
        コスト見積もりコンポーネント用のコンテキストマネージャー
        
        Yields:
            すべてのツールが設定され、リソースが適切に管理されたエージェント
            
        Ensures:
            Code InterpreterとMCPクライアントリソースの適切なクリーンアップ
        """        
        try:
            logger.info("🚀 Initializing AWS Cost Estimation Agent...")
            
            # 順序立ててコンポーネントをセットアップ
            self._setup_code_interpreter()
            aws_pricing_client = self._setup_aws_pricing_client()
            
            # 永続的なMCPコンテキストを持つエージェントを作成
            with aws_pricing_client:
                pricing_tools = aws_pricing_client.list_tools_sync()
                logger.info(f"Found {len(pricing_tools)} AWS pricing tools")
                
                # execute_cost_calculationとMCP料金ツールの両方を持つエージェントを作成
                all_tools = [self.execute_cost_calculation] + pricing_tools
                agent = Agent(
                    model=DEFAULT_MODEL,
                    tools=all_tools,
                    system_prompt=SYSTEM_PROMPT
                )
                
                yield agent
                
        except Exception as e:
            logger.exception(f"❌ Component setup failed: {e}")
            raise
        finally:
            # 成功・失敗に関係なくクリーンアップが実行されることを保証
            self.cleanup()

    def estimate_costs(self, architecture_description: str) -> str:
        """
        与えられたアーキテクチャ説明に対してコストを見積もり
        
        Args:
            architecture_description: 見積もり対象システムの説明
            
        Returns:
            連結された文字列としてのコスト見積もり結果
        """
        logger.info("📊 Starting cost estimation...")
        logger.info(f"Architecture: {architecture_description}")
        
        try:
            with self._estimation_agent() as agent:
                # Use the agent to process the cost estimation request
                prompt = COST_ESTIMATION_PROMPT.format(
                    architecture_description=architecture_description
                )
                result = agent(prompt)
                
                logger.info("✅ Cost estimation completed")

                if result.message and result.message.get("content"):
                    # すべてのContentBlockからテキストを抽出して連結
                    text_parts = []
                    for content_block in result.message["content"]:
                        if isinstance(content_block, dict) and "text" in content_block:
                            text_parts.append(content_block["text"])
                    return "".join(text_parts) if text_parts else "No text content found."
                else:
                    return "No estimation result."

        except Exception as e:
            logger.exception(f"❌ Cost estimation failed: {e}")
            error_details = traceback.format_exc()
            return f"❌ Cost estimation failed: {e}\n\nStacktrace:\n{error_details}"

    async def estimate_costs_stream(self, architecture_description: str) -> AsyncGenerator[dict, None]:
        """
        ストリーミングレスポンスで与えられたアーキテクチャ説明に対してコストを見積もり
        
        Amazon Bedrockのベストプラクティスに従った適切なデルタベースのストリーミングを実装します。
        これは、Strands stream_async()が適切なデルタの代わりに重複するコンテンツチャンクを
        送信する可能性があるという一般的な問題を解決します。
        
        Args:
            architecture_description: 見積もり対象システムの説明
            
        Yields:
            真のデルタコンテンツを持つストリーミングイベント（新しいテキストのみ、重複なし）
            
        使用例:
            async for event in agent.estimate_costs_stream(description):
                if "data" in event:
                    print(event["data"], end="", flush=True)  # 直接印刷、蓄積不要
        """
        logger.info("📊 Starting streaming cost estimation...")
        logger.info(f"Architecture: {architecture_description}")
        
        try:
            with self._estimation_agent() as agent:
                # Use the agent to process the cost estimation request with streaming
                prompt = COST_ESTIMATION_PROMPT.format(
                    architecture_description=architecture_description
                )
                
                logger.info("🔄 Streaming cost estimation response...")
                
                # 重複を防ぐための適切なデルタハンドリングを実装
                # これはAmazon Bedrock ContentBlockDeltaEventパターンに従う
                previous_output = ""
                
                agent_stream = agent.stream_async(prompt, callback_handler=null_callback_handler)
                
                async for event in agent_stream:
                    if "data" in event:
                        current_chunk = str(event["data"])
                        
                        # Bedrockのベストプラクティスに従ってデルタ計算を処理
                        if current_chunk.startswith(previous_output):
                            # これは増分更新 - 新しい部分のみを抽出
                            delta_content = current_chunk[len(previous_output):]
                            if delta_content:  # 実際に新しいコンテンツがある場合のみyield
                                previous_output = current_chunk
                                yield {"data": delta_content}
                        else:
                            # これは完全に新しいチャンクまたはリセット - そのままyield
                            previous_output = current_chunk
                            yield {"data": current_chunk}
                    else:
                        # データ以外のイベント（エラー、メタデータなど）をパススルー
                        yield event
                
                logger.info("✅ Streaming cost estimation completed")

        except Exception as e:
            logger.exception(f"❌ Streaming cost estimation failed: {e}")
            # ストリーミング形式でエラーイベントをyield
            yield {
                "error": True,
                "data": f"❌ Streaming cost estimation failed: {e}\n\nStacktrace:\n{traceback.format_exc()}"
            }

    def cleanup(self) -> None:
        """リソースをクリーンアップ"""
        logger.info("🧹 Cleaning up resources...")
        
        if self.code_interpreter:
            try:
                self.code_interpreter.stop()
                logger.info("✅ Code Interpreter session stopped")
            except Exception as e:
                logger.warning(f"⚠️ Error stopping Code Interpreter: {e}")
            finally:
                self.code_interpreter = None
