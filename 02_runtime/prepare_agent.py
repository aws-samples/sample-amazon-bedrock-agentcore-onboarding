#!/usr/bin/env python3
"""
AgentCore Runtime - エージェント登録・管理ツール

Amazon Bedrock AgentCore RuntimeにAIエージェントをデプロイするためのシンプルなツール。
"""

import json
import shutil
import logging
from pathlib import Path
import boto3
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from botocore.exceptions import ClientError

# ログ設定を構成
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
console = Console()

# 定数
DEFAULT_REGION = boto3.Session().region_name
DEPLOYMENTS_DIR = Path('./deployment')


class AgentPreparer:
    """デプロイ用エージェントの準備を処理"""
    
    def __init__(self, source_dir: str, region: str = DEFAULT_REGION):
        self.source_dir = Path(source_dir)
        self.region = region
        self.iam_client = boto3.client('iam', region_name=region)
    
    @property
    def agent_name(self) -> str:
        """
        ソースディレクトリからエージェント名を抽出（最後のフォルダ名）
        
        Returns:
            str: エージェントの名前
        """
        return self.source_dir.name if self.source_dir.is_dir() else self.source_dir.stem

    def prepare(self) -> str:
        """
        デプロイメントディレクトリとIAMロールを作成してエージェントをデプロイ用に準備
            
        Returns:
            str: エージェント設定用コマンド
        """
        # デプロイメントディレクトリを作成
        deployment_dir = self.create_source_directory()
        
        # IAMロールを作成
        role_info = self.create_agentcore_role()

        # agentcore configureコマンドを構築
        command = "\n".join([
            "",
            f"uv run agentcore configure --entrypoint {deployment_dir}/invoke.py \\",
            f"--name {self.agent_name} \\",
            f"--execution-role {role_info['role_arn']} \\",
            f"--requirements-file {deployment_dir}/requirements.txt \\",
            f"--region {self.region} "
        ])

        return command

    def create_source_directory(self) -> str:
        """
        ソースディレクトリ全体をコピーしてデプロイメントディレクトリを作成
            
        Returns:
            デプロイメントディレクトリへのパス
        """
        logger.info(f"Creating deployment directory from {self.source_dir}")

        # ソースディレクトリの存在を検証
        if not self.source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {self.source_dir}")

        # デプロイメントディレクトリを作成
        target_dir = DEPLOYMENTS_DIR / self.agent_name
        target_dir.mkdir(parents=True, exist_ok=True)

        # ソースディレクトリからPythonファイルをコピー
        logger.info(f"Copying Python files from {self.source_dir} to {target_dir}")
        for file_path in self.source_dir.glob("*.py"):
            dest_path = target_dir / file_path.name
            shutil.copy2(file_path, dest_path)
            logger.info(f"Copied {file_path.name}")
            
        logger.info(f"Source directory is copied to deployment directory: {DEPLOYMENTS_DIR}")
        return str(DEPLOYMENTS_DIR)

    def create_agentcore_role(self) -> dict:
        """
        AgentCore権限を持つIAMロールを作成
        https://github.com/awslabs/amazon-bedrock-agentcore-samples に基づく
                    
        Returns:
            ARNを含むロール情報
        """
        role_name = f"AgentCoreRole-{self.agent_name}"
        logger.info(f"Creating IAM role: {role_name}")
        
        # アカウントIDを取得
        sts_client = boto3.client('sts', region_name=self.region)
        account_id = sts_client.get_caller_identity()['Account']
        
        # 信頼ポリシーを作成
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "bedrock-agentcore.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {
                            "aws:SourceAccount": account_id
                        },
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{account_id}:*"
                        }
                    }
                }
            ]
        }
        
        # 実行ポリシーを作成
        execution_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "BedrockPermissions",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream"
                    ],
                    "Resource": "*"
                },
                {
                    "Sid": "ECRImageAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ecr:BatchGetImage",
                        "ecr:GetDownloadUrlForLayer"
                    ],
                    "Resource": [
                        f"arn:aws:ecr:{self.region}:{account_id}:repository/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:DescribeLogStreams",
                        "logs:CreateLogGroup"
                    ],
                    "Resource": [
                        f"arn:aws:logs:{self.region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:DescribeLogGroups"
                    ],
                    "Resource": [
                        f"arn:aws:logs:{self.region}:{account_id}:log-group:*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogStream",
                        "logs:PutLogEvents"
                    ],
                    "Resource": [
                        f"arn:aws:logs:{self.region}:{account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"
                    ]
                },
                {
                    "Sid": "ECRTokenAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ecr:GetAuthorizationToken"
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "xray:PutTraceSegments",
                        "xray:PutTelemetryRecords",
                        "xray:GetSamplingRules",
                        "xray:GetSamplingTargets"
                        ],
                    "Resource": [ "*" ]
                },
                {
                    "Effect": "Allow",
                    "Resource": "*",
                    "Action": "cloudwatch:PutMetricData",
                    "Condition": {
                        "StringEquals": {
                            "cloudwatch:namespace": "bedrock-agentcore"
                        }
                    }
                },
                {
                    "Sid": "GetAgentAccessToken",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetWorkloadAccessToken",
                        "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                        "bedrock-agentcore:GetWorkloadAccessTokenForUserId"
                    ],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{self.region}:{account_id}:workload-identity-directory/default*",
                        f"arn:aws:bedrock-agentcore:{self.region}:{account_id}:workload-identity-directory/default/workload-identity/{self.agent_name}-*"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:CreateCodeInterpreter",
                        "bedrock-agentcore:StartCodeInterpreterSession",
                        "bedrock-agentcore:InvokeCodeInterpreter",
                        "bedrock-agentcore:StopCodeInterpreterSession",
                        "bedrock-agentcore:DeleteCodeInterpreter",
                        "bedrock-agentcore:ListCodeInterpreters",
                        "bedrock-agentcore:GetCodeInterpreter",
                        "bedrock-agentcore:GetCodeInterpreterSession",
                        "bedrock-agentcore:ListCodeInterpreterSessions"
                    ],
                    "Resource": "arn:aws:bedrock-agentcore:*:*:*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "pricing:*"
                    ],
                    "Resource": "*"
                }
            ]
        }
        
        role_exists = False
        response = None

        try:
            response = self.iam_client.get_role(RoleName=role_name)
            logger.info(f"Role {role_name} already exists")
            role_exists = True
        except ClientError:
            pass

        if not role_exists:
            try:
                # ロールを作成
                response = self.iam_client.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description=f'AgentCore execution role for {self.agent_name}'
                )
                logger.info(f"IAM role created successfully: {role_name}")
                
            except ClientError as e:
                logger.error(f"Failed to create IAM role: {e}")
                return {}  # 失敗を示すために空の辞書を返す

            # 実行ポリシーがアタッチされていることを常に確認（新規と既存のロール両方）
            try:
                self.iam_client.put_role_policy(
                    RoleName=role_name,
                    PolicyName=f'{role_name}-ExecutionPolicy',
                    PolicyDocument=json.dumps(execution_policy)
                )
                    
                logger.info(f"Execution policy attached to role: {role_name}")
                
            except ClientError as e:
                logger.error(f"Failed to attach execution policy: {e}")
                return {}  # 失敗を示すために空の辞書を返す

        return {
            'agent_name': self.agent_name,
            'role_name': role_name,
            'role_arn': response['Role']['Arn']
        }


@click.command()
@click.option('--source-dir', default="../01_code_interpreter/cost_estimator_agent", required=True, help='Source directory to copy')
@click.option('--region', default=DEFAULT_REGION, help='AWS region')
def prepare(source_dir: str, region: str):
    """ソースディレクトリをコピーしてデプロイ用エージェントを準備"""
    console.print(f"[bold blue]Preparing agent from: {source_dir}[/bold blue]")
    
    preparer = AgentPreparer(source_dir, region)
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            _ = progress.add_task("[cyan]Preparing agent...", total=None)
            configure_command = preparer.prepare()
            progress.stop()
        
        # 明確な視覚的階層で成功出力
        console.print("\n[bold green]✓ Agent preparation completed successfully![/bold green]")
        console.print(f"\n[bold]Agent Name:[/bold] {preparer.agent_name}")
        console.print(f"[bold]Deployment Directory:[/bold] {DEPLOYMENTS_DIR}")
        console.print(f"[bold]Region:[/bold] {region}")
        
        # 明確な視覚的分離で次のステップ
        console.print("\n[bold yellow]📋 Next Steps:[/bold yellow]")
        console.print("\n[bold]1. Configure the agent runtime:[/bold]")
        console.print(f"   [cyan]{configure_command}[/cyan]")
        
        console.print("\n[bold]2. Launch the agent:[/bold]")
        console.print("   [cyan]uv run agentcore launch[/cyan]")
        
        console.print("\n[bold]3. Test your agent:[/bold]")
        console.print("   [cyan]uv run agentcore invoke '{\"prompt\": \"I would like to connect t3.micro from my PC. How much does it cost?\"}'[/cyan]")
        
        # プロのコツ
        console.print("\n[dim]💡 Tip: You can copy and paste the commands above directly into your terminal.[/dim]")
        
    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {e}[/bold red]")
        raise click.Abort()


if __name__ == '__main__':
    prepare()
