#!/usr/bin/env python3
"""
AgentCore Runtime - Agent Registration and Management Tool

A simple tool for deploying AI agents to Amazon Bedrock AgentCore Runtime.
"""

import json
import os
import shutil
import logging
from pathlib import Path
import boto3
import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
console = Console()

# Constants
DEFAULT_REGION = (
    boto3.Session().region_name
    or os.environ.get('AWS_REGION')
    or os.environ.get('AWS_DEFAULT_REGION')
)
DEPLOYMENTS_DIR = Path('./deployment')


class AgentPreparer:
    """Handles preparation of agent for deployment"""
    
    def __init__(self, source_dir: str, region: str = DEFAULT_REGION):
        self.source_dir = Path(source_dir)
        self.region = region
        self.iam_client = boto3.client('iam', region_name=region)
    
    @property
    def agent_name(self) -> str:
        """
        Extract agent name from the source directory (last folder name)
        
        Returns:
            str: Name of the agent
        """
        return self.source_dir.name if self.source_dir.is_dir() else self.source_dir.stem

    def prepare(self) -> str:
        """
        Prepare agent for deployment by creating deployment directory and IAM role

        Returns:
            str: Command for agent configure
        """
        if not self.region:
            raise click.ClickException(
                "AWS region is not configured. Please run:\n"
                "  aws configure set region <your-region>  (e.g. us-west-2)\n"
                "Then re-run this script."
            )

        # Create deployment directory
        deployment_dir = self.create_source_directory()

        # Create IAM role
        role_info = self.create_agentcore_role()

        # Build agentcore configure command
        command = "\n".join([
            "",
            f"uv run agentcore configure --entrypoint {deployment_dir}/invoke.py \\",
            f"--name {self.agent_name} \\",
            f"--execution-role {role_info['role_arn']} \\",
            f"--requirements-file {deployment_dir}/requirements.txt \\",
            "--non-interactive \\",
            "--deployment-type direct_code_deploy \\",
            "--disable-memory \\",
            f"--region {self.region} "
        ])

        return command

    def create_source_directory(self) -> str:
        """
        Create deployment directory by copying entire source directory
            
        Returns:
            Path to the deployment directory
        """
        logger.info(f"Creating deployment directory from {self.source_dir}")

        # Validate source directory exists
        if not self.source_dir.exists():
            raise FileNotFoundError(f"Source directory not found: {self.source_dir}")

        # Create deployment directory
        target_dir = DEPLOYMENTS_DIR / self.agent_name
        target_dir.mkdir(parents=True, exist_ok=True)

        # Copy Python files from source directory
        logger.info(f"Copying Python files from {self.source_dir} to {target_dir}")
        for file_path in self.source_dir.glob("*.py"):
            dest_path = target_dir / file_path.name
            shutil.copy2(file_path, dest_path)
            logger.info(f"Copied {file_path.name}")
            
        logger.info(f"Source directory is copied to deployment directory: {DEPLOYMENTS_DIR}")
        return str(DEPLOYMENTS_DIR)

    def create_agentcore_role(self) -> dict:
        """
        Create IAM role with AgentCore permissions
        Based on https://github.com/awslabs/amazon-bedrock-agentcore-samples
                    
        Returns:
            Role information including ARN
        """
        role_name = f"AgentCoreRole-{self.agent_name}"
        logger.info(f"Creating IAM role: {role_name}")
        
        # Get account ID
        sts_client = boto3.client('sts', region_name=self.region)
        account_id = sts_client.get_caller_identity()['Account']
        
        # Create trust policy
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
        
        # Create execution policy
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
                response = self.iam_client.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description=f'AgentCore execution role for {self.agent_name}'
                )
                logger.info(f"IAM role created successfully: {role_name}")
            except ClientError as e:
                logger.error(f"Failed to create IAM role: {e}")
                return {}

        # Always ensure the execution policy is attached (for both new and existing roles)
        try:
            self.iam_client.put_role_policy(
                RoleName=role_name,
                PolicyName=f'{role_name}-ExecutionPolicy',
                PolicyDocument=json.dumps(execution_policy)
            )
            logger.info(f"Execution policy attached to role: {role_name}")
        except ClientError as e:
            logger.error(f"Failed to attach execution policy: {e}")
            return {}

        return {
            'agent_name': self.agent_name,
            'role_name': role_name,
            'role_arn': response['Role']['Arn']
        }


@click.command()
@click.option('--source-dir', default="../01_code_interpreter/cost_estimator_agent", required=True, help='Source directory to copy')
@click.option('--region', default=DEFAULT_REGION, help='AWS region')
def prepare(source_dir: str, region: str):
    """Prepare agent for deployment by copying source directory"""
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
        
        # Success output with clear visual hierarchy
        console.print("\n[bold green]✓ Agent preparation completed successfully![/bold green]")
        console.print(f"\n[bold]Agent Name:[/bold] {preparer.agent_name}")
        console.print(f"[bold]Deployment Directory:[/bold] {DEPLOYMENTS_DIR}")
        console.print(f"[bold]Region:[/bold] {region}")
        
        # Next steps with clear visual separation
        console.print("\n[bold yellow]📋 Next Steps:[/bold yellow]")
        console.print("\n[bold]1. Configure the agent runtime:[/bold]")
        console.print(f"   [cyan]{configure_command}[/cyan]")
        
        console.print("\n[bold]2. Launch the agent:[/bold]")
        console.print("   [cyan]uv run agentcore launch[/cyan]")
        
        console.print("\n[bold]3. Test your agent:[/bold]")
        console.print("   [cyan]uv run agentcore invoke '{\"prompt\": \"I would like to connect t3.micro from my PC. How much does it cost?\"}'[/cyan]")
        
        # Pro tip
        console.print("\n[dim]💡 Tip: You can copy and paste the commands above directly into your terminal.[/dim]")
        
    except Exception as e:
        console.print(f"\n[bold red]❌ Error: {e}[/bold red]")
        raise click.Abort()


if __name__ == '__main__':
    prepare()
